# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Trazabilidad documental upstream/downstream."""

from __future__ import annotations

from typing import Any
from werkzeug.routing import BuildError

from cacao_accounting.database import DocumentRelation, database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, normalize_doctype
from cacao_accounting.document_flow.repository import get_document
from cacao_accounting.document_flow.status import document_status_payload


def _document_payload(document_type: str, document_id: str) -> dict[str, Any]:
    """Serializa datos minimos de un documento para arboles de flujo."""
    doctype = normalize_doctype(document_type)
    document = get_document(doctype, document_id)
    return {
        "document_type": doctype,
        "document_id": document_id,
        "document_no": getattr(document, "document_no", None) or document_id,
        "company": getattr(document, "company", None),
        "status": document_status_payload(doctype, document_id) if document else None,
    }


def document_flow_tree(document_type: str, document_id: str) -> dict[str, Any]:
    """Construye una vista compacta de relaciones documentales."""
    doctype = normalize_doctype(document_type)
    upstream_rows = (
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(target_type=doctype, target_id=document_id)
            .order_by(DocumentRelation.created)
        )
        .scalars()
        .all()
    )
    downstream_rows = (
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(source_type=doctype, source_id=document_id)
            .order_by(DocumentRelation.created)
        )
        .scalars()
        .all()
    )
    return {
        "document": _document_payload(doctype, document_id),
        "upstream": [_relation_payload(row, upstream=True) for row in upstream_rows],
        "downstream": [_relation_payload(row, upstream=False) for row in downstream_rows],
    }


def _relation_payload(relation: DocumentRelation, upstream: bool) -> dict[str, Any]:
    """Serializa una relacion de flujo."""
    related_type = relation.source_type if upstream else relation.target_type
    related_id = relation.source_id if upstream else relation.target_id
    return {
        "relation_id": relation.id,
        "relation_type": relation.relation_type,
        "status": relation.status,
        "qty": float(relation.qty or 0),
        "uom": relation.uom,
        "document": _document_payload(related_type, related_id),
    }


def _is_create_actions_enabled(document: Any) -> bool:
    """Indica si el documento puede exponer acciones ``Crear`` en UI."""
    if not document:
        return False
    return getattr(document, "docstatus", None) == 1


def _create_action_payload(action: Any, document_id: str) -> dict[str, Any]:
    """Serializa una accion de creacion con URL navegable cuando es posible."""
    from flask import url_for

    create_url: str | None
    endpoint_args: dict[str, Any] = {action.source_param: document_id}
    if action.query_params:
        endpoint_args.update(action.query_params)
    try:
        create_url = url_for(action.endpoint, **endpoint_args)
    except (BuildError, RuntimeError):
        create_url = None
    return {
        "label": action.label,
        "target_type": action.target_type,
        "model_target_type": action.model_target_type,
        "endpoint": action.endpoint,
        "source_param": action.source_param,
        "query_params": action.query_params or {},
        "condition": action.condition,
        "enabled": action.enabled,
        "create_url": create_url,
    }


def get_create_actions(document_type: str, document_id: str) -> list[dict[str, Any]]:
    """Devuelve las acciones ``Crear`` disponibles para un documento submitted.

    Solo se exponen acciones cuando el documento tiene ``docstatus == 1``
    (aprobado). Cada acción incluye una URL navegable construida con
    ``url_for`` y los query params definidos en el registro.
    """
    doctype = normalize_doctype(document_type)
    spec = DOCUMENT_TYPES.get(doctype)
    document = get_document(doctype, document_id)
    if not spec or not _is_create_actions_enabled(document):
        return []
    return [_create_action_payload(action, document_id) for action in spec.create_actions if action.enabled]
