"""Política común para validar anulaciones de documentos contabilizados."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import or_, select

from cacao_accounting.database import (
    AccountingPeriod,
    BankAccount,
    BankTransaction,
    DocumentRelation,
    DocumentTransition,
    LandedCostAllocation,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    ReconciliationItem,
    StockValuationLayer,
    User,
    WithholdingCertificate,
    database,
)
from cacao_accounting.document_identifiers import IdentifierConfigurationError, parse_posting_date


class CancellationPolicyError(ValueError):
    """Error de dominio producido por una solicitud de anulación inválida."""


@dataclass(frozen=True)
class CancellationRequest:
    """Datos inmutables aportados por quien solicita una anulación."""

    document: Any
    effective_date: date | str | None
    actor_user_id: str | None
    reason: str | None
    requested_at: Any = None


@dataclass(frozen=True)
class CancellationContext:
    """Datos resueltos que deben compartir GL, SLE y auditoría."""

    company: str
    original_date: date
    effective_date: date
    accounting_period_id: str
    fiscal_year_id: str | None
    actor_user_id: str
    reason: str
    requested_at: Any = None


@dataclass(frozen=True)
class CancellationDependency:
    """Efecto posterior que impide anular un documento de forma segura."""

    kind: str
    identifier: str
    detail: str


def resolve_cancellation(request: CancellationRequest, source_type: str, source_id: str) -> CancellationContext:
    """Valida una solicitud y devuelve la fecha/período que debe usar el posting.

    La función no modifica la sesión. Todas las comprobaciones se ejecutan antes
    de crear contrapartidas para que GL, SLE y la auditoría compartan la misma
    decisión y puedan confirmarse atómicamente por el caller.
    """
    document = request.document
    _validate_document_status(document)
    company = _document_company(document)
    actor, reason = _request_metadata(request)
    original_date, effective_date = _resolve_effective_dates(request, document)
    original_period, effective_period = _resolve_periods(company, original_date, effective_date)
    _validate_periods(original_period, effective_period)
    _validate_dependencies(document, source_type, source_id)
    _ensure_no_previous_cancellation(source_type, source_id)

    return CancellationContext(
        company=company,
        original_date=original_date,
        effective_date=effective_date,
        accounting_period_id=str(original_period.id),
        fiscal_year_id=str(original_period.fiscal_year_id) if original_period.fiscal_year_id else None,
        actor_user_id=actor,
        reason=reason,
        requested_at=request.requested_at,
    )


def _validate_document_status(document: Any) -> None:
    """Require a submitted document before resolving cancellation metadata."""
    if getattr(document, "docstatus", 0) != 1:
        raise CancellationPolicyError("Solo se puede cancelar un documento aprobado.")


def _document_company(document: Any) -> str:
    """Resolve the company of an ordinary or bank document."""
    company = str(getattr(document, "company", None) or getattr(document, "entity", None) or "")
    if not company and isinstance(document, BankTransaction):
        bank_account = database.session.get(BankAccount, document.bank_account_id)
        company = str(getattr(bank_account, "company", None) or "")
    if not company:
        raise CancellationPolicyError("El documento no tiene compania definida.")
    return company


def _request_metadata(request: CancellationRequest) -> tuple[str, str]:
    """Normalize and require the actor and reason of a cancellation."""
    reason = str(request.reason or "").strip()
    if not reason:
        raise CancellationPolicyError("Debe indicar el motivo de la anulacion.")
    actor = str(request.actor_user_id or "").strip()
    if not actor:
        raise CancellationPolicyError("Debe indicar el usuario que ejecuta la anulacion.")
    if database.session.get(User, actor) is None:
        raise CancellationPolicyError("El usuario que ejecuta la anulacion no existe.")
    return actor, reason


def _resolve_effective_dates(request: CancellationRequest, document: Any) -> tuple[date, date]:
    """Resolve the original and effective accounting dates."""
    original_date = _document_date(document)
    try:
        effective_date = parse_posting_date(request.effective_date) if request.effective_date is not None else original_date
    except IdentifierConfigurationError as exc:
        raise CancellationPolicyError(str(exc)) from exc
    if effective_date < original_date:
        raise CancellationPolicyError("La fecha de anulacion no puede ser anterior a la fecha original.")
    return original_date, effective_date


def _resolve_periods(company: str, original_date: date, effective_date: date) -> tuple[AccountingPeriod, AccountingPeriod]:
    """Resolve both periods needed for the same-period invariant."""
    return _period_for_date(company, original_date), _period_for_date(company, effective_date)


def _validate_periods(original_period: AccountingPeriod, effective_period: AccountingPeriod) -> None:
    """Require the effective date to remain in the original open period."""
    if original_period.id != effective_period.id:
        raise CancellationPolicyError("La anulacion debe registrarse en el mismo periodo contable del documento.")
    if bool(original_period.is_closed) or not bool(original_period.enabled):
        raise CancellationPolicyError("No puede anularse: periodo contable cerrado o deshabilitado.")
    if bool(effective_period.is_closed) or not bool(effective_period.enabled):
        raise CancellationPolicyError("No puede anularse en un periodo contable cerrado o deshabilitado.")


def _validate_dependencies(document: Any, source_type: str, source_id: str) -> None:
    """Reject active downstream effects with a business-readable error."""
    dependencies = active_cancellation_dependencies(document, source_type, source_id)
    if dependencies:
        details = ", ".join(f"{dependency.detail} ({dependency.identifier})" for dependency in dependencies)
        raise CancellationPolicyError(f"No se puede anular el documento porque tiene efectos activos: {details}.")


def _ensure_no_previous_cancellation(source_type: str, source_id: str) -> None:
    """Enforce cancellation idempotency before writing the transition."""
    existing = database.session.execute(
        select(DocumentTransition.id).where(
            DocumentTransition.source_type == source_type,
            DocumentTransition.source_id == source_id,
            DocumentTransition.transition_type.in_(("cancellation", "reversal")),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise CancellationPolicyError("El documento ya tiene una anulacion o una reversion registrada.")


def active_cancellation_dependencies(document: Any, source_type: str, source_id: str) -> list[CancellationDependency]:
    """Enumera relaciones y efectos posteriores que bloquean una anulación."""
    dependencies: list[CancellationDependency] = []
    source_types = {
        source_type,
        str(getattr(document, "document_type", "") or ""),
        str(getattr(document, "__tablename__", "")),
    }
    source_types.discard("")

    relation_rows = database.session.execute(
        select(DocumentRelation).where(
            DocumentRelation.source_type.in_(source_types),
            DocumentRelation.source_id == source_id,
            DocumentRelation.status == "active",
        )
    ).scalars()
    dependencies.extend(_relation_dependencies(relation_rows))

    if not isinstance(document, PaymentEntry):
        payment_rows = database.session.execute(
            select(PaymentReference)
            .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
            .where(
                PaymentReference.reference_id == source_id,
                PaymentReference.reference_type.in_(source_types),
                PaymentEntry.docstatus == 1,
            )
        ).scalars()
        dependencies.extend(
            CancellationDependency("aplicacion de pago", str(row.payment_id), "payment_entry") for row in payment_rows
        )

    if isinstance(document, BankTransaction):
        reconciliation_rows = database.session.execute(
            select(ReconciliationItem).where(
                or_(
                    ReconciliationItem.source_id == source_id,
                    ReconciliationItem.target_id == source_id,
                    ReconciliationItem.reference_id == source_id,
                ),
                ReconciliationItem.status.not_in(("cancelled", "reverted", "closed")),
            )
        ).scalars()
        dependencies.extend(
            CancellationDependency("conciliacion bancaria", str(row.id), "reconciliation_item") for row in reconciliation_rows
        )

    if isinstance(document, PaymentEntry):
        certificates = database.session.execute(
            select(WithholdingCertificate).where(
                WithholdingCertificate.payment_id == source_id,
                WithholdingCertificate.status != "cancelled",
            )
        ).scalars()
        dependencies.extend(
            CancellationDependency("certificado de retencion", str(row.id), "withholding_certificate") for row in certificates
        )

    if isinstance(document, PurchaseInvoice):
        allocations = database.session.execute(
            select(LandedCostAllocation.id).where(
                LandedCostAllocation.document_type.in_(source_types),
                LandedCostAllocation.document_id == source_id,
            )
        ).scalars()
        dependencies.extend(
            CancellationDependency("costo capitalizable", str(row), "landed_cost_allocation") for row in allocations
        )

    dependencies.extend(_consumed_stock_dependencies(document, source_type, source_id))
    return dependencies


def _relation_dependencies(relations: Any) -> list[CancellationDependency]:
    """Return active relations, excluding known draft document targets."""
    from cacao_accounting.document_flow.registry import DOCUMENT_TYPES
    from cacao_accounting.document_flow.repository import get_document

    dependencies: list[CancellationDependency] = []
    for relation in relations:
        if relation.target_type in DOCUMENT_TYPES:
            target = get_document(relation.target_type, relation.target_id)
            if target is not None and getattr(target, "docstatus", 0) in (0, 2):
                continue
        dependencies.append(CancellationDependency("relacion documental", str(relation.target_id), str(relation.target_type)))
    return dependencies


def _document_date(document: Any) -> date:
    """Obtiene la fecha original de un documento operativo o journal."""
    value = getattr(document, "posting_date", None) or getattr(document, "date", None)
    if not isinstance(value, date):
        raise CancellationPolicyError("El documento no tiene fecha de contabilizacion definida.")
    return value


def _period_for_date(company: str, posting_date: date) -> AccountingPeriod:
    """Resuelve un único período contable por compañía y fecha."""
    period = (
        database.session.execute(
            select(AccountingPeriod)
            .where(AccountingPeriod.entity == company)
            .where(AccountingPeriod.start <= posting_date)
            .where(AccountingPeriod.end >= posting_date)
            .order_by(AccountingPeriod.start.desc())
        )
        .scalars()
        .first()
    )
    if period is None:
        raise CancellationPolicyError("No existe un periodo contable configurado para la fecha indicada.")
    return period


def _consumed_stock_dependencies(document: Any, source_type: str, source_id: str) -> list[CancellationDependency]:
    """Detecta consumo posterior de capas generadas por el documento."""
    if not hasattr(document, "__tablename__") or str(document.__tablename__) not in {
        "stock_entry",
        "purchase_receipt",
        "delivery_note",
    }:
        return []
    layer_ids = (
        database.session.execute(
            select(StockValuationLayer.id).where(
                StockValuationLayer.voucher_type == source_type,
                StockValuationLayer.voucher_id == source_id,
                StockValuationLayer.qty > 0,
            )
        )
        .scalars()
        .all()
    )
    if not layer_ids:
        return []
    consumed = database.session.execute(
        select(StockValuationLayer).where(
            StockValuationLayer.source_layer_id.in_(layer_ids),
            StockValuationLayer.qty < 0,
            StockValuationLayer.voucher_id != source_id,
        )
    ).scalars()
    return [CancellationDependency("consumo de inventario", str(row.voucher_id), str(row.voucher_type)) for row in consumed]
