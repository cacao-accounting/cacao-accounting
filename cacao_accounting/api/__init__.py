# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""End point para peticiones realizadas vía api."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from functools import wraps
from typing import Any, cast

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required
from jwt import decode

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.document_flow import (
    DocumentFlowError,
    close_document_balances,
    close_line_balance,
    create_target_document,
    document_flow_summary,
    get_document_flow_items,
    get_pending_lines,
    list_source_documents,
)
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, DocumentType, normalize_doctype
from cacao_accounting.document_flow.repository import get_document
from cacao_accounting.document_flow.service import get_source_items
from cacao_accounting.document_flow.status import _, document_status_payload
from cacao_accounting.document_flow.tracing import document_flow_tree
from cacao_accounting.form_preferences import get_form_preference, reset_form_preference, save_form_preference
from cacao_accounting.search_select import SearchSelectError, search_select

api = Blueprint("api", __name__, template_folder="templates")


def token_requerido(f):  # pragma: no cover
    """Decorador para proteger el acceso a la API vía tokens."""

    @wraps(f)
    def wrapper(*args, **kwds):
        """Protege la API con un token."""
        token = None

        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return {
                "message": "Authentication Token is missing!",
                "data": None,
                "error": "Unauthorized",
            }, 401

        try:
            data = decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            assert data is not None  # nosec

            if not current_user:
                return {
                    "message": "Invalid Authentication token!",
                    "data": None,
                    "error": "Unauthorized",
                }, 401

            if not current_user.is_authenticated:
                abort(403)

        except Exception as e:
            return {
                "message": "Something went wrong",
                "data": None,
                "error": str(e),
            }, 500

        return f(*args, **kwds)

    return wrapper


@api.route("/api/test")
@token_requerido
def test_appy():
    """Vista de prueba para probar el API."""
    responde_data = {
        "Response": "Holis",
    }

    return jsonify(responde_data)


@api.route("/api/search-select")
@login_required
def api_search_select():
    """Devuelve opciones para campos de seleccion asistida."""
    doctype = request.args.get("doctype", "").strip()
    query = request.args.get("q", "").strip()
    raw_limit = request.args.get("limit")
    reserved_params = {"doctype", "q", "limit"}
    filters = {
        key: request.args.getlist(key) for key in request.args if key not in reserved_params and request.args.getlist(key)
    }
    try:
        limit = int(raw_limit) if raw_limit else None
        payload = search_select(doctype=doctype, query=query, filters=filters, limit=limit)
    except ValueError as exc:
        if not isinstance(exc, SearchSelectError):
            return jsonify({"error": _("Parametro invalido."), "message": str(exc)}), 400
        return jsonify({"error": _(str(exc)), "message": _(str(exc))}), exc.status_code
    return jsonify(payload)


@api.route("/api/form-preferences/<path:form_key>/<view_key>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_form_preferences(form_key: str, view_key: str):
    """Lee, guarda o restablece preferencias de formulario del usuario actual."""
    user_id = str(current_user.id)
    if request.method == "GET":
        return jsonify(get_form_preference(user_id=user_id, form_key=form_key, view_key=view_key))
    if request.method == "DELETE":
        return jsonify(reset_form_preference(user_id=user_id, form_key=form_key, view_key=view_key))
    payload = request.get_json(silent=True) or {}
    return jsonify(save_form_preference(user_id=user_id, form_key=form_key, view_key=view_key, payload=payload))


@api.route("/api/buying/purchase-order/<order_id>/items")
@login_required
def api_purchase_order_items(order_id: str):
    """Devuelve las líneas de una orden de compra en formato JSON."""
    items = _source_items_or_abort("purchase_order", order_id)
    return jsonify({"order_id": order_id, "items": items})


@api.route("/api/sales/sales-order/<order_id>/items")
@login_required
def api_sales_order_items(order_id: str):
    """Devuelve las líneas de una orden de venta en formato JSON."""
    items = _source_items_or_abort("sales_order", order_id)
    return jsonify({"order_id": order_id, "items": items})


@api.route("/api/sales/sales-request/<request_id>/items")
@login_required
def api_sales_request_items(request_id: str):
    """Devuelve las líneas de un pedido de venta en formato JSON."""
    items = _source_items_or_abort("sales_request", request_id)
    return jsonify({"request_id": request_id, "items": items})


@api.route("/api/sales/sales-quotation/<quotation_id>/items")
@login_required
def api_sales_quotation_items(quotation_id: str):
    """Devuelve las líneas de una cotización de venta en formato JSON."""
    items = _source_items_or_abort("sales_quotation", quotation_id)
    return jsonify({"quotation_id": quotation_id, "items": items})


@api.route("/api/buying/purchase-receipt/<receipt_id>/items")
@login_required
def api_purchase_receipt_items(receipt_id: str):
    """Devuelve las líneas de una recepción de compra en formato JSON."""
    items = _source_items_or_abort("purchase_receipt", receipt_id)
    return jsonify({"receipt_id": receipt_id, "items": items})


@api.route("/api/sales/delivery-note/<note_id>/items")
@login_required
def api_delivery_note_items(note_id: str):
    """Devuelve las líneas de una nota de entrega en formato JSON."""
    items = _source_items_or_abort("delivery_note", note_id)
    return jsonify({"note_id": note_id, "items": items})


@api.route("/api/buying/purchase-invoice/<invoice_id>/items")
@login_required
def api_purchase_invoice_items(invoice_id: str):
    """Devuelve las líneas de una factura de compra en formato JSON."""
    items = _source_items_or_abort("purchase_invoice", invoice_id)
    return jsonify({"invoice_id": invoice_id, "items": items})


@api.route("/api/sales/sales-invoice/<invoice_id>/items")
@login_required
def api_sales_invoice_items(invoice_id: str):
    """Devuelve las líneas de una factura de venta en formato JSON."""
    items = _source_items_or_abort("sales_invoice", invoice_id)
    return jsonify({"invoice_id": invoice_id, "items": items})


@api.route("/api/document-flow/items")
@login_required
def api_document_flow_items():
    """Devuelve lineas pendientes para uno o mas documentos origen."""
    target_type = request.args.get("target_type", "")
    sources = request.args.getlist("source")
    if not target_type or not sources:
        abort(400)
    try:
        items = get_document_flow_items(target_type, sources)
    except DocumentFlowError as exc:
        abort(exc.status_code)
    return jsonify({"target_type": target_type, "items": items})


@api.route("/api/document-flow/source-documents")
@login_required
def api_document_flow_source_documents():
    """Devuelve documentos fuente disponibles para un tipo destino."""
    target_type = request.args.get("target_document_type") or request.args.get("target_type") or ""
    company = request.args.get("company") or request.args.get("company_id")
    party_type = request.args.get("party_type")
    party_id = request.args.get("party_id") or request.args.get("party")
    if not target_type:
        abort(400)
    try:
        sources = list_source_documents(
            target_type=target_type,
            company=company,
            party_type=party_type,
            party_id=party_id,
        )
    except (DocumentFlowError, KeyError):
        abort(400)
    return jsonify({"target_type": target_type, "source_documents": sources})


@api.route("/api/document-flow/pending-lines")
@login_required
def api_document_flow_pending_lines():
    """Devuelve lineas pendientes desde uno o varios documentos fuente."""
    source_type = request.args.get("source_document_type") or request.args.get("source_type") or ""
    target_type = request.args.get("target_document_type") or request.args.get("target_type") or ""
    source_ids = request.args.getlist("source_document_ids[]") or request.args.getlist("source_document_ids")
    source_ids = source_ids or request.args.getlist("source_id")
    company = request.args.get("company") or request.args.get("company_id")
    if not source_type or not target_type or not source_ids:
        abort(400)
    try:
        lines = get_pending_lines(
            source_document_type=source_type,
            source_document_ids=source_ids,
            target_document_type=target_type,
            company=company,
        )
    except DocumentFlowError as exc:
        abort(exc.status_code)
    return jsonify({"target_type": target_type, "items": lines})


@api.route("/api/document-flow/create-target", methods=["POST"])
@login_required
def api_document_flow_create_target():
    """Crea un documento destino desde lineas fuente seleccionadas."""
    try:
        payload = request.get_json(silent=True) or {}
        result = create_target_document(payload)
    except DocumentFlowError as exc:
        abort(exc.status_code)
    except KeyError:
        abort(400)
    return jsonify(result), 201


@api.route("/api/document-flow/close-line", methods=["POST"])
@login_required
def api_document_flow_close_line():
    """Cierra manualmente el saldo de una linea fuente."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        state = close_line_balance(
            source_type=str(payload.get("source_document_type") or payload.get("source_type") or ""),
            source_id=str(payload.get("source_document_id") or payload.get("source_id") or ""),
            source_item_id=str(payload.get("source_row_id") or payload.get("source_item_id") or ""),
            target_type=str(payload.get("target_document_type") or payload.get("target_type") or ""),
            qty=payload.get("qty"),
            reason=str(payload.get("reason") or ""),
        )
    except DocumentFlowError as exc:
        abort(exc.status_code)
    return jsonify({"state": state})


@api.route("/api/document-flow/close-document", methods=["POST"])
@login_required
def api_document_flow_close_document():
    """Cierra saldos pendientes de un documento fuente completo."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        states = close_document_balances(
            source_type=str(payload.get("source_document_type") or payload.get("source_type") or ""),
            source_id=str(payload.get("source_document_id") or payload.get("source_id") or ""),
            target_type=str(payload.get("target_document_type") or payload.get("target_type") or ""),
            reason=str(payload.get("reason") or ""),
        )
    except DocumentFlowError as exc:
        abort(exc.status_code)
    return jsonify({"states": states})


@api.route("/api/document-flow/recalculate-status/<document_type>/<document_id>", methods=["POST"])
@login_required
def api_document_flow_recalculate_status(document_type: str, document_id: str):
    """Devuelve el estado documental calculado."""
    return jsonify({"status": document_status_payload(document_type, document_id)})


@api.route("/api/document-flow/tree")
@login_required
def api_document_flow_tree():
    """Devuelve trazabilidad upstream/downstream de un documento."""
    document_type = request.args.get("document_type", "")
    document_id = request.args.get("document_id", "")
    if not document_type or not document_id:
        abort(400)
    return jsonify(document_flow_tree(document_type, document_id))


@api.route("/api/document-flow/summary")
@login_required
def api_document_flow_summary():
    """Devuelve resumen agrupado por tipo documental de relaciones de un documento."""
    document_type = request.args.get("document_type", "")
    document_id = request.args.get("document_id", "")
    if not document_type or not document_id:
        abort(400)
    return jsonify(document_flow_summary(document_type, document_id))


def _source_items_or_abort(source_type: str, source_id: str):
    """Helper para endpoints legacy de items por documento."""
    try:
        return get_source_items(source_type, source_id, request.args.get("target_type"))
    except DocumentFlowError as exc:
        abort(exc.status_code)


@api.route("/document-flow/list/<doctype>")
@login_required
def document_flow_related_list(doctype: str):
    """Muestra una lista de documentos filtrada por relacion documental."""
    from cacao_accounting.database import DocumentRelation, database

    doctype_key = normalize_doctype(doctype)
    spec = DOCUMENT_TYPES.get(doctype_key)
    if not spec:
        abort(404)
    spec = cast(DocumentType, spec)

    related_doctype = normalize_doctype(request.args.get("related_doctype", ""))
    related_id = request.args.get("related_id", "")

    related_doc = get_document(related_doctype, related_id) if related_doctype and related_id else None
    related_no = getattr(related_doc, "document_no", related_id) if related_doc else related_id

    related_spec = DOCUMENT_TYPES.get(related_doctype, None)
    related_label = related_spec.label if related_spec and related_spec.label else related_doctype

    target_ids: list[str] = []
    if related_doctype and related_id:
        rows_as_target = (
            database.session.execute(
                database.select(DocumentRelation.target_id)
                .filter_by(source_type=related_doctype, source_id=related_id, target_type=doctype_key)
                .distinct()
            )
            .scalars()
            .all()
        )
        rows_as_source = (
            database.session.execute(
                database.select(DocumentRelation.source_id)
                .filter_by(target_type=related_doctype, target_id=related_id, source_type=doctype_key)
                .distinct()
            )
            .scalars()
            .all()
        )
        target_ids = list(set(rows_as_target) | set(rows_as_source))

    documents: list[Any] = []
    if target_ids:
        pk_col = getattr(spec.header_model, "id", None)
        if pk_col is not None:
            documents = list(
                database.session.execute(database.select(spec.header_model).where(pk_col.in_(target_ids))).scalars().all()
            )

    return render_template(
        "document_flow_related_list.html",
        spec=spec,
        documents=documents,
        related_doctype=related_doctype,
        related_id=related_id,
        related_no=related_no,
        related_label=related_label,
        titulo=f"Documentos relacionados — {spec.label}",
    )
