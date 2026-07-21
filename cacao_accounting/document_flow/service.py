# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de flujo documental y parcialidades.

Convencion de naming para referencias de pago:
- ``flow_source_type``: tipo logico del documento fuente (e.g. ``purchase_credit_note``).
- ``model_type``: tipo fisico del modelo SQLAlchemy (e.g. ``purchase_invoice``).
- ``document_id``: identificador del documento referenciado.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from flask_login import current_user
from sqlalchemy import select

from cacao_accounting.database import (
    AuditLog,
    DocumentRelation,
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
from cacao_accounting.audit_trail_service import log_create
from cacao_accounting.document_identifiers import assign_document_identifier

_MSG_LINEA_ORIGEN = "Linea origen no encontrada."


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
            invoice_type = "sales_invoice" if parent_type == "sales_order" else "purchase_invoice"
            direct_billed = consumed_qty_for_source(parent_type, rel.source_id, rel.source_item_id, invoice_type)

            intermediary_type = "delivery_note" if parent_type == "sales_order" else "purchase_receipt"

            indirect_billed = Decimal("0")
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
    source_item, target_item = _validate_relation_documents(
        source_key, source_id, source_item_id, target_key, target_id, target_item_id
    )
    _assert_same_company(source_key, source_id, target_key, target_id)
    _validate_relation_status(source_key, source_id, target_key, target_id)
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
    database.session.flush()
    _audit(
        "document_relation",
        relation.id,
        "create",
        None,
        {"status": relation.status, "qty": str(relation.qty)},
    )
    if source_item_id:
        recompute_line_flow_state(source_key, source_id, source_item_id, target_key, relation.company)
        _update_source_cache(source_key, source_id, source_item_id, target_key)
    return relation


def _validate_relation_documents(source_key, source_id, source_item_id, target_key, target_id, target_item_id):
    """Valida el flujo y las líneas asociadas a una relación."""
    if not is_allowed_flow(source_key, target_key):
        raise DocumentFlowError(f"Relacion no permitida: {source_key} -> {target_key}", 400)
    source_item = get_document_item(source_key, source_item_id) if source_item_id else None
    target_item = get_document_item(target_key, target_item_id) if target_item_id else None
    if source_item_id and not source_item:
        raise DocumentFlowError(_MSG_LINEA_ORIGEN, 404)
    if target_item_id and not target_item:
        raise DocumentFlowError("Linea destino no encontrada.", 404)
    if source_item and get_item_parent_id(get_document_type(source_key), source_item) != source_id:
        raise DocumentFlowError("La linea origen no pertenece al documento indicado.", 409)
    return source_item, target_item


def _validate_relation_status(source_key: str, source_id: str, target_key: str, target_id: str) -> None:
    """Valida estados de documentos en una relación."""
    source_doc = get_document(source_key, source_id)
    target_doc = get_document(target_key, target_id)
    if source_doc is not None and getattr(source_doc, "docstatus", None) != 1:
        raise DocumentFlowError("El documento origen debe estar aprobado (docstatus=1) para crear la relacion.", 409)
    if target_doc is not None and getattr(target_doc, "docstatus", None) == 2:
        raise DocumentFlowError("No se puede crear una relacion hacia un documento cancelado (docstatus=2).", 409)


def revert_relations_for_target(target_type: str, target_id: str, reason: str = "target_cancelled") -> int:
    """Revierte relaciones activas de un documento destino y libera saldos.

    Tambien revierte relaciones donde el documento cancelado es SOURCE
    (relaciones downstream), propagando la invalidez de caches.
    """
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
    downstream = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(source_type=target_key, source_id=target_id, status="active")
        )
        .scalars()
        .all()
    )
    for relation in downstream:
        before = {"status": relation.status, "qty": str(relation.qty)}
        relation.status = "reverted"
        relation.reversed_at = now
        relation.reversed_by = _current_user_id()
        relation.reversal_reason = reason
        if relation.source_item_id:
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
    return len(relations) + len(downstream)


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
    log_create(target)
    return target


def _process_target_line(
    index: int,
    selected: dict[str, Any],
    target: Any,
    target_spec: Any,
    target_type: str,
) -> dict[str, Any]:
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
        from cacao_accounting.document_flow.payment import _create_payment_target

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


# Re-exportir funciones de pago desde el modulo dedicado para compatibilidad.
from cacao_accounting.document_flow.payment import (  # noqa: E402
    PaymentAllocationContext,
    apply_advance_to_invoice,
    apply_payment_reconciliation,
    compute_outstanding_amount,
    compute_payment_unallocated_amount,
    payment_reference_candidates,
    payment_reconciliation_candidates,
    refresh_outstanding_amount_cache,
)

__all__ = [
    "DocumentFlowError",
    "PaymentAllocationContext",
    "apply_advance_to_invoice",
    "apply_payment_reconciliation",
    "close_document_balances",
    "close_line_balance",
    "compute_outstanding_amount",
    "compute_payment_unallocated_amount",
    "create_document_relation",
    "create_target_document",
    "get_document_flow_items",
    "get_pending_lines",
    "get_source_items",
    "list_source_documents",
    "payment_reference_candidates",
    "payment_reconciliation_candidates",
    "pending_qty",
    "refresh_outstanding_amount_cache",
    "refresh_source_caches_for_target",
    "revert_relations_for_target",
]
