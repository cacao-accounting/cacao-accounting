# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de flujo documental y parcialidades."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from flask_login import current_user
from sqlalchemy import or_, select

from cacao_accounting.database import (
    AuditLog,
    BankAccount,
    DocumentRelation,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    SalesInvoice,
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
    if document_type not in {"sales_invoice", "purchase_invoice"}:
        return []
    query = select(PaymentReference).filter_by(reference_type=document_type, reference_id=getattr(document, "id", ""))
    if as_of_date is not None:
        query = query.where(
            or_(
                PaymentReference.allocation_date.is_(None),
                PaymentReference.allocation_date <= as_of_date,
            )
        )
    return list(database.session.execute(query).scalars().all())


def compute_outstanding_amount(document: Any, as_of_date: date | None = None) -> Decimal:
    """Calcula el saldo vivo de una factura usando las referencias de pago."""
    if as_of_date is None:
        as_of_date = date.today()
    grand_total = decimal_or_zero(getattr(document, "grand_total", None))
    allocated = sum(
        decimal_or_zero(reference.allocated_amount)
        for reference in _document_payment_references(document, as_of_date=as_of_date)
    )
    outstanding = grand_total - allocated
    return outstanding if outstanding > 0 else Decimal("0")


def refresh_outstanding_amount_cache(document: Any, as_of_date: date | None = None) -> Decimal:
    """Sincroniza el campo cacheado `outstanding_amount` con el valor calculado."""
    outstanding = compute_outstanding_amount(document, as_of_date=as_of_date)
    if hasattr(document, "outstanding_amount"):
        document.outstanding_amount = outstanding
    if hasattr(document, "base_outstanding_amount"):
        document.base_outstanding_amount = outstanding
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
    invoice: SalesInvoice | PurchaseInvoice | None = database.session.get(SalesInvoice, invoice_id)
    reference_type = "sales_invoice"
    party_id = getattr(invoice, "customer_id", None) if invoice else None
    if invoice is None:
        invoice = database.session.get(PurchaseInvoice, invoice_id)
        reference_type = "purchase_invoice"
        party_id = getattr(invoice, "supplier_id", None) if invoice else None
    if invoice is None:
        raise DocumentFlowError("La factura no existe.")
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
        raise DocumentFlowError("El monto aplicado debe ser mayor que cero.")
    if amount > payment_total - allocated_before:
        raise DocumentFlowError("El monto excede el remanente del anticipo.")
    if amount > outstanding:
        raise DocumentFlowError("El monto excede el saldo pendiente de la factura.")
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type=reference_type,
        reference_id=invoice.id,
        total_amount=getattr(invoice, "grand_total", None),
        outstanding_amount=outstanding,
        allocated_amount=amount,
        allocation_date=allocation_date,
    )
    database.session.add(reference)
    refresh_outstanding_amount_cache(invoice, as_of_date=allocation_date)
    return reference


def _state_quantities(
    source_type: str,
    source_id: str,
    source_item_id: str,
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


def pending_qty(source_type: str, source_id: str, source_item_id: str, target_type: str) -> Decimal:
    """Calcula la cantidad pendiente para una linea origen hacia un target."""
    source_item = get_document_item(source_type, source_item_id)
    if not source_item:
        raise DocumentFlowError("Linea origen no encontrada.", 404)
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


def _update_source_cache(source_type: str, source_id: str, source_item_id: str, target_type: str) -> None:
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
    source_item_id: str,
    target_type: str,
    target_id: str,
    target_item_id: str,
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
    source_item = get_document_item(source_key, source_item_id)
    target_item = get_document_item(target_key, target_item_id)
    if not source_item or not target_item:
        raise DocumentFlowError("Linea origen o destino no encontrada.", 404)

    real_source_id = get_item_parent_id(source_spec, source_item)
    if real_source_id != source_id:
        raise DocumentFlowError("La linea origen no pertenece al documento indicado.", 409)
    _assert_same_company(source_key, source_id, target_key, target_id)

    qty_decimal = decimal_or_zero(qty)
    if qty_decimal <= 0:
        raise DocumentFlowError("La cantidad relacionada debe ser mayor que cero.", 409)
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
    source_item_id: str,
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


def list_source_documents(target_type: str, company: str | None = None) -> list[dict[str, Any]]:
    """Lista documentos fuente aprobados con saldo para un destino."""
    target_key = normalize_doctype(target_type)
    sources = sorted(source for source, target in ALLOWED_FLOWS if target == target_key)
    rows: list[dict[str, Any]] = []
    for source_key in sources:
        spec = get_document_type(source_key)
        query = database.select(spec.header_model).filter_by(docstatus=1)
        if company and hasattr(spec.header_model, "company"):
            query = query.filter_by(company=company)
        for document in database.session.execute(query).scalars().all():
            items = get_source_items(source_key, document.id, target_key)
            if items:
                rows.append(
                    {
                        "source_type": source_key,
                        "source_id": document.id,
                        "document_no": getattr(document, "document_no", None) or document.id,
                        "company": getattr(document, "company", None),
                        "posting_date": str(getattr(document, "posting_date", "") or ""),
                        "pending_lines": len(items),
                    }
                )
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

    created_lines = []
    for index, selected in enumerate(lines):
        source_type = normalize_doctype(str(selected.get("source_document_type") or selected.get("source_type") or ""))
        source_id = str(selected.get("source_document_id") or selected.get("source_id") or "")
        source_item_id = str(selected.get("source_row_id") or selected.get("source_item_id") or "")
        source_item = get_document_item(source_type, source_item_id)
        if not source_item:
            raise DocumentFlowError("Linea origen no encontrada.", 404)
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
        created_lines.append({"index": index, "target_item_id": item.id})
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
    bank_account = (
        database.session.get(BankAccount, payload.get("bank_account_id")) if payload.get("bank_account_id") else None
    )
    payment = PaymentEntry(
        company=company,
        docstatus=0,
        payment_type=str(payload.get("payment_type") or "receive"),
        party_type=payload.get("party_type"),
        party_id=payload.get("party_id"),
        bank_account_id=payload.get("bank_account_id"),
    )
    database.session.add(payment)
    database.session.flush()
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
    total = Decimal("0")
    for selected in payload.get("lines") or []:
        reference_type = normalize_doctype(str(selected.get("source_document_type") or selected.get("source_type") or ""))
        reference_id = str(selected.get("source_document_id") or selected.get("source_id") or "")
        invoice = get_document(reference_type, reference_id)
        if not invoice:
            raise DocumentFlowError("Factura origen no encontrada.", 404)
        if company and getattr(invoice, "company", None) and getattr(invoice, "company") != company:
            raise DocumentFlowError("No se pueden mezclar companias incompatibles.", 409)
        allocated = decimal_or_zero(selected.get("qty") or selected.get("allocated_amount"))
        outstanding = decimal_or_zero(getattr(invoice, "outstanding_amount", None) or getattr(invoice, "grand_total", 0))
        if allocated <= 0 or allocated > outstanding:
            raise DocumentFlowError("El monto aplicado excede el saldo pendiente.", 409)
        database.session.add(
            PaymentReference(
                payment_id=payment.id,
                reference_type=reference_type,
                reference_id=reference_id,
                total_amount=getattr(invoice, "grand_total", None),
                outstanding_amount=outstanding,
                allocated_amount=allocated,
                allocation_date=payment.posting_date,
            )
        )
        setattr(invoice, "outstanding_amount", outstanding - allocated)
        setattr(invoice, "base_outstanding_amount", outstanding - allocated)
        total += allocated
    if payment.payment_type == "pay":
        payment.paid_amount = total
        payment.base_paid_amount = total
    else:
        payment.received_amount = total
        payment.base_received_amount = total
    database.session.commit()
    return {"target_type": "payment_entry", "target_id": payment.id, "document_no": payment.document_no, "lines": []}
