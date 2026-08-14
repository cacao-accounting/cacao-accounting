# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio core para Confirmación de Saldos de Clientes y Proveedores."""

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select

from cacao_accounting.database import (
    database,
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    SalesInvoice,
    PurchaseInvoice,
    PaymentEntry,
    PaymentReference,
    DocumentRelation,
    Entity,
    Party,
    AuditTrail,
)
from cacao_accounting.document_flow.payment import compute_outstanding_amount
from cacao_accounting.audit_trail_service import log_balance_confirmation_event

# Helper functions for calculations


def _utcnow() -> datetime:
    """Retorna la fecha/hora actual en UTC con zona horaria explícita."""
    return datetime.now(timezone.utc)


def build_cancellation_map(doc_types: tuple[str, ...]) -> dict[tuple[str, str], date]:
    """Agrupa la fecha de anulación más temprana por (tipo, id) de documento.

    Reemplaza una consulta por documento (N+1) por una única consulta para el
    conjunto de tipos de documento de la confirmación.
    """
    rows = database.session.execute(
        select(AuditTrail.document_type, AuditTrail.document_id, AuditTrail.timestamp)
        .where(AuditTrail.action == "cancelled", AuditTrail.document_type.in_(doc_types))
        .order_by(AuditTrail.timestamp.asc())
    ).all()
    cancelled: dict[tuple[str, str], date] = {}
    for doc_type, doc_id, timestamp in rows:
        key = (doc_type, doc_id)
        if key not in cancelled and timestamp is not None:
            cancelled[key] = timestamp.date()
    return cancelled


def is_cancelled_before_cutoff(doc_type: str, doc_id: str, cutoff_date: date) -> bool:
    """Retorna verdadero si el documento fue cancelado antes o en la fecha de corte."""
    stmt = (
        select(AuditTrail.timestamp)
        .where(AuditTrail.document_type == doc_type, AuditTrail.document_id == doc_id, AuditTrail.action == "cancelled")
        .order_by(AuditTrail.timestamp.asc())
        .limit(1)
    )
    res = database.session.execute(stmt).scalar()
    if res:
        return res.date() <= cutoff_date
    return False


def compute_payment_unallocated_amount_at_date(
    payment: PaymentEntry, as_of_date: date, cancelled_map: dict[tuple[str, str], date] | None = None
) -> Decimal:
    """Calcula el saldo no aplicado de un pago a la fecha de corte."""
    if getattr(payment, "docstatus", 0) == 2:
        cancel_date = (cancelled_map or {}).get(("payment_entry", payment.id))
        if cancel_date is None:
            if is_cancelled_before_cutoff("payment_entry", payment.id, as_of_date):
                return Decimal("0")
        elif cancel_date <= as_of_date:
            return Decimal("0")
    if payment.posting_date > as_of_date:
        return Decimal("0")
    payment_total = Decimal(str(payment.paid_amount or payment.received_amount or 0))
    if payment_total <= 0:
        return Decimal("0")

    # Obtener todas las aplicaciones del pago realizadas antes o en la fecha de corte
    stmt = select(PaymentReference).where(
        PaymentReference.payment_id == payment.id,
        or_(PaymentReference.allocation_date <= as_of_date, PaymentReference.allocation_date.is_(None)),
    )
    references = database.session.execute(stmt).scalars().all()
    consumed = Decimal("0")
    for ref in references:
        # Verificar la relación del pago y si fue cancelada/revertida antes de la fecha de corte
        rel_stmt = select(DocumentRelation).where(
            DocumentRelation.target_item_id == ref.id, DocumentRelation.target_type == "payment_entry"
        )
        relation = database.session.execute(rel_stmt).scalars().first()
        if relation:
            is_active_at_date = True
            if relation.status == "cancelled":
                cancel_date = relation.cancelled_at.date() if relation.cancelled_at else None
                if cancel_date and cancel_date <= as_of_date:
                    is_active_at_date = False
            if relation.status == "reverted":
                revert_date = relation.reversed_at.date() if relation.reversed_at else None
                if revert_date and revert_date <= as_of_date:
                    is_active_at_date = False

            if is_active_at_date:
                consumed += Decimal(str(ref.allocated_amount or 0))
        else:
            consumed += Decimal(str(ref.allocated_amount or 0))

    remaining = payment_total - consumed
    return remaining if remaining > 0 else Decimal("0")


def compute_applied_credit_document_amount(document: Any, as_of_date: date) -> Decimal:
    """Suma el monto de una nota de crédito/débito ya aplicado a facturas al corte.

    Las notas de crédito y débito aplicadas a una factura se reflejan en el saldo
    vivo de esa factura a través de la relación documental ``invoice_reversal``.
    Para evitar contarlas dos veces como partidas abiertas, la confirmación resta
    ese monto aplicado del saldo independiente de la nota.
    """
    raw_document_type = getattr(document, "document_type", None) or getattr(document, "__tablename__", "")
    document_type = str(raw_document_type or "")
    if document_type not in {"sales_credit_note", "sales_debit_note", "purchase_credit_note", "purchase_debit_note"}:
        return Decimal("0")
    document_id = getattr(document, "id", "")

    def _sum_applied(source_types: tuple[str, ...], invoice_model: Any) -> Decimal:
        query = (
            select(func.sum(DocumentRelation.amount))
            .join(
                invoice_model,
                (DocumentRelation.source_id == invoice_model.id) & DocumentRelation.source_type.in_(source_types),
            )
            .where(
                DocumentRelation.relation_type == "invoice_reversal",
                DocumentRelation.target_type == document_type,
                DocumentRelation.target_id == document_id,
                DocumentRelation.status == "active",
                invoice_model.docstatus == 1,
                invoice_model.posting_date <= as_of_date,
            )
        )
        return Decimal(str(database.session.execute(query).scalar() or 0))

    applied = _sum_applied(("sales_invoice",), SalesInvoice) + _sum_applied(("purchase_invoice",), PurchaseInvoice)
    return applied


def get_open_documents_at_cutoff(
    company_id: str,
    party_id: str,
    party_type: str,
    cutoff_date: date,
) -> list[dict[str, Any]]:
    """Obtiene y calcula todas las partidas abiertas a una fecha de corte determinada."""
    items = []
    cancelled_map = build_cancellation_map(("sales_invoice", "purchase_invoice", "payment_entry"))

    # 1. Facturas y notas de crédito/débito
    if party_type in ("customer", "supplier"):
        model_class: Any = SalesInvoice if party_type == "customer" else PurchaseInvoice
        party_filter = (
            SalesInvoice.customer_id == party_id if party_type == "customer" else PurchaseInvoice.supplier_id == party_id
        )
        default_invoice_label = "Factura" if party_type == "customer" else "Factura de Compra"

        stmt = select(model_class).where(
            model_class.company == company_id,
            party_filter,
            model_class.posting_date <= cutoff_date,
            model_class.docstatus.in_((1, 2)),
        )
        rows = database.session.execute(stmt).scalars().all()
        for doc in rows:
            if doc.docstatus == 2:
                # Excluir si se canceló antes de la fecha de corte
                doc_type_name = doc.document_type or model_class.__tablename__
                if is_cancelled_before_cutoff(doc_type_name, doc.id, cutoff_date):
                    continue

            # Determinar tipo legible y signo del saldo
            is_credit_document = doc.is_return or doc.document_type in (
                "sales_credit_note",
                "sales_return",
                "purchase_credit_note",
                "purchase_return",
            )
            sign = Decimal("-1") if is_credit_document else Decimal("1")

            outstanding = compute_outstanding_amount(doc, as_of_date=cutoff_date)
            if is_credit_document:
                outstanding = outstanding - compute_applied_credit_document_amount(doc, cutoff_date)
            if outstanding <= 0:
                continue

            doc_type_label = default_invoice_label
            if doc.document_type in ("sales_credit_note", "purchase_credit_note"):
                doc_type_label = "Nota de Crédito"
            elif doc.document_type in ("sales_debit_note", "purchase_debit_note"):
                doc_type_label = "Nota de Débito"
            elif doc.document_type == "sales_return":
                doc_type_label = "Devolución"
            elif doc.document_type == "purchase_return":
                doc_type_label = "Devolución de Compra"

            # Fecha de vencimiento si aplica
            due_date = None
            if hasattr(doc, "due_date") and doc.due_date:
                due_date = doc.due_date.isoformat()

            items.append(
                {
                    "document_id": doc.id,
                    "document_type": doc_type_label,
                    "document_no": doc.document_no or doc.id,
                    "document_date": doc.posting_date.isoformat() if doc.posting_date else None,
                    "due_date": due_date,
                    "currency": doc.transaction_currency or doc.base_currency,
                    "original_amount": str(sign * Decimal(str(doc.grand_total or 0))),
                    "outstanding_amount": str(sign * outstanding),
                }
            )

    # 2. Anticipos / Pagos no aplicados
    payment_type = "receive" if party_type == "customer" else "pay"
    p_stmt = select(PaymentEntry).where(
        PaymentEntry.company == company_id,
        PaymentEntry.party_type == party_type,
        PaymentEntry.party_id == party_id,
        PaymentEntry.payment_type == payment_type,
        PaymentEntry.posting_date <= cutoff_date,
        PaymentEntry.docstatus.in_((1, 2)),
    )
    p_rows = database.session.execute(p_stmt).scalars().all()
    for payment in p_rows:
        if payment.docstatus == 2:
            cancel_date = cancelled_map.get(("payment_entry", payment.id))
            if cancel_date is None:
                if is_cancelled_before_cutoff("payment_entry", payment.id, cutoff_date):
                    continue
            elif cancel_date <= cutoff_date:
                continue

        unapplied = compute_payment_unallocated_amount_at_date(payment, cutoff_date, cancelled_map)
        if unapplied == 0:
            continue

        original_val = Decimal(str(payment.paid_amount or payment.received_amount or 0))
        items.append(
            {
                "document_id": payment.id,
                "document_type": "Anticipo / Pago no aplicado" if payment.is_advance else "Pago no aplicado",
                "document_no": payment.document_no or payment.id,
                "document_date": payment.posting_date.isoformat() if payment.posting_date else None,
                "due_date": None,
                "currency": payment.currency,
                "original_amount": str(-original_val),
                "outstanding_amount": str(-unapplied),
            }
        )

    return items


def prepare_invitation_token(invitation: Any) -> tuple[str, str]:
    """Genera de forma segura nuevos tokens y códigos de verificación."""
    raw_token = secrets.token_urlsafe(32)
    raw_code = "".join(secrets.choice("0123456789") for _ in range(6))

    invitation.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invitation.verification_code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    # Almacenar temporalmente los códigos para el envío (no se guardan en la bd en texto plano)
    invitation._raw_token = raw_token
    invitation._raw_code = raw_code
    return raw_token, raw_code


def compute_snapshot_hash(snapshot_data: dict[str, Any]) -> str:
    """Calcula el hash SHA-256 de forma inmutable y ordenada."""
    serialized = json.dumps(snapshot_data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_balance_confirmation(
    company_id: str,
    party_id: str,
    party_type: str,
    cutoff_date: date,
    emails: list[str],
    created_by_user_id: str | None,
    expiration_days: int = 15,
) -> BalanceConfirmation:
    """Crea una nueva confirmación de saldo con su respectivo snapshot inmutable."""
    company = database.session.execute(select(Entity).where(Entity.code == company_id)).scalar_one_or_none()
    party = database.session.get(Party, party_id)
    if not company or not party:
        raise ValueError("Compañía o tercero no válido.")

    # Obtener partidas abiertas
    items = get_open_documents_at_cutoff(company_id, party_id, party_type, cutoff_date)

    # Calcular totales por moneda
    totals: dict[str, Decimal] = {}
    for item in items:
        currency = item["currency"]
        totals[currency] = totals.get(currency, Decimal("0")) + Decimal(item["outstanding_amount"])

    snapshot_data = {
        "company_id": company.code,
        "company_name": company.company_name,
        "party_id": party.id,
        "party_name": party.name,
        "party_type": party_type,
        "cutoff_date": cutoff_date.isoformat(),
        "items": items,
        "totals": {currency: str(total) for currency, total in totals.items()},
        "emails": [email.strip().lower() for email in emails],
    }

    snapshot_json = json.dumps(snapshot_data, ensure_ascii=False)
    snapshot_hash = compute_snapshot_hash(snapshot_data)

    expires_at = _utcnow() + timedelta(days=expiration_days)

    confirmation = BalanceConfirmation(
        company=company_id,
        party_type=party_type,
        party_id=party_id,
        cutoff_date=cutoff_date,
        status="draft",
        created_by=created_by_user_id,
        expires_at=expires_at,
        snapshot_json=snapshot_json,
        snapshot_hash=snapshot_hash,
    )
    database.session.add(confirmation)
    database.session.flush()

    # Generar document_no único
    confirmation.document_no = f"CONF-{confirmation.id[:8].upper()}"

    # Log audit event
    log_balance_confirmation_event(
        confirmation,
        "balance_confirmation_created",
        after=snapshot_data,
        comment="Creado borrador de solicitud de confirmación de saldos.",
    )

    # Generar invitaciones para cada correo electrónico
    for email in emails:
        invitation = BalanceConfirmationInvitation(
            balance_confirmation_id=confirmation.id,
            email=email.strip().lower(),
            token_hash="",
            verification_code_hash="",
            status="pending",
            expires_at=expires_at,
        )
        prepare_invitation_token(invitation)
        database.session.add(invitation)

    return confirmation
