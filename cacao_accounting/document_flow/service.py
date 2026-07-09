# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de flujo documental y parcialidades."""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from flask_login import current_user
from sqlalchemy import func, or_, select

from cacao_accounting.database import (
    AuditLog,
    BankAccount,
    Book,
    ComprobanteContable,
    ComprobanteContableDetalle,
    DocumentRelation,
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
from cacao_accounting.document_flow.registry import (
    ALLOWED_FLOWS,
    get_document_type,
    get_flow,
    is_allowed_flow,
    normalize_doctype,
)
from cacao_accounting.document_flow.repository import (
    consumed_qty_for_source,
    decimal_or_zero,
    get_document,
    get_document_company,
    get_document_item,
    get_document_items,
    get_item_parent_id,
    get_line_flow_state,
    recompute_line_flow_state,
    save_relation,
)
from cacao_accounting.document_identifiers import assign_document_identifier

_MSG_MONTO_MAYOR_CERO = "El monto aplicado debe ser mayor que cero."
_MSG_LINEA_ORIGEN = "Linea origen no encontrada."


def _document_exchange_rate(document: Any) -> Decimal:
    """Resuelve el tipo de cambio del documento, default 1 si no aplica."""
    rate = getattr(document, "exchange_rate", None)
    return decimal_or_zero(rate) if rate else Decimal("1")


def _base_amount(amount: Decimal, document: Any) -> Decimal:
    """Convierte un monto en moneda del documento a moneda base."""
    return amount * _document_exchange_rate(document)


@dataclass
class PaymentAllocationContext:
    """Contexto de asignación de pago para crear referencias y relaciones."""

    allocation_date: date
    allocated: Decimal
    discount: Decimal
    gain_loss: Decimal
    difference: Decimal
    outstanding: Decimal


class DocumentFlowError(ValueError):
    """Error controlado del motor de flujo documental."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Initialize DocumentFlowError with a message and HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


def _to_json_number(value: Any) -> float:
    """Convierte Decimal/None a float para JSON y templates."""
    return float(decimal_or_zero(value))


def _current_user_id() -> str | None:
    """Devuelve el usuario actual cuando existe un request autenticado."""
    try:
        if current_user and current_user.is_authenticated:
            return str(current_user.id)
    except RuntimeError:
        return None
    return None


def _audit(entity_type: str, entity_id: str, action: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> None:
    """Registra auditoria generica del flujo documental."""
    database.session.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_data=json.dumps(before, default=str) if before is not None else None,
            after_data=json.dumps(after, default=str) if after is not None else None,
            user_id=_current_user_id(),
        )
    )


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
        .where(
            DocumentRelation.source_type == document_type,
            DocumentRelation.source_id == document_id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
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
    if references:
        return references

    physical_reference_type = "purchase_invoice" if document_type.startswith("purchase_") else "sales_invoice"
    fallback_query = (
        select(PaymentReference)
        .outerjoin(
            DocumentRelation,
            (DocumentRelation.target_item_id == PaymentReference.id) & (DocumentRelation.target_type == "payment_entry"),
        )
        .where(
            PaymentReference.reference_type == physical_reference_type,
            PaymentReference.reference_id == document_id,
            or_(DocumentRelation.id.is_(None), DocumentRelation.status == "active"),
        )
    )
    if as_of_date is not None:
        fallback_query = fallback_query.where(
            or_(
                PaymentReference.allocation_date.is_(None),
                PaymentReference.allocation_date <= as_of_date,
            )
        )
    return list(database.session.execute(fallback_query).scalars().all())


def compute_outstanding_amount(document: Any, as_of_date: date | None = None) -> Decimal:
    """Calcula el saldo vivo de una factura usando las referencias de pago y notas de credito/debito."""
    if as_of_date is None:
        as_of_date = date.today()
    grand_total = decimal_or_zero(getattr(document, "grand_total", None))
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

    # Helper para sumar notas filtrando por tipo, estatus (posteadas) y fecha.
    def _sum_notes(target_types: tuple[str, ...]) -> Decimal:
        query = (
            select(func.sum(DocumentRelation.amount))
            .join(
                SalesInvoice,
                (DocumentRelation.target_id == SalesInvoice.id) & (DocumentRelation.target_type.startswith("sales_")),
            )
            .where(
                DocumentRelation.source_type == document_type,
                DocumentRelation.source_id == document_id,
                DocumentRelation.status == "active",
                DocumentRelation.target_type.in_(target_types),
                SalesInvoice.docstatus == 1,
                SalesInvoice.posting_date <= as_of_date,
            )
        )
        res = database.session.execute(query).scalar() or Decimal("0")

        # Tambien buscar en PurchaseInvoice si aplica
        query_purchase = (
            select(func.sum(DocumentRelation.amount))
            .join(
                PurchaseInvoice,
                (DocumentRelation.target_id == PurchaseInvoice.id) & (DocumentRelation.target_type.startswith("purchase_")),
            )
            .where(
                DocumentRelation.source_type == document_type,
                DocumentRelation.source_id == document_id,
                DocumentRelation.status == "active",
                DocumentRelation.target_type.in_(target_types),
                PurchaseInvoice.docstatus == 1,
                PurchaseInvoice.posting_date <= as_of_date,
            )
        )
        res_p = database.session.execute(query_purchase).scalar() or Decimal("0")

        return decimal_or_zero(res) + decimal_or_zero(res_p)

    res_credit = _sum_notes(("sales_credit_note", "purchase_credit_note"))
    res_debit = _sum_notes(("sales_debit_note", "purchase_debit_note"))

    return res_credit - res_debit


def _compute_cash_consumed_from_reference(
    reference_id, reference_type, flow_source_type, allocated_amount, discount_amount, gain_loss_amount, relation_status
):
    """Calcula el efectivo consumido por una referencia de pago."""
    source_type = normalize_doctype(str(flow_source_type or reference_type or ""))
    if source_type in {"purchase_order", "sales_order"}:
        return Decimal("0"), None
    cash_consumed = decimal_or_zero(allocated_amount) - decimal_or_zero(discount_amount) - decimal_or_zero(gain_loss_amount)
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
    reference_rows = database.session.execute(
        select(
            PaymentReference.id,
            PaymentReference.reference_type,
            PaymentReference.flow_source_type,
            PaymentReference.allocated_amount,
            PaymentReference.discount_amount,
            PaymentReference.gain_loss_amount,
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
        cash_consumed, relation_status = _compute_cash_consumed_from_reference(*row)
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


def _load_advance_invoice(invoice_id: str) -> tuple[SalesInvoice | PurchaseInvoice, str, str | None]:
    """Carga la factura de un anticipo y devuelve su tipo de referencia y tercero."""
    invoice: SalesInvoice | PurchaseInvoice | None = database.session.get(SalesInvoice, invoice_id)
    reference_type = "sales_invoice"
    party_id = getattr(invoice, "customer_id", None) if invoice else None
    if invoice is None:
        invoice = database.session.get(PurchaseInvoice, invoice_id)
        reference_type = "purchase_invoice"
        party_id = getattr(invoice, "supplier_id", None) if invoice else None
    if invoice is None:
        raise DocumentFlowError("La factura no existe.")
    return invoice, reference_type, party_id


def _validate_advance_allocation(
    payment: PaymentEntry,
    invoice: SalesInvoice | PurchaseInvoice,
    party_id: str | None,
    amount: Decimal,
    allocation_date: date,
) -> tuple[Decimal, Decimal]:
    """Valida la aplicación del anticipo y devuelve el outstanding antes/despues."""
    if payment.company != invoice.company:
        raise DocumentFlowError("El anticipo y la factura pertenecen a companias distintas.")
    if payment.party_id and party_id and payment.party_id != party_id:
        raise DocumentFlowError("El anticipo pertenece a otro tercero.")
    allocated_before = sum(
        (
            decimal_or_zero(reference.allocated_amount)
            for reference in database.session.execute(select(PaymentReference).filter_by(payment_id=payment.id)).scalars()
        ),
        Decimal("0"),
    )
    payment_total = decimal_or_zero(payment.paid_amount or payment.received_amount)
    outstanding = compute_outstanding_amount(invoice, as_of_date=allocation_date)
    if amount <= 0:
        raise DocumentFlowError(_MSG_MONTO_MAYOR_CERO)
    if amount > payment_total - allocated_before:
        raise DocumentFlowError("El monto excede el remanente del anticipo.")
    if amount > outstanding:
        raise DocumentFlowError("El monto excede el saldo pendiente de la factura.")
    return outstanding, outstanding - amount


def _payment_candidate_date(document: Any) -> date | None:
    """Resuelve la fecha representativa de un candidato de pago."""
    value = (
        getattr(document, "posting_date", None)
        or getattr(document, "bill_date", None)
        or getattr(document, "transaction_date", None)
        or getattr(document, "due_date", None)
    )
    return value if isinstance(value, date) else None


def _payment_candidate_party(document: Any, source_type: str) -> tuple[str, str | None]:
    """Resuelve tipo e id de tercero para un candidato de pago."""
    source_key = normalize_doctype(source_type)
    if source_key.startswith("purchase_"):
        return "supplier", getattr(document, "supplier_id", None)
    return "customer", getattr(document, "customer_id", None)


def _payment_candidate_physical_type(source_type: str) -> str:
    """Devuelve el tipo físico persistido para la referencia de pago."""
    source_key = normalize_doctype(source_type)
    if source_key in {"purchase_credit_note", "purchase_debit_note"}:
        return "purchase_invoice"
    if source_key in {"sales_credit_note", "sales_debit_note"}:
        return "sales_invoice"
    return source_key


def _payment_order_allocated(source_type: str, source_id: str) -> Decimal:
    """Calcula anticipos activos ya vinculados a una orden."""
    rows = database.session.execute(
        select(PaymentReference.allocated_amount)
        .join(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .where(
            DocumentRelation.source_type == source_type,
            DocumentRelation.source_id == source_id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
        )
    ).scalars()
    return sum((decimal_or_zero(amount) for amount in rows), Decimal("0"))


def _payment_candidate_outstanding(document: Any, source_type: str) -> Decimal:
    """Calcula el saldo disponible de un candidato para referencia de pago."""
    source_key = normalize_doctype(source_type)
    total = decimal_or_zero(getattr(document, "grand_total", None))
    if source_key in {"purchase_order", "sales_order"}:
        pending = total - _payment_order_allocated(source_key, str(getattr(document, "id", "")))
        return pending if pending > 0 else Decimal("0")
    return compute_outstanding_amount(document)


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
        raise DocumentFlowError("Debe indicar compania, tipo de tercero y tercero.", 400)
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
    rows: list[dict[str, Any]] = []
    for document in database.session.execute(query).scalars().all():
        outstanding = _payment_candidate_outstanding(document, source_type)
        if outstanding <= 0:
            continue
        rows.append(_build_candidate_row(document, source_type, party_type, party_id, company))
    return rows


def _build_candidate_row(document: Any, source_type: str, party_type: str, party_id: str, company: str) -> dict[str, Any]:
    document_date = _payment_candidate_date(document)
    physical_type = _payment_candidate_physical_type(source_type)
    return {
        "source_type": source_type,
        "reference_type": physical_type,
        "flow_source_type": source_type,
        "reference_id": document.id,
        "source_id": document.id,
        "document_no": getattr(document, "document_no", None) or document.id,
        "document_date": document_date.isoformat() if document_date else "",
        "party_type": party_type,
        "party_id": party_id,
        "company": company,
        "currency": getattr(document, "currency", None) or "",
        "grand_total": _to_json_number(getattr(document, "grand_total", None)),
        "pending_amount": _to_json_number(_payment_candidate_outstanding(document, source_type)),
        "source_label": source_type,
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
        raise DocumentFlowError("Debe indicar compania y tipo de tercero.", 400)

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

    rows: list[dict[str, Any]] = []
    for payment in database.session.execute(payment_query.order_by(PaymentEntry.posting_date, PaymentEntry.id)).scalars():
        unallocated = compute_payment_unallocated_amount(payment)
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
    """Resuelve los doctypes origen válidos para el tipo de tercero."""
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


def _payment_reference_model(reference_type: str) -> type[PurchaseInvoice] | type[SalesInvoice]:
    """Devuelve el modelo fisico de una referencia AR/AP."""
    source_key = normalize_doctype(reference_type)
    if source_key.startswith("purchase_"):
        return PurchaseInvoice
    if source_key.startswith("sales_"):
        return SalesInvoice
    raise DocumentFlowError("Tipo de referencia invalido.", 400)


def _payment_reference_party(document: Any, source_type: str) -> tuple[str, str | None]:
    """Resuelve el tercero esperado para una referencia AR/AP."""
    return _payment_candidate_party(document, source_type)


def _payment_type_matches_source(payment_type: str, source_type: str) -> bool:
    """Valida que el tipo de pago sea compatible con factura o nota."""
    expected = {
        "purchase_invoice": "pay",
        "purchase_debit_note": "pay",
        "purchase_credit_note": "receive",
        "sales_invoice": "receive",
        "sales_debit_note": "receive",
        "sales_credit_note": "pay",
    }.get(normalize_doctype(source_type))
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
        raise DocumentFlowError("La conciliacion requiere al menos una linea.")
    if not company or party_type not in {"supplier", "customer"} or not party_id:
        raise DocumentFlowError("Debe indicar compania, tipo de tercero y tercero.", 400)

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
    payment_id = str(raw_line.get("payment_id") or "")
    reference_id = str(raw_line.get("reference_id") or "")
    flow_source_type = normalize_doctype(str(raw_line.get("flow_source_type") or raw_line.get("reference_type") or ""))
    reference_type = normalize_doctype(
        str(raw_line.get("reference_type") or _payment_candidate_physical_type(flow_source_type))
    )
    allocated = decimal_or_zero(raw_line.get("allocated_amount"))
    discount = decimal_or_zero(raw_line.get("discount_amount"))
    gain_loss = decimal_or_zero(raw_line.get("gain_loss_amount"))
    difference = decimal_or_zero(raw_line.get("difference_amount") or gain_loss)

    if allocated <= 0:
        raise DocumentFlowError(_MSG_MONTO_MAYOR_CERO, 409)
    key = (payment_id, flow_source_type, reference_id)
    if key in processed:
        raise DocumentFlowError("No se puede aplicar la misma factura dos veces en un pago.", 409)
    processed.add(key)

    # CAS-06: FOR UPDATE para prevenir sobre-aplicación concurrente
    payment = database.session.query(PaymentEntry).with_for_update().get(payment_id)
    _validate_payment(payment, company, party_type, party_id, flow_source_type)
    assert payment is not None

    if payment_id not in payment_remaining:
        payment_remaining[payment_id] = compute_payment_unallocated_amount(payment)
    consumed = _cash_consumed(allocated, discount, gain_loss)
    if consumed > payment_remaining[payment_id] + Decimal("0.01"):
        raise DocumentFlowError("El monto aplicado excede el saldo disponible del pago.", 409)

    document = _get_reference_document(flow_source_type, reference_id, company, party_type, party_id)
    _validate_payment_currency_match(payment, document)
    _check_duplicate_application(payment.id, flow_source_type, reference_id)
    outstanding = _validate_and_get_outstanding(document, allocated, allocation_date)
    allocation_ctx = PaymentAllocationContext(
        allocation_date=allocation_date,
        allocated=allocated,
        discount=discount,
        gain_loss=gain_loss,
        difference=difference,
        outstanding=outstanding,
    )

    _create_payment_reference_and_relation(
        raw_line,
        payment,
        document,
        flow_source_type,
        reference_type,
        reference_id,
        allocation_ctx,
    )
    _update_document_outstanding(document, outstanding, allocated)
    _create_reconciliation_item(
        reconciliation_id,
        flow_source_type,
        reference_id,
        payment.id,
        allocated,
        allocation_date,
    )
    payment_remaining[payment_id] -= consumed


def _validate_payment(payment: Any, company: str, party_type: str, party_id: str, flow_source_type: str) -> None:
    if not payment or payment.docstatus != 1:
        raise DocumentFlowError("El pago debe existir y estar aprobado.", 404)
    if payment.company != company or payment.party_type != party_type or payment.party_id != party_id:
        raise DocumentFlowError("El pago no coincide con la compania o tercero de la conciliacion.", 409)
    if not _payment_type_matches_source(payment.payment_type, flow_source_type):
        raise DocumentFlowError("El tipo de pago no corresponde con el documento referenciado.", 409)


def _get_reference_document(flow_source_type: str, reference_id: str, company: str, party_type: str, party_id: str) -> Any:
    model = _payment_reference_model(flow_source_type)
    document = database.session.query(model).with_for_update().get(reference_id)
    if not document or getattr(document, "docstatus", 0) != 1:
        raise DocumentFlowError("El documento referenciado debe existir y estar aprobado.", 404)
    if getattr(document, "company", None) != company:
        raise DocumentFlowError("El documento referenciado no pertenece a la misma compania.", 409)
    expected_party_type, expected_party_id = _payment_reference_party(document, flow_source_type)
    if expected_party_type != party_type or expected_party_id != party_id:
        raise DocumentFlowError("El documento referenciado no coincide con el tercero.", 409)
    return document


def _validate_payment_currency_match(payment: Any, document: Any) -> None:
    """CAS-03: Valida que la moneda del pago coincida con la moneda del documento referenciado.

    Evita inconsistencias contables al aplicar pagos a documentos con moneda diferente.
    """
    payment_currency = getattr(payment, "currency", None)
    document_currency = getattr(document, "transaction_currency", None) or getattr(document, "currency", None)
    if payment_currency and document_currency and payment_currency != document_currency:
        raise DocumentFlowError(
            "La moneda del pago ({0}) no coincide con la moneda del documento referenciado ({1}). "
            "No se permiten aplicaciones cruzadas de moneda.".format(payment_currency, document_currency),
            409,
        )


def _check_duplicate_application(payment_id: str, flow_source_type: str, reference_id: str) -> None:
    existing = database.session.execute(
        select(PaymentReference.id)
        .join(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .where(
            PaymentReference.payment_id == payment_id,
            DocumentRelation.source_type == flow_source_type,
            DocumentRelation.source_id == reference_id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        raise DocumentFlowError("El documento ya esta aplicado a este pago.", 409)


def _validate_and_get_outstanding(document: Any, allocated: Decimal, allocation_date: date) -> Decimal:
    outstanding = compute_outstanding_amount(document, as_of_date=allocation_date)
    if outstanding <= 0:
        raise DocumentFlowError("El documento referenciado no tiene saldo pendiente.", 409)
    if allocated > outstanding + Decimal("0.01"):
        raise DocumentFlowError("El monto aplicado excede el saldo pendiente del documento.", 409)
    return outstanding


def _create_payment_reference_and_relation(
    raw_line: dict[str, Any],
    payment: Any,
    document: Any,
    flow_source_type: str,
    reference_type: str,
    reference_id: str,
    allocation_ctx: PaymentAllocationContext,
) -> None:
    physical_type = _payment_candidate_physical_type(flow_source_type)
    outstanding_after = allocation_ctx.outstanding - allocation_ctx.allocated
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=physical_type or reference_type,
        flow_source_type=flow_source_type,
        reference_id=reference_id,
        reference_document_no=getattr(document, "document_no", None) or reference_id,
        reference_date=_payment_candidate_date(document),
        party_type=payment.party_type,
        party_id=payment.party_id,
        company=payment.company,
        currency=getattr(document, "currency", None) or getattr(payment, "currency", None),
        total_amount=getattr(document, "grand_total", None),
        outstanding_amount=allocation_ctx.outstanding,
        outstanding_amount_after=outstanding_after,
        allocated_amount=allocation_ctx.allocated,
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
    create_document_relation(
        source_type=flow_source_type,
        source_id=reference_id,
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
    reference_id: str,
    payment_id: str,
    allocated: Decimal,
    allocation_date: date,
) -> None:
    database.session.add(
        ReconciliationItem(
            reconciliation_id=reconciliation_id,
            reference_type=flow_source_type,
            reference_id=reference_id,
            amount=allocated,
            allocated_amount=allocated,
            reconciliation_date=allocation_date,
            source_type="payment_entry",
            source_id=payment_id,
            target_type=flow_source_type,
            target_id=reference_id,
        )
    )


def refresh_outstanding_amount_cache(document: Any, as_of_date: date | None = None) -> Decimal:
    """Sincroniza el campo cacheado `outstanding_amount` con el valor calculado."""
    outstanding = compute_outstanding_amount(document, as_of_date=as_of_date)
    if hasattr(document, "outstanding_amount"):
        document.outstanding_amount = outstanding
    if hasattr(document, "base_outstanding_amount"):
        document.base_outstanding_amount = _base_amount(outstanding, document)
    return outstanding


def apply_advance_to_invoice(
    payment_entry_id: str,
    invoice_id: str,
    amount: Decimal,
    allocation_date: date,
) -> PaymentReference:
    """Aplica un anticipo existente contra una factura AR/AP."""
    payment = database.session.get(PaymentEntry, payment_entry_id)
    if not payment:
        raise DocumentFlowError("El pago/anticipo no existe.")
    invoice, reference_type, party_id = _load_advance_invoice(invoice_id)
    outstanding, outstanding_after = _validate_advance_allocation(payment, invoice, party_id, amount, allocation_date)
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=reference_type,
        reference_id=invoice.id,
        reference_document_no=getattr(invoice, "document_no", None) or invoice.id,
        reference_date=getattr(invoice, "posting_date", None),
        party_type="Customer" if reference_type == "sales_invoice" else "Supplier",
        party_id=party_id,
        company=invoice.company,
        currency=getattr(invoice, "currency", None) or getattr(payment, "currency", None),
        total_amount=getattr(invoice, "grand_total", None),
        outstanding_amount=outstanding,
        outstanding_amount_after=outstanding_after,
        allocated_amount=amount,
        allocation_date=allocation_date,
    )
    database.session.add(reference)
    database.session.flush()
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
    refresh_outstanding_amount_cache(invoice, as_of_date=allocation_date)
    _maybe_settle_advance_against_invoice(payment, invoice, reference_type, amount, allocation_date)
    return reference


def _maybe_settle_advance_against_invoice(
    payment: PaymentEntry,
    invoice: SalesInvoice | PurchaseInvoice,
    reference_type: str,
    amount: Decimal,
    allocation_date: date,
) -> None:
    """S2P-07: netea el anticipo contra la cuenta por pagar/cobrar.

    Si la configuracion de la compania tiene ``apply_advances_automatically``
    activo, genera un comprobante contable de neteo:
    compras -> Dr Cuenta por Pagar / Cr Cuenta de Anticipo a Proveedores;
    ventas  -> Dr Cuenta de Anticipo a Clientes / Cr Cuenta por Cobrar.
    """
    from cacao_accounting.contabilidad.default_accounts import get_company_default_accounts
    from cacao_accounting.contabilidad.posting import post_comprobante_contable
    from cacao_accounting.document_identifiers import assign_document_identifier

    company = invoice.company
    defaults = get_company_default_accounts(company)
    if not defaults or not defaults.apply_advances_automatically:
        return
    if amount <= 0:
        return

    is_purchase = reference_type == "purchase_invoice"
    party_account_id = defaults.default_payable if is_purchase else defaults.default_receivable
    advance_account_id = defaults.supplier_advance_account_id if is_purchase else defaults.customer_advance_account_id
    if not party_account_id or not advance_account_id:
        return

    book = (
        database.session.execute(select(Book).filter_by(entity=company).order_by(Book.is_primary.desc(), Book.code))
        .scalars()
        .first()
    )
    user_id = getattr(payment, "created_by", None) or "system"
    journal = ComprobanteContable(
        entity=company,
        book=book.code if book else None,
        user_id=str(user_id),
        date=allocation_date,
        reference=payment.document_no or payment.id,
        memo="Neteo de anticipo contra factura",
        status="submitted",
        voucher_type="journal_entry",
        book_codes=book.code if book else None,
        transaction_currency=None,
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
    except Exception:
        journal.document_no = f"{company}-ADV-{journal.id[-8:]}"
    if is_purchase:
        debit_account, credit_account = party_account_id, advance_account_id
    else:
        debit_account, credit_account = advance_account_id, party_account_id
    from cacao_accounting.database import Accounts as _Accounts

    _debit_code = database.session.execute(select(_Accounts).filter_by(id=debit_account)).scalars().first()
    _credit_code = database.session.execute(select(_Accounts).filter_by(id=credit_account)).scalars().first()
    debit_code = _debit_code.code if _debit_code else debit_account
    credit_code = _credit_code.code if _credit_code else credit_account
    database.session.add(
        ComprobanteContableDetalle(
            entity=company,
            account=debit_code,
            book=book.code if book else None,
            date=allocation_date,
            transaction="journal_entry",
            transaction_id=journal.id,
            value=amount,
            value_default=amount,
            memo="Neteo de anticipo",
            voucher_type="journal_entry",
        )
    )
    database.session.add(
        ComprobanteContableDetalle(
            entity=company,
            account=credit_code,
            book=book.code if book else None,
            date=allocation_date,
            transaction="journal_entry",
            transaction_id=journal.id,
            value=-amount,
            value_default=-amount,
            memo="Neteo de anticipo",
            voucher_type="journal_entry",
        )
    )
    post_comprobante_contable(journal)
    journal.status = "submitted"
    database.session.add(journal)


def _state_quantities(
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str | None,
) -> tuple[Decimal, Decimal]:
    """Obtiene cantidades canceladas/cerradas para una linea si existe estado cacheado."""
    if not target_type:
        return Decimal("0"), Decimal("0")
    state = get_line_flow_state(source_type, source_id, source_item_id, target_type)
    if not state:
        return Decimal("0"), Decimal("0")
    return decimal_or_zero(state.cancelled_qty), decimal_or_zero(state.closed_qty)


def _line_payload(source_type: str, source_id: str, item: Any, target_type: str | None = None) -> dict[str, Any]:
    """Construye la respuesta estandar para una linea origen."""
    qty = decimal_or_zero(getattr(item, "qty", 0))
    consumed = consumed_qty_for_source(source_type, source_id, item.id, target_type)
    cancelled, closed = _state_quantities(source_type, source_id, item.id, target_type)
    pending = qty - consumed - cancelled - closed
    if pending < Decimal("0"):
        pending = Decimal("0")
    rate = decimal_or_zero(getattr(item, "rate", 0))
    amount = pending * rate
    state = get_line_flow_state(source_type, source_id, item.id, target_type) if target_type else None
    return {
        "source_type": normalize_doctype(source_type),
        "source_id": source_id,
        "source_item_id": item.id,
        "item_code": getattr(item, "item_code", ""),
        "item_name": getattr(item, "item_name", "") or "",
        "source_qty": _to_json_number(qty),
        "consumed_qty": _to_json_number(consumed),
        "processed_qty": _to_json_number(consumed),
        "cancelled_qty": _to_json_number(cancelled),
        "closed_qty": _to_json_number(closed),
        "pending_qty": _to_json_number(pending),
        "line_status": state.line_status if state else "open",
        "qty": _to_json_number(pending),
        "uom": getattr(item, "uom", "") or "",
        "rate": _to_json_number(rate),
        "amount": _to_json_number(amount),
    }


def get_source_items(source_type: str, source_id: str, target_type: str | None = None) -> list[dict[str, Any]]:
    """Devuelve lineas disponibles desde un documento origen."""
    source_key = normalize_doctype(source_type)
    target_key = normalize_doctype(target_type) if target_type else None
    if target_key and not is_allowed_flow(source_key, target_key):
        raise DocumentFlowError(f"Relacion no permitida: {source_key} -> {target_key}", 400)
    source = get_document(source_key, source_id)
    if not source:
        raise DocumentFlowError("Documento origen no encontrado.", 404)
    if getattr(source, "docstatus", 0) != 1:
        return []
    source_items = get_document_items(source_key, source_id)
    return [
        payload
        for payload in (_line_payload(source_key, source_id, item, target_key) for item in source_items)
        if decimal_or_zero(payload["pending_qty"]) > 0
    ]


def get_document_flow_items(target_type: str, source_values: list[str]) -> list[dict[str, Any]]:
    """Devuelve lineas pendientes para uno o mas documentos origen."""
    target_key = normalize_doctype(target_type)
    items: list[dict[str, Any]] = []
    for value in source_values:
        if ":" not in value:
            raise DocumentFlowError("El parametro source debe usar formato doctype:id.", 400)
        source_type, source_id = value.split(":", 1)
        items.extend(get_source_items(source_type, source_id, target_key))
    return items


def pending_qty(source_type: str, source_id: str, source_item_id: str | None, target_type: str) -> Decimal:
    """Calcula la cantidad pendiente para una linea origen hacia un target."""
    source_item = get_document_item(source_type, source_item_id)
    if not source_item:
        raise DocumentFlowError(_MSG_LINEA_ORIGEN, 404)
    qty = decimal_or_zero(getattr(source_item, "qty", 0))
    consumed = consumed_qty_for_source(source_type, source_id, source_item_id, target_type)
    cancelled, closed = _state_quantities(source_type, source_id, source_item_id, target_type)
    pending = qty - consumed - cancelled - closed
    return pending if pending > 0 else Decimal("0")


def _assert_same_company(source_type: str, source_id: str, target_type: str, target_id: str) -> None:
    """Valida aislamiento por compania."""
    source_company = get_document_company(source_type, source_id)
    target_company = get_document_company(target_type, target_id)
    if source_company and target_company and source_company != target_company:
        raise DocumentFlowError("El documento origen y destino pertenecen a companias distintas.", 409)


def _update_source_cache(source_type: str, source_id: str, source_item_id: str | None, target_type: str) -> None:
    """Actualiza campos cache de consumo cuando existen en la linea origen."""
    source_key = normalize_doctype(source_type)
    target_key = normalize_doctype(target_type)
    source_item = get_document_item(source_key, source_item_id)
    if not source_item:
        return
    consumed = consumed_qty_for_source(source_key, source_id, source_item_id, target_key)
    if source_key == "purchase_order" and target_key == "purchase_receipt":
        source_item.received_qty = consumed
    elif source_key == "purchase_order" and target_key == "purchase_invoice":
        source_item.billed_qty = consumed
    elif source_key == "sales_order" and target_key == "delivery_note":
        source_item.delivered_qty = consumed
    elif source_key == "sales_order" and target_key == "sales_invoice":
        source_item.billed_qty = consumed

    # Trazabilidad transitiva: Si el source_key es un documento intermedio,
    # debemos actualizar tambien el documento padre original si existe.
    _update_transitive_source_cache(source_key, source_id, source_item_id, target_key)


def _update_transitive_source_cache(source_key: str, source_id: str, source_item_id: str | None, target_key: str) -> None:
    """Propaga la actualizacion de cache a documentos padre (p.ej de Nota Entrega a Orden de Venta)."""
    if source_key == "delivery_note" and target_key == "sales_invoice":
        _propagate_billed_qty(source_key, source_id, source_item_id, "sales_order")
    elif source_key == "purchase_receipt" and target_key == "purchase_invoice":
        _propagate_billed_qty(source_key, source_id, source_item_id, "purchase_order")


def _propagate_billed_qty(source_type: str, source_id: str, source_item_id: str | None, parent_type: str) -> None:
    """Suma facturacion de documentos intermedios y la asigna al campo billed_qty del padre."""
    relations = database.session.execute(
        select(DocumentRelation).where(
            DocumentRelation.target_type == source_type,
            DocumentRelation.target_id == source_id,
            DocumentRelation.target_item_id == source_item_id,
            DocumentRelation.source_type == parent_type,
            DocumentRelation.status == "active",
        )
    ).scalars()
    for rel in relations:
        if not rel.source_item_id:
            continue
        parent_item = get_document_item(parent_type, rel.source_item_id)
        if parent_item and hasattr(parent_item, "billed_qty"):
            # El billed_qty del padre es la suma de lo facturado desde el padre directamente
            # MAS lo facturado desde sus documentos derivados (recepciones/entregas).
            invoice_type = "sales_invoice" if parent_type == "sales_order" else "purchase_invoice"
            direct_billed = consumed_qty_for_source(parent_type, rel.source_id, rel.source_item_id, invoice_type)

            # Sumar lo facturado a traves de intermediarios (Nota Entrega / Recepcion)
            intermediary_type = "delivery_note" if parent_type == "sales_order" else "purchase_receipt"

            indirect_billed = Decimal("0")
            # Buscar todos los intermediarios vinculados a este item padre
            intermediaries = database.session.execute(
                select(DocumentRelation).where(
                    DocumentRelation.source_type == parent_type,
                    DocumentRelation.source_id == rel.source_id,
                    DocumentRelation.source_item_id == rel.source_item_id,
                    DocumentRelation.target_type == intermediary_type,
                    DocumentRelation.status == "active",
                )
            ).scalars()

            for inter_rel in intermediaries:
                indirect_billed += consumed_qty_for_source(
                    intermediary_type, inter_rel.target_id, inter_rel.target_item_id, invoice_type
                )

            parent_item.billed_qty = direct_billed + indirect_billed


def refresh_source_caches_for_target(target_type: str, target_id: str) -> None:
    """Recalcula caches de origen afectados por un documento destino."""
    target_key = normalize_doctype(target_type)
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(target_type=target_key, target_id=target_id)
    ).scalars()
    for relation in relations:
        _update_source_cache(relation.source_type, relation.source_id, relation.source_item_id, target_key)


def create_document_relation(
    *,
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str,
    target_id: str,
    target_item_id: str | None,
    qty: Any,
    uom: str | None = None,
    rate: Any = None,
    amount: Any = None,
) -> DocumentRelation:
    """Crea una relacion entre lineas validando parcialidad y compania."""
    source_key = normalize_doctype(source_type)
    target_key = normalize_doctype(target_type)
    if not is_allowed_flow(source_key, target_key):
        raise DocumentFlowError(f"Relacion no permitida: {source_key} -> {target_key}", 400)

    source_spec = get_document_type(source_key)
    source_item = get_document_item(source_key, source_item_id) if source_item_id else None
    target_item = get_document_item(target_key, target_item_id) if target_item_id else None

    if source_item_id and not source_item:
        raise DocumentFlowError(_MSG_LINEA_ORIGEN, 404)
    if target_item_id and not target_item:
        raise DocumentFlowError("Linea destino no encontrada.", 404)

    if source_item:
        real_source_id = get_item_parent_id(source_spec, source_item)
        if real_source_id != source_id:
            raise DocumentFlowError("La linea origen no pertenece al documento indicado.", 409)

    _assert_same_company(source_key, source_id, target_key, target_id)

    qty_decimal = decimal_or_zero(qty)
    if qty_decimal <= 0:
        raise DocumentFlowError("La cantidad relacionada debe ser mayor que cero.", 409)

    if source_item_id:
        available = pending_qty(source_key, source_id, source_item_id, target_key)
        if qty_decimal > available:
            raise DocumentFlowError("La cantidad relacionada excede el pendiente disponible.", 409)

    flow = get_flow(source_key, target_key)
    relation = DocumentRelation(
        source_type=source_key,
        source_id=source_id,
        source_item_id=source_item_id,
        target_type=target_key,
        target_id=target_id,
        target_item_id=target_item_id,
        company=get_document_company(source_key, source_id) or get_document_company(target_key, target_id),
        qty=qty_decimal,
        uom=uom or getattr(target_item, "uom", None),
        rate=decimal_or_zero(rate),
        amount=decimal_or_zero(amount),
        relation_type=flow.relation_type,
        status="active",
    )
    save_relation(relation)
    if source_item_id:
        recompute_line_flow_state(source_key, source_id, source_item_id, target_key, relation.company)
        _update_source_cache(source_key, source_id, source_item_id, target_key)
    return relation


def revert_relations_for_target(target_type: str, target_id: str, reason: str = "target_cancelled") -> int:
    """Revierte relaciones activas de un documento destino y libera saldos."""
    target_key = normalize_doctype(target_type)
    relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(target_type=target_key, target_id=target_id, status="active")
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for relation in relations:
        before = {"status": relation.status, "qty": str(relation.qty)}
        relation.status = "reverted"
        relation.reversed_at = now
        relation.reversed_by = _current_user_id()
        relation.reversal_reason = reason
        if relation.source_item_id:
            # Solo las relaciones con línea fuente requieren recomputar estados
            # y caches. Las relaciones header-only (por ejemplo factura -> pago)
            # se revierten únicamente a nivel de trazabilidad.
            recompute_line_flow_state(
                relation.source_type,
                relation.source_id,
                relation.source_item_id,
                relation.target_type,
                relation.company,
            )
            _update_source_cache(relation.source_type, relation.source_id, relation.source_item_id, relation.target_type)
        _audit(
            "document_relation",
            relation.id,
            "revert",
            before,
            {"status": relation.status, "reason": reason},
        )
    return len(relations)


def close_line_balance(
    *,
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str,
    qty: Any | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Cierra manualmente saldo pendiente de una linea fuente."""
    source_key = normalize_doctype(source_type)
    target_key = normalize_doctype(target_type)
    if not reason.strip():
        raise DocumentFlowError("Debe indicar el motivo del cierre de saldo.", 409)
    available = pending_qty(source_key, source_id, source_item_id, target_key)
    close_qty = available if qty in (None, "") else decimal_or_zero(qty)
    if close_qty <= 0:
        raise DocumentFlowError("La cantidad a cerrar debe ser mayor que cero.", 409)
    if close_qty > available:
        raise DocumentFlowError("La cantidad a cerrar excede el pendiente disponible.", 409)
    company = get_document_company(source_key, source_id)
    state = recompute_line_flow_state(source_key, source_id, source_item_id, target_key, company)
    before = {
        "closed_qty": str(state.closed_qty),
        "pending_qty": str(state.pending_qty),
        "line_status": state.line_status,
    }
    state.closed_qty = decimal_or_zero(state.closed_qty) + close_qty
    state.closed_at = datetime.now(UTC)
    state.closed_by = _current_user_id()
    state.close_reason = reason.strip()
    state = recompute_line_flow_state(source_key, source_id, source_item_id, target_key, company)
    _audit(
        "document_line_flow_state",
        state.id,
        "close",
        before,
        {"closed_qty": str(state.closed_qty), "pending_qty": str(state.pending_qty), "reason": reason.strip()},
    )
    return _state_payload(state)


def close_document_balances(
    *,
    source_type: str,
    source_id: str,
    target_type: str,
    reason: str,
) -> list[dict[str, Any]]:
    """Cierra todo el saldo pendiente de un documento fuente hacia un target."""
    closed: list[dict[str, Any]] = []
    for item in get_document_items(source_type, source_id):
        available = pending_qty(source_type, source_id, item.id, target_type)
        if available > 0:
            closed.append(
                close_line_balance(
                    source_type=source_type,
                    source_id=source_id,
                    source_item_id=item.id,
                    target_type=target_type,
                    qty=available,
                    reason=reason,
                )
            )
    return closed


def _state_payload(state: Any) -> dict[str, Any]:
    """Serializa estado de linea para API."""
    return {
        "source_type": state.source_type,
        "source_id": state.source_id,
        "source_item_id": state.source_item_id,
        "target_type": state.target_type,
        "source_qty": _to_json_number(state.source_qty),
        "processed_qty": _to_json_number(state.processed_qty),
        "cancelled_qty": _to_json_number(state.cancelled_qty),
        "closed_qty": _to_json_number(state.closed_qty),
        "pending_qty": _to_json_number(state.pending_qty),
        "line_status": state.line_status,
    }


def _build_source_query(spec: Any, company: str | None, party_id: str | None, party_type: str | None) -> Any:
    """Construye la consulta base para documentos fuente."""
    query = database.select(spec.header_model).filter_by(docstatus=1)
    if company and hasattr(spec.header_model, "company"):
        query = query.filter_by(company=company)
    if party_id:
        if hasattr(spec.header_model, "customer_id") and party_type == "customer":
            query = query.filter_by(customer_id=party_id)
        elif hasattr(spec.header_model, "supplier_id") and party_type == "supplier":
            query = query.filter_by(supplier_id=party_id)
    return query


def _collect_source_document_row(
    source_key: str,
    document: Any,
    target_key: str,
) -> dict[str, Any] | None:
    """Recolecta informacion de un documento fuente si tiene lineas pendientes."""
    items = get_source_items(source_key, document.id, target_key)
    if not items:
        return None
    return {
        "source_type": source_key,
        "source_id": document.id,
        "document_no": getattr(document, "document_no", None) or document.id,
        "company": getattr(document, "company", None),
        "posting_date": str(getattr(document, "posting_date", "") or ""),
        "pending_lines": len(items),
    }


def list_source_documents(
    target_type: str,
    company: str | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
) -> list[dict[str, Any]]:
    """Lista documentos fuente aprobados con saldo para un destino."""
    target_key = normalize_doctype(target_type)
    sources = sorted(source for source, _target in ALLOWED_FLOWS if _target == target_key)
    rows: list[dict[str, Any]] = []
    for source_key in sources:
        spec = get_document_type(source_key)
        query = _build_source_query(spec, company, party_id, party_type)
        for document in database.session.execute(query).scalars().all():
            row = _collect_source_document_row(source_key, document, target_key)
            if row:
                rows.append(row)
    return rows


def get_pending_lines(
    *,
    source_document_type: str,
    source_document_ids: list[str],
    target_document_type: str,
    company: str | None = None,
) -> list[dict[str, Any]]:
    """Obtiene lineas pendientes desde uno o varios documentos fuente."""
    lines: list[dict[str, Any]] = []
    for source_id in source_document_ids:
        source_company = get_document_company(source_document_type, source_id)
        if company and source_company and source_company != company:
            raise DocumentFlowError("No se pueden mezclar companias incompatibles.", 409)
        document = get_document(source_document_type, source_id)
        document_no = getattr(document, "document_no", None) or source_id
        for line in get_source_items(source_document_type, source_id, target_document_type):
            line["source_document_no"] = document_no
            lines.append(line)
    return lines


def _create_target_header(
    target_spec: Any,
    target_type: str,
    company: str,
    posting_date: Any,
    payload: dict[str, Any],
) -> Any:
    """Crea y persiste el header del documento destino."""
    header_values = {
        "company": company,
        "posting_date": posting_date,
        "docstatus": 0,
        "purpose": payload.get("purpose") or "receipt",
        "supplier_id": payload.get("supplier_id"),
        "supplier_name": payload.get("supplier_name"),
        "customer_id": payload.get("customer_id"),
        "customer_name": payload.get("customer_name"),
        "remarks": payload.get("remarks"),
    }
    target = target_spec.header_model(
        **{
            field: value
            for field, value in header_values.items()
            if value is not None and hasattr(target_spec.header_model, field)
        }
    )
    database.session.add(target)
    database.session.flush()
    assign_document_identifier(
        document=target,
        entity_type=target_type,
        posting_date_raw=posting_date,
        naming_series_id=payload.get("naming_series_id"),
        external_counter_id=payload.get("external_counter_id"),
        external_number=payload.get("external_number"),
    )
    return target


def _process_target_line(
    index: int,
    selected: dict[str, Any],
    target: Any,
    target_spec: Any,
    target_type: str,
) -> dict[str, str]:
    """Procesa una linea individual del documento destino."""
    source_type = normalize_doctype(str(selected.get("source_document_type") or selected.get("source_type") or ""))
    source_id = str(selected.get("source_document_id") or selected.get("source_id") or "")
    source_item_id = str(selected.get("source_row_id") or selected.get("source_item_id") or "")
    source_item = get_document_item(source_type, source_item_id)
    if not source_item:
        raise DocumentFlowError(_MSG_LINEA_ORIGEN, 404)
    qty = decimal_or_zero(selected.get("qty"))
    rate = decimal_or_zero(getattr(source_item, "rate", 0))
    amount = qty * rate
    item_values = {
        target_spec.parent_field: target.id,
        "item_code": getattr(source_item, "item_code", ""),
        "item_name": getattr(source_item, "item_name", None),
        "description": getattr(source_item, "description", None),
        "qty": qty,
        "uom": getattr(source_item, "uom", None),
        "rate": rate,
        "amount": amount,
    }
    item = target_spec.item_model(
        **{field: value for field, value in item_values.items() if hasattr(target_spec.item_model, field)}
    )
    database.session.add(item)
    database.session.flush()
    create_document_relation(
        source_type=source_type,
        source_id=source_id,
        source_item_id=source_item_id,
        target_type=target_type,
        target_id=target.id,
        target_item_id=item.id,
        qty=qty,
        uom=getattr(item, "uom", None),
        rate=rate,
        amount=amount,
    )
    return {"index": index, "target_item_id": item.id}


def create_target_document(payload: dict[str, Any]) -> dict[str, Any]:
    """Crea un documento destino generico a partir de lineas fuente."""
    target_type = normalize_doctype(str(payload.get("target_document_type", "")))
    company = payload.get("company") or payload.get("company_id")
    posting_date = payload.get("posting_date")
    lines = payload.get("lines") or []
    if not target_type or not company or not posting_date or not lines:
        raise DocumentFlowError("Debe indicar destino, compania, fecha y lineas.", 400)
    if target_type == "payment_entry":
        return _create_payment_target(payload)

    target_spec = get_document_type(target_type)
    target = _create_target_header(target_spec, target_type, company, posting_date, payload)

    created_lines = []
    for index, selected in enumerate(lines):
        created_lines.append(_process_target_line(index, selected, target, target_spec, target_type))
    database.session.commit()
    return {
        "target_type": target_type,
        "target_id": target.id,
        "document_no": getattr(target, "document_no", None),
        "lines": created_lines,
    }


def _create_payment_target(payload: dict[str, Any]) -> dict[str, Any]:
    """Crea un pago generico desde facturas fuente."""
    company = payload.get("company") or payload.get("company_id")
    posting_date = payload.get("posting_date")
    bank_account = _load_payment_bank_account(payload)
    payment = _build_payment_target_payment(company, posting_date, payload)
    assign_payment_identifier(payment, bank_account, posting_date, payload)
    total = _apply_payment_target_lines(payment, company, payload)
    _update_payment_target_amounts(payment, total)
    database.session.commit()
    return _payment_target_result(payment)


def _load_payment_bank_account(payload: dict[str, Any]) -> BankAccount | None:
    """Carga la cuenta bancaria opcional para un pago destino."""
    bank_account_id = payload.get("bank_account_id")
    if not bank_account_id:
        return None
    return database.session.get(BankAccount, bank_account_id)


def _build_payment_target_payment(company: str | None, posting_date: Any, payload: dict[str, Any]) -> PaymentEntry:
    """Construye el pago destino a partir del payload validado."""
    payment = PaymentEntry(
        company=company,
        docstatus=0,
        posting_date=posting_date,
        payment_type=str(payload.get("payment_type") or "receive"),
        party_type=payload.get("party_type"),
        party_id=payload.get("party_id"),
        bank_account_id=payload.get("bank_account_id"),
        remarks=payload.get("remarks"),
    )
    database.session.add(payment)
    database.session.flush()
    return payment


def assign_payment_identifier(
    payment: PaymentEntry,
    bank_account: BankAccount | None,
    posting_date: Any,
    payload: dict[str, Any],
) -> None:
    """Asigna el identificador físico al pago destino."""
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
        raise DocumentFlowError("No se puede repetir la misma factura en un solo pago.", 409)
    processed_reference_keys.add(reference_key)

    # S2P-10: Usa with_for_update() para prevenir condiciones de carrera
    # al asignar pagos directamente. Sin bloqueo, otro proceso podria
    # modificar la factura entre la lectura y la persistencia.
    model = _payment_reference_model(reference_type)
    invoice = database.session.query(model).with_for_update().get(reference_id)
    if not invoice:
        raise DocumentFlowError("Factura origen no encontrada.", 404)
    if company and getattr(invoice, "company", None) and getattr(invoice, "company") != company:
        raise DocumentFlowError("No se pueden mezclar companias incompatibles.", 409)

    allocated = decimal_or_zero(selected.get("qty") or selected.get("allocated_amount"))
    outstanding = compute_outstanding_amount(invoice)
    _validate_payment_target_allocation(allocated, outstanding)
    _persist_payment_target_allocation(payment, reference_type, reference_id, invoice, allocated, outstanding)
    return allocated


def _validate_payment_target_allocation(allocated: Decimal, outstanding: Decimal) -> None:
    """Valida la cantidad a aplicar contra una factura origen."""
    if allocated <= 0:
        raise DocumentFlowError(_MSG_MONTO_MAYOR_CERO, 409)
    if allocated > outstanding:
        raise DocumentFlowError("El monto aplicado excede el saldo pendiente.", 409)


def _persist_payment_target_allocation(
    payment: PaymentEntry,
    reference_type: str,
    reference_id: str,
    invoice: Any,
    allocated: Decimal,
    outstanding: Decimal,
) -> None:
    """Persist the payment reference and document relation for an allocation."""
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=reference_type,
        reference_id=reference_id,
        total_amount=getattr(invoice, "grand_total", None),
        outstanding_amount=outstanding,
        allocated_amount=allocated,
        allocation_date=payment.posting_date,
    )
    database.session.add(reference)
    database.session.flush()
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


def _update_payment_target_amounts(payment: PaymentEntry, total: Decimal) -> None:
    """Actualiza los importes del pago segun su direccion contable."""
    if payment.payment_type == "pay":
        payment.paid_amount = total
        payment.base_paid_amount = total
    else:
        payment.received_amount = total
        payment.base_received_amount = total


def _payment_target_result(payment: PaymentEntry) -> dict[str, Any]:
    """Construye la respuesta final del pago destino."""
    return {"target_type": "payment_entry", "target_id": payment.id, "document_no": payment.document_no, "lines": []}
