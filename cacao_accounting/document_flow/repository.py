# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Consultas para el motor de flujo documental."""

from decimal import Decimal
from typing import Any

from cacao_accounting.database import DocumentLineFlowState, DocumentRelation, database
from cacao_accounting.document_flow.registry import DocumentType, get_document_type, normalize_doctype


def decimal_or_zero(value: Any) -> Decimal:
    """Convierte valores numericos de SQLAlchemy/formularios a Decimal."""
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def get_document(doctype: str, document_id: str) -> Any | None:
    """Obtiene un documento por tipo e id."""
    spec = get_document_type(doctype)
    return database.session.get(spec.header_model, document_id)


def get_document_company(doctype: str, document_id: str) -> str | None:
    """Obtiene la compania del documento."""
    document = get_document(doctype, document_id)
    return getattr(document, "company", None) if document else None


def get_document_items(doctype: str, document_id: str) -> list[Any]:
    """Devuelve las lineas de un documento."""
    spec = get_document_type(doctype)
    parent_column = getattr(spec.item_model, spec.parent_field)
    return list(
        database.session.execute(
            database.select(spec.item_model).where(parent_column == document_id).order_by(spec.item_model.created)
        ).scalars()
    )


def get_document_item(doctype: str, item_id: str | None) -> Any | None:
    """Obtiene una linea por tipo documental."""
    spec = get_document_type(doctype)
    return database.session.get(spec.item_model, item_id)


def get_item_parent_id(spec: DocumentType, item: Any) -> str:
    """Devuelve el id del header al que pertenece una linea."""
    return str(getattr(item, spec.parent_field))


def iter_active_relations_for_source(
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str | None = None,
) -> list[DocumentRelation]:
    """Devuelve relaciones cuyo target no esta cancelado."""
    source_key = normalize_doctype(source_type)
    target_key = normalize_doctype(target_type) if target_type else None
    query = database.select(DocumentRelation).filter_by(
        source_type=source_key,
        source_id=source_id,
        source_item_id=source_item_id,
        status="active",
    )
    if target_key:
        query = query.filter_by(target_type=target_key)

    active: list[DocumentRelation] = []
    relations = database.session.execute(query).scalars().all()
    for relation in relations:
        target = get_document(relation.target_type, relation.target_id)
        if target and getattr(target, "docstatus", 0) != 2:
            active.append(relation)
    return active


def consumed_qty_for_source(
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str | None = None,
) -> Decimal:
    """Suma la cantidad consumida por relaciones activas."""
    return sum(
        (
            decimal_or_zero(relation.qty)
            for relation in iter_active_relations_for_source(source_type, source_id, source_item_id, target_type)
        ),
        Decimal("0"),
    )


def save_relation(relation: DocumentRelation) -> DocumentRelation:
    """Agrega una relacion a la sesion actual."""
    database.session.add(relation)
    return relation


def get_line_flow_state(
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str,
) -> DocumentLineFlowState | None:
    """Obtiene el estado cacheado de una linea fuente para un destino."""
    return database.session.execute(
        database.select(DocumentLineFlowState).filter_by(
            source_type=normalize_doctype(source_type),
            source_id=source_id,
            source_item_id=source_item_id,
            target_type=normalize_doctype(target_type),
        )
    ).scalar_one_or_none()


def recompute_line_flow_state(
    source_type: str,
    source_id: str,
    source_item_id: str | None,
    target_type: str,
    company: str | None = None,
) -> DocumentLineFlowState:
    """Recalcula y persiste el estado de una linea fuente."""
    source_key = normalize_doctype(source_type)
    target_key = normalize_doctype(target_type)
    source_item = get_document_item(source_key, source_item_id)
    source_qty = decimal_or_zero(getattr(source_item, "qty", 0)) if source_item else Decimal("0")
    state = get_line_flow_state(source_key, source_id, source_item_id, target_key)
    if state is None:
        state = DocumentLineFlowState(
            source_type=source_key,
            source_id=source_id,
            source_item_id=source_item_id,
            target_type=target_key,
            company=company,
            source_qty=source_qty,
        )
        database.session.add(state)
    elif company and not state.company:
        state.company = company

    state.source_qty = source_qty
    state.processed_qty = consumed_qty_for_source(source_key, source_id, source_item_id, target_key)
    cancelled = decimal_or_zero(state.cancelled_qty)
    closed = decimal_or_zero(state.closed_qty)
    pending = source_qty - decimal_or_zero(state.processed_qty) - cancelled - closed
    state.pending_qty = pending if pending > 0 else Decimal("0")
    if closed >= source_qty and source_qty > 0:
        state.line_status = "closed"
    elif state.pending_qty == 0 and source_qty > 0:
        state.line_status = "complete"
    elif decimal_or_zero(state.processed_qty) > 0:
        state.line_status = "partial"
    else:
        state.line_status = "open"
    database.session.flush()
    return state


def recompute_states_for_source(
    source_type: str,
    source_id: str,
    target_type: str | None = None,
) -> list[DocumentLineFlowState]:
    """Recalcula estados de todas las lineas de un documento fuente."""
    source_key = normalize_doctype(source_type)
    target_keys = [normalize_doctype(target_type)] if target_type else []
    if not target_keys:
        target_keys = sorted(
            {
                row[0]
                for row in database.session.execute(
                    database.select(DocumentRelation.target_type).filter_by(
                        source_type=source_key,
                        source_id=source_id,
                    )
                )
            }
        )
    states: list[DocumentLineFlowState] = []
    company = get_document_company(source_key, source_id)
    for item in get_document_items(source_key, source_id):
        for target_key in target_keys:
            states.append(recompute_line_flow_state(source_key, source_id, item.id, target_key, company))
    return states
