# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Trazabilidad documental upstream/downstream."""

from __future__ import annotations

from typing import Any

from werkzeug.routing import BuildError

from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, normalize_doctype
from cacao_accounting.document_flow.repository import get_document


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
        "label": str(action.label) if action.label is not None else None,
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
