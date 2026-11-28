# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Política común para validar anulaciones de documentos contabilizados."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import and_, or_, select

from cacao_accounting.database import (
    AccountingPeriod,
    BankAccount,
    BankTransaction,
    ComprobanteContable,
    DocumentRelation,
    DocumentTransition,
    GLEntry,
    ImportLandedCost,
    LandedCostAllocation,
    PaymentEntry,
    PaymentReference,
    PurchaseCreditNoteAllocation,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    ReconciliationItem,
    StockValuationLayer,
    User,
    WithholdingCertificate,
    database,
)
from cacao_accounting.contabilidad.journal_constants import JOURNAL_REVERSAL_RETRY_PREFIX
from cacao_accounting.document_identifiers import IdentifierConfigurationError, parse_posting_date


from cacao_accounting.i18n import _


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
        raise CancellationPolicyError(_("Solo se puede cancelar un documento aprobado."))


def _document_company(document: Any) -> str:
    """Resolve the company of an ordinary or bank document."""
    company = str(getattr(document, "company", None) or getattr(document, "entity", None) or "")
    if not company and isinstance(document, BankTransaction):
        bank_account = database.session.get(BankAccount, document.bank_account_id)
        company = str(getattr(bank_account, "company", None) or "")
    if not company:
        raise CancellationPolicyError(_("El documento no tiene compañía definida."))
    return company


def _request_metadata(request: CancellationRequest) -> tuple[str, str]:
    """Normalize and require the actor and reason of a cancellation."""
    reason = str(request.reason or "").strip()
    if not reason:
        raise CancellationPolicyError(_("Debe indicar el motivo de la anulación."))
    actor = str(request.actor_user_id or "").strip()
    if not actor:
        raise CancellationPolicyError(_("Debe indicar el usuario que ejecuta la anulación."))
    if database.session.get(User, actor) is None:
        raise CancellationPolicyError(_("El usuario que ejecuta la anulación no existe."))
    return actor, reason


def _resolve_effective_dates(request: CancellationRequest, document: Any) -> tuple[date, date]:
    """Resolve the original and effective accounting dates."""
    original_date = _document_date(document)
    try:
        effective_date = parse_posting_date(request.effective_date) if request.effective_date is not None else original_date
    except IdentifierConfigurationError as exc:
        raise CancellationPolicyError(str(exc)) from exc
    if effective_date != original_date:
        raise CancellationPolicyError(_("La fecha de anulación debe coincidir con la fecha de contabilización del documento."))
    return original_date, effective_date


def _resolve_periods(company: str, original_date: date, effective_date: date) -> tuple[AccountingPeriod, AccountingPeriod]:
    """Resolve both periods needed for the same-period invariant."""
    return _period_for_date(company, original_date), _period_for_date(company, effective_date)


def _validate_periods(original_period: AccountingPeriod, effective_period: AccountingPeriod) -> None:
    """Require the effective date to remain in the original open period."""
    if original_period.id != effective_period.id:
        raise CancellationPolicyError(_("La anulación debe registrarse en el mismo periodo contable del documento."))
    if bool(original_period.is_closed) or not bool(original_period.enabled):
        raise CancellationPolicyError(_("No puede anularse: periodo contable cerrado o deshabilitado."))
    if bool(effective_period.is_closed) or not bool(effective_period.enabled):
        raise CancellationPolicyError(_("No puede anularse en un periodo contable cerrado o deshabilitado."))


def _validate_dependencies(document: Any, source_type: str, source_id: str) -> None:
    """Reject active downstream effects with a business-readable error."""
    dependencies = active_cancellation_dependencies(document, source_type, source_id)
    if dependencies:
        details = ", ".join(f"{dependency.detail} ({dependency.identifier})" for dependency in dependencies)
        raise CancellationPolicyError(
            _("No se puede anular el documento porque tiene efectos activos: %(details)s.") % {"details": details}
        )


def _ensure_no_previous_cancellation(source_type: str, source_id: str) -> None:
    """Enforce cancellation idempotency before writing the transition."""
    transitions = database.session.execute(
        select(DocumentTransition).where(
            DocumentTransition.source_type == source_type,
            DocumentTransition.source_id == source_id,
        )
    ).scalars()
    for transition in transitions:
        if transition.transition_type == "cancellation":
            raise CancellationPolicyError(_("El documento ya tiene una anulación o una reversion registrada."))
        if transition.transition_type != "reversal" and not transition.transition_type.startswith(
            JOURNAL_REVERSAL_RETRY_PREFIX
        ):
            continue
        if transition.target_type != "journal_entry" or not transition.target_id:
            raise CancellationPolicyError(_("El documento ya tiene una anulación o una reversion registrada."))
        target_status = database.session.execute(
            select(ComprobanteContable.status).where(ComprobanteContable.id == transition.target_id)
        ).scalar_one_or_none()
        if target_status != "rejected":
            raise CancellationPolicyError(_("El documento ya tiene una anulación o una reversion registrada."))


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

    # #1316: una partida bancaria puede conciliarse contra una línea GL del
    # documento. Anular el documento dejaría esa partida apuntando a una línea
    # cancelada y el movimiento bancario seguiría consumido.
    gl_documents = select(GLEntry.id).where(
        GLEntry.voucher_id == source_id,
        GLEntry.is_cancelled.is_(False),
    )
    company = getattr(document, "company", None) or getattr(document, "entity", None)
    if company:
        gl_documents = gl_documents.where(GLEntry.company == company)
    reconciliation_gl_rows = database.session.execute(
        select(ReconciliationItem).where(
            ReconciliationItem.target_type == "gl_entry",
            ReconciliationItem.target_id.in_(gl_documents),
            ReconciliationItem.status.not_in(("cancelled", "reverted", "closed")),
        )
    ).scalars()
    dependencies.extend(
        CancellationDependency("conciliacion bancaria", str(row.id), "reconciliation_item") for row in reconciliation_gl_rows
    )

    if isinstance(document, PaymentEntry):
        # Las referencias del pago son efectos internos reversibles. El hook de
        # cancelación revierte sus relaciones y refresca los saldos afectados;
        # bloquearlas aquí haría imposible cancelar cualquier pago aplicado.
        certificates = database.session.execute(
            select(WithholdingCertificate).where(
                WithholdingCertificate.payment_id == source_id,
                WithholdingCertificate.status != "cancelled",
            )
        ).scalars()
        dependencies.extend(
            CancellationDependency("certificado de retencion", str(row.id), "withholding_certificate") for row in certificates
        )

    if isinstance(document, ImportLandedCost):
        dependencies.extend(_landed_cost_consumption_dependencies(document, source_types, source_id))

    if isinstance(document, PurchaseReceipt) and document.is_return:
        dependencies.extend(_physical_return_credit_note_dependencies(document, source_id))

    dependencies.extend(_consumed_stock_dependencies(document, source_type, source_id))
    return dependencies


def _physical_return_credit_note_dependencies(document: PurchaseReceipt, source_id: str) -> list[CancellationDependency]:
    """Block return cancellation while an active physical credit note uses it."""
    note_rows = database.session.execute(
        select(PurchaseInvoice.id, PurchaseInvoice.document_no)
        .join(PurchaseInvoiceItem, PurchaseInvoiceItem.purchase_invoice_id == PurchaseInvoice.id)
        .join(
            PurchaseCreditNoteAllocation,
            PurchaseCreditNoteAllocation.credit_note_item_id == PurchaseInvoiceItem.id,
        )
        .join(PurchaseReceiptItem, PurchaseReceiptItem.id == PurchaseCreditNoteAllocation.return_receipt_item_id)
        .where(
            PurchaseReceiptItem.purchase_receipt_id == source_id,
            PurchaseCreditNoteAllocation.company == document.company,
            PurchaseCreditNoteAllocation.allocation_type == "physical_return",
            PurchaseCreditNoteAllocation.status == "active",
            PurchaseInvoice.document_type == "purchase_credit_note",
            PurchaseInvoice.credit_note_type == "physical_return",
            PurchaseInvoice.docstatus == 1,
        )
        .distinct()
    ).all()
    return [
        CancellationDependency(
            "nota de crédito física activa",
            str(note_no or note_id),
            _("nota de crédito física activa"),
        )
        for note_id, note_no in note_rows
    ]


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
        raise CancellationPolicyError(_("El documento no tiene fecha de contabilizacion definida."))
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
        raise CancellationPolicyError(_("No existe un periodo contable configurado para la fecha indicada."))
    return period


def _consumed_stock_dependencies(document: Any, source_type: str, source_id: str) -> list[CancellationDependency]:
    """Detecta consumo posterior de capas o lotes generados por el documento."""
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
    dependencies: list[CancellationDependency] = []
    seen: set[tuple[str, str]] = set()
    if layer_ids:
        consumed = database.session.execute(
            select(StockValuationLayer).where(
                StockValuationLayer.source_layer_id.in_(layer_ids),
                StockValuationLayer.qty < 0,
                StockValuationLayer.voucher_id != source_id,
            )
        ).scalars()
        for row in consumed:
            key = (str(row.voucher_type), str(row.voucher_id))
            if key in seen or not _stock_consumption_is_active(row.voucher_type, row.voucher_id):
                continue
            seen.add(key)
            dependencies.append(CancellationDependency("consumo de inventario", key[1], key[0]))

    from cacao_accounting.database import StockLedgerEntry

    inbound_batches = database.session.execute(
        select(
            StockLedgerEntry.company,
            StockLedgerEntry.item_code,
            StockLedgerEntry.warehouse,
            StockLedgerEntry.batch_id,
        ).where(
            StockLedgerEntry.voucher_type == source_type,
            StockLedgerEntry.voucher_id == source_id,
            StockLedgerEntry.is_cancelled.is_(False),
            StockLedgerEntry.qty_change > 0,
            StockLedgerEntry.batch_id.is_not(None),
        )
    ).all()
    for company, item_code, warehouse, batch_id in inbound_batches:
        consumed_rows = database.session.execute(
            select(StockLedgerEntry.voucher_type, StockLedgerEntry.voucher_id).where(
                StockLedgerEntry.company == company,
                StockLedgerEntry.item_code == item_code,
                StockLedgerEntry.warehouse == warehouse,
                StockLedgerEntry.batch_id == batch_id,
                StockLedgerEntry.is_cancelled.is_(False),
                StockLedgerEntry.qty_change < 0,
                StockLedgerEntry.voucher_id != source_id,
            )
        ).all()
        for voucher_type, voucher_id in consumed_rows:
            key = (str(voucher_type), str(voucher_id))
            if key in seen or not _stock_consumption_is_active(key[0], key[1]):
                continue
            seen.add(key)
            dependencies.append(CancellationDependency("consumo de inventario por lote", key[1], key[0]))

    return dependencies


def _stock_consumption_is_active(voucher_type: str, voucher_id: str) -> bool:
    """Fail closed when the consumer cannot be resolved; ignore drafts/cancelled vouchers."""
    from cacao_accounting.document_flow.registry import get_document_type

    try:
        document_type = get_document_type(voucher_type)
    except ValueError:
        return True
    consumer = database.session.get(document_type.header_model, voucher_id)
    if consumer is None:
        return True
    return getattr(consumer, "docstatus", None) not in (0, 2)


def _landed_cost_consumption_dependencies(
    document: ImportLandedCost,
    source_types: set[str],
    source_id: str,
) -> list[CancellationDependency]:
    """Block landed-cost cancellation when later active outflows consumed stock."""
    allocations = database.session.execute(
        select(LandedCostAllocation).where(
            LandedCostAllocation.company == _document_company(document),
            LandedCostAllocation.document_type.in_(source_types),
            LandedCostAllocation.document_id == source_id,
        )
    ).scalars()
    dependencies: list[CancellationDependency] = []
    seen: set[tuple[str, str]] = set()
    for allocation in allocations:
        allocated_layer = database.session.get(StockValuationLayer, allocation.stock_valuation_layer_id)
        if allocated_layer is None:
            continue
        later_consumption = database.session.execute(
            select(StockValuationLayer)
            .where(
                StockValuationLayer.company == allocation.company,
                StockValuationLayer.item_code == allocation.item_code,
                StockValuationLayer.warehouse == allocation.warehouse,
                StockValuationLayer.qty < 0,
                or_(
                    StockValuationLayer.posting_date > allocated_layer.posting_date,
                    and_(
                        StockValuationLayer.posting_date == allocated_layer.posting_date,
                        StockValuationLayer.id > allocated_layer.id,
                    ),
                ),
            )
            .order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
        ).scalars()
        for layer in later_consumption:
            key = (str(layer.voucher_type), str(layer.voucher_id))
            if key in seen or not _stock_consumption_is_active(*key):
                continue
            seen.add(key)
            dependencies.append(CancellationDependency("consumo de inventario", key[1], key[0]))
    return dependencies
