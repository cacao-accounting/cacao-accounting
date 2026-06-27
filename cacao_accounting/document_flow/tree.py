# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio reutilizable de árbol de flujo documental recursivo.

Construye un árbol upstream/downstream desde cualquier documento del
sistema, con soporte para relaciones N:N, prevención de ciclos y límite
de profundidad configurable.
"""

from __future__ import annotations

from typing import Any

from cacao_accounting.database import DocumentRelation, PaymentReference, database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, normalize_doctype
from cacao_accounting.document_flow.repository import get_document
from cacao_accounting.document_flow.status import document_status_payload

DEFAULT_MAX_DEPTH: int = 10
DEFAULT_MAX_NODES: int = 100

_CURRENCY_FIELDS = ("currency", "transaction_currency")
_PARTY_NAME_FIELDS = ("party_name", "supplier_name", "customer_name")


# ---------------------------------------------------------------------------
# Nodo individual
# ---------------------------------------------------------------------------


def get_document_node(document_type: str, document_id: str) -> dict[str, Any]:
    """Construye el payload de metadatos de un nodo del árbol.

    Devuelve campos enriquecidos: label, url de detalle, estado, fecha,
    tercero, moneda y monto, compatibles con la respuesta JSON del endpoint
    /api/document-flow/tree.
    """
    doctype = normalize_doctype(document_type)
    spec = DOCUMENT_TYPES.get(doctype)
    document = get_document(doctype, document_id)

    label = spec.label if spec and spec.label else doctype
    detail_url = _build_detail_url(spec, document_id) if spec else None

    node: dict[str, Any] = {
        "document_type": doctype,
        "document_id": document_id,
        "document_no": getattr(document, "document_no", None) or document_id,
        "label": label,
        "docstatus": _resolve_docstatus(document),
        "posting_date": _serialize_date(_resolve_date(document, spec)),
        "party_name": _resolve_party_name(document, spec),
        "currency": _resolve_currency(document),
        "total": _resolve_total(document, spec),
        "url": detail_url,
        "status": document_status_payload(doctype, document_id) if document else None,
    }
    return node


# ---------------------------------------------------------------------------
# Árbol recursivo
# ---------------------------------------------------------------------------


def get_upstream_tree(
    document_type: str,
    document_id: str,
    *,
    visited: set[tuple[str, str]] | None = None,
    depth: int = 0,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_counter: list[int] | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> list[dict[str, Any]]:
    """Devuelve la lista de nodos origen (upstream) con hijos recursivos.

    Cada elemento de la lista es un nodo con el campo ``children`` que a su
    vez puede contener más nodos upstream.  Se protege contra ciclos mediante
    el conjunto ``visited`` y contra explosión de profundidad/nodos con los
    límites configurables.
    """
    if visited is None:
        visited = set()
    if node_counter is None:
        node_counter = [0]

    if depth >= max_depth:
        return [{"max_depth_reached": True}]

    doctype = normalize_doctype(document_type)
    key = (doctype, document_id)
    if key in visited:
        return [{"cycle_detected": True, "document_type": doctype, "document_id": document_id}]
    visited.add(key)

    rows: list[DocumentRelation] = list(
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(target_type=doctype, target_id=document_id)
            .order_by(DocumentRelation.created)
        )
        .scalars()
        .all()
    )

    seen_pairs: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        src_type = row.source_type
        src_id = row.source_id
        pair = (src_type, src_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        if node_counter[0] >= max_nodes:
            result.append({"max_nodes_reached": True})
            break

        node = get_document_node(src_type, src_id)
        node["relation_type"] = row.relation_type
        node["relation_status"] = row.status
        node_counter[0] += 1

        node["children"] = get_upstream_tree(
            src_type,
            src_id,
            visited=visited,
            depth=depth + 1,
            max_depth=max_depth,
            node_counter=node_counter,
            max_nodes=max_nodes,
        )
        result.append(node)

    visited.discard(key)
    return result


def get_downstream_tree(
    document_type: str,
    document_id: str,
    *,
    visited: set[tuple[str, str]] | None = None,
    depth: int = 0,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_counter: list[int] | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> list[dict[str, Any]]:
    """Devuelve la lista de nodos derivados (downstream) con hijos recursivos.

    Funciona simétricamente a ``get_upstream_tree``, recorriendo las
    relaciones cuyo source es el documento actual.  Para ``payment_entry``
    también incluye los documentos aplicados vía ``PaymentReference``.
    """
    if visited is None:
        visited = set()
    if node_counter is None:
        node_counter = [0]

    if depth >= max_depth:
        return [{"max_depth_reached": True}]

    doctype = normalize_doctype(document_type)
    key = (doctype, document_id)
    if key in visited:
        return [{"cycle_detected": True, "document_type": doctype, "document_id": document_id}]
    visited.add(key)

    rows: list[DocumentRelation] = list(
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(source_type=doctype, source_id=document_id)
            .order_by(DocumentRelation.created)
        )
        .scalars()
        .all()
    )

    seen_pairs: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        tgt_type = row.target_type
        tgt_id = row.target_id
        pair = (tgt_type, tgt_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        if node_counter[0] >= max_nodes:
            result.append({"max_nodes_reached": True})
            break

        node = get_document_node(tgt_type, tgt_id)
        node["relation_type"] = row.relation_type
        node["relation_status"] = row.status
        node_counter[0] += 1

        node["children"] = get_downstream_tree(
            tgt_type,
            tgt_id,
            visited=visited,
            depth=depth + 1,
            max_depth=max_depth,
            node_counter=node_counter,
            max_nodes=max_nodes,
        )
        result.append(node)

    # Agrega referencias de pago para documentos que actúan como fuente de cobro/pago.
    _append_payment_reference_nodes(
        doctype,
        document_id,
        seen_pairs,
        result,
        visited=visited,
        depth=depth,
        max_depth=max_depth,
        node_counter=node_counter,
        max_nodes=max_nodes,
    )

    visited.discard(key)
    return result


def build_document_flow_tree(
    document_type: str,
    document_id: str,
    *,
    direction: str = "all",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> dict[str, Any]:
    """Construye el árbol completo upstream + downstream de un documento.

    Parámetros
    ----------
    document_type:
        Tipo documental normalizado o alias (p.ej. ``sales_invoice``).
    document_id:
        Identificador primario del documento.
    direction:
        ``"all"`` (defecto), ``"upstream"`` o ``"downstream"``.
    max_depth:
        Profundidad máxima de recursión (defecto 10).
    max_nodes:
        Número máximo de nodos totales a incluir (defecto 100).

    Devuelve
    --------
    dict con claves ``current``, ``upstream``, ``downstream`` y ``meta``.
    """
    doctype = normalize_doctype(document_type)
    current = get_document_node(doctype, document_id)

    node_counter: list[int] = [0]
    cycle_detected = False

    upstream: list[dict[str, Any]] = []
    downstream: list[dict[str, Any]] = []

    if direction in ("all", "upstream"):
        upstream = get_upstream_tree(
            doctype,
            document_id,
            max_depth=max_depth,
            node_counter=node_counter,
            max_nodes=max_nodes,
        )
        cycle_detected = cycle_detected or _has_cycle_flag(upstream)

    if direction in ("all", "downstream"):
        downstream = get_downstream_tree(
            doctype,
            document_id,
            max_depth=max_depth,
            node_counter=node_counter,
            max_nodes=max_nodes,
        )
        cycle_detected = cycle_detected or _has_cycle_flag(downstream)

    return {
        "current": current,
        "upstream": upstream,
        "downstream": downstream,
        "create_actions": _get_create_actions(doctype, document_id),
        "meta": {
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "node_count": node_counter[0],
            "cycle_detected": cycle_detected,
        },
    }


def _get_create_actions(doctype: str, document_id: str) -> list[dict[str, Any]]:
    """Devuelve las acciones disponibles para crear documentos derivados."""
    from cacao_accounting.document_flow.tracing import (
        _create_action_payload,
        _is_create_actions_enabled,
    )

    spec = DOCUMENT_TYPES.get(doctype)
    if not spec:
        return []
    document = get_document(doctype, document_id)
    if not _is_create_actions_enabled(document):
        return []
    return [_create_action_payload(action, document_id) for action in spec.create_actions if action.enabled]


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _build_detail_url(spec: Any, document_id: str) -> str | None:
    """Construye la URL de detalle de un documento usando su spec."""
    if not spec or not spec.detail_endpoint:
        return None
    try:
        from flask import url_for

        kwargs: dict[str, str] = {spec.detail_arg: document_id}
        return url_for(spec.detail_endpoint, **kwargs)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return None


def _serialize_date(value: Any) -> str | None:
    """Serializa una fecha a ISO-8601 si existe."""
    if value is None:
        return None
    return str(value)


def _resolve_date(document: Any, spec: Any) -> Any | None:
    """Obtiene la fecha principal del documento."""
    if document is None:
        return None
    if spec and spec.date_field:
        val = getattr(document, spec.date_field, None)
        if val:
            return val
    return getattr(document, "posting_date", None) or getattr(document, "date", None)


def _resolve_docstatus(document: Any) -> int | None:
    """Obtiene docstatus numérico, incluyendo comprobantes manuales."""
    if document is None:
        return None
    docstatus = getattr(document, "docstatus", None)
    if docstatus is not None:
        return int(docstatus)
    status = str(getattr(document, "status", "") or "").lower()
    if status in {"draft", "rejected"}:
        return 0
    if status == "submitted":
        return 1
    if status == "cancelled":
        return 2
    return None


def _resolve_party_name(document: Any, spec: Any) -> str | None:
    """Obtiene el nombre de tercero del documento."""
    if document is None:
        return None
    for field in _PARTY_NAME_FIELDS:
        val = getattr(document, field, None)
        if val:
            return str(val)
    if spec and spec.party_field:
        val = getattr(document, spec.party_field, None)
        if val:
            return str(val)
    return None


def _resolve_currency(document: Any) -> str | None:
    """Obtiene el código de moneda del documento."""
    if document is None:
        return None
    for field in _CURRENCY_FIELDS:
        val = getattr(document, field, None)
        if val:
            return str(val)
    return None


def _resolve_total(document: Any, spec: Any) -> float | None:
    """Obtiene el monto total del documento."""
    if document is None or spec is None:
        return None
    if spec.key == "journal_entry":
        return _resolve_journal_total(document)
    field = spec.total_field or "grand_total"
    val = getattr(document, field, None)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _resolve_journal_total(document: Any) -> float | None:
    """Calcula el total visible de un comprobante contable."""
    from cacao_accounting.database import ComprobanteContableDetalle

    lines = database.session.execute(
        database.select(ComprobanteContableDetalle).filter_by(transaction="journal_entry", transaction_id=document.id)
    ).scalars()
    debit = 0.0
    credit = 0.0
    for line in lines:
        value = float(getattr(line, "value", 0) or 0)
        if value >= 0:
            debit += value
        else:
            credit += abs(value)
    total = max(debit, credit)
    return total if total else None


def _has_cycle_flag(nodes: list[dict[str, Any]]) -> bool:
    """Indica si algún nodo del árbol tiene la bandera cycle_detected."""
    for node in nodes:
        if node.get("cycle_detected"):
            return True
        if _has_cycle_flag(node.get("children") or []):
            return True
    return False


def _append_payment_reference_nodes(
    doctype: str,
    document_id: str,
    seen_pairs: set[tuple[str, str]],
    result: list[dict[str, Any]],
    *,
    visited: set[tuple[str, str]],
    depth: int,
    max_depth: int,
    node_counter: list[int],
    max_nodes: int,
) -> None:
    """Agrega nodos derivados desde PaymentReference cuando corresponda.

    Las facturas y notas cuyo ``document_id`` aparece como
    ``reference_id`` en ``PaymentReference`` se exponen como downstream
    del pago correspondiente. Esto garantiza visibilidad de relaciones N:N
    aun cuando no exista DocumentRelation explícita.
    """
    ref_doctypes = {
        "sales_invoice",
        "purchase_invoice",
        "sales_debit_note",
        "purchase_debit_note",
        "sales_credit_note",
        "purchase_credit_note",
        "sales_order",
        "purchase_order",
    }
    if doctype in ref_doctypes:
        pay_refs: list[PaymentReference] = list(
            database.session.execute(
                database.select(PaymentReference)
                .filter_by(reference_type=doctype, reference_id=document_id)
                .order_by(PaymentReference.created)
            )
            .scalars()
            .all()
        )

        for ref in pay_refs:
            pay_id = ref.payment_id
            pair = ("payment_entry", pay_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            if node_counter[0] >= max_nodes:
                result.append({"max_nodes_reached": True})
                break

            node = get_document_node("payment_entry", pay_id)
            node["relation_type"] = "payment"
            node["relation_status"] = "active"
            node["applied_amount"] = float(ref.allocated_amount or 0)
            node_counter[0] += 1

            node["children"] = get_downstream_tree(
                "payment_entry",
                pay_id,
                visited=visited,
                depth=depth + 1,
                max_depth=max_depth,
                node_counter=node_counter,
                max_nodes=max_nodes,
            )
            result.append(node)
        return

    if doctype != "payment_entry":
        return

    refs: list[PaymentReference] = list(
        database.session.execute(
            database.select(PaymentReference).filter_by(payment_id=document_id).order_by(PaymentReference.created)
        )
        .scalars()
        .all()
    )

    for ref in refs:
        ref_type = normalize_doctype(ref.reference_type)
        ref_id = ref.reference_id
        pair = (ref_type, ref_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        if node_counter[0] >= max_nodes:
            result.append({"max_nodes_reached": True})
            break

        node = get_document_node(ref_type, ref_id)
        node["relation_type"] = "payment_reference"
        node["relation_status"] = "active"
        node["applied_amount"] = float(ref.allocated_amount or 0)
        node_counter[0] += 1

        node["children"] = get_downstream_tree(
            ref_type,
            ref_id,
            visited=visited,
            depth=depth + 1,
            max_depth=max_depth,
            node_counter=node_counter,
            max_nodes=max_nodes,
        )
        result.append(node)
