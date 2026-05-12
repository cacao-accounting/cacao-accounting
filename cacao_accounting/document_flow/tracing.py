# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Trazabilidad documental upstream/downstream."""

from __future__ import annotations

from typing import Any

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


def _doctype_module(doctype: str) -> str:
    """Devuelve la etiqueta del modulo al que pertenece un tipo documental."""
    spec = DOCUMENT_TYPES.get(doctype)
    return spec.module_label if spec else "General"


def _doctype_label(doctype: str) -> str:
    """Devuelve la etiqueta legible de un tipo documental."""
    spec = DOCUMENT_TYPES.get(doctype)
    return spec.label if spec and spec.label else doctype


def document_flow_summary(document_type: str, document_id: str) -> dict[str, Any]:
    """Devuelve un resumen agrupado de documentos relacionados con contadores.

    Agrupa las relaciones upstream (origen) y downstream (destino) por tipo
    documental, calculando contadores activos e historicos para el panel de
    trazabilidad en la vista de detalle.
    """
    doctype = normalize_doctype(document_type)

    upstream_rows: list[DocumentRelation] = list(
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(target_type=doctype, target_id=document_id)
            .order_by(DocumentRelation.created)
        )
        .scalars()
        .all()
    )
    downstream_rows: list[DocumentRelation] = list(
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(source_type=doctype, source_id=document_id)
            .order_by(DocumentRelation.created)
        )
        .scalars()
        .all()
    )

    upstream_groups = _build_groups(upstream_rows, use_source=True, current_id=document_id, current_type=doctype)
    downstream_groups = _build_groups(downstream_rows, use_source=False, current_id=document_id, current_type=doctype)

    spec = DOCUMENT_TYPES.get(doctype)
    create_actions = []
    if spec:
        create_actions = [
            {"label": action.label, "target_type": action.target_type, "endpoint": action.endpoint}
            for action in spec.create_actions
        ]

    return {
        "document_type": doctype,
        "document_id": document_id,
        "upstream": upstream_groups,
        "downstream": downstream_groups,
        "create_actions": create_actions,
    }


def _build_groups(
    rows: list[DocumentRelation],
    use_source: bool,
    current_id: str,
    current_type: str,
) -> list[dict[str, Any]]:
    """Agrupa relaciones por tipo documental con contadores y documentos."""
    from flask import url_for

    groups: dict[str, dict[str, Any]] = {}
    for relation in rows:
        related_type = relation.source_type if use_source else relation.target_type
        related_id = relation.source_id if use_source else relation.target_id
        is_active = relation.status == "active"

        if related_type not in groups:
            try:
                list_url: str | None = url_for(
                    "api.document_flow_related_list",
                    doctype=related_type,
                    related_doctype=current_type,
                    related_id=current_id,
                )
            except Exception:  # noqa: BLE001 — url_for puede fallar fuera de contexto de peticion
                list_url = None

            groups[related_type] = {
                "doctype": related_type,
                "label": _doctype_label(related_type),
                "module": _doctype_module(related_type),
                "list_url": list_url,
                "active_count": 0,
                "historical_count": 0,
                "documents": [],
            }

        if is_active:
            groups[related_type]["active_count"] += 1
        else:
            groups[related_type]["historical_count"] += 1

        doc_payload = _document_payload(related_type, related_id)
        groups[related_type]["documents"].append(
            {
                "relation_id": relation.id,
                "relation_type": relation.relation_type,
                "status": relation.status,
                "document": doc_payload,
                "badge_class": (
                    doc_payload.get("status", {}).get("badge_class", "text-bg-secondary")
                    if doc_payload.get("status")
                    else "text-bg-secondary"
                ),
            }
        )

    return list(groups.values())
