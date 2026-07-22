# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""End point para peticiones realizadas vía api."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from functools import wraps
from typing import Any, cast
from urllib.parse import urlparse

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from jwt import decode
from jwt.exceptions import PyJWTError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.document_flow import (
    DocumentFlowError,
    close_document_balances,
    close_line_balance,
    create_target_document,
    get_document_flow_items,
    get_pending_lines,
    list_source_documents,
    payment_reconciliation_candidates,
    payment_reference_candidates,
)
from cacao_accounting.collaboration_service import (
    CollaborationError,
    abort_for_collaboration_error,
    add_document_comment,
    active_users,
    create_document_task,
    document_url,
    list_user_tasks,
    open_task_count,
    update_task_status,
)
from cacao_accounting.database import StockBin, database
from cacao_accounting.decorators import exige_acceso_compania
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, DocumentType, normalize_doctype
from cacao_accounting.document_flow.repository import get_document
from cacao_accounting.document_flow.service import get_source_items
from cacao_accounting.document_flow.status import _, document_status_payload
from cacao_accounting.document_flow.tracing import document_flow_tree
from cacao_accounting.document_flow.tree import build_document_flow_tree
from cacao_accounting.fiscal_preview_service import fiscal_preview
from cacao_accounting.form_preferences import get_form_preference, reset_form_preference, save_form_preference
from cacao_accounting.search_select import SearchSelectError, search_select
from cacao_accounting.api.line_import import line_import_bp
from cacao_accounting.api.dashboard import dashboard_api
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting.limiter import rate_limit_blueprint

api = Blueprint("api", __name__, template_folder="templates")
api.register_blueprint(line_import_bp)
api.register_blueprint(dashboard_api)

rate_limit_blueprint(api)
rate_limit_blueprint(line_import_bp)
rate_limit_blueprint(dashboard_api)


def _require_flow_company_access(payload: dict[str, Any], action: str = "crear") -> None:
    """Authorize document-flow mutations against the source document company."""
    source_type = normalize_doctype(str(payload.get("source_document_type") or payload.get("source_type") or ""))
    source_id = str(payload.get("source_document_id") or payload.get("source_id") or "")
    source = get_document(source_type, source_id) if source_type and source_id else None
    if not source:
        abort(404)
    module = _module_for_document_type(source_type)
    if module:
        exige_acceso_compania(module, getattr(source, "company", None), action)


def _module_for_document_type(document_type: str) -> str | None:
    """Map a document-flow type to its operational ACL module."""
    return {
        "sales_request": "sales",
        "sales_quotation": "sales",
        "sales_order": "sales",
        "delivery_note": "sales",
        "sales_invoice": "sales",
        "purchase_request": "purchases",
        "purchase_quotation": "purchases",
        "supplier_quotation": "purchases",
        "purchase_order": "purchases",
        "purchase_receipt": "purchases",
        "purchase_invoice": "purchases",
        "stock_entry": "inventory",
    }.get(document_type)


def _require_document_read_access(document_type: str, document_id: str) -> Any:
    """Load a document and enforce its company-scoped read permission."""
    normalized_type = normalize_doctype(document_type)
    document = get_document(normalized_type, document_id)
    if not document:
        abort(404)
    module = _module_for_document_type(normalized_type)
    if module:
        exige_acceso_compania(module, getattr(document, "company", None), "consultar")
    return document


def token_requerido(f):  # pragma: no cover
    """Decorador para proteger el acceso a la API vía tokens."""

    @wraps(f)
    def wrapper(*args, **kwds):
        """Protege la API con un token."""
        token = None

        if "Authorization" in request.headers:
            parts = request.headers["Authorization"].split(" ")
            if len(parts) > 1:
                token = parts[1]

        if not token:
            return {
                "message": "Authentication Token is missing!",
                "data": None,
                "error": "Unauthorized",
            }, 401

        try:
            data = decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            assert data is not None  # nosec
            user_id = data.get("user_id")

            from cacao_accounting.database import User, database

            identidad = database.session.get(User, user_id)
            if not identidad or identidad.token != token:
                return {
                    "message": "Invalid or expired Authentication token!",
                    "data": None,
                    "error": "Unauthorized",
                }, 401

            from flask_login import login_user

            if not current_user or not current_user.is_authenticated:
                login_user(identidad, remember=False, force=False)

        except (KeyError, PyJWTError) as e:
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


@api.route("/api/fiscal/preview", methods=["POST"])
@login_required
def api_fiscal_preview():
    """Devuelve preview fiscal unificado para formularios del MVP."""
    payload = request.get_json(silent=True) or {}
    try:
        result = fiscal_preview(payload)
    except ValueError as exc:
        current_app.logger.warning("Fiscal preview validation error: %s", str(exc))
        return jsonify({"error": _("No se pudo calcular el preview fiscal."), "message": _("Revise los datos enviados.")}), 400
    return jsonify(result)


@api.route("/api/documents/<document_type>/<document_id>/comments", methods=["POST"])
@login_required
def api_document_comment(document_type: str, document_id: str):
    """Add a cloud-only comment to a document timeline."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        entry = add_document_comment(
            document_type,
            document_id,
            str(payload.get("comment") or ""),
            str(current_user.id),
        )
    except CollaborationError as exc:
        abort_for_collaboration_error(exc)
    if request.form and request.referrer:
        parsed = urlparse(request.referrer)
        if parsed.netloc == "" or parsed.netloc == request.host:
            return redirect(request.referrer)
        return redirect(url_for("cacao_app.pagina_inicio"))
    return jsonify({"id": entry.id, "action": entry.action}), 201


@api.route("/api/documents/<document_type>/<document_id>/tasks", methods=["POST"])
@login_required
def api_document_task(document_type: str, document_id: str):
    """Create a cloud-only task attached to a document."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        task = create_document_task(document_type, document_id, payload, str(current_user.id))
    except CollaborationError as exc:
        abort_for_collaboration_error(exc)
    if request.form and request.referrer:
        parsed = urlparse(request.referrer)
        if parsed.netloc == "" or parsed.netloc == request.host:
            return redirect(request.referrer)
        return redirect(url_for("cacao_app.pagina_inicio"))
    return jsonify({"id": task.id, "status": task.status}), 201


@api.route("/api/tasks/<task_id>/status", methods=["POST"])
@login_required
def api_task_status(task_id: str):
    """Update a cloud-only document task status."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        task = update_task_status(task_id, str(payload.get("status") or ""), str(current_user.id))
    except CollaborationError as exc:
        abort_for_collaboration_error(exc)
    return jsonify({"id": task.id, "status": task.status})


@api.route("/tasks/my", methods=["GET", "POST"])
@login_required
def my_tasks():
    """Render the current user's cloud task inbox."""
    if is_desktop_mode():
        abort(403)
    if request.method == "POST":
        try:
            update_task_status(
                str(request.form.get("task_id") or ""),
                str(request.form.get("status") or ""),
                str(current_user.id),
            )
        except CollaborationError as exc:
            abort_for_collaboration_error(exc)

    status = request.args.get("status") or None
    priority = request.args.get("priority") or None
    company = request.args.get("company") or None
    due_date_from = _date_filter("due_date_from")
    due_date_to = _date_filter("due_date_to")
    tasks = list_user_tasks(
        str(current_user.id),
        status=status,
        priority=priority,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        company=company,
    )
    return render_template(
        "tasks/my.html",
        tasks=tasks,
        document_url=document_url,
        active_users=active_users(),
        open_task_count=open_task_count(str(current_user.id)),
        titulo=_("Mis tareas"),
    )


def _date_filter(name: str):
    value = request.args.get(name)
    if not value:
        return None
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError:
        abort(400)


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


@api.route("/api/inventory/stock-entry/<entry_id>/items")
@login_required
def api_stock_entry_items(entry_id: str):
    """Devuelve las líneas de un movimiento de inventario en formato JSON."""
    items = _source_items_or_abort("stock_entry", entry_id)
    return jsonify({"entry_id": entry_id, "items": items})


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
    if not target_type or not company:
        abort(400)
    module = _module_for_document_type(normalize_doctype(target_type))
    if module:
        exige_acceso_compania(module, company, "consultar")
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
    if not source_type or not target_type or not source_ids or not company:
        abort(400)
    module = _module_for_document_type(normalize_doctype(source_type))
    if module:
        exige_acceso_compania(module, company, "consultar")
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


@api.route("/api/document-flow/payment-reference-candidates")
@login_required
def api_document_flow_payment_reference_candidates():
    """Devuelve documentos candidatos para referencias de Payment Entry."""
    company = request.args.get("company") or request.args.get("company_id") or ""
    party_type = request.args.get("party_type") or ""
    party_id = request.args.get("party_id") or request.args.get("party") or ""
    source_types = (
        request.args.getlist("source_type") or request.args.getlist("source_types[]") or request.args.getlist("source_types")
    )
    include_orders = (request.args.get("advance_mode") or "").lower() in {"1", "true", "yes", "on"}
    if not source_types:
        abort(400)
    module = {"supplier": "purchases", "customer": "sales"}.get(party_type)
    if module:
        exige_acceso_compania(module, company, "consultar")
    try:
        candidates = payment_reference_candidates(
            company=company,
            party_type=party_type,
            party_id=party_id,
            source_types=source_types,
            include_orders=include_orders,
        )
    except DocumentFlowError as exc:
        abort(exc.status_code)
    return jsonify({"items": candidates})


@api.route("/api/document-flow/payment-reconciliation-candidates")
@login_required
def api_document_flow_payment_reconciliation_candidates():
    """Devuelve pagos abiertos y documentos pendientes para conciliacion masiva."""
    company = request.args.get("company") or request.args.get("company_id") or ""
    party_type = request.args.get("party_type") or ""
    party_id = request.args.get("party_id") or request.args.get("party") or None
    currency = request.args.get("currency") or None
    module = {"supplier": "purchases", "customer": "sales"}.get(party_type)
    if module:
        exige_acceso_compania(module, company, "consultar")
    try:
        candidates = payment_reconciliation_candidates(
            company=company,
            party_type=party_type,
            party_id=party_id,
            currency=currency,
        )
    except DocumentFlowError as exc:
        abort(exc.status_code)
    return jsonify(candidates)


@api.route("/api/inventory/stock-bin-snapshot")
@login_required
def api_inventory_stock_bin_snapshot():
    """Devuelve existencia y valuacion actual por item/bodega."""
    company = request.args.get("company") or ""
    item_code = request.args.get("item_code") or ""
    warehouse = request.args.get("warehouse") or ""
    if not company or not item_code or not warehouse:
        abort(400)
    exige_acceso_compania("inventory", company, "consultar")
    bin_row = (
        database.session.execute(
            database.select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse)
        )
        .scalars()
        .first()
    )
    return jsonify(
        {
            "item_code": item_code,
            "warehouse": warehouse,
            "company": company,
            "actual_qty": float(bin_row.actual_qty or 0) if bin_row else 0,
            "reserved_qty": float(bin_row.reserved_qty or 0) if bin_row else 0,
            "valuation_rate": float(bin_row.valuation_rate or 0) if bin_row else 0,
            "stock_value": float(bin_row.stock_value or 0) if bin_row else 0,
        }
    )


@api.route("/api/document-flow/create-target", methods=["POST"])
@login_required
def api_document_flow_create_target():
    """Crea un documento destino desde lineas fuente seleccionadas."""
    try:
        payload = request.get_json(silent=True) or {}
        _require_flow_company_access(payload, "crear")
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
    _require_flow_company_access(payload, "editar")
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
    _require_flow_company_access(payload, "editar")
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
    _require_document_read_access(document_type, document_id)
    return jsonify({"status": document_status_payload(document_type, document_id)})


@api.route("/api/document-flow/tree")
@login_required
def api_document_flow_tree():
    """Devuelve árbol recursivo upstream/downstream de un documento.

    Parámetros de query:
        document_type   Tipo documental (requerido).
        document_id     ID del documento (requerido).
        direction       ``all`` (defecto), ``upstream`` o ``downstream``.
        max_depth       Profundidad máxima (defecto 10).
        max_nodes       Número máximo de nodos (defecto 100).
        legacy          Si ``1``, usa el formato plano original de document_flow_tree.
    """
    document_type = request.args.get("document_type", "")
    document_id = request.args.get("document_id", "")
    if not document_type or not document_id:
        abort(400)
    _require_document_read_access(document_type, document_id)
    if (request.args.get("legacy") or "").lower() in {"1", "true"}:
        return jsonify(document_flow_tree(document_type, document_id))
    direction = request.args.get("direction", "all")
    if direction not in {"all", "upstream", "downstream"}:
        abort(400)
    try:
        max_depth = int(request.args.get("max_depth") or 10)
        max_nodes = int(request.args.get("max_nodes") or 100)
    except ValueError:
        abort(400)
    return jsonify(
        build_document_flow_tree(document_type, document_id, direction=direction, max_depth=max_depth, max_nodes=max_nodes)
    )


def _source_items_or_abort(source_type: str, source_id: str):
    """Get source items or abort with error status."""
    try:
        _require_document_read_access(source_type, source_id)
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

    related_doc = _require_document_read_access(related_doctype, related_id) if related_doctype and related_id else None
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


@api.route("/api/business-unit/<id_or_code>/hierarchy")
@login_required
def api_business_unit_hierarchy(id_or_code: str):
    """Devuelve la jerarquía completa de una Unidad de Negocio."""
    from cacao_accounting.database import BusinessUnit

    node = database.session.get(BusinessUnit, id_or_code)
    if not node:
        node = database.session.execute(database.select(BusinessUnit).filter_by(code=id_or_code)).scalar_one_or_none()
    if not node:
        abort(404)

    return jsonify(
        {
            "parent": {"id": node.parent.id, "code": node.parent.code, "name": node.parent.name} if node.parent else None,
            "children": [{"id": c.id, "code": c.code, "name": c.name} for c in node.children],
            "ancestors": [{"id": a.id, "code": a.code, "name": a.name} for a in node.ancestors],
            "descendants": [{"id": d.id, "code": d.code, "name": d.name} for d in node.descendants],
        }
    )


@api.route("/api/unit/<id_or_code>/hierarchy")
@login_required
def api_unit_hierarchy(id_or_code: str):
    """Devuelve la jerarquía completa de una Unidad de Negocio (Unit)."""
    from cacao_accounting.database import Unit

    node = database.session.get(Unit, id_or_code)
    if not node:
        node = database.session.execute(database.select(Unit).filter_by(code=id_or_code)).scalar_one_or_none()
    if not node:
        abort(404)

    return jsonify(
        {
            "parent": {"id": node.parent.id, "code": node.parent.code, "name": node.parent.name} if node.parent else None,
            "children": [{"id": c.id, "code": c.code, "name": c.name} for c in node.children],
            "ancestors": [{"id": a.id, "code": a.code, "name": a.name} for a in node.ancestors],
            "descendants": [{"id": d.id, "code": d.code, "name": d.name} for d in node.descendants],
        }
    )


@api.route("/api/project/<id_or_code>/hierarchy")
@login_required
def api_project_hierarchy(id_or_code: str):
    """Devuelve la jerarquía completa de un Proyecto."""
    from cacao_accounting.database import Project

    node = database.session.get(Project, id_or_code)
    if not node:
        node = database.session.execute(database.select(Project).filter_by(code=id_or_code)).scalar_one_or_none()
    if not node:
        abort(404)

    return jsonify(
        {
            "parent": {"id": node.parent.id, "code": node.parent.code, "name": node.parent.name} if node.parent else None,
            "children": [{"id": c.id, "code": c.code, "name": c.name} for c in node.children],
            "ancestors": [{"id": a.id, "code": a.code, "name": a.name} for a in node.ancestors],
            "descendants": [{"id": d.id, "code": d.code, "name": d.name} for d in node.descendants],
        }
    )
