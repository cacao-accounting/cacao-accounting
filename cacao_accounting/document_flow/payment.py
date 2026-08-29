# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de pago, conciliacion AR/AP y referencias de pago.

Convencion de naming para referencias de pago:
- ``flow_source_type``: tipo logico del documento fuente (e.g. ``purchase_credit_note``).
- ``model_type``: tipo fisico del modelo SQLAlchemy (e.g. ``purchase_invoice``).
- ``document_id``: identificador del documento referenciado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from cacao_accounting.database import (
    Accounts,
    Book,
    ComprobanteContable,
    ComprobanteContableDetalle,
    DocumentRelation,
    Entity,
    GLEntry,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    PurchaseOrder,
    Reconciliation,
    ReconciliationItem,
    SalesInvoice,
    SalesOrder,
    database,
)
from cacao_accounting.document_flow.registry import normalize_doctype
from cacao_accounting.document_flow.repository import decimal_or_zero

if TYPE_CHECKING:
    from cacao_accounting.contabilidad.arap_allocation import AllocationLine

_MSG_MONTO_MAYOR_CERO = "El monto aplicado debe ser mayor que cero."

MAX_RECONCILIATION_LINES = 100


def _list_open_items(**filters: Any) -> tuple[Any, ...]:
    """Importa el resolver tarde para evitar ciclos al cargar Flask."""
    from cacao_accounting.contabilidad.arap_allocation import list_open_items

    return list_open_items(**filters)


def _document_flow_error(message: str, status_code: int = 400) -> ValueError:
    """Resuelve DocumentFlowError via import tardio para evitar circular."""
    from cacao_accounting.document_flow.service import DocumentFlowError as _DFE

    return _DFE(message, status_code)


@dataclass
class PaymentAllocationContext:
    """Contexto de asignacion de pago para crear referencias y relaciones."""

    allocation_date: date
    allocated: Decimal
    discount: Decimal
    gain_loss: Decimal
    difference: Decimal
    outstanding: Decimal


def _to_json_number(value: Any) -> str:
    """Serializa montos exactos sin convertirlos a ``float``."""
    return str(decimal_or_zero(value))


def _document_exchange_rate(document: Any) -> Decimal:
    """Resuelve el tipo de cambio del documento, default 1 si no aplica."""
    rate = getattr(document, "exchange_rate", None)
    return decimal_or_zero(rate) if rate else Decimal("1")


def _base_amount(amount: Decimal, document: Any) -> Decimal:
    """Convierte un monto en moneda del documento a moneda base."""
    return amount * _document_exchange_rate(document)


def _payment_candidate_physical_type(flow_source_type: str) -> str:
    """Devuelve el tipo fisico del modelo SQLAlchemy para una referencia de pago."""
    source_key = normalize_doctype(flow_source_type)
    if source_key in {"purchase_credit_note", "purchase_debit_note"}:
        return "purchase_invoice"
    if source_key in {"sales_credit_note", "sales_debit_note"}:
        return "sales_invoice"
    return source_key


def _payment_candidate_date(document: Any) -> date | None:
    """Resuelve la fecha representativa de un candidato de pago."""
    value = (
        getattr(document, "posting_date", None)
        or getattr(document, "bill_date", None)
        or getattr(document, "transaction_date", None)
        or getattr(document, "due_date", None)
    )
    return value if isinstance(value, date) else None


def _document_transaction_currency(document: Any) -> str | None:
    """Resolve a document's currency without silent fallback.

    Solo se considera ``transaction_currency`` explicita. Los campos
    ``currency`` y ``base_currency`` quedan disponibles pero no se usan como
    inferencia silenciosa para preservar el contrato de moneda completa.
    """
    currency = getattr(document, "transaction_currency", None)
    return str(currency) if currency else None


def _payment_candidate_party(document: Any, flow_source_type: str) -> tuple[str, str | None]:
    """Resuelve tipo e id de tercero para un candidato de pago."""
    source_key = normalize_doctype(flow_source_type)
    if source_key.startswith("purchase_"):
        return "supplier", getattr(document, "supplier_id", None)
    return "customer", getattr(document, "customer_id", None)


def _payment_candidate_outstanding(document: Any, flow_source_type: str) -> Decimal:
    """Calcula el saldo disponible de un candidato para referencia de pago."""
    source_key = normalize_doctype(flow_source_type)
    total = decimal_or_zero(getattr(document, "grand_total", None))
    if source_key in {"purchase_order", "sales_order"}:
        pending = total - _payment_order_allocated(
            source_key,
            str(getattr(document, "id", "")),
            company=getattr(document, "company", None),
        )
        return pending if pending > 0 else Decimal("0")
    return compute_outstanding_amount(document)


def _payment_order_allocated(flow_source_type: str, source_id: str, company: str | None = None) -> Decimal:
    """Calcula anticipos activos ya vinculados a una orden."""
    query = (
        select(PaymentReference.allocated_amount)
        .join(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            DocumentRelation.source_type == flow_source_type,
            DocumentRelation.source_id == source_id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
            PaymentEntry.docstatus == 1,
        )
    )
    if company:
        query = query.where(PaymentEntry.company == company)
    rows = database.session.execute(query).scalars()
    return sum((decimal_or_zero(amount) for amount in rows), Decimal("0"))


def _document_payment_references(document: Any, as_of_date: date | None = None) -> list[PaymentReference]:
    """Devuelve las referencias de pago asociadas a una factura."""
    raw_document_type = getattr(document, "document_type", None) or getattr(document, "__tablename__", "")
    document_type = normalize_doctype(str(raw_document_type or ""))
    document_id = getattr(document, "id", "")
    if document_type not in {
        "sales_invoice",
        "purchase_invoice",
        "sales_credit_note",
        "purchase_credit_note",
        "sales_debit_note",
        "purchase_debit_note",
    }:
        return []

    relation_query = (
        select(PaymentReference)
        .join(
            DocumentRelation,
            DocumentRelation.target_item_id == PaymentReference.id,
        )
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            DocumentRelation.source_type == document_type,
            DocumentRelation.source_id == document_id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
            PaymentEntry.docstatus == 1,
            PaymentEntry.company == document.company,
            or_(DocumentRelation.company.is_(None), DocumentRelation.company == document.company),
        )
    )
    if as_of_date is not None:
        relation_query = relation_query.where(
            or_(
                PaymentReference.allocation_date.is_(None),
                PaymentReference.allocation_date <= as_of_date,
            )
        )
    references = list(database.session.execute(relation_query).scalars().all())

    physical_reference_type = "purchase_invoice" if document_type.startswith("purchase_") else "sales_invoice"
    fallback_query = (
        select(PaymentReference)
        .outerjoin(
            DocumentRelation,
            (DocumentRelation.target_item_id == PaymentReference.id) & (DocumentRelation.target_type == "payment_entry"),
        )
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            PaymentReference.reference_type == physical_reference_type,
            PaymentReference.reference_id == document_id,
            PaymentEntry.docstatus == 1,
            PaymentEntry.company == document.company,
            or_(DocumentRelation.company.is_(None), DocumentRelation.company == document.company),
            DocumentRelation.id.is_(None),
        )
    )
    if as_of_date is not None:
        fallback_query = fallback_query.where(
            or_(
                PaymentReference.allocation_date.is_(None),
                PaymentReference.allocation_date <= as_of_date,
            )
        )
    legacy_references = list(database.session.execute(fallback_query).scalars().all())
    return references + legacy_references


def compute_outstanding_amount(document: Any, as_of_date: date | None = None) -> Decimal:
    """Calcula el saldo vivo de una factura usando las referencias de pago y notas de credito/debito."""
    if as_of_date is None:
        as_of_date = date.today()
    from cacao_accounting.database import ARAPLedgerEntry

    document_type = normalize_doctype(str(getattr(document, "document_type", None) or getattr(document, "__tablename__", "")))
    ledger_query = select(func.sum(ARAPLedgerEntry.document_amount)).where(
        ARAPLedgerEntry.document_type == document_type,
        ARAPLedgerEntry.document_id == str(getattr(document, "id", "")),
        ARAPLedgerEntry.posting_date <= as_of_date,
    )
    grand_total = decimal_or_zero(getattr(document, "grand_total", None))
    ledger_rows = database.session.execute(ledger_query).scalar_one_or_none()
    if ledger_rows is not None:
        opening_exists = database.session.execute(
            select(ARAPLedgerEntry.id)
            .where(
                ARAPLedgerEntry.document_type == document_type,
                ARAPLedgerEntry.document_id == str(getattr(document, "id", "")),
                ARAPLedgerEntry.event_type == "opening",
            )
            .limit(1)
        ).scalar_one_or_none()
        balance = decimal_or_zero(ledger_rows) if opening_exists else grand_total + decimal_or_zero(ledger_rows)
        # Pagos/anticipos legacy pueden haberse aplicado después del posting
        # del documento y todavía no tener un evento documental. Se agregan
        # solo las referencias cuyo pago no aparece ya en el ledger, evitando
        # doble descuento de aplicaciones que sí fueron posteadas.
        represented_payment_ids = set(
            database.session.execute(
                select(ARAPLedgerEntry.reference_id).where(
                    ARAPLedgerEntry.document_type == document_type,
                    ARAPLedgerEntry.document_id == str(getattr(document, "id", "")),
                    ARAPLedgerEntry.event_type == "allocation",
                )
            ).scalars()
        )
        pending_references = [
            reference
            for reference in _document_payment_references(document, as_of_date=as_of_date)
            if str(reference.payment_id) not in represented_payment_ids
        ]
        balance -= sum((decimal_or_zero(reference.allocated_amount) for reference in pending_references), Decimal("0"))
        return balance if balance > 0 else Decimal("0")
    allocated_payments = sum(
        decimal_or_zero(reference.allocated_amount)
        for reference in _document_payment_references(document, as_of_date=as_of_date)
    )
    allocated_notes = _compute_allocated_notes_amount(document, as_of_date=as_of_date)
    outstanding = grand_total - allocated_payments - allocated_notes
    return outstanding if outstanding > 0 else Decimal("0")


def _compute_allocated_notes_amount(document: Any, as_of_date: date) -> Decimal:
    """Suma el monto de notas de credito/debito aplicadas y posteadas al documento."""
    raw_document_type = getattr(document, "document_type", None) or getattr(document, "__tablename__", "")
    document_type = normalize_doctype(str(raw_document_type or ""))
    document_id = getattr(document, "id", "")

    def _sum_notes(target_types: tuple[str, ...]) -> Decimal:
        query = (
            select(func.sum(DocumentRelation.amount))
            .join(
                SalesInvoice,
                (DocumentRelation.target_id == SalesInvoice.id)
                & DocumentRelation.target_type.in_(("sales_invoice", "sales_credit_note", "sales_debit_note")),
            )
            .where(
                DocumentRelation.source_type == document_type,
                DocumentRelation.source_id == document_id,
                DocumentRelation.status == "active",
                SalesInvoice.document_type.in_(target_types),
                SalesInvoice.docstatus == 1,
                SalesInvoice.posting_date <= as_of_date,
            )
        )
        res = database.session.execute(query).scalar() or Decimal("0")

        query_purchase = (
            select(func.sum(DocumentRelation.amount))
            .join(
                PurchaseInvoice,
                (DocumentRelation.target_id == PurchaseInvoice.id)
                & DocumentRelation.target_type.in_(
                    ("purchase_invoice", "purchase_return", "purchase_credit_note", "purchase_debit_note")
                ),
            )
            .where(
                DocumentRelation.source_type == document_type,
                DocumentRelation.source_id == document_id,
                DocumentRelation.status == "active",
                PurchaseInvoice.document_type.in_(target_types),
                PurchaseInvoice.docstatus == 1,
                PurchaseInvoice.posting_date <= as_of_date,
            )
        )
        res_p = database.session.execute(query_purchase).scalar() or Decimal("0")

        return decimal_or_zero(res) + decimal_or_zero(res_p)

    res_credit = _sum_notes(("sales_credit_note", "purchase_credit_note", "purchase_return"))
    res_debit = _sum_notes(("sales_debit_note", "purchase_debit_note"))

    return res_credit - res_debit


def _compute_cash_consumed_from_reference(
    reference_id,
    reference_type,
    flow_source_type,
    allocated_amount,
    discount_amount,
    gain_loss_amount,
    relation_status,
    payment_amount=None,
):
    """Calcula el efectivo consumido por una referencia de pago."""
    source_type = normalize_doctype(str(flow_source_type or reference_type or ""))
    if source_type in {"purchase_order", "sales_order"}:
        return Decimal("0"), None
    cash_consumed = decimal_or_zero(payment_amount) or decimal_or_zero(allocated_amount) - decimal_or_zero(
        discount_amount
    ) - decimal_or_zero(gain_loss_amount)
    if cash_consumed < 0:
        cash_consumed = Decimal("0")
    return cash_consumed, str(relation_status) if relation_status else None


def compute_payment_unallocated_amount(payment: PaymentEntry) -> Decimal:
    """Calcula el saldo no aplicado (abierto) de un pago."""
    if getattr(payment, "docstatus", 0) == 2:
        return Decimal("0")
    payment_total = decimal_or_zero(payment.paid_amount or payment.received_amount)
    if payment_total <= 0:
        return Decimal("0")
    from cacao_accounting.database import ARAPLedgerEntry

    ledger_balance = database.session.execute(
        select(func.sum(ARAPLedgerEntry.document_amount)).where(
            ARAPLedgerEntry.document_type == "payment_entry",
            ARAPLedgerEntry.document_id == str(payment.id),
        )
    ).scalar_one_or_none()
    if ledger_balance is not None:
        remaining = -decimal_or_zero(ledger_balance)
        represented_reference_ids = set(
            database.session.execute(
                select(ARAPLedgerEntry.reference_id).where(
                    ARAPLedgerEntry.document_type == "payment_entry",
                    ARAPLedgerEntry.document_id == str(payment.id),
                    ARAPLedgerEntry.event_type == "allocation",
                )
            ).scalars()
        )
        pending_reference_amount = database.session.execute(
            select(
                func.coalesce(func.sum(func.coalesce(PaymentReference.payment_amount, PaymentReference.allocated_amount)), 0)
            ).where(
                PaymentReference.payment_id == payment.id,
                ~PaymentReference.reference_id.in_(represented_reference_ids or {"__none__"}),
            )
        ).scalar_one()
        remaining -= decimal_or_zero(pending_reference_amount)
        return remaining if remaining > 0 else Decimal("0")
    reference_rows = database.session.execute(
        select(
            PaymentReference.id,
            PaymentReference.reference_type,
            PaymentReference.flow_source_type,
            PaymentReference.allocated_amount,
            PaymentReference.discount_amount,
            PaymentReference.gain_loss_amount,
            PaymentReference.payment_amount,
            DocumentRelation.status,
        )
        .outerjoin(
            DocumentRelation,
            (DocumentRelation.target_item_id == PaymentReference.id) & (DocumentRelation.target_type == "payment_entry"),
        )
        .where(PaymentReference.payment_id == payment.id)
    ).all()
    if not reference_rows:
        return payment_total
    consumed_by_reference: dict[str, Decimal] = {}
    relation_status_by_reference: dict[str, set[str]] = {}
    for row in reference_rows:
        cash_consumed, relation_status = _compute_cash_consumed_from_reference(
            row[0], row[1], row[2], row[3], row[4], row[5], row[7], payment_amount=row[6]
        )
        if cash_consumed == Decimal("0") and relation_status is None:
            continue
        reference_id_str = str(row[0])
        consumed_by_reference[reference_id_str] = consumed_by_reference.get(reference_id_str, Decimal("0")) + cash_consumed
        if relation_status:
            relation_status_by_reference.setdefault(reference_id_str, set()).add(relation_status)
    consumed = sum(
        cash
        for ref_id, cash in consumed_by_reference.items()
        if not relation_status_by_reference.get(ref_id) or "active" in relation_status_by_reference[ref_id]
    )
    remaining = payment_total - consumed
    return remaining if remaining > 0 else Decimal("0")


def refresh_outstanding_amount_cache(document: Any, as_of_date: date | None = None) -> Decimal:
    """Sincroniza el campo cacheado `outstanding_amount` con el valor calculado."""
    outstanding = compute_outstanding_amount(document, as_of_date=as_of_date)
    if hasattr(document, "outstanding_amount"):
        document.outstanding_amount = outstanding
    if hasattr(document, "base_outstanding_amount"):
        document.base_outstanding_amount = _base_amount(outstanding, document)
    return outstanding


def payment_reference_candidates(
    *,
    company: str,
    party_type: str,
    party_id: str,
    source_types: list[str],
    include_orders: bool = False,
) -> list[dict[str, Any]]:
    """Devuelve documentos candidatos para la tabla de referencias de pago."""
    if not company or party_type not in {"supplier", "customer"} or not party_id:
        raise _document_flow_error("Debe indicar compania, tipo de tercero y tercero.")
    allowed_by_party = (
        {"purchase_invoice", "purchase_debit_note", "purchase_credit_note", "purchase_order"}
        if party_type == "supplier"
        else {"sales_invoice", "sales_debit_note", "sales_credit_note", "sales_order"}
    )
    model_by_type = _get_model_by_type()
    rows: list[dict[str, Any]] = []
    for raw_source_type in source_types:
        source_type = normalize_doctype(raw_source_type)
        if source_type not in allowed_by_party:
            continue
        if not _should_include_orders(source_type, include_orders):
            continue
        query = _build_candidate_query(model_by_type, source_type, company, party_type, party_id)
        if query is None:
            continue
        rows.extend(_collect_candidates_from_documents(query, source_type, party_type, party_id, company))
    return rows


def _get_model_by_type() -> dict[str, Any]:
    return {
        "purchase_invoice": PurchaseInvoice,
        "purchase_debit_note": PurchaseInvoice,
        "purchase_credit_note": PurchaseInvoice,
        "purchase_order": PurchaseOrder,
        "sales_invoice": SalesInvoice,
        "sales_debit_note": SalesInvoice,
        "sales_credit_note": SalesInvoice,
        "sales_order": SalesOrder,
    }


def _should_include_orders(source_type: str, include_orders: bool) -> bool:
    if source_type in {"purchase_order", "sales_order"} and not include_orders:
        return False
    return True


def _build_candidate_query(
    model_by_type: dict[str, Any], source_type: str, company: str, party_type: str, party_id: str
) -> Any | None:
    model = model_by_type.get(source_type)
    if model is None:
        return None
    query = database.select(model).filter_by(company=company, docstatus=1)
    if hasattr(model, "document_type"):
        query = query.filter_by(document_type=source_type)
    return _apply_candidate_party_filter(query, party_type, party_id)


def _apply_candidate_party_filter(query: Any, party_type: str, party_id: str) -> Any:
    """Aplica el filtro de tercero esperado a la consulta de candidatos."""
    if party_type == "supplier":
        return query.filter_by(supplier_id=party_id)
    return query.filter_by(customer_id=party_id)


def _collect_candidates_from_documents(
    query: Any, source_type: str, party_type: str, party_id: str, company: str
) -> list[dict[str, Any]]:
    open_items = {
        (item.document_type, item.document_id): item
        for item in _list_open_items(company=company, party_type=party_type, party_id=party_id)
    }
    rows: list[dict[str, Any]] = []
    for document in database.session.execute(query).scalars().all():
        open_item = open_items.get((source_type, str(document.id)))
        outstanding = open_item.outstanding if open_item is not None else _payment_candidate_outstanding(document, source_type)
        if outstanding <= 0:
            continue
        rows.append(_build_candidate_row(document, source_type, party_type, party_id, company, outstanding=outstanding))
    return rows


def _build_candidate_row(
    document: Any,
    flow_source_type: str,
    party_type: str,
    party_id: str,
    company: str,
    *,
    outstanding: Decimal | None = None,
) -> dict[str, Any]:
    """Serializa un documento candidato para conciliacion AR/AP."""
    document_date = _payment_candidate_date(document)
    physical_type = _payment_candidate_physical_type(flow_source_type)
    return {
        "flow_source_type": flow_source_type,
        "model_type": physical_type,
        "document_id": document.id,
        "document_no": getattr(document, "document_no", None) or document.id,
        "document_date": document_date.isoformat() if document_date else "",
        "party_type": party_type,
        "party_id": party_id,
        "company": company,
        "currency": _document_transaction_currency(document) or "",
        "grand_total": _to_json_number(getattr(document, "grand_total", None)),
        "pending_amount": _to_json_number(
            outstanding if outstanding is not None else _payment_candidate_outstanding(document, flow_source_type)
        ),
    }


def payment_reconciliation_candidates(
    *,
    company: str,
    party_type: str,
    party_id: str | None = None,
    currency: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Devuelve pagos abiertos y documentos pendientes para conciliacion AR/AP."""
    if not company or party_type not in {"supplier", "customer"}:
        raise _document_flow_error("Debe indicar compania y tipo de tercero.")

    payments = _candidate_payments(company, party_type, party_id, currency)
    documents = _candidate_documents(company, party_type, party_id, currency)
    return {"payments": payments, "documents": documents}


def _candidate_payments(
    company: str,
    party_type: str,
    party_id: str | None,
    currency: str | None,
) -> list[dict[str, Any]]:
    """Devuelve pagos abiertos candidatos para conciliacion."""
    payment_query = (
        select(PaymentEntry)
        .filter_by(company=company, party_type=party_type, docstatus=1)
        .where(PaymentEntry.payment_type.in_(("pay", "receive")))
    )
    if party_id:
        payment_query = payment_query.filter_by(party_id=party_id)
    if currency:
        payment_query = payment_query.filter_by(currency=currency)

    open_items = {
        item.document_id: item
        for item in _list_open_items(
            company=company,
            party_type=party_type,
            party_id=party_id,
            currency=currency,
        )
        if item.document_type == "payment_entry"
    }
    rows: list[dict[str, Any]] = []
    for payment in database.session.execute(payment_query.order_by(PaymentEntry.posting_date, PaymentEntry.id)).scalars():
        open_item = open_items.get(str(payment.id))
        unallocated = open_item.outstanding if open_item is not None else compute_payment_unallocated_amount(payment)
        if unallocated <= 0:
            continue
        rows.append(
            {
                "payment_id": payment.id,
                "document_no": getattr(payment, "document_no", None) or payment.id,
                "payment_type": payment.payment_type,
                "posting_date": payment.posting_date.isoformat() if payment.posting_date else "",
                "party_type": payment.party_type,
                "party_id": payment.party_id,
                "party_name": payment.party_name or "",
                "company": payment.company,
                "currency": payment.currency or "",
                "unallocated_amount": _to_json_number(unallocated),
            }
        )
    return rows


def _candidate_documents(
    company: str,
    party_type: str,
    party_id: str | None,
    currency: str | None,
) -> list[dict[str, Any]]:
    """Devuelve documentos origen candidatos para conciliacion."""
    if not party_id:
        return []

    source_types = _candidate_source_types(party_type)
    documents = payment_reference_candidates(
        company=company,
        party_type=party_type,
        party_id=party_id,
        source_types=source_types,
    )
    return _filter_candidates_by_currency(documents, currency)


def _candidate_source_types(party_type: str) -> list[str]:
    """Resuelve los doctypes origen validos para el tipo de tercero."""
    if party_type == "supplier":
        return ["purchase_invoice", "purchase_debit_note", "purchase_credit_note"]
    return ["sales_invoice", "sales_debit_note", "sales_credit_note"]


def _filter_candidates_by_currency(
    documents: list[dict[str, Any]],
    currency: str | None,
) -> list[dict[str, Any]]:
    """Filtra documentos candidatos por moneda si aplica."""
    if not currency:
        return documents
    return [document for document in documents if document.get("currency") in {"", currency}]


def _payment_reference_model(flow_source_type: str) -> type[PurchaseInvoice] | type[SalesInvoice]:
    """Devuelve el modelo fisico de una referencia AR/AP."""
    source_key = normalize_doctype(flow_source_type)
    if source_key.startswith("purchase_"):
        return PurchaseInvoice
    if source_key.startswith("sales_"):
        return SalesInvoice
    raise _document_flow_error("Tipo de referencia invalido.")


def _payment_reference_party(document: Any, flow_source_type: str) -> tuple[str, str | None]:
    """Resuelve el tercero esperado para una referencia AR/AP."""
    return _payment_candidate_party(document, flow_source_type)


def _payment_type_matches_source(payment_type: str, flow_source_type: str) -> bool:
    """Valida que el tipo de pago sea compatible con factura o nota."""
    expected = {
        "purchase_invoice": "pay",
        "purchase_debit_note": "pay",
        "purchase_credit_note": "receive",
        "sales_invoice": "receive",
        "sales_debit_note": "receive",
        "sales_credit_note": "pay",
    }.get(normalize_doctype(flow_source_type))
    return expected is None or payment_type == expected


def _cash_consumed(allocated: Decimal, discount: Decimal, gain_loss: Decimal) -> Decimal:
    """Calcula el efectivo consumido por una aplicacion de pago."""
    consumed = allocated - discount - gain_loss
    return consumed if consumed > 0 else Decimal("0")


def apply_payment_reconciliation(
    *,
    company: str,
    party_type: str,
    party_id: str,
    allocation_date: date,
    lines: list[dict[str, Any]],
) -> Reconciliation:
    """Aplica pagos existentes contra documentos AR/AP abiertos."""
    if not lines:
        raise _document_flow_error("La conciliacion requiere al menos una linea.")
    if len(lines) > MAX_RECONCILIATION_LINES:
        raise _document_flow_error(
            "El numero de lineas excede el maximo permitido ({0}).".format(MAX_RECONCILIATION_LINES),
        )
    if not company or party_type not in {"supplier", "customer"} or not party_id:
        raise _document_flow_error("Debe indicar compania, tipo de tercero y tercero.")
    latest_allocation = database.session.execute(
        select(func.max(PaymentReference.allocation_date))
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            PaymentEntry.company == company,
            PaymentEntry.party_type == party_type,
            PaymentEntry.party_id == party_id,
            PaymentEntry.docstatus == 1,
        )
    ).scalar_one()
    if latest_allocation and allocation_date < latest_allocation:
        raise _document_flow_error(
            f"La fecha de conciliación no puede ser anterior a una aplicación existente ({latest_allocation})."
        )

    reconciliation = Reconciliation(
        company=company,
        party_id=party_id,
        recon_date=allocation_date,
        recon_type="AP" if party_type == "supplier" else "AR",
    )
    database.session.add(reconciliation)
    database.session.flush()

    processed: set[tuple[str, str, str]] = set()
    payment_remaining: dict[str, Decimal] = {}
    for raw_line in lines:
        _process_reconciliation_line(
            raw_line, company, party_type, party_id, allocation_date, reconciliation.id, processed, payment_remaining
        )
    return reconciliation


def _process_reconciliation_line(
    raw_line: dict[str, Any],
    company: str,
    party_type: str,
    party_id: str,
    allocation_date: date,
    reconciliation_id: str,
    processed: set[tuple[str, str, str]],
    payment_remaining: dict[str, Decimal],
) -> None:
    from cacao_accounting.contabilidad.arap_allocation import (
        ARAPOpenItem,
        AllocationLine,
        AllocationRequest,
        OpenItemResolver,
        apply_allocation,
        plan_allocation,
    )

    payment_id = str(raw_line.get("payment_id") or "")
    document_id = str(raw_line.get("reference_id") or raw_line.get("document_id") or "")
    flow_source_type = normalize_doctype(str(raw_line.get("flow_source_type") or raw_line.get("reference_type") or ""))
    model_type = normalize_doctype(
        str(raw_line.get("reference_type") or raw_line.get("model_type") or _payment_candidate_physical_type(flow_source_type))
    )
    allocated = decimal_or_zero(raw_line.get("allocated_amount"))
    discount = decimal_or_zero(raw_line.get("discount_amount"))
    gain_loss = decimal_or_zero(raw_line.get("gain_loss_amount"))
    difference = decimal_or_zero(raw_line.get("difference_amount") or gain_loss)

    if allocated <= 0:
        raise _document_flow_error(_MSG_MONTO_MAYOR_CERO, 409)
    if discount + gain_loss >= allocated:
        raise _document_flow_error(
            "El descuento + diferencia de cambio ({0}) no puede ser igual o mayor al monto asignado ({1}).".format(
                discount + gain_loss, allocated
            ),
            409,
        )
    key = (payment_id, flow_source_type, document_id)
    if key in processed:
        raise _document_flow_error("No se puede aplicar la misma factura dos veces en un pago.", 409)
    processed.add(key)

    payment = database.session.get(PaymentEntry, payment_id, with_for_update=True)
    _validate_payment(payment, company, party_type, party_id, flow_source_type)
    assert payment is not None

    if payment_id not in payment_remaining:
        payment_remaining[payment_id] = compute_payment_unallocated_amount(payment)
    document = _get_reference_document(flow_source_type, document_id, company, party_type, party_id)
    _check_duplicate_application(payment.id, flow_source_type, document_id)
    outstanding = _validate_and_get_outstanding(document, allocated, allocation_date)
    if discount or gain_loss:
        payment_currency = str(getattr(payment, "currency", None) or "")
        document_currency = _document_transaction_currency(document) or payment_currency
        requested_rate = raw_line.get("payment_exchange_rate") or raw_line.get("exchange_rate")
        if payment_currency == document_currency:
            effective_rate = Decimal("1")
        else:
            effective_rate = decimal_or_zero(requested_rate)
            if effective_rate <= 0:
                raise _document_flow_error("Se requiere una tasa positiva entre la moneda del documento y la del pago.", 409)
        consumed = _cash_consumed(allocated, discount, gain_loss) * effective_rate
        if consumed > payment_remaining[payment_id] + Decimal("0.01"):
            raise _document_flow_error("El monto aplicado excede el saldo disponible del pago.", 409)
        allocation_line = AllocationLine(
            document_id=document_id,
            document_type=flow_source_type,
            document_currency=str(_document_transaction_currency(document) or payment.currency),
            source_currency=str(payment.currency),
            document_amount=allocated,
            source_amount=consumed,
            rate=effective_rate,
            idempotency_key=f"{payment.id}:{flow_source_type}:{document_id}",
        )
    else:
        allocation_line = _plan_reconciliation_allocation(
            raw_line=raw_line,
            payment=payment,
            document=document,
            flow_source_type=flow_source_type,
            document_id=document_id,
            outstanding=outstanding,
            allocated=allocated,
            available=payment_remaining[payment_id],
        )
    consumed = allocation_line.source_amount
    allocation_ctx = PaymentAllocationContext(
        allocation_date=allocation_date,
        allocated=allocated,
        discount=discount,
        gain_loss=gain_loss,
        difference=difference,
        outstanding=outstanding,
    )

    if discount or gain_loss:
        _persist_reconciliation_allocation(
            raw_line=raw_line,
            payment=payment,
            document=document,
            flow_source_type=flow_source_type,
            model_type=model_type,
            document_id=document_id,
            allocation_ctx=allocation_ctx,
            allocation_line=allocation_line,
            reconciliation_id=reconciliation_id,
        )
        payment_remaining[payment_id] -= consumed
        return
    resolver = OpenItemResolver(
        [
            ARAPOpenItem(
                document_id=document_id,
                document_type=flow_source_type,
                currency=allocation_line.document_currency,
                outstanding=outstanding,
                company=company,
                party_type=party_type,
                party_id=party_id,
            )
        ]
    )
    plan = plan_allocation(
        payment_remaining[payment_id],
        allocation_line.source_currency,
        [
            AllocationRequest(
                document_id=document_id,
                amount=allocated,
                rate=allocation_line.rate,
                idempotency_key=allocation_line.idempotency_key,
            )
        ],
        resolver=resolver,
    )
    apply_allocation(
        plan,
        resolver=resolver,
        persist=lambda line: _persist_reconciliation_allocation(
            raw_line=raw_line,
            payment=payment,
            document=document,
            flow_source_type=flow_source_type,
            model_type=model_type,
            document_id=document_id,
            allocation_ctx=allocation_ctx,
            allocation_line=line,
            reconciliation_id=reconciliation_id,
        ),
    )
    payment_remaining[payment_id] -= consumed


def _plan_reconciliation_allocation(
    *,
    raw_line: dict[str, Any],
    payment: PaymentEntry,
    document: Any,
    flow_source_type: str,
    document_id: str,
    outstanding: Decimal,
    allocated: Decimal,
    available: Decimal,
) -> AllocationLine:
    """Valida una línea con el motor AR/AP y devuelve importes en ambas monedas."""
    from cacao_accounting.contabilidad.arap_allocation import (
        ARAPOpenItem,
        AllocationCurrencyError,
        AllocationError,
        AllocationOverpaymentError,
        AllocationRequest,
        OpenItemResolver,
        plan_allocation,
    )

    payment_currency = str(getattr(payment, "currency", None) or "")
    # Las filas legacy pueden no tener snapshot documental. Conservamos esa
    # compatibilidad únicamente cuando no se solicita una conversión; los
    # documentos nuevos siguen llegando con ``transaction_currency``.
    document_currency = _document_transaction_currency(document) or payment_currency
    if not payment_currency:
        raise _document_flow_error("La conciliacion requiere moneda explicita en el pago.", 409)
    requested_rate = raw_line.get("payment_exchange_rate")
    if requested_rate is None and document_currency != payment_currency:
        requested_rate = raw_line.get("exchange_rate")
    if document_currency == payment_currency:
        effective_rate = Decimal("1")
    else:
        if requested_rate is None:
            raise _document_flow_error("Se requiere una tasa positiva entre la moneda del documento y la del pago.", 409)
        effective_rate = decimal_or_zero(requested_rate)
    resolver = OpenItemResolver(
        [
            ARAPOpenItem(
                document_id=document_id,
                document_type=flow_source_type,
                currency=document_currency,
                outstanding=outstanding,
            )
        ]
    )
    try:
        plan = plan_allocation(
            available,
            payment_currency,
            [
                AllocationRequest(
                    document_id=document_id,
                    amount=allocated,
                    rate=effective_rate,
                    idempotency_key=f"{payment.id}:{flow_source_type}:{document_id}",
                )
            ],
            resolver=resolver,
        )
    except (AllocationCurrencyError, AllocationOverpaymentError, AllocationError) as exc:
        message = str(exc)
        if isinstance(exc, AllocationOverpaymentError) and "efectivo" in message.lower():
            message = "El monto aplicado excede el saldo disponible del pago."
        raise _document_flow_error(message, 409) from exc
    line = plan.lines[0]
    if line.source_amount > available + Decimal("0.01"):
        raise _document_flow_error("El monto aplicado excede el saldo disponible del pago.", 409)
    return line


def _persist_reconciliation_allocation(
    *,
    raw_line: dict[str, Any],
    payment: PaymentEntry,
    document: Any,
    flow_source_type: str,
    model_type: str,
    document_id: str,
    allocation_ctx: PaymentAllocationContext,
    allocation_line: AllocationLine,
    reconciliation_id: str,
) -> None:
    """Persist legacy artifacts from an already validated AR/AP line."""
    enriched_line = {
        **raw_line,
        "payment_currency": allocation_line.source_currency,
        "payment_amount": allocation_line.source_amount,
        "payment_exchange_rate": allocation_line.rate,
    }
    _create_payment_reference_and_relation(
        enriched_line,
        payment,
        document,
        flow_source_type,
        model_type,
        document_id,
        allocation_ctx,
    )
    if getattr(payment, "docstatus", 0) == 1:
        from cacao_accounting.contabilidad.arap_ledger_service import post_payment_application_ar_ap

        post_payment_application_ar_ap(
            payment,
            document,
            document_amount=allocation_line.document_amount,
            payment_amount=allocation_line.source_amount,
            allocation_date=allocation_ctx.allocation_date,
            reference_type=flow_source_type,
        )
    _update_document_outstanding(document, allocation_ctx.outstanding, allocation_ctx.allocated)
    _create_reconciliation_item(
        reconciliation_id,
        flow_source_type,
        document_id,
        payment.id,
        allocation_ctx.allocated,
        allocation_ctx.allocation_date,
    )


def _validate_payment(payment: Any, company: str, party_type: str, party_id: str, flow_source_type: str) -> None:
    if not payment or payment.docstatus != 1:
        raise _document_flow_error("El pago debe existir y estar aprobado.", 404)
    if payment.company != company or payment.party_type != party_type or payment.party_id != party_id:
        raise _document_flow_error("El pago no coincide con la compania o tercero de la conciliacion.", 409)
    if not _payment_type_matches_source(payment.payment_type, flow_source_type):
        raise _document_flow_error("El tipo de pago no corresponde con el documento referenciado.", 409)


def _get_reference_document(flow_source_type: str, document_id: str, company: str, party_type: str, party_id: str) -> Any:
    model = _payment_reference_model(flow_source_type)
    document = database.session.get(model, document_id, with_for_update=True)
    if not document or getattr(document, "docstatus", 0) != 1:
        raise _document_flow_error("El documento referenciado debe existir y estar aprobado.", 404)
    if getattr(document, "company", None) != company:
        raise _document_flow_error("El documento referenciado no pertenece a la misma compania.", 409)
    expected_party_type, expected_party_id = _payment_reference_party(document, flow_source_type)
    if expected_party_type != party_type or expected_party_id != party_id:
        raise _document_flow_error("El documento referenciado no coincide con el tercero.", 409)
    return document


def _validate_payment_currency_match(payment: Any, document: Any, *, infer_missing: bool = False) -> None:
    """CAS-03: Valida que la moneda del pago coincida con la moneda del documento referenciado."""
    payment_currency = getattr(payment, "currency", None)
    document_currency = _document_transaction_currency(document)
    if infer_missing and not payment_currency and document_currency:
        payment.currency = document_currency
        payment.transaction_currency = document_currency
        payment_currency = document_currency
    if payment_currency and document_currency and payment_currency != document_currency:
        raise _document_flow_error(
            "La moneda del pago ({0}) no coincide con la moneda del documento referenciado ({1}). "
            "No se permiten aplicaciones cruzadas de moneda.".format(payment_currency, document_currency),
            409,
        )


def _check_duplicate_application(payment_id: str, flow_source_type: str, document_id: str) -> None:
    existing = database.session.execute(
        select(PaymentReference.id)
        .join(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .where(
            PaymentReference.payment_id == payment_id,
            DocumentRelation.source_type == flow_source_type,
            DocumentRelation.source_id == document_id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        raise _document_flow_error("El documento ya esta aplicado a este pago.", 409)


def _validate_and_get_outstanding(document: Any, allocated: Decimal, allocation_date: date) -> Decimal:
    outstanding = compute_outstanding_amount(document, as_of_date=allocation_date)
    if outstanding <= 0:
        raise _document_flow_error("El documento referenciado no tiene saldo pendiente.", 409)
    if allocated > outstanding + Decimal("0.01"):
        raise _document_flow_error("El monto aplicado excede el saldo pendiente del documento.", 409)
    return outstanding


def _create_payment_reference_and_relation(
    raw_line: dict[str, Any],
    payment: Any,
    document: Any,
    flow_source_type: str,
    model_type: str,
    document_id: str,
    allocation_ctx: PaymentAllocationContext,
) -> None:
    physical_type = _payment_candidate_physical_type(flow_source_type)
    outstanding_after = allocation_ctx.outstanding - allocation_ctx.allocated
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=physical_type or model_type,
        flow_source_type=flow_source_type,
        reference_id=document_id,
        reference_document_no=getattr(document, "document_no", None) or document_id,
        reference_date=_payment_candidate_date(document),
        party_type=payment.party_type,
        party_id=payment.party_id,
        company=payment.company,
        currency=_document_transaction_currency(document) or getattr(payment, "currency", None),
        total_amount=getattr(document, "grand_total", None),
        outstanding_amount=allocation_ctx.outstanding,
        outstanding_amount_after=outstanding_after,
        allocated_amount=allocation_ctx.allocated,
        payment_currency=raw_line.get("payment_currency"),
        payment_amount=decimal_or_zero(raw_line.get("payment_amount")),
        payment_exchange_rate=decimal_or_zero(raw_line.get("payment_exchange_rate")),
        exchange_rate=decimal_or_zero(raw_line.get("exchange_rate"))
        or decimal_or_zero(getattr(document, "exchange_rate", None))
        or Decimal("1"),
        difference_amount=allocation_ctx.difference,
        allocation_date=allocation_ctx.allocation_date,
        discount_amount=allocation_ctx.discount,
        gain_loss_amount=allocation_ctx.gain_loss,
        notes=raw_line.get("notes"),
    )
    database.session.add(reference)
    database.session.flush()
    from cacao_accounting.document_flow.service import create_document_relation

    create_document_relation(
        source_type=flow_source_type,
        source_id=document_id,
        source_item_id=None,
        target_type="payment_entry",
        target_id=payment.id,
        target_item_id=reference.id,
        qty=Decimal("1"),
        rate=allocation_ctx.allocated,
        amount=allocation_ctx.allocated,
    )


def _update_document_outstanding(document: Any, outstanding: Decimal, allocated: Decimal) -> None:
    outstanding_after = outstanding - allocated
    setattr(document, "outstanding_amount", outstanding_after)
    setattr(document, "base_outstanding_amount", _base_amount(outstanding_after, document))


def _create_reconciliation_item(
    reconciliation_id: str,
    flow_source_type: str,
    document_id: str,
    payment_id: str,
    allocated: Decimal,
    allocation_date: date,
) -> None:
    database.session.add(
        ReconciliationItem(
            reconciliation_id=reconciliation_id,
            reference_type=flow_source_type,
            reference_id=document_id,
            amount=allocated,
            allocated_amount=allocated,
            reconciliation_date=allocation_date,
            source_type="payment_entry",
            source_id=payment_id,
            target_type=flow_source_type,
            target_id=document_id,
        )
    )


def _load_advance_invoice(invoice_id: str) -> tuple[SalesInvoice | PurchaseInvoice, str, str | None]:
    """Carga la factura de un anticipo y devuelve su tipo de referencia y tercero."""
    invoice: SalesInvoice | PurchaseInvoice | None = database.session.get(SalesInvoice, invoice_id, with_for_update=True)
    reference_type = "sales_invoice"
    party_id = getattr(invoice, "customer_id", None) if invoice else None
    if invoice is None:
        invoice = database.session.get(PurchaseInvoice, invoice_id, with_for_update=True)
        reference_type = "purchase_invoice"
        party_id = getattr(invoice, "supplier_id", None) if invoice else None
    if invoice is None:
        raise _document_flow_error("La factura no existe.", 404)
    if invoice.docstatus != 1:
        raise _document_flow_error("La factura debe estar aprobada para aplicar un anticipo.", 409)
    return invoice, reference_type, party_id


def _advance_allocated_amount(payment_id: str) -> Decimal:
    """Sum active advance applications, excluding reverted document relations."""
    allocated = database.session.execute(
        select(func.coalesce(func.sum(func.coalesce(PaymentReference.payment_amount, PaymentReference.allocated_amount)), 0))
        .outerjoin(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .where(
            PaymentReference.payment_id == payment_id,
            or_(DocumentRelation.id.is_(None), DocumentRelation.status == "active"),
        )
    ).scalar_one()
    return decimal_or_zero(allocated)


def _validate_advance_allocation(
    payment: PaymentEntry,
    invoice: SalesInvoice | PurchaseInvoice,
    party_id: str | None,
    amount: Decimal,
    allocation_date: date,
    exchange_rate: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Valida la aplicacion del anticipo y devuelve el outstanding antes/despues."""
    if payment.company != invoice.company:
        raise _document_flow_error("El anticipo y la factura pertenecen a companias distintas.", 409)
    if payment.party_id and party_id and payment.party_id != party_id:
        raise _document_flow_error("El anticipo pertenece a otro tercero.", 409)
    allocated_before = _advance_allocated_amount(payment.id)
    payment_total = decimal_or_zero(payment.paid_amount or payment.received_amount)
    outstanding = compute_outstanding_amount(invoice, as_of_date=allocation_date)
    current_outstanding = compute_outstanding_amount(invoice)
    if amount <= 0:
        raise _document_flow_error(_MSG_MONTO_MAYOR_CERO, 409)
    payment_currency = str(getattr(payment, "currency", None) or "")
    document_currency = _document_transaction_currency(invoice) or payment_currency
    if not payment_currency or not document_currency:
        raise _document_flow_error("La aplicación requiere monedas explícitas.", 409)
    if payment_currency == document_currency:
        rate = Decimal("1")
    else:
        rate = decimal_or_zero(exchange_rate)
        if rate <= 0:
            raise _document_flow_error("Se requiere una tasa positiva entre la moneda del documento y la del pago.", 409)
    payment_consumed = amount * rate
    if payment_consumed > payment_total - allocated_before:
        raise _document_flow_error("El monto excede el remanente del anticipo.", 409)
    if amount > outstanding:
        raise _document_flow_error("El monto excede el saldo pendiente de la factura.", 409)
    if amount > current_outstanding:
        raise _document_flow_error("El monto excede el saldo pendiente vigente de la factura.", 409)
    return outstanding, outstanding - amount, rate


def apply_advance_to_invoice(
    payment_entry_id: str,
    invoice_id: str,
    amount: Decimal,
    allocation_date: date,
    exchange_rate: Decimal | None = None,
) -> PaymentReference:
    """Aplica un anticipo existente contra una factura AR/AP."""
    payment = database.session.get(PaymentEntry, payment_entry_id, with_for_update=True)
    if not payment:
        raise _document_flow_error("El pago/anticipo no existe.", 404)
    if payment.docstatus != 1:
        raise _document_flow_error("El pago/anticipo debe estar aprobado.", 409)
    invoice, reference_type, party_id = _load_advance_invoice(invoice_id)
    outstanding, outstanding_after, effective_rate = _validate_advance_allocation(
        payment, invoice, party_id, amount, allocation_date, exchange_rate
    )
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=reference_type,
        reference_id=invoice.id,
        reference_document_no=getattr(invoice, "document_no", None) or invoice.id,
        reference_date=getattr(invoice, "posting_date", None),
        party_type="customer" if reference_type == "sales_invoice" else "supplier",
        party_id=party_id,
        company=invoice.company,
        currency=_document_transaction_currency(invoice) or getattr(payment, "currency", None),
        total_amount=getattr(invoice, "grand_total", None),
        outstanding_amount=outstanding,
        outstanding_amount_after=outstanding_after,
        allocated_amount=amount,
        payment_currency=getattr(payment, "currency", None),
        payment_amount=amount * effective_rate,
        payment_exchange_rate=effective_rate,
        allocation_date=allocation_date,
    )
    database.session.add(reference)
    database.session.flush()
    from cacao_accounting.document_flow.service import create_document_relation

    create_document_relation(
        source_type=reference_type,
        source_id=invoice.id,
        source_item_id=None,
        target_type="payment_entry",
        target_id=payment.id,
        target_item_id=reference.id,
        qty=Decimal("1"),
        rate=amount,
        amount=amount,
    )
    if getattr(payment, "docstatus", 0) == 1:
        from cacao_accounting.contabilidad.arap_ledger_service import post_payment_application_ar_ap

        post_payment_application_ar_ap(
            payment,
            invoice,
            document_amount=amount,
            payment_amount=amount * effective_rate,
            allocation_date=allocation_date,
            reference_type=reference_type,
        )
    refresh_outstanding_amount_cache(invoice)
    _maybe_settle_advance_against_invoice(payment, invoice, reference_type, amount, allocation_date)
    return reference


def _maybe_settle_advance_against_invoice(
    payment: PaymentEntry,
    invoice: SalesInvoice | PurchaseInvoice,
    reference_type: str,
    amount: Decimal,
    allocation_date: date,
) -> None:
    """Netea el anticipo contra la cuenta por pagar/cobrar en GL.

    El neteo solo se genera cuando la compañía habilita la aplicación automática
    de anticipos. La referencia del subledger se conserva aunque la opción esté
    desactivada, pero el asiento de compensación no se publica en GL.
    """
    from cacao_accounting.contabilidad.default_accounts import get_company_default_accounts

    company = invoice.company
    defaults = get_company_default_accounts(company)
    if not defaults:
        return
    if not defaults.apply_advances_automatically:
        return
    if amount <= 0:
        return

    is_purchase = reference_type == "purchase_invoice"
    party_account_id = defaults.default_payable if is_purchase else defaults.default_receivable
    advance_account_id = defaults.supplier_advance_account_id if is_purchase else defaults.customer_advance_account_id
    if not party_account_id or not advance_account_id:
        return

    _post_advance_settlement_journal(
        company=company,
        is_purchase=is_purchase,
        party_account_id=party_account_id,
        advance_account_id=advance_account_id,
        payment=payment,
        invoice=invoice,
        amount=amount,
        allocation_date=allocation_date,
        exchange_gain_account_id=defaults.exchange_gain_account_id,
        exchange_loss_account_id=defaults.exchange_loss_account_id,
    )


def _post_advance_settlement_journal(
    *,
    company: str,
    is_purchase: bool,
    party_account_id: str,
    advance_account_id: str,
    payment: PaymentEntry,
    invoice: SalesInvoice | PurchaseInvoice,
    amount: Decimal,
    allocation_date: date,
    exchange_gain_account_id: str | None,
    exchange_loss_account_id: str | None,
) -> None:
    """Crea y publica el asiento de neteo de anticipo contra factura."""
    from cacao_accounting.contabilidad.posting import post_comprobante_contable
    from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier

    books = list(
        database.session.execute(
            select(Book).where(Book.entity == company, Book.status == "activo").order_by(Book.is_primary.desc(), Book.code)
        ).scalars()
    )
    user_id = getattr(payment, "created_by", None) or "system"
    journal = ComprobanteContable(
        entity=company,
        book=books[0].code if books else None,
        user_id=str(user_id),
        date=allocation_date,
        reference=payment.document_no or payment.id,
        memo="Neteo de anticipo contra factura",
        status="submitted",
        voucher_type="journal_entry",
        book_codes=json.dumps([book.code for book in books]) if books else None,
        transaction_currency=payment.transaction_currency or invoice.transaction_currency,
        base_currency=payment.base_currency or invoice.base_currency,
        exchange_rate=payment.exchange_rate or invoice.exchange_rate,
    )
    database.session.add(journal)
    database.session.flush()
    try:
        assign_document_identifier(
            document=journal,
            entity_type="journal_entry",
            posting_date_raw=allocation_date,
            naming_series_id=None,
            allow_closing=True,
        )
    except IdentifierConfigurationError:
        journal.document_no = f"{company}-ADV-{journal.id[-8:]}"
    _create_advance_settlement_lines(
        company=company,
        journal=journal,
        party_account_id=party_account_id,
        advance_account_id=advance_account_id,
        is_purchase=is_purchase,
        payment=payment,
        invoice=invoice,
        amount=amount,
        allocation_date=allocation_date,
        books=books,
        exchange_gain_account_id=exchange_gain_account_id,
        exchange_loss_account_id=exchange_loss_account_id,
    )
    post_comprobante_contable(journal, ledger_code=[book.code for book in books] or None)  # type: ignore[misc]
    journal.status = "submitted"
    database.session.add(journal)


def _document_total_for_allocation(document: Any) -> Decimal:
    """Resuelve el total nominal usado para prorratear el valor en libros."""
    return decimal_or_zero(
        getattr(document, "grand_total", None)
        or getattr(document, "paid_amount", None)
        or getattr(document, "received_amount", None)
    )


def _document_currency_for_settlement(document: Any, company: str) -> str | None:
    """Resuelve la moneda original, incluyendo columnas legacy de pagos."""
    currency = _document_transaction_currency(document)
    if currency:
        return str(currency)
    entity = database.session.execute(select(Entity).where(Entity.code == company)).scalars().first()
    return str(entity.currency) if entity and entity.currency else None


def _fallback_settlement_value(
    document: Any,
    company: str,
    book: Book,
    amount: Decimal,
    allocation_date: date,
) -> Decimal:
    """Convierte el monto cuando todavía no existen entradas GL de soporte."""
    source_currency = _document_currency_for_settlement(document, company)
    if not source_currency or not book.currency or source_currency == book.currency:
        return amount
    base_currency = getattr(document, "base_currency", None)
    exchange_rate = decimal_or_zero(getattr(document, "exchange_rate", None))
    if base_currency == book.currency and exchange_rate > 0:
        return amount * exchange_rate
    from cacao_accounting.contabilidad.posting import _lookup_exchange_rate

    return amount * _lookup_exchange_rate(source_currency, book.currency, allocation_date)  # type: ignore[misc]


def _allocated_carrying_value(
    document: Any,
    account_id: str,
    company: str,
    book: Book,
    amount: Decimal,
    allocation_date: date,
) -> Decimal:
    """Prorratea el saldo histórico real del documento en un libro."""
    net = database.session.execute(
        select(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).where(
            GLEntry.company == company,
            GLEntry.ledger_id == book.id,
            GLEntry.voucher_id == document.id,
            GLEntry.account_id == account_id,
            GLEntry.is_cancelled.is_(False),
            GLEntry.is_reversal.is_(False),
        )
    ).scalar_one()
    carrying_total = abs(decimal_or_zero(net))
    nominal_total = _document_total_for_allocation(document)
    if carrying_total > 0 and nominal_total > 0:
        return carrying_total * amount / nominal_total
    return _fallback_settlement_value(document, company, book, amount, allocation_date)


def _add_settlement_line(
    *,
    journal: ComprobanteContable,
    company: str,
    account_code: str,
    book: Book,
    value: Decimal,
    allocation_date: date,
    memo: str,
) -> None:
    """Agrega una línea funcional dirigida a un libro específico."""
    database.session.add(
        ComprobanteContableDetalle(
            entity=company,
            account=account_code,
            book=book.code,
            date=allocation_date,
            transaction="journal_entry",
            transaction_id=journal.id,
            value=value,
            value_default=value,
            currency_id=book.currency,
            memo=memo,
            voucher_type="journal_entry",
        )
    )


def _create_advance_settlement_lines(
    *,
    company: str,
    journal: ComprobanteContable,
    party_account_id: str,
    advance_account_id: str,
    is_purchase: bool,
    payment: PaymentEntry,
    invoice: SalesInvoice | PurchaseInvoice,
    amount: Decimal,
    allocation_date: date,
    books: list[Book],
    exchange_gain_account_id: str | None,
    exchange_loss_account_id: str | None,
) -> None:
    """Crea el neteo por libro y reconoce la diferencia cambiaria realizada."""
    accounts = {
        account.id: account
        for account in database.session.execute(
            select(Accounts).where(
                Accounts.entity == company,
                Accounts.id.in_(
                    [
                        party_account_id,
                        advance_account_id,
                        exchange_gain_account_id,
                        exchange_loss_account_id,
                    ]
                ),
            )
        ).scalars()
    }
    party_account = accounts.get(party_account_id)
    advance_account = accounts.get(advance_account_id)
    if not party_account or not advance_account:
        raise _document_flow_error("Las cuentas de anticipo y del tercero no son válidas para la compañía.")

    for book in books:
        party_value = _allocated_carrying_value(invoice, party_account_id, company, book, amount, allocation_date).quantize(
            Decimal("0.0001")
        )
        advance_value = _allocated_carrying_value(
            payment, advance_account_id, company, book, amount, allocation_date
        ).quantize(Decimal("0.0001"))
        debit_account, debit_value, credit_account, credit_value = (
            (party_account, party_value, advance_account, advance_value)
            if is_purchase
            else (advance_account, advance_value, party_account, party_value)
        )
        _add_settlement_line(
            journal=journal,
            company=company,
            account_code=debit_account.code,
            book=book,
            value=debit_value,
            allocation_date=allocation_date,
            memo="Neteo de anticipo",
        )
        _add_settlement_line(
            journal=journal,
            company=company,
            account_code=credit_account.code,
            book=book,
            value=-credit_value,
            allocation_date=allocation_date,
            memo="Neteo de anticipo",
        )
        difference = debit_value - credit_value
        if difference == 0:
            continue
        fx_account_id = exchange_gain_account_id if difference > 0 else exchange_loss_account_id
        fx_account = accounts.get(fx_account_id) if fx_account_id else None
        if not fx_account:
            raise _document_flow_error("Falta la cuenta de diferencia cambiaria para netear el anticipo.")
        _add_settlement_line(
            journal=journal,
            company=company,
            account_code=fx_account.code,
            book=book,
            value=-difference,
            allocation_date=allocation_date,
            memo="Diferencia cambiaria realizada en neteo de anticipo",
        )


def _create_payment_target(payload: dict[str, Any]) -> dict[str, Any]:
    """Crea un pago generico desde facturas fuente."""
    company = payload.get("company") or payload.get("company_id")
    from cacao_accounting.decorators import exige_acceso_compania

    # La autorización del documento origen no concede por sí sola permiso
    # para crear documentos del módulo bancario.
    exige_acceso_compania("cash", company, "crear", allow_unauthenticated=True)
    posting_date = payload.get("posting_date")
    bank_account = _load_payment_bank_account(payload)
    payment = _build_payment_target_payment(company, posting_date, payload)
    assign_payment_identifier(payment, bank_account, posting_date, payload)
    total = _apply_payment_target_lines(payment, company, payload)
    _update_payment_target_amounts(payment, total)
    database.session.commit()
    return _payment_target_result(payment)


def _load_payment_bank_account(payload: dict[str, Any]) -> Any:
    """Carga la cuenta bancaria opcional para un pago destino."""
    from cacao_accounting.database import BankAccount

    bank_account_id = payload.get("bank_account_id")
    if not bank_account_id:
        return None
    return database.session.get(BankAccount, bank_account_id)


def _build_payment_target_payment(company: str | None, posting_date: Any, payload: dict[str, Any]) -> PaymentEntry:
    """Construye el pago destino a partir del payload validado."""
    paid_from_account_id, paid_to_account_id = _resolve_payment_target_gl_accounts(company, payload)
    payment = PaymentEntry(
        company=company,
        docstatus=0,
        posting_date=posting_date,
        payment_type=str(payload.get("payment_type") or "receive"),
        party_type=payload.get("party_type"),
        party_id=payload.get("party_id"),
        bank_account_id=payload.get("bank_account_id"),
        currency=payload.get("currency"),
        transaction_currency=payload.get("currency"),
        base_currency=payload.get("base_currency"),
        exchange_rate=payload.get("exchange_rate"),
        paid_from_account_id=paid_from_account_id,
        paid_to_account_id=paid_to_account_id,
        remarks=payload.get("remarks"),
    )
    database.session.add(payment)
    database.session.flush()
    return payment


def _resolve_payment_target_gl_accounts(company: str | None, payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Resuelve y valida las cuentas GL de una transferencia interna destino.

    El flujo documental no pasa por el formulario bancario, por lo que debe
    aplicar aquí la misma garantía: cada pata usa la cuenta GL de su cuenta
    bancaria y ambas cuentas pertenecen a la compañía del pago.
    """
    if str(payload.get("payment_type") or "") != "internal_transfer":
        return None, None

    from cacao_accounting.database import BankAccount

    source_id = payload.get("bank_account_id")
    target_id = payload.get("target_bank_account_id")
    source_bank = database.session.get(BankAccount, source_id) if source_id else None
    target_bank = database.session.get(BankAccount, target_id) if target_id else None
    if not source_bank or not target_bank:
        raise _document_flow_error("La transferencia interna requiere cuentas bancarias válidas.", 409)
    if source_bank.id == target_bank.id:
        raise _document_flow_error("La cuenta bancaria de origen y destino deben ser distintas.", 409)
    if company and (source_bank.company != company or target_bank.company != company):
        raise _document_flow_error("Las cuentas bancarias deben pertenecer a la compañía del pago.", 409)

    source_account_id = payload.get("paid_from_account_id") or source_bank.gl_account_id
    target_account_id = payload.get("paid_to_account_id") or target_bank.gl_account_id
    if not source_account_id or not target_account_id:
        raise _document_flow_error("Ambas cuentas bancarias deben tener una cuenta contable configurada.", 409)
    if payload.get("paid_from_account_id") and payload["paid_from_account_id"] != source_bank.gl_account_id:
        raise _document_flow_error("La cuenta contable de origen no coincide con la cuenta bancaria.", 409)
    if payload.get("paid_to_account_id") and payload["paid_to_account_id"] != target_bank.gl_account_id:
        raise _document_flow_error("La cuenta contable de destino no coincide con la cuenta bancaria.", 409)
    return str(source_account_id), str(target_account_id)


def assign_payment_identifier(
    payment: PaymentEntry,
    bank_account: Any,
    posting_date: Any,
    payload: dict[str, Any],
) -> None:
    """Asigna el identificador fisico al pago destino."""
    from cacao_accounting.document_identifiers import assign_document_identifier

    assign_document_identifier(
        document=payment,
        entity_type="payment_entry",
        posting_date_raw=posting_date,
        naming_series_id=payload.get("naming_series_id") or (bank_account.default_naming_series_id if bank_account else None),
        external_counter_id=payload.get("external_counter_id")
        or (bank_account.default_external_counter_id if bank_account else None),
        external_number=payload.get("external_number"),
        external_context={"bank_account_id": payment.bank_account_id},
    )


def _apply_payment_target_lines(payment: PaymentEntry, company: str | None, payload: dict[str, Any]) -> Decimal:
    """Aplica las lineas de conciliacion al pago destino y devuelve el total."""
    total = Decimal("0")
    processed_reference_keys: set[tuple[str, str]] = set()
    for selected in payload.get("lines") or []:
        total += _apply_payment_target_line(payment, company, selected, processed_reference_keys)
    return total


def _apply_payment_target_line(
    payment: PaymentEntry,
    company: str | None,
    selected: dict[str, Any],
    processed_reference_keys: set[tuple[str, str]],
) -> Decimal:
    """Aplica una linea de conciliacion a un pago destino."""
    reference_type = normalize_doctype(str(selected.get("source_document_type") or selected.get("source_type") or ""))
    reference_id = str(selected.get("source_document_id") or selected.get("source_id") or "")
    reference_key = (reference_type, reference_id)
    if reference_key in processed_reference_keys:
        raise _document_flow_error("No se puede repetir la misma factura en un solo pago.", 409)
    processed_reference_keys.add(reference_key)

    model = _payment_reference_model(reference_type)
    invoice = database.session.get(model, reference_id, with_for_update=True)
    if not invoice:
        raise _document_flow_error("Factura origen no encontrada.", 404)
    if company and getattr(invoice, "company", None) and getattr(invoice, "company") != company:
        raise _document_flow_error("No se pueden mezclar companias incompatibles.", 409)
    if getattr(invoice, "docstatus", 0) != 1:
        raise _document_flow_error("La factura origen debe estar aprobada.", 409)
    expected_party_type, expected_party_id = _payment_reference_party(invoice, reference_type)
    if payment.party_type != expected_party_type or payment.party_id != expected_party_id:
        raise _document_flow_error("La factura origen no coincide con el tercero del pago.", 409)
    if not _payment_type_matches_source(payment.payment_type, reference_type):
        raise _document_flow_error("El tipo de pago no corresponde con la factura origen.", 409)

    allocated = decimal_or_zero(selected.get("qty") or selected.get("allocated_amount"))
    payment_currency = str(getattr(payment, "currency", None) or "")
    document_currency = _document_transaction_currency(invoice) or payment_currency
    if not payment_currency and document_currency:
        payment.currency = document_currency
        payment.transaction_currency = document_currency
        payment_currency = document_currency
    requested_rate = selected.get("payment_exchange_rate") or selected.get("exchange_rate")
    if payment_currency == document_currency:
        effective_rate = Decimal("1")
    else:
        effective_rate = decimal_or_zero(requested_rate)
        if effective_rate <= 0:
            raise _document_flow_error("Se requiere una tasa positiva entre la moneda del documento y la del pago.", 409)
    outstanding = compute_outstanding_amount(invoice)
    _validate_payment_target_allocation(allocated, outstanding)
    _persist_payment_target_allocation(payment, reference_type, reference_id, invoice, allocated, outstanding, effective_rate)
    return allocated


def _validate_payment_target_allocation(allocated: Decimal, outstanding: Decimal) -> None:
    """Valida la cantidad a aplicar contra una factura origen."""
    if allocated <= 0:
        raise _document_flow_error(_MSG_MONTO_MAYOR_CERO, 409)
    if allocated > outstanding:
        raise _document_flow_error("El monto aplicado excede el saldo pendiente.", 409)


def _persist_payment_target_allocation(
    payment: PaymentEntry,
    reference_type: str,
    reference_id: str,
    invoice: Any,
    allocated: Decimal,
    outstanding: Decimal,
    exchange_rate: Decimal = Decimal("1"),
) -> None:
    """Persist the payment reference and document relation for an allocation."""
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=reference_type,
        reference_id=reference_id,
        total_amount=getattr(invoice, "grand_total", None),
        outstanding_amount=outstanding,
        allocated_amount=allocated,
        payment_currency=getattr(payment, "currency", None),
        payment_amount=allocated * exchange_rate,
        payment_exchange_rate=exchange_rate,
        allocation_date=payment.posting_date,
        exchange_rate=getattr(payment, "exchange_rate", None),
        discount_amount=getattr(payment, "discount_amount", None),
        gain_loss_amount=getattr(payment, "gain_loss_amount", None),
        difference_amount=None,
    )
    database.session.add(reference)
    database.session.flush()
    from cacao_accounting.document_flow.service import create_document_relation

    create_document_relation(
        source_type=reference_type,
        source_id=reference_id,
        source_item_id=None,
        target_type="payment_entry",
        target_id=payment.id,
        target_item_id=reference.id,
        qty=Decimal("1"),
        uom=None,
        rate=allocated,
        amount=allocated,
    )
    setattr(invoice, "outstanding_amount", outstanding - allocated)
    setattr(invoice, "base_outstanding_amount", _base_amount(outstanding - allocated, invoice))
    if getattr(payment, "docstatus", 0) == 1:
        from cacao_accounting.contabilidad.arap_ledger_service import post_payment_application_ar_ap

        post_payment_application_ar_ap(
            payment,
            invoice,
            document_amount=allocated,
            payment_amount=allocated * exchange_rate,
            allocation_date=getattr(payment, "posting_date", None) or date.today(),
            reference_type=reference_type,
        )


def _update_payment_target_amounts(payment: PaymentEntry, total: Decimal) -> None:
    """Actualiza los importes del pago segun su direccion contable."""
    base_total = total * (decimal_or_zero(payment.exchange_rate) or Decimal("1"))
    if payment.payment_type == "pay":
        payment.paid_amount = total
        payment.base_paid_amount = base_total
    else:
        payment.received_amount = total
        payment.base_received_amount = base_total


def _payment_target_result(payment: PaymentEntry) -> dict[str, Any]:
    """Construye la respuesta final del pago destino."""
    return {"target_type": "payment_entry", "target_id": payment.id, "document_no": payment.document_no, "lines": []}
