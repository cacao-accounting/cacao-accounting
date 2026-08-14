# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio core para Confirmación de Saldos de Clientes y Proveedores."""

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
import secrets

from sqlalchemy import select, or_

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


def compute_payment_unallocated_amount_at_date(payment: PaymentEntry, as_of_date: date) -> Decimal:
    """Calcula el saldo no aplicado de un pago a la fecha de corte."""
    if getattr(payment, "docstatus", 0) == 2:
        if is_cancelled_before_cutoff("payment_entry", payment.id, as_of_date):
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


def get_open_documents_at_cutoff(
    company_id: str,
    party_id: str,
    party_type: str,
    cutoff_date: date,
) -> list[dict[str, Any]]:
    """Obtiene y calcula todas las partidas abiertas a una fecha de corte determinada."""
    items = []

    # 1. Facturas y notas de crédito/débito
    if party_type == "customer":
        # Facturas, notas de crédito, notas de débito de clientes
        stmt = select(SalesInvoice).where(
            SalesInvoice.company == company_id,
            SalesInvoice.customer_id == party_id,
            SalesInvoice.posting_date <= cutoff_date,
            SalesInvoice.docstatus.in_((1, 2)),
        )
        rows = database.session.execute(stmt).scalars().all()
        for doc in rows:
            if doc.docstatus == 2:
                # Excluir si se canceló antes de la fecha de corte
                doc_type_name = doc.document_type or "sales_invoice"
                if is_cancelled_before_cutoff(doc_type_name, doc.id, cutoff_date):
                    continue

            # Determinar tipo legible y signo del saldo
            is_credit_document = doc.is_return or doc.document_type in ("sales_credit_note", "sales_return")
            sign = Decimal("-1") if is_credit_document else Decimal("1")

            outstanding = compute_outstanding_amount(doc, as_of_date=cutoff_date)
            if outstanding == 0:
                continue

            doc_type_label = "Factura"
            if doc.document_type == "sales_credit_note":
                doc_type_label = "Nota de Crédito"
            elif doc.document_type == "sales_debit_note":
                doc_type_label = "Nota de Débito"
            elif doc.document_type == "sales_return":
                doc_type_label = "Devolución"

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
                    "original_amount": float(sign * Decimal(str(doc.grand_total or 0))),
                    "outstanding_amount": float(sign * outstanding),
                }
            )

    elif party_type == "supplier":
        # Facturas, notas de crédito, notas de débito de proveedores
        stmt = select(PurchaseInvoice).where(
            PurchaseInvoice.company == company_id,
            PurchaseInvoice.supplier_id == party_id,
            PurchaseInvoice.posting_date <= cutoff_date,
            PurchaseInvoice.docstatus.in_((1, 2)),
        )
        rows = database.session.execute(stmt).scalars().all()
        for doc in rows:
            if doc.docstatus == 2:
                # Excluir si se canceló antes de la fecha de corte
                doc_type_name = doc.document_type or "purchase_invoice"
                if is_cancelled_before_cutoff(doc_type_name, doc.id, cutoff_date):
                    continue

            is_credit_document = doc.is_return or doc.document_type in ("purchase_credit_note", "purchase_return")
            sign = Decimal("-1") if is_credit_document else Decimal("1")

            outstanding = compute_outstanding_amount(doc, as_of_date=cutoff_date)
            if outstanding == 0:
                continue

            doc_type_label = "Factura de Compra"
            if doc.document_type == "purchase_credit_note":
                doc_type_label = "Nota de Crédito"
            elif doc.document_type == "purchase_debit_note":
                doc_type_label = "Nota de Débito"
            elif doc.document_type == "purchase_return":
                doc_type_label = "Devolución de Compra"

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
                    "original_amount": float(sign * Decimal(str(doc.grand_total or 0))),
                    "outstanding_amount": float(sign * outstanding),
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
            if is_cancelled_before_cutoff("payment_entry", payment.id, cutoff_date):
                continue

        unapplied = compute_payment_unallocated_amount_at_date(payment, cutoff_date)
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
                "original_amount": float(-original_val),
                "outstanding_amount": float(-unapplied),
            }
        )

    return items


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
    totals: dict[str, float] = {}
    for item in items:
        currency = item["currency"]
        totals[currency] = float(Decimal(str(totals.get(currency, 0.0))) + Decimal(str(item["outstanding_amount"])))

    snapshot_data = {
        "company_id": company.code,
        "company_name": company.company_name,
        "party_id": party.id,
        "party_name": party.name,
        "party_type": party_type,
        "cutoff_date": cutoff_date.isoformat(),
        "items": items,
        "totals": totals,
        "emails": [email.strip().lower() for email in emails],
    }

    snapshot_json = json.dumps(snapshot_data, ensure_ascii=False)
    snapshot_hash = compute_snapshot_hash(snapshot_data)

    expires_at = datetime.utcnow() + timedelta(days=expiration_days)

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
        # Generar token seguro e inmutable
        raw_token = secrets.token_urlsafe(32)
        raw_code = "".join(secrets.choice("0123456789") for _ in range(6))

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        verification_code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

        invitation = BalanceConfirmationInvitation(
            balance_confirmation_id=confirmation.id,
            email=email.strip().lower(),
            token_hash=token_hash,
            verification_code_hash=verification_code_hash,
            status="pending",
            expires_at=expires_at,
        )
        database.session.add(invitation)

        # Almacenar temporalmente los códigos para el envío (no se guardan en la bd en texto plano)
        invitation._raw_token = raw_token
        invitation._raw_code = raw_code

    return confirmation
