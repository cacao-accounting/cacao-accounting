# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Estados informativos calculados para documentos operativos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value

else:

    def _(value: str) -> str:
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):
            return value


from cacao_accounting.document_flow.registry import ALLOWED_FLOWS, normalize_doctype
from cacao_accounting.document_flow.repository import (
    consumed_qty_for_source,
    decimal_or_zero,
    get_document,
    get_document_items,
    get_line_flow_state,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount


@dataclass(frozen=True)
class DocumentStatusInfo:
    """Estado unico calculado para UI y reportes."""

    code: str
    label: str
    full_label: str
    tone: str
    badge_class: str
    icon: str


@dataclass(frozen=True)
class FlowProgress:
    """Avance agregado de un documento fuente hacia un tipo destino."""

    target_type: str
    relation_type: str
    total_qty: Decimal
    processed_qty: Decimal
    closed_qty: Decimal
    pending_qty: Decimal


BADGE_CLASSES = {
    "gray": "text-bg-secondary",
    "green": "text-bg-success",
    "blue": "text-bg-primary",
    "red": "text-bg-danger",
}

BADGE_ICONS = {
    "gray": "bi-circle-fill",
    "green": "bi-check-circle-fill",
    "blue": "bi-arrow-repeat",
    "red": "bi-exclamation-triangle-fill",
}


def _status(code: str, label: str, tone: str, full_label: str | None = None) -> DocumentStatusInfo:
    """Construye un estado de documento consistente para templates y API."""
    return DocumentStatusInfo(
        code=code,
        label=_(label),
        full_label=_(full_label or label),
        tone=tone,
        badge_class=BADGE_CLASSES[tone],
        icon=BADGE_ICONS[tone],
    )


def calculate_document_status(document_type: str, document_or_id: Any) -> DocumentStatusInfo:
    """Calcula el estado principal visible de un documento."""
    doctype = normalize_doctype(document_type)
    document = document_or_id if not isinstance(document_or_id, str) else get_document(doctype, document_or_id)
    if document is None:
        return _status("requires_attention", "Requiere Atención", "red")

    docstatus = getattr(document, "docstatus", None)
    if docstatus == 0:
        return _status("draft", "Borrador", "gray")
    if docstatus == 2:
        return _status("cancelled", "Cancelado", "gray")

    payment_status = _payment_status(doctype, document)
    if payment_status:
        return payment_status

    progress = _primary_flow_progress(doctype, document)
    if progress:
        return _status_from_progress(progress)

    if docstatus == 1:
        return _status("open", "Abierto", "blue")
    return _status("requires_attention", "Requiere Atención", "red")


def _payment_status(doctype: str, document: Any) -> DocumentStatusInfo | None:
    """Calcula estados de pago para facturas y pagos."""
    if doctype == "payment_entry":
        return _status("paid", "Pagado", "green")

    if doctype not in {"purchase_invoice", "sales_invoice"}:
        return None

    grand_total = decimal_or_zero(getattr(document, "grand_total", 0))
    outstanding = compute_outstanding_amount(document)
    if grand_total <= 0:
        return None
    if outstanding <= 0:
        return _status("paid", "Pagado", "green")
    paid = grand_total - outstanding
    if paid > 0:
        return _status("partially_paid", "Pagado Parcialmente", "blue")
    if doctype == "purchase_invoice":
        return _status("pending_payment", "Pendiente Pagar", "blue")
    return _status("pending_collection", "Pendiente Cobrar", "blue")


def _primary_flow_progress(doctype: str, document: Any) -> FlowProgress | None:
    """Devuelve el flujo operativo que debe gobernar el estado principal."""
    target_priority = {
        "purchase_order": ["purchase_receipt", "purchase_invoice"],
        "purchase_receipt": ["purchase_invoice"],
        "purchase_request": ["purchase_order", "purchase_quotation"],
        "purchase_quotation": ["supplier_quotation"],
        "supplier_quotation": ["purchase_order"],
        "sales_order": ["delivery_note", "sales_invoice"],
        "delivery_note": ["sales_invoice"],
        "sales_request": ["sales_quotation"],
        "sales_quotation": ["sales_order"],
    }
    for target_type in target_priority.get(doctype, []):
        if (doctype, target_type) not in ALLOWED_FLOWS:
            continue
        progress = _flow_progress(doctype, document.id, target_type)
        if progress and (progress.pending_qty > 0 or progress.processed_qty > 0 or progress.closed_qty > 0):
            if progress.pending_qty > 0:
                return progress
    for target_type in target_priority.get(doctype, []):
        progress = _flow_progress(doctype, document.id, target_type)
        if progress and progress.total_qty > 0:
            return progress
    return None


def _flow_progress(source_type: str, source_id: str, target_type: str) -> FlowProgress | None:
    """Calcula avance por cantidades para un flujo fuente -> destino."""
    items = get_document_items(source_type, source_id)
    if not items:
        return None
    total = Decimal("0")
    processed = Decimal("0")
    closed = Decimal("0")
    for item in items:
        qty = decimal_or_zero(getattr(item, "qty", 0))
        state = get_line_flow_state(source_type, source_id, item.id, target_type)
        total += decimal_or_zero(getattr(state, "source_qty", None) or qty)
        processed += consumed_qty_for_source(source_type, source_id, item.id, target_type)
        closed += decimal_or_zero(getattr(state, "closed_qty", 0)) if state else Decimal("0")
    pending = total - processed - closed
    if pending < 0:
        pending = Decimal("0")
    relation_type = ALLOWED_FLOWS[(source_type, target_type)].relation_type
    return FlowProgress(
        target_type=target_type,
        relation_type=relation_type,
        total_qty=total,
        processed_qty=processed,
        closed_qty=closed,
        pending_qty=pending,
    )


def _status_from_progress(progress: FlowProgress) -> DocumentStatusInfo:
    """Mapea avance operativo a un estado visible unico."""
    if progress.pending_qty == 0:
        return _status("completed", "Completado", "green")

    partial = progress.processed_qty > 0 or progress.closed_qty > 0
    match progress.relation_type:
        case "receipt":
            return (
                _status("partially_received", "Recibido Parcialmente", "blue")
                if partial
                else _status("pending_receipt", "Pendiente Recibir", "blue")
            )
        case "delivery":
            return (
                _status("partially_delivered", "Entregado Parcialmente", "blue")
                if partial
                else _status("pending_delivery", "Pendiente Entregar", "blue")
            )
        case "billing":
            return (
                _status("partially_billed", "Facturado Parcialmente", "blue")
                if partial
                else _status("pending_billing", "Pendiente Facturar", "blue")
            )
        case "payment":
            return (
                _status("partially_paid", "Pagado Parcialmente", "blue")
                if partial
                else _status("pending_payment", "Pendiente Pagar", "blue")
            )
        case _:
            return _status("completed" if not progress.pending_qty else "open", "Abierto", "blue")


def document_status_payload(document_type: str, document_or_id: Any) -> dict[str, str]:
    """Serializa el estado calculado para API JSON."""
    status = calculate_document_status(document_type, document_or_id)
    return {
        "code": status.code,
        "label": status.label,
        "full_label": status.full_label,
        "tone": status.tone,
        "badge_class": status.badge_class,
        "icon": status.icon,
    }
