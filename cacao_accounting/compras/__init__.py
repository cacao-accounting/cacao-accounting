# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Compras."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
import json
from datetime import date
from decimal import Decimal
from logging import getLogger
from typing import Any

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from cacao_accounting.exceptions import flash_error
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.compras.purchase_reconciliation_service import (
    get_purchase_reconciliation_panel_groups,
    get_purchase_reconciliation_pending,
)
from cacao_accounting.database import (
    CompanyParty,
    DocumentRelation,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseRequest,
    PurchaseRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    database,
)

# Librerias de terceros
from ulid import ULID

# Recursos locales
from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_create, log_submit, log_update
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.decorators import modulo_activo, verifica_acceso as verifica_acceso  # noqa: F401
from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
    document_flow_summary,
    refresh_source_caches_for_target,
    revert_relations_for_target,
    validate_submit_prerequisites,
)
from cacao_accounting.document_flow.repository import consumed_qty_for_source, has_active_source_relations
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.fiscal_persistence_service import persist_document_fiscal_snapshot
from cacao_accounting.list_filters import apply_list_filters
from cacao_accounting.party_management import (  # noqa: F401
    apply_party_group,
    apply_party_profile,
    build_party_detail_context,
    create_party_address,
    create_party_contact,
    deactivate_party_address,
    deactivate_party_contact,
    generate_party_code,
    party_group_label,
    toggle_party_customer_role,
    toggle_party_supplier_role as toggle_party_supplier_role,  # noqa: F401
    PartyRoleToggleError,
    update_party_address,
    update_party_contact,
)
from cacao_accounting.party_settings import (
    draft_party_company_settings_rows,
    party_company_settings_rows,
    upsert_party_company_settings_rows,
)
from cacao_accounting.version import APPNAME

logger = getLogger(__name__)

# < --------------------------------------------------------------------------------------------- >
compras = Blueprint("compras", __name__, template_folder="templates")

PURCHASE_INVOICE = "purchase_invoice"
PURCHASE_DEBIT_NOTE = "purchase_debit_note"
PURCHASE_CREDIT_NOTE = "purchase_credit_note"
PURCHASE_RETURN = "purchase_return"

FACTURA_DE_COMPRA = "Factura de Compra"
COMPRAS_FACTURA_COMPRA_DEVOLUCION_LISTA_HTML = "compras/factura_compra_devolucion_lista.html"
COMPRAS_PROVEEDOR_NUEVO_TEMPLATE = "compras/proveedor_nuevo.html"
COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO = "compras.compras_factura_compra_nuevo"
COMPRAS_COMPRAS_ORDEN_COMPRA = "compras.compras_orden_compra"
COMPRAS_COMPRAS_RECEPCION = "compras.compras_recepcion"
COMPRAS_COMPRAS_FACTURA_COMPRA = "compras.compras_factura_compra"

FORMKEY_PURCHASE_REQUEST = "purchases.purchase_request"
FORMKEY_SUPPLIER_QUOTATION = "purchases.supplier_quotation"
FORMKEY_PURCHASE_ORDER = "purchases.purchase_order"
FORMKEY_PURCHASE_QUOTATION = "purchases.purchase_quotation"
FORMKEY_PURCHASE_RECEIPT = "purchases.purchase_receipt"
FORMKEY_PURCHASE_INVOICE = "purchases.purchase_invoice"
ROUTE_COMPRAS_SOLICITUD_COMPRA = "compras.compras_solicitud_compra"
ROUTE_COMPRAS_SOLICITUD_COTIZACION = "compras.compras_solicitud_cotizacion"
ROUTE_COMPRAS_COTIZACION_PROVEEDOR = "compras.compras_cotizacion_proveedor"
ROUTE_COMPRAS_PROVEEDOR = "compras.compras_proveedor"
LABEL_SOLICITUD_COMPRA = "Solicitud de Compra"
LABEL_SOLICITUD_COTIZACION = "Solicitud de Cotización"
LABEL_ORDEN_COMPRA = "Orden de Compra"
LABEL_FACTURA_COMPRA_LONG = "Factura de Compra"

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    PURCHASE_INVOICE: FACTURA_DE_COMPRA,
    PURCHASE_DEBIT_NOTE: "Nota de Débito de Compra",
    PURCHASE_CREDIT_NOTE: "Nota de Crédito de Compra",
    PURCHASE_RETURN: "Devolución de Compra",
}


def _parse_date(value: str | None) -> date | None:
    """Parsea una fecha en formato ISO."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return [("", "")]

    return [("", "")] + [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


def _party_or_404(party_id: str) -> Party:
    """Obtiene un tercero por tipo o aborta."""
    party = database.session.execute(database.select(Party).filter_by(id=party_id, is_supplier=True)).scalar_one_or_none()
    if not party:
        abort(404)
    return party


def _paginate_list(model, search_fields, query=None, *, include_status: bool = True):
    """Pagina un listado aplicando los filtros GET comunes."""
    base_query = query if query is not None else database.select(model)
    filtered_query = apply_list_filters(base_query, model, search_fields, include_status=include_status)
    return database.paginate(
        filtered_query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )


@compras.route("/")
@compras.route("/compras")
@compras.route("/buying")
@modulo_activo("purchases")
@login_required
def compras_():
    """Pantalla principal del modulo de compras."""
    return render_template("compras.html")


@compras.route("/purchase-order/list")
@modulo_activo("purchases")
@login_required
def compras_orden_compra_lista():
    """Listado de ordenes de compra."""
    consulta = _paginate_list(
        PurchaseOrder,
        (PurchaseOrder.document_no, PurchaseOrder.supplier_name, PurchaseOrder.supplier_invoice_no, PurchaseOrder.remarks),
    )
    titulo = "Listado de Ordenes de Compra - " + APPNAME
    return render_template("compras/orden_compra_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-request/list")
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_lista():
    """Listado de solicitudes de compra internas."""
    consulta = _paginate_list(
        PurchaseRequest,
        (PurchaseRequest.document_no, PurchaseRequest.requested_by, PurchaseRequest.department, PurchaseRequest.remarks),
    )
    titulo = "Listado de Solicitudes de Compra - " + APPNAME
    return render_template("compras/solicitud_compra_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-request/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_nueva():
    """Formulario para crear una solicitud de compra interna."""
    from cacao_accounting.compras.forms import FormularioSolicitudCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioSolicitudCompra()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    from cacao_accounting.form_preferences import get_column_preferences

    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("purchase_request", selected_company)
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Solicitud de Compra - " + APPNAME
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_REQUEST,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_REQUEST),
        "availableSourceTypes": [],
    }
    if request.method == "POST":
        try:
            posting_date = _parse_date(request.form.get("posting_date"))
            solicitud = PurchaseRequest(
                requested_by=request.form.get("requested_by"),
                department=request.form.get("department"),
                company=request.form.get("company") or None,
                posting_date=posting_date,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(solicitud)
            database.session.flush()
            assign_document_identifier(
                document=solicitud,
                entity_type="purchase_request",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _qty, total = _save_purchase_request_items(solicitud.id)
            solicitud.total = total
            solicitud.base_total = total
            solicitud.grand_total = total
            log_create(solicitud)
            database.session.commit()
            flash("Solicitud de compra creada correctamente.", "success")
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=solicitud.id))
        except (IdentifierConfigurationError, DocumentFlowError) as exc:
            database.session.rollback()
            flash_error(exc)
    return render_template(
        "compras/solicitud_compra_nueva.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/purchase-request/<request_id>")
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra(request_id: str):
    """Detalle de solicitud de compra."""
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    items = database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=request_id)).all()
    create_actions = document_flow_summary("purchase_request", request_id).get("create_actions", [])
    create_actions_json = json.dumps(create_actions, ensure_ascii=False)
    titulo = (registro.document_no or request_id) + " - " + APPNAME
    return render_template(
        "compras/solicitud_compra.html",
        registro=registro,
        items=items,
        titulo=titulo,
        create_actions_json=create_actions_json,
    )


@compras.route("/purchase-request/<request_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_editar(request_id: str):
    """Edita una solicitud de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioSolicitudCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioSolicitudCompra(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("purchase_request", selected_company)
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        try:
            before_state = _capture_purchase_state(registro)
            registro.requested_by = request.form.get("requested_by")
            registro.department = request.form.get("department")
            registro.company = request.form.get("company") or None
            registro.posting_date = _parse_date(request.form.get("posting_date"))
            registro.remarks = request.form.get("remarks")
            for item in database.session.execute(
                database.select(PurchaseRequestItem).filter_by(purchase_request_id=registro.id)
            ).scalars():
                database.session.delete(item)
            _qty, total = _save_purchase_request_items(registro.id)
            registro.total = total
            registro.base_total = total
            registro.grand_total = total
            after_state = _capture_purchase_state(registro)
            log_update(registro, before=before_state, after=after_state)
            database.session.commit()
            flash("Solicitud de compra actualizada correctamente.", "success")
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=registro.id))
        except (IdentifierConfigurationError, DocumentFlowError) as exc:
            database.session.rollback()
            flash_error(exc)

    lineas = database.session.execute(
        database.select(PurchaseRequestItem).filter_by(purchase_request_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_REQUEST,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_REQUEST),
        "availableSourceTypes": [],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
            }
            for item in lineas
        ],
    }
    return render_template(
        "compras/solicitud_compra_nueva.html",
        form=formulario,
        titulo="Editar Solicitud de Compra - " + APPNAME,
        edit=True,
        registro=registro,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/purchase-request/<request_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_duplicar(request_id: str):
    """Duplica una solicitud de compra como borrador nuevo."""
    origen = database.session.get(PurchaseRequest, request_id)
    if not origen:
        abort(404)
    duplicada = PurchaseRequest(
        requested_by=origen.requested_by,
        department=origen.department,
        company=origen.company,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicada)
    database.session.flush()
    assign_document_identifier(
        document=duplicada,
        entity_type="purchase_request",
        posting_date_raw=duplicada.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(
        database.select(PurchaseRequestItem).filter_by(purchase_request_id=origen.id)
    ).scalars():
        linea = PurchaseRequestItem(
            purchase_request_id=duplicada.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
    log_create(duplicada)
    database.session.commit()
    flash("Solicitud de compra duplicada como nuevo borrador.", "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=duplicada.id))


@compras.route("/purchase-request/<request_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_submit(request_id: str):
    """Aprueba una solicitud de compra.

    ``require_party=False`` es intencional: una solicitud de compra interna
    puede aprobarse sin proveedor asignado. El proveedor se asigna al
    convertir en cotización u orden de compra.
    """
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=False, require_rate_positive=True)
        check_budget_control(
            company=registro.company,
            posting_date=registro.posting_date,
            supplier_id=None,
            document_id=registro.id,
            document_type="purchase_request",
            items=items
        )
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    flash("Solicitud de compra aprobada.", "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))


@compras.route("/purchase-request/<request_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_cancel(request_id: str):
    """Cancela una solicitud de compra."""
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_request", request_id):
        flash("No se puede cancelar la solicitud de compra porque tiene órdenes de compra o cotizaciones activas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("purchase_request", request_id)
    refresh_source_caches_for_target("purchase_request", request_id)
    database.session.commit()
    flash("Solicitud de compra cancelada.", "warning")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))


@compras.route("/supplier-quotation/list")
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_lista():
    """Listado de cotizaciones de proveedor."""
    consulta = _paginate_list(
        SupplierQuotation,
        (SupplierQuotation.document_no, SupplierQuotation.supplier_name, SupplierQuotation.remarks),
    )
    titulo = "Listado de Cotizaciones de Proveedor - " + APPNAME
    return render_template("compras/cotizacion_proveedor_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/supplier-quotation/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_nueva():
    """Formulario para crear una cotización de proveedor."""
    from cacao_accounting.compras.forms import FormularioCotizacionProveedor
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioCotizacionProveedor()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = _supplier_quotation_selected_company(formulario.company.choices)
    formulario.naming_series.choices = _series_choices("supplier_quotation", selected_company)
    formulario.supplier_id.choices = _supplier_quotation_supplier_choices()
    if request.method == "POST":
        response = _create_supplier_quotation_from_request()
        if response is not None:
            return response
    from_request_id, from_rfq_id = _supplier_quotation_origin_ids()
    solicitud_origen, rfq_origen = _supplier_quotation_sources(from_request_id, from_rfq_id)
    items_disponibles, uoms_disponibles = _supplier_quotation_catalogs()
    titulo = "Nueva Cotización de Proveedor - " + APPNAME
    transaction_config = _supplier_quotation_transaction_config(
        form_key=FORMKEY_SUPPLIER_QUOTATION,
        items=items_disponibles,
        uoms=uoms_disponibles,
        initial_source_type=_supplier_quotation_initial_source_type(from_request_id, from_rfq_id),
    )
    return render_template(
        "compras/cotizacion_proveedor_nueva.html",
        form=formulario,
        titulo=titulo,
        solicitud_origen=solicitud_origen,
        from_request_id=from_request_id,
        rfq_origen=rfq_origen,
        from_rfq_id=from_rfq_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


def _supplier_quotation_origin_ids() -> tuple[str | None, str | None]:
    """Obtiene los identificadores de origen para la cotizacion de proveedor."""
    from_request_id = request.args.get("from_request") or request.form.get("from_request")
    from_rfq_id = request.args.get("from_rfq") or request.form.get("from_rfq")
    return from_request_id, from_rfq_id


def _create_supplier_quotation_from_request():
    """Crea una cotizacion de proveedor a partir del formulario enviado."""
    try:
        _, from_rfq_id = _supplier_quotation_origin_ids()
        supplier_id = request.form.get("supplier_id") or None
        supplier = database.session.get(Party, supplier_id) if supplier_id else None
        posting_date = _parse_date(request.form.get("posting_date"))
        cotizacion = SupplierQuotation(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            purchase_quotation_id=from_rfq_id or None,
            company=request.form.get("company") or None,
            posting_date=posting_date,
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        database.session.add(cotizacion)
        database.session.flush()
        assign_document_identifier(
            document=cotizacion,
            entity_type="supplier_quotation",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _qty, total = _save_supplier_quotation_items(cotizacion.id)
        cotizacion.total = total
        cotizacion.base_total = total
        cotizacion.grand_total = total
        log_create(cotizacion)
        database.session.commit()
        flash("Cotización de proveedor creada correctamente.", "success")
        return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=cotizacion.id))
    except (IdentifierConfigurationError, DocumentFlowError) as exc:
        database.session.rollback()
        flash_error(exc)
    return None


@compras.route("/supplier-quotation/<quotation_id>")
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor(quotation_id: str):
    """Detalle de una cotización de proveedor."""
    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    items = database.session.execute(
        database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=quotation_id)
    ).all()
    titulo = (registro.document_no or quotation_id) + " - " + APPNAME
    return render_template("compras/cotizacion_proveedor.html", registro=registro, items=items, titulo=titulo)


@compras.route("/supplier-quotation/<quotation_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_editar(quotation_id: str):
    """Edita una cotizacion de proveedor en borrador."""
    from cacao_accounting.compras.forms import FormularioCotizacionProveedor
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioCotizacionProveedor(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("supplier_quotation", selected_company)
    formulario.supplier_id.choices = _supplier_quotation_supplier_choices()
    items_disponibles, uoms_disponibles = _supplier_quotation_catalogs()

    if request.method == "POST":
        return _handle_supplier_quotation_update(registro, request.form, quotation_id)

    lineas = database.session.execute(
        database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=registro.id)
    ).scalars()
    transaction_config = _supplier_quotation_transaction_config(
        form_key=FORMKEY_SUPPLIER_QUOTATION,
        items=items_disponibles,
        uoms=uoms_disponibles,
        initial_source_type="purchase_quotation",
        initial_header={
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.supplier_id or "",
            "party_label": registro.supplier_name or "",
        },
        initial_lines=[
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
            }
            for item in lineas
        ],
        available_source_types=[{"value": "purchase_quotation", "label": _(LABEL_SOLICITUD_COTIZACION)}],
    )
    return render_template(
        "compras/cotizacion_proveedor_nueva.html",
        form=formulario,
        titulo="Editar Cotizacion de Proveedor - " + APPNAME,
        edit=True,
        registro=registro,
        rfq_origen=None,
        from_rfq_id=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


def _supplier_quotation_selected_company(choices: list[tuple[str, str]]) -> str | None:
    """Resuelve la compañía seleccionada para la cotización de proveedor."""
    return request.values.get("company") or (choices[0][0] if choices else None)


def _purchase_quotation_selected_company(choices: list[tuple[str, str]]) -> str | None:
    """Resuelve la compañía seleccionada para la solicitud de cotización."""
    return request.values.get("company") or (choices[0][0] if choices else None)


def _supplier_quotation_supplier_choices() -> list[tuple[str, str]]:
    """Construye el listado de proveedores para el formulario."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _supplier_quotation_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Carga catálogos reutilizados por la cotización de proveedor."""
    items_disponibles = [
        {"code": item[0].code, "name": item[0].name, "uom": item[0].default_uom}
        for item in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [
        {"code": uom[0].code, "name": uom[0].name} for uom in database.session.execute(database.select(UOM)).all()
    ]
    return items_disponibles, uoms_disponibles


def _supplier_quotation_transaction_config(
    *,
    form_key: str,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    initial_source_type: str,
    initial_header: dict[str, str] | None = None,
    initial_lines: list[dict[str, str]] | None = None,
    available_source_types: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """Construye la configuración transaccional compartida de cotización."""
    from cacao_accounting.form_preferences import get_column_preferences

    transaction_config: dict[str, object] = {
        "formKey": form_key,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "columns": get_column_preferences(current_user.id, form_key),
        "availableSourceTypes": available_source_types
        or [
            {"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)},
            {"value": "purchase_quotation", "label": _(LABEL_SOLICITUD_COTIZACION)},
        ],
        "initialSourceType": initial_source_type,
    }
    if initial_header:
        transaction_config["initialHeader"] = initial_header
    if initial_lines:
        transaction_config["initialLines"] = initial_lines
    return transaction_config


def _supplier_quotation_initial_source_type(from_request_id: str | None, from_rfq_id: str | None) -> str:
    """Resolve the initial source type for supplier quotations."""
    if from_request_id:
        return "purchase_request"
    if from_rfq_id:
        return "purchase_quotation"
    return ""


def _supplier_quotation_sources(
    from_request_id: str | None,
    from_rfq_id: str | None,
) -> tuple[PurchaseRequest | None, PurchaseQuotation | None]:
    """Resuelve los documentos origen de la cotización de proveedor."""
    solicitud_origen = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
    rfq_origen = database.session.get(PurchaseQuotation, from_rfq_id) if from_rfq_id else None
    return solicitud_origen, rfq_origen


def _handle_supplier_quotation_update(registro: SupplierQuotation, form: dict, quotation_id: str):
    """Maneja la actualizacion de una cotizacion de proveedor desde el formulario POST."""
    before_state = _capture_purchase_state(registro)
    supplier_id = form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = form.get("company") or None
    registro.posting_date = _parse_date(form.get("posting_date"))
    registro.remarks = form.get("remarks")
    for item in database.session.execute(
        database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _qty, total = _save_supplier_quotation_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Cotizacion de proveedor actualizada correctamente."), "success")
    return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))


def _handle_supplier_create(
    form: dict,
    selected_company: str | None,
    company_choices: list,
    formulario: Any,
    titulo: str,
):
    """Maneja la creacion de un nuevo proveedor desde el formulario POST."""
    proveedor = Party(
        code=str(ULID()),
        is_supplier=True,
        name=form.get("name") or "",
        comercial_name=form.get("comercial_name"),
        tax_id=form.get("tax_id"),
        is_active=form.get("is_active", "on") is not None,
    )
    try:
        database.session.add(proveedor)
        apply_party_group(proveedor, form.get("party_group_id") or None, role="supplier")
        apply_party_profile(proveedor, form)
        database.session.flush()
        proveedor.code = generate_party_code(proveedor.id, selected_company, "supplier")
        upsert_party_company_settings_rows(proveedor.id, "supplier", form)
        database.session.commit()
        return redirect("/buying/supplier/list")
    except ValueError as exc:
        database.session.rollback()
        company_settings_rows = draft_party_company_settings_rows("supplier", form)
        flash_error(exc)
    return render_template(
        COMPRAS_PROVEEDOR_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(form.get("party_group_id") or None),
    )


def _handle_supplier_update(
    proveedor: Party,
    form: dict,
    selected_company: str | None,
    company_choices: list,
    formulario: Any,
    titulo: str,
):
    """Maneja la actualizacion de un proveedor existente desde el formulario POST."""
    try:
        proveedor.name = form.get("name") or ""
        proveedor.comercial_name = form.get("comercial_name") or None
        proveedor.tax_id = form.get("tax_id") or None
        proveedor.is_active = form.get("is_active") is not None
        apply_party_group(proveedor, form.get("party_group_id") or None, role="supplier")
        apply_party_profile(proveedor, form)
        upsert_party_company_settings_rows(proveedor.id, "supplier", form)
        database.session.commit()
        flash(_("Proveedor actualizado correctamente."), "success")
        return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=proveedor.id))
    except ValueError as exc:
        database.session.rollback()
        company_settings_rows = draft_party_company_settings_rows("supplier", form)
        flash_error(exc)
    return render_template(
        COMPRAS_PROVEEDOR_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        edit=True,
        registro=proveedor,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(proveedor.party_group_id),
    )


@compras.route("/supplier-quotation/<quotation_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_duplicar(quotation_id: str):
    """Duplica una cotizacion de proveedor como borrador nuevo."""
    origen = database.session.get(SupplierQuotation, quotation_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicada = SupplierQuotation(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        purchase_quotation_id=None,
        company=origen.company,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicada)
    database.session.flush()
    assign_document_identifier(
        document=duplicada,
        entity_type="supplier_quotation",
        posting_date_raw=duplicada.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(
        database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=origen.id)
    ).scalars():
        linea = SupplierQuotationItem(
            supplier_quotation_id=duplicada.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
    log_create(duplicada)
    database.session.commit()
    flash(_("Cotizacion de proveedor duplicada como nuevo borrador."), "success")
    return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=duplicada.id))


@compras.route("/supplier-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_submit(quotation_id: str):
    """Aprueba una cotizacion de proveedor."""
    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True, require_rate_positive=True)
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))
    flash(_("Cotizacion de proveedor aprobada."), "success")
    return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))


@compras.route("/supplier-quotation/<quotation_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_cancel(quotation_id: str):
    """Cancela una cotizacion de proveedor."""
    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("supplier_quotation", quotation_id):
        flash("No se puede cancelar la cotización de proveedor porque tiene solicitudes de cotización activas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("supplier_quotation", quotation_id)
    refresh_source_caches_for_target("supplier_quotation", quotation_id)
    database.session.commit()
    flash(_("Cotizacion de proveedor cancelada."), "warning")
    return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))


@compras.route("/request-for-quotation/comparison")
@modulo_activo("purchases")
@login_required
def compras_comparativo_ofertas_lista():
    """Listado de comparativos de ofertas para solicitudes de cotización."""
    consulta = _paginate_list(
        PurchaseQuotation,
        (PurchaseQuotation.document_no, PurchaseQuotation.supplier_name, PurchaseQuotation.remarks),
    )
    titulo = "Comparativo de Ofertas - " + APPNAME
    return render_template("compras/comparativo_ofertas_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/request-for-quotation/<rfq_id>/offers")
@modulo_activo("purchases")
@login_required
def compras_comparativo_ofertas(rfq_id: str):
    """Comparativo de ofertas para una solicitud de cotización específica."""
    registro = database.session.get(PurchaseQuotation, rfq_id)
    if not registro:
        abort(404)
    offers = database.session.execute(database.select(SupplierQuotation).filter_by(purchase_quotation_id=rfq_id)).all()
    titulo = "Comparativo de Ofertas - " + (registro.document_no or rfq_id)
    return render_template("compras/comparativo_ofertas.html", registro=registro, offers=offers, titulo=titulo)


@compras.route("/purchase-receipt/list")
@modulo_activo("purchases")
@login_required
def compras_recepcion_lista():
    """Listado de recepciones de compra."""
    consulta = _paginate_list(
        PurchaseReceipt,
        (PurchaseReceipt.document_no, PurchaseReceipt.supplier_name, PurchaseReceipt.remarks),
    )
    titulo = "Listado de Recepciones de Compra - " + APPNAME
    return render_template("compras/recepcion_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-invoice/list")
@modulo_activo("purchases")
@login_required
def compras_factura_compra_lista():
    """Listado de facturas de compra."""
    consulta = _paginate_list(
        PurchaseInvoice,
        (
            PurchaseInvoice.document_no,
            PurchaseInvoice.supplier_name,
            PurchaseInvoice.supplier_invoice_no,
            PurchaseInvoice.remarks,
        ),
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_INVOICE),
    )
    titulo = "Listado de Facturas de Compra - " + APPNAME
    return render_template("compras/factura_compra_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-invoice/debit-note/list")
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nota_debito_lista():
    """Listado de notas de débito de compra."""
    consulta = _paginate_list(
        PurchaseInvoice,
        (
            PurchaseInvoice.document_no,
            PurchaseInvoice.supplier_name,
            PurchaseInvoice.supplier_invoice_no,
            PurchaseInvoice.remarks,
        ),
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_DEBIT_NOTE),
    )
    titulo = "Listado de Notas de Débito de Compra - " + APPNAME
    return render_template(
        COMPRAS_FACTURA_COMPRA_DEVOLUCION_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Notas de Débito de Compra",
        new_button_label="Nueva Nota de Débito",
        page_caption="Listado de notas de débito de compra.",
        new_document_type=PURCHASE_DEBIT_NOTE,
    )


@compras.route("/purchase-invoice/credit-note/list")
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nota_credito_lista():
    """Listado de notas de crédito de compra."""
    consulta = _paginate_list(
        PurchaseInvoice,
        (
            PurchaseInvoice.document_no,
            PurchaseInvoice.supplier_name,
            PurchaseInvoice.supplier_invoice_no,
            PurchaseInvoice.remarks,
        ),
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_CREDIT_NOTE),
    )
    titulo = "Listado de Notas de Crédito de Compra - " + APPNAME
    return render_template(
        COMPRAS_FACTURA_COMPRA_DEVOLUCION_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Notas de Crédito de Compra",
        new_button_label="Nueva Nota de Crédito",
        page_caption="Listado de notas de crédito de compra.",
        new_document_type=PURCHASE_CREDIT_NOTE,
    )


@compras.route("/purchase-invoice/return/list")
@modulo_activo("purchases")
@login_required
def compras_factura_compra_devolucion_lista():
    """Listado de devoluciones de compra."""
    consulta = _paginate_list(
        PurchaseInvoice,
        (
            PurchaseInvoice.document_no,
            PurchaseInvoice.supplier_name,
            PurchaseInvoice.supplier_invoice_no,
            PurchaseInvoice.remarks,
        ),
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_RETURN),
    )
    titulo = "Listado de Devoluciones de Compra - " + APPNAME
    return render_template(
        COMPRAS_FACTURA_COMPRA_DEVOLUCION_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Devoluciones de Compra",
        new_button_label="Nueva Devolución",
        page_caption="Listado de devoluciones de compra.",
        new_document_type=PURCHASE_RETURN,
    )


@compras.route("/purchase-invoice/debit-note/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nota_debito_nueva():
    """Alias explicito para crear nota de débito de compra."""
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO, document_type=PURCHASE_DEBIT_NOTE))


@compras.route("/purchase-invoice/credit-note/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nota_credito_nueva():
    """Alias explicito para crear nota de crédito de compra."""
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO, document_type=PURCHASE_CREDIT_NOTE))


@compras.route("/purchase-invoice/return/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_devolucion_nueva():
    """Alias explicito para crear devolución de compra."""
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO, document_type=PURCHASE_RETURN))


@compras.route("/supplier/list")
@modulo_activo("purchases")
@login_required
def compras_proveedor_lista():
    """Listado de proveedores."""
    consulta = _paginate_list(
        Party,
        (Party.code, Party.name, Party.comercial_name, Party.tax_id),
        database.select(Party).filter(Party.is_supplier.is_(True)),
        include_status=False,
    )
    titulo = "Listado de Proveedores - " + APPNAME
    return render_template("compras/proveedor_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-reconciliation")
@modulo_activo("purchases")
@login_required
def compras_purchase_reconciliation():
    """Report pending purchase reconciliation lines."""
    company = request.args.get("company", "cacao")
    rows = get_purchase_reconciliation_pending(company=company)
    titulo = _("Conciliacion de Compras Pendiente") + " - " + APPNAME
    return render_template("compras/purchase_reconciliation.html", rows=rows, company=company, titulo=titulo)


@compras.route("/purchase-reconciliation/panel")
@modulo_activo("purchases")
@login_required
def compras_reconciliation_panel():
    """Panel de conciliacion de compras agrupado por orden de compra."""
    company = request.args.get("company", "cacao")
    groups = get_purchase_reconciliation_panel_groups(company=company)
    titulo = _("Panel de Conciliacion de Compras") + " - " + APPNAME
    return render_template(
        "compras/purchase_reconciliation_panel.html",
        groups=groups,
        company=company,
        titulo=titulo,
    )


@compras.route("/supplier/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_nuevo():
    """Formulario para crear un nuevo proveedor."""
    from cacao_accounting.compras.forms import FormularioProveedor
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioProveedor()
    titulo = "Nuevo Proveedor - " + APPNAME
    company_choices = obtener_lista_entidades_por_id_razonsocial()

    selected_company = request.values.get("company") or (company_choices[0][0] if company_choices else None)
    company_settings_rows = party_company_settings_rows(None, selected_company, role="supplier")
    if request.method == "POST":
        return _handle_supplier_create(request.form, selected_company, company_choices, formulario, titulo)
    return render_template(
        COMPRAS_PROVEEDOR_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(request.form.get("party_group_id") or None),
    )


@compras.route("/supplier/<supplier_id>")
@modulo_activo("purchases")
@login_required
def compras_proveedor(supplier_id):
    """Detalle de proveedor."""
    registro = database.session.execute(database.select(Party).filter_by(id=supplier_id, is_supplier=True)).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    detail = build_party_detail_context(registro[0])
    return render_template("compras/proveedor.html", registro=registro[0], detail=detail, titulo=titulo)


@compras.route("/supplier/<supplier_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_editar(supplier_id: str):
    """Formulario para editar un proveedor."""
    from cacao_accounting.compras.forms import FormularioProveedor
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    proveedor = database.session.execute(
        database.select(Party).filter_by(id=supplier_id, is_supplier=True)
    ).scalar_one_or_none()
    if not proveedor:
        abort(404)
    formulario = FormularioProveedor(obj=proveedor)
    titulo = f"Editar Proveedor - {APPNAME}"
    company_choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (company_choices[0][0] if company_choices else None)
    company_settings_rows = party_company_settings_rows(proveedor.id, selected_company, role="supplier")
    if request.method == "POST":
        return _handle_supplier_update(proveedor, request.form, selected_company, company_choices, formulario, titulo)
    return render_template(
        COMPRAS_PROVEEDOR_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        edit=True,
        registro=proveedor,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(proveedor.party_group_id),
    )


@compras.route("/supplier/<supplier_id>/contacts", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_contacto_crear(supplier_id: str):
    """Crea un contacto para un proveedor."""
    _party_or_404(supplier_id)
    try:
        create_party_contact(supplier_id, request.form)
        database.session.commit()
        flash(_("Contacto agregado correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id))


@compras.route("/supplier/<supplier_id>/contacts/<link_id>/edit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_contacto_editar(supplier_id: str, link_id: str):
    """Edita un contacto de proveedor."""
    _party_or_404(supplier_id)
    try:
        update_party_contact(supplier_id, link_id, request.form)
        database.session.commit()
        flash(_("Contacto actualizado correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id))


@compras.route("/supplier/<supplier_id>/contacts/<link_id>/deactivate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_contacto_desactivar(supplier_id: str, link_id: str):
    """Desactiva un contacto de proveedor."""
    _party_or_404(supplier_id)
    deactivate_party_contact(supplier_id, link_id)
    database.session.commit()
    flash(_("Contacto desactivado correctamente."), "success")
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id))


@compras.route("/supplier/<supplier_id>/addresses", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_direccion_crear(supplier_id: str):
    """Crea una direccion para un proveedor."""
    _party_or_404(supplier_id)
    try:
        create_party_address(supplier_id, request.form)
        database.session.commit()
        flash(_("Direccion agregada correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id))


@compras.route("/supplier/<supplier_id>/addresses/<link_id>/edit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_direccion_editar(supplier_id: str, link_id: str):
    """Edita una direccion de proveedor."""
    _party_or_404(supplier_id)
    try:
        update_party_address(supplier_id, link_id, request.form)
        database.session.commit()
        flash(_("Direccion actualizada correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id))


@compras.route("/supplier/<supplier_id>/addresses/<link_id>/deactivate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_direccion_desactivar(supplier_id: str, link_id: str):
    """Desactiva una direccion de proveedor."""
    _party_or_404(supplier_id)
    deactivate_party_address(supplier_id, link_id)
    database.session.commit()
    flash(_("Direccion desactivada correctamente."), "success")
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id))


def _form_decimal(field_name: str, default: str = "0") -> Decimal:
    """Convierte un valor de formulario a Decimal."""
    value = request.form.get(field_name)
    return Decimal(str(value if value not in (None, "") else default))


def _line_amount(index: int) -> Decimal:
    """Obtiene o calcula el monto de una linea."""
    amount = request.form.get(f"amount_{index}")
    if amount not in (None, ""):
        return Decimal(str(amount))
    return _form_decimal(f"qty_{index}", "1") * _form_decimal(f"rate_{index}", "0")


def _create_line_relation(
    index: int,
    target_type: str,
    target_id: str,
    target_item_id: str,
    qty: Decimal,
    uom: str | None,
    rate: Decimal,
    amount: Decimal,
) -> None:
    """Crea relacion documental para una linea importada desde un origen."""
    source_type = request.form.get(f"source_type_{index}")
    source_id = request.form.get(f"source_id_{index}")
    source_item_id = request.form.get(f"source_item_id_{index}")
    if not (source_type and source_id and source_item_id):
        return
    create_document_relation(
        source_type=source_type,
        source_id=source_id,
        source_item_id=source_item_id,
        target_type=target_type,
        target_id=target_id,
        target_item_id=target_item_id,
        qty=qty,
        uom=uom,
        rate=rate,
        amount=amount,
    )


def _save_purchase_order_items(order_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una orden de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = PurchaseOrderItem(
                purchase_order_id=order_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_order", order_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_purchase_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una solicitud de cotización de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = PurchaseQuotationItem(
                purchase_quotation_id=quotation_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_quotation", quotation_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_purchase_request_items(request_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una solicitud de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            linea = PurchaseRequestItem(
                purchase_request_id=request_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=request.form.get(f"uom_{i}") or None,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_supplier_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una cotización de proveedor desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = SupplierQuotationItem(
                supplier_quotation_id=quotation_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "supplier_quotation", quotation_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_purchase_receipt_items(receipt_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una recepción de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            warehouse_code = request.form.get(f"warehouse_{i}") or None
            if warehouse_code:
                from cacao_accounting.database import Warehouse

                wh = database.session.execute(database.select(Warehouse).filter_by(code=warehouse_code)).scalar_one_or_none()
                if wh is None:
                    raise DocumentFlowError(f"Almacén '{warehouse_code}' no encontrado.", 404)
                if not wh.is_active:
                    raise DocumentFlowError(f"Almacén '{warehouse_code}' está inactivo.", 409)
            linea = PurchaseReceiptItem(
                purchase_receipt_id=receipt_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
                warehouse=warehouse_code,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_receipt", receipt_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_purchase_invoice_items(invoice_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una factura de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = PurchaseInvoiceItem(
                purchase_invoice_id=invoice_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_invoice", invoice_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _persist_purchase_invoice_fiscal_snapshot(invoice: PurchaseInvoice) -> None:
    """Persist the editable fiscal snapshot captured in the form."""
    persist_document_fiscal_snapshot(
        company=str(invoice.company or ""),
        document_type=invoice.document_type or PURCHASE_INVOICE,
        document_id=invoice.id,
        currency=None,
        tax_lines=request.form.get("tax_lines_payload"),
        tax_summary=request.form.get("tax_summary_payload"),
    )


def _build_purchase_order_transaction_config(items_disponibles, uoms_disponibles, source_origen, initial_source_type):
    from cacao_accounting.form_preferences import get_column_preferences

    transaction_config = {
        "formKey": FORMKEY_PURCHASE_ORDER,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_ORDER),
        "availableSourceTypes": [
            {"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)},
            {"value": "purchase_quotation", "label": _(LABEL_SOLICITUD_COTIZACION)},
            {"value": "supplier_quotation", "label": _("Cotización de Proveedor")},
        ],
        "initialSourceType": initial_source_type,
    }
    if source_origen:
        transaction_config["initialHeader"] = {
            "company": source_origen.company or "",
            "posting_date": str(date.today()),
        }
    return transaction_config


@compras.route("/purchase-order/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_nuevo():
    """Formulario para crear una orden de compra."""
    from cacao_accounting.compras.forms import FormularioOrdenCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioOrdenCompra()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()

    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("purchase_order", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    from_request_id = request.args.get("from_request") or request.form.get("from_request")
    from_rfq_id = request.args.get("from_rfq") or request.form.get("from_rfq")
    from_supplier_quotation_id = request.args.get("from_supplier_quotation") or request.form.get("from_supplier_quotation")
    solicitud_origen = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
    rfq_origen = database.session.get(PurchaseQuotation, from_rfq_id) if from_rfq_id else None
    supplier_quotation_origen = (
        database.session.get(SupplierQuotation, from_supplier_quotation_id) if from_supplier_quotation_id else None
    )
    titulo = "Nueva Orden de Compra - " + APPNAME
    if request.method == "POST":
        response = _create_purchase_order_from_request(request.form)
        if response is not None:
            return response
    if from_request_id:
        initial_source_type = "purchase_request"
    elif from_rfq_id:
        initial_source_type = "purchase_quotation"
    elif from_supplier_quotation_id:
        initial_source_type = "supplier_quotation"
    else:
        initial_source_type = ""

    source_origen = solicitud_origen or rfq_origen or supplier_quotation_origen
    transaction_config = _build_purchase_order_transaction_config(
        items_disponibles, uoms_disponibles, source_origen, initial_source_type
    )
    return render_template(
        "compras/orden_compra_nuevo.html",
        form=formulario,
        titulo=titulo,
        from_request_id=from_request_id,
        from_rfq_id=from_rfq_id,
        from_supplier_quotation_id=from_supplier_quotation_id,
        solicitud_origen=solicitud_origen,
        rfq_origen=rfq_origen,
        supplier_quotation_origen=supplier_quotation_origen,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/purchase-order/<order_id>")
@modulo_activo("purchases")
@login_required
def compras_orden_compra(order_id):
    """Detalle de orden de compra."""
    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    items = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=order_id)).all()
    titulo = (registro.document_no or order_id) + " - " + APPNAME
    return render_template("compras/orden_compra.html", registro=registro, items=items, titulo=titulo)


@compras.route("/purchase-order/<order_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_editar(order_id: str):
    """Edita una orden de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioOrdenCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioOrdenCompra(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = _purchase_order_selected_company(registro.company)
    formulario.naming_series.choices = _series_choices("purchase_order", selected_company)
    formulario.supplier_id.choices = _purchase_order_supplier_choices()
    items_disponibles, uoms_disponibles = _purchase_order_catalogs()

    if request.method == "POST":
        response = _update_purchase_order_from_request(registro)
        if response is not None:
            return response

    transaction_config = _purchase_order_transaction_config(
        registro=registro,
        items=items_disponibles,
        uoms=uoms_disponibles,
        columns=get_column_preferences(current_user.id, FORMKEY_PURCHASE_ORDER),
    )
    return render_template(
        "compras/orden_compra_nuevo.html",
        form=formulario,
        titulo="Editar Orden de Compra - " + APPNAME,
        edit=True,
        registro=registro,
        from_request_id=None,
        solicitud_origen=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


def _purchase_order_selected_company(default_company: str | None) -> str | None:
    """Resuelve la compañía seleccionada para la orden de compra."""
    return request.values.get("company") or default_company


def _purchase_order_supplier_choices() -> list[tuple[str, str]]:
    """Construye el listado de proveedores para órdenes de compra."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _purchase_order_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Carga catálogos reutilizados por órdenes de compra."""
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items_disponibles, uoms_disponibles


def _purchase_order_transaction_config(
    *,
    registro: PurchaseOrder,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    columns: list[dict[str, str | bool | int]],
) -> dict[str, object]:
    """Construye la configuración transaccional para la edición de órdenes de compra."""
    lineas = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=registro.id)).scalars()
    return {
        "formKey": FORMKEY_PURCHASE_ORDER,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "columns": columns,
        "availableSourceTypes": [
            {"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)},
            {"value": "supplier_quotation", "label": _("Cotización de Proveedor")},
        ],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.supplier_id or "",
            "party_label": registro.supplier_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
            }
            for item in lineas
        ],
    }


def _create_purchase_order_from_request(form: dict):
    """Crea una orden de compra desde el formulario enviado."""
    supplier_id = form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    posting_date = _parse_date(form.get("posting_date"))
    transaction_currency = form.get("transaction_currency") or None
    orden = PurchaseOrder(
        supplier_id=supplier_id,
        supplier_name=supplier.name if supplier else None,
        company=form.get("company") or None,
        posting_date=posting_date,
        remarks=form.get("remarks"),
        transaction_currency=transaction_currency,
        docstatus=0,
    )
    try:
        database.session.add(orden)
        database.session.flush()
        assign_document_identifier(
            document=orden,
            entity_type="purchase_order",
            posting_date_raw=posting_date,
            naming_series_id=form.get("naming_series") or None,
        )
        total_qty, total = _save_purchase_order_items(orden.id)
        orden.total_qty = total_qty
        orden.total = total
        orden.net_total = total
        orden.grand_total = total
        orden.exchange_rate = _purchase_exchange_rate(form.get("company"), posting_date, transaction_currency)
        orden.base_total = (total * orden.exchange_rate).quantize(Decimal("0.0001"))
        log_create(orden)
        database.session.commit()
        flash("Orden de compra creada correctamente.", "success")
        return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=orden.id))
    except (IdentifierConfigurationError, DocumentFlowError) as exc:
        database.session.rollback()
        flash_error(exc)
        return None


def _update_purchase_order_from_request(registro: PurchaseOrder):
    """Actualiza una orden de compra desde el formulario enviado."""
    before_state = _capture_purchase_state(registro)
    supplier_id = request.form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    registro.transaction_currency = request.form.get("transaction_currency") or None
    for item in database.session.execute(
        database.select(PurchaseOrderItem).filter_by(purchase_order_id=registro.id)
    ).scalars():
        database.session.delete(item)
    total_qty, total = _save_purchase_order_items(registro.id)
    registro.total_qty = total_qty
    registro.total = total
    registro.net_total = total
    registro.grand_total = total
    registro.exchange_rate = _purchase_exchange_rate(registro.company, registro.posting_date, registro.transaction_currency)
    registro.base_total = (total * registro.exchange_rate).quantize(Decimal("0.0001"))
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Orden de compra actualizada correctamente."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=registro.id))


@compras.route("/purchase-order/<order_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_duplicar(order_id: str):
    """Duplica una orden de compra como borrador nuevo."""
    origen = database.session.get(PurchaseOrder, order_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseOrder(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        transaction_currency=origen.transaction_currency,
        exchange_rate=origen.exchange_rate,
        docstatus=0,
    )
    database.session.add(duplicada)
    database.session.flush()
    assign_document_identifier(
        document=duplicada,
        entity_type="purchase_order",
        posting_date_raw=duplicada.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    total_qty = Decimal("0")
    for item in database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=origen.id)).scalars():
        linea = PurchaseOrderItem(
            purchase_order_id=duplicada.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total_qty += item.qty or Decimal("0")
        total += item.amount or Decimal("0")
    duplicada.total_qty = total_qty
    duplicada.total = total
    duplicada.net_total = total
    duplicada.grand_total = total
    duplicada.base_total = total
    log_create(duplicada)
    database.session.commit()
    flash(_("Orden de compra duplicada como nuevo borrador."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=duplicada.id))


@compras.route("/request-for-quotation/list")
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_lista():
    """Listado de solicitudes de cotización."""
    consulta = _paginate_list(
        PurchaseQuotation,
        (PurchaseQuotation.document_no, PurchaseQuotation.supplier_name, PurchaseQuotation.remarks),
    )
    titulo = "Listado de Solicitudes de Cotización - " + APPNAME
    return render_template("compras/solicitud_cotizacion_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/request-for-quotation/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_nueva():
    """Formulario para crear una solicitud de cotización."""
    from cacao_accounting.compras.forms import FormularioSolicitudCotizacion
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    formulario = FormularioSolicitudCotizacion()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = _purchase_quotation_selected_company(formulario.company.choices)
    formulario.naming_series.choices = _series_choices("purchase_quotation", selected_company)
    formulario.supplier_id.choices = _purchase_quotation_supplier_choices()
    from_request_id = _purchase_quotation_origin_id()
    solicitud_origen = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
    items_disponibles, uoms_disponibles = _purchase_quotation_catalogs()
    titulo = "Nueva Solicitud de Cotización - " + APPNAME
    transaction_config = _purchase_quotation_transaction_config(
        items=items_disponibles,
        uoms=uoms_disponibles,
        initial_source_type="purchase_request" if from_request_id else "",
        initial_header=(
            {
                "company": solicitud_origen.company or "",
                "posting_date": str(date.today()),
            }
            if solicitud_origen
            else None
        ),
        columns=get_column_preferences(current_user.id, FORMKEY_PURCHASE_QUOTATION),
    )
    if request.method == "POST":
        response = _create_purchase_quotation_from_request()
        if response is not None:
            return response
    return render_template(
        "compras/solicitud_cotizacion_nuevo.html",
        form=formulario,
        titulo=titulo,
        from_request_id=from_request_id,
        solicitud_origen=solicitud_origen,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


def _purchase_quotation_origin_id() -> str | None:
    """Obtiene el documento origen para una solicitud de cotización."""
    return request.args.get("from_request") or request.form.get("from_request")


def _purchase_quotation_supplier_choices() -> list[tuple[str, str]]:
    """Construye las opciones de proveedores para solicitudes de cotización."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _purchase_quotation_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Carga los catálogos de ítems y unidades usados en solicitudes de cotización."""
    items = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items, uoms


def _purchase_quotation_transaction_config(
    *,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    initial_source_type: str,
    initial_header: dict[str, str] | None = None,
    columns: list[dict[str, str | bool | int]] | None = None,
) -> dict[str, Any]:
    """Construye la configuración transaccional para solicitudes de cotización."""
    transaction_config: dict[str, Any] = {
        "formKey": FORMKEY_PURCHASE_QUOTATION,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "columns": columns or [],
        "availableSourceTypes": [{"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)}],
        "initialSourceType": initial_source_type,
    }
    if initial_header:
        transaction_config["initialHeader"] = initial_header
    return transaction_config


def _create_purchase_quotation_from_request():
    """Crea una solicitud de cotización a partir del formulario enviado."""
    try:
        supplier_id = request.form.get("supplier_id") or None
        supplier = database.session.get(Party, supplier_id) if supplier_id else None
        posting_date = _parse_date(request.form.get("posting_date"))
        cotizacion = PurchaseQuotation(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            company=request.form.get("company") or None,
            posting_date=posting_date,
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        database.session.add(cotizacion)
        database.session.flush()
        assign_document_identifier(
            document=cotizacion,
            entity_type="purchase_quotation",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _qty, total = _save_purchase_quotation_items(cotizacion.id)
        cotizacion.total = total
        cotizacion.base_total = total
        cotizacion.grand_total = total
        log_create(cotizacion)
        database.session.commit()
        flash("Solicitud de cotización creada correctamente.", "success")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=cotizacion.id))
    except (IdentifierConfigurationError, DocumentFlowError) as exc:
        database.session.rollback()
        flash_error(exc)
    return None


@compras.route("/request-for-quotation/<quotation_id>")
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion(quotation_id: str):
    """Detalle de solicitud de cotización."""
    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    items = database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=quotation_id)
    ).all()
    offers = database.session.execute(database.select(SupplierQuotation).filter_by(purchase_quotation_id=quotation_id)).all()
    titulo = (registro.document_no or quotation_id) + " - " + APPNAME
    return render_template(
        "compras/solicitud_cotizacion.html",
        registro=registro,
        items=items,
        offers=offers,
        titulo=titulo,
    )


def _handle_purchase_quotation_edit_post(registro):
    from cacao_accounting.database import Party

    before_state = _capture_purchase_state(registro)
    supplier_id = request.form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    for item in database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _qty, total = _save_purchase_quotation_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Solicitud de cotizacion actualizada correctamente."), "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=registro.id))


@compras.route("/request-for-quotation/<quotation_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_editar(quotation_id: str):
    """Edita una solicitud de cotizacion en borrador."""
    from cacao_accounting.compras.forms import FormularioSolicitudCotizacion
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioSolicitudCotizacion(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("purchase_quotation", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        return _handle_purchase_quotation_edit_post(registro)

    lineas = database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_QUOTATION,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_QUOTATION),
        "availableSourceTypes": [{"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)}],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.supplier_id or "",
            "party_label": registro.supplier_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
            }
            for item in lineas
        ],
    }
    return render_template(
        "compras/solicitud_cotizacion_nuevo.html",
        form=formulario,
        titulo="Editar Solicitud de Cotizacion - " + APPNAME,
        edit=True,
        registro=registro,
        from_request_id=None,
        solicitud_origen=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/request-for-quotation/<quotation_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_duplicar(quotation_id: str):
    """Duplica una solicitud de cotizacion como borrador nuevo."""
    origen = database.session.get(PurchaseQuotation, quotation_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseQuotation(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicada)
    database.session.flush()
    assign_document_identifier(
        document=duplicada,
        entity_type="purchase_quotation",
        posting_date_raw=duplicada.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=origen.id)
    ).scalars():
        linea = PurchaseQuotationItem(
            purchase_quotation_id=duplicada.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
    log_create(duplicada)
    database.session.commit()
    flash(_("Solicitud de cotizacion duplicada como nuevo borrador."), "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=duplicada.id))


@compras.route("/request-for-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_submit(quotation_id: str):
    """Aprueba una solicitud de cotizacion.

    ``require_party=False`` es intencional: una solicitud de cotización interna
    puede aprobarse sin proveedor asignado. El proveedor se asigna al
    convertir en orden de compra.
    """
    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=False, require_rate_positive=True)
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))
    flash(_("Solicitud de cotizacion aprobada."), "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))


@compras.route("/request-for-quotation/<quotation_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_cancel(quotation_id: str):
    """Cancela una solicitud de cotizacion."""
    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_quotation", quotation_id):
        flash("No se puede cancelar la solicitud de cotización porque tiene órdenes de compra activas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("purchase_quotation", quotation_id)
    refresh_source_caches_for_target("purchase_quotation", quotation_id)
    database.session.commit()
    flash(_("Solicitud de cotizacion cancelada."), "warning")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))


@compras.route("/purchase-order/<order_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_submit(order_id: str):
    """Aprueba una orden de compra."""
    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True, require_rate_positive=True)
        check_budget_control(
            company=registro.company,
            posting_date=registro.posting_date,
            supplier_id=registro.supplier_id,
            document_id=registro.id,
            document_type="purchase_order",
            items=items
        )
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))
    flash("Orden de compra aprobada.", "success")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))


@compras.route("/purchase-order/<order_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_cancel(order_id: str):
    """Cancela una orden de compra."""
    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_order", order_id):
        flash("No se puede cancelar la orden de compra porque tiene recepciones o facturas activas.", "danger")
        return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("purchase_order", order_id)
    refresh_source_caches_for_target("purchase_order", order_id)
    database.session.commit()
    flash("Orden de compra cancelada.", "warning")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))


@compras.route("/purchase-receipt/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_recepcion_nuevo():
    """Formulario para crear una recepción de compra."""
    from cacao_accounting.compras.forms import FormularioRecepcionCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse

    formulario = FormularioRecepcionCompra()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    from cacao_accounting.form_preferences import get_column_preferences

    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("purchase_receipt", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    orden_origen = database.session.get(PurchaseOrder, from_order_id) if from_order_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    # INV-03: Filtrar almacenes por compañía usando WarehouseCompanyAccount
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name}
        for w in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]
    titulo = "Nueva Recepción de Compra - " + APPNAME
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_RECEIPT,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_RECEIPT),
        "availableSourceTypes": [{"value": "purchase_order", "label": _(LABEL_ORDEN_COMPRA)}],
    }
    if request.method == "POST":
        try:
            posting_date = _parse_date(request.form.get("posting_date"))
            supplier_id = request.form.get("supplier_id") or None
            supplier = database.session.get(Party, supplier_id) if supplier_id else None
            recepcion = PurchaseReceipt(
                supplier_id=supplier_id,
                supplier_name=supplier.name if supplier else None,
                company=request.form.get("company") or None,
                posting_date=posting_date,
                purchase_order_id=request.form.get("from_order") or None,
                remarks=request.form.get("remarks"),
                transaction_currency=request.form.get("transaction_currency") or None,
                docstatus=0,
            )
            database.session.add(recepcion)
            database.session.flush()
            assign_document_identifier(
                document=recepcion,
                entity_type="purchase_receipt",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_purchase_receipt_items(recepcion.id)
            recepcion.total = total
            recepcion.grand_total = total
            recepcion.exchange_rate = _purchase_exchange_rate(
                request.form.get("company"), posting_date, request.form.get("transaction_currency")
            )
            recepcion.base_total = (total * recepcion.exchange_rate).quantize(Decimal("0.0001"))
            log_create(recepcion)
            database.session.commit()
            flash("Recepción de compra creada correctamente.", "success")
            return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=recepcion.id))
        except (DocumentFlowError, IdentifierConfigurationError) as exc:
            database.session.rollback()
            flash_error(exc)
    return render_template(
        "compras/recepcion_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        from_order_id=from_order_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/purchase-receipt/<receipt_id>")
@modulo_activo("purchases")
@login_required
def compras_recepcion(receipt_id):
    """Detalle de recepción de compra."""
    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        registro = database.session.execute(
            database.select(PurchaseReceipt).filter_by(document_no=receipt_id)
        ).scalar_one_or_none()
    if not registro:
        abort(404)
    items = database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id)).all()
    create_actions = document_flow_summary("purchase_receipt", receipt_id).get("create_actions", [])
    create_actions_json = json.dumps(create_actions, ensure_ascii=False)
    titulo = (registro.document_no or registro.id) + " - " + APPNAME
    return render_template(
        "compras/recepcion.html",
        registro=registro,
        items=items,
        titulo=titulo,
        create_actions_json=create_actions_json,
        audit_timeline=format_document_timeline("purchase_receipt", registro.id),
    )


@compras.route("/purchase-receipt/<receipt_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_recepcion_editar(receipt_id: str):
    """Edita una recepcion de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioRecepcionCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse
    from cacao_accounting.form_preferences import get_column_preferences

    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioRecepcionCompra(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("purchase_receipt", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    # INV-03: Filtrar almacenes por compañía usando WarehouseCompanyAccount
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name}
        for w in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]

    if request.method == "POST":
        return _handle_purchase_receipt_edit_post(registro)

    lineas = database.session.execute(
        database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_RECEIPT,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_RECEIPT),
        "availableSourceTypes": [{"value": "purchase_order", "label": _(LABEL_ORDEN_COMPRA)}],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.supplier_id or "",
            "party_label": registro.supplier_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
                "warehouse": item.warehouse or "",
            }
            for item in lineas
        ],
    }
    return render_template(
        "compras/recepcion_nuevo.html",
        form=formulario,
        titulo="Editar Recepcion de Compra - " + APPNAME,
        edit=True,
        registro=registro,
        orden_origen=None,
        from_order_id=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
        transaction_config=transaction_config,
    )


def _handle_purchase_receipt_edit_post(registro):
    before_state = _capture_purchase_state(registro)
    supplier_id = request.form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")

    for rel in database.session.execute(
        database.select(DocumentRelation).filter_by(target_type="purchase_receipt", target_id=registro.id)
    ).scalars():
        database.session.delete(rel)

    for item in database.session.execute(
        database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _total_qty, total = _save_purchase_receipt_items(registro.id)
    registro.total = total
    registro.grand_total = total
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Recepcion de compra actualizada correctamente."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=registro.id))


@compras.route("/purchase-receipt/<receipt_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_recepcion_duplicar(receipt_id: str):
    """Duplica una recepcion de compra como borrador nuevo."""
    origen = database.session.get(PurchaseReceipt, receipt_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseReceipt(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicada)
    database.session.flush()
    assign_document_identifier(
        document=duplicada,
        entity_type="purchase_receipt",
        posting_date_raw=duplicada.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(
        database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=origen.id)
    ).scalars():
        linea = PurchaseReceiptItem(
            purchase_receipt_id=duplicada.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
            warehouse=item.warehouse,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    duplicada.grand_total = total
    log_create(duplicada)
    database.session.commit()
    flash(_("Recepcion de compra duplicada como nuevo borrador."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=duplicada.id))


def _validate_receipt_quantities_against_po(receipt_id: str) -> None:
    """Valida que las cantidades recibidas no excedan las ordenadas en la OC."""
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="purchase_receipt",
            target_id=receipt_id,
            status="active",
        )
    ).scalars()
    for rel in relations:
        if rel.source_type != "purchase_order" or not rel.source_item_id:
            continue
        po_item = database.session.get(PurchaseOrderItem, rel.source_item_id)
        if not po_item:
            continue
        consumed = consumed_qty_for_source("purchase_order", rel.source_id, rel.source_item_id, "purchase_receipt")
        ordered = Decimal(str(po_item.qty or 0))
        if consumed > ordered:
            raise ValueError(
                _("Sobre-recepción: cantidad recibida {} excede la ordenada {} para el artículo {}.").format(
                    consumed, ordered, po_item.item_code
                )
            )


def _validate_invoice_quantities_against_receipt(invoice_id: str) -> None:
    """Valida que las cantidades facturadas no excedan las recibidas/recepcionadas (3-way match).

    Cuando la factura se vincula directamente a una OC (sin recepción),
    valida contra la cantidad ordenada en la OC.
    """
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="purchase_invoice",
            target_id=invoice_id,
            status="active",
        )
    ).scalars()
    for rel in relations:
        if not rel.source_item_id:
            continue
        if rel.source_type == "purchase_receipt":
            receipt_item = database.session.get(PurchaseReceiptItem, rel.source_item_id)
            if not receipt_item:
                continue
            consumed = consumed_qty_for_source("purchase_receipt", rel.source_id, rel.source_item_id, "purchase_invoice")
            received = Decimal(str(receipt_item.qty or 0))
            if consumed > received:
                raise ValueError(
                    _("Sobre-facturación: cantidad facturada {} excede la recibida {} para el artículo {}.").format(
                        consumed, received, receipt_item.item_code
                    )
                )
        elif rel.source_type == "purchase_order":
            po_item = database.session.get(PurchaseOrderItem, rel.source_item_id)
            if not po_item:
                continue
            consumed = consumed_qty_for_source("purchase_order", rel.source_id, rel.source_item_id, "purchase_invoice")
            ordered = Decimal(str(po_item.qty or 0))
            if consumed > ordered:
                raise ValueError(
                    _("Sobre-facturación: cantidad facturada {} excede la ordenada {} para el artículo {}.").format(
                        consumed, ordered, po_item.item_code
                    )
                )


def _validate_invoice_requires_supplier_link(invoice_id: str) -> None:
    """Exige vínculo a recepción/orden según la configuración del proveedor.

    Si el proveedor no permite facturar sin recepción (o sin orden), la
    factura debe estar vinculada explícitamente, de lo contrario se omite
    la validación de 3-way match y se podrían facturar cantidades sin control.
    """
    invoice = database.session.get(PurchaseInvoice, invoice_id)
    if not invoice or not invoice.supplier_id:
        return
    cp = database.session.execute(
        database.select(CompanyParty).filter_by(party_id=invoice.supplier_id, company=invoice.company)
    ).scalar_one_or_none()
    if not cp:
        return
    relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="purchase_invoice", target_id=invoice_id, status="active")
        )
        .scalars()
        .all()
    )
    has_receipt_link = any(r.source_type == "purchase_receipt" for r in relations)
    has_order_link = any(r.source_type == "purchase_order" for r in relations)
    if not cp.allow_purchase_invoice_without_receipt and not has_receipt_link:
        raise ValueError(_("La factura debe estar vinculada a una recepción de compra según la configuración del proveedor."))
    if not cp.allow_purchase_invoice_without_order and not has_receipt_link and not has_order_link:
        raise ValueError(
            _("La factura debe estar vinculada a una orden o recepción de compra según la configuración del proveedor.")
        )


@compras.route("/purchase-receipt/<receipt_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_recepcion_submit(receipt_id: str):
    """Aprueba una recepción de compra."""
    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True, require_rate_positive=True)
        _validate_receipt_quantities_against_po(receipt_id)
        submit_document(registro)
        log_submit(registro)
        database.session.commit()
        flash("Recepcion de compra aprobada.", "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))


@compras.route("/purchase-receipt/<receipt_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_recepcion_cancel(receipt_id: str):
    """Cancela una recepción de compra."""
    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_receipt", receipt_id):
        flash("No se puede cancelar la recepción de compra porque tiene facturas de compra activas.", "danger")
        return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))
    try:
        cancel_document(registro)
        revert_relations_for_target("purchase_receipt", receipt_id)
        refresh_source_caches_for_target("purchase_receipt", receipt_id)
        log_cancel(registro)
        database.session.commit()
        flash("Recepción de compra cancelada.", "warning")
    except PostingError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))


@compras.route("/purchase-invoice/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nuevo():
    """Formulario para crear una factura de compra."""
    from cacao_accounting.compras.forms import FormularioFacturaCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioFacturaCompra()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    from cacao_accounting.form_preferences import get_column_preferences

    selected_company = _purchase_invoice_selected_company(formulario.company.choices)
    formulario.naming_series.choices = _series_choices("purchase_invoice", selected_company)
    formulario.supplier_id.choices = _purchase_invoice_supplier_choices()
    source_ids = _purchase_invoice_source_ids()
    from_order_id = source_ids["from_order_id"]
    from_receipt_id = source_ids["from_receipt_id"]
    from_invoice_id = source_ids["from_invoice_id"]
    document_type = _purchase_invoice_document_type(source_ids)
    formulario.is_return.data = document_type == PURCHASE_RETURN
    orden_origen, recepcion_origen, factura_origen = _purchase_invoice_sources(source_ids)
    document_title = DOCUMENT_TYPE_LABELS.get(document_type, FACTURA_DE_COMPRA)
    items_disponibles, uoms_disponibles = _purchase_invoice_catalogs()
    titulo = f"Nueva {document_title} - {APPNAME}"
    transaction_config = _purchase_invoice_transaction_config(
        items=items_disponibles,
        uoms=uoms_disponibles,
        columns=get_column_preferences(current_user.id, FORMKEY_PURCHASE_INVOICE),
    )
    if request.method == "POST":
        response = _create_purchase_invoice_from_request()
        if response is not None:
            return response
    return render_template(
        "compras/factura_compra_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        recepcion_origen=recepcion_origen,
        factura_origen=factura_origen,
        from_order_id=from_order_id,
        from_receipt_id=from_receipt_id,
        from_invoice_id=from_invoice_id,
        document_type=document_type,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


def _purchase_invoice_selected_company(choices: list[tuple[str, str]]) -> str | None:
    """Resolve the selected company for the purchase invoice."""
    return request.values.get("company") or (choices[0][0] if choices else None)


def _purchase_invoice_supplier_choices() -> list[tuple[str, str]]:
    """Build the supplier choices list for purchase invoices."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _purchase_invoice_source_ids() -> dict[str, str | None]:
    """Get the source identifiers used by the purchase invoice."""
    return {
        "from_order_id": request.args.get("from_order") or request.form.get("from_order"),
        "from_receipt_id": request.args.get("from_receipt") or request.form.get("from_receipt"),
        "from_invoice_id": (
            request.args.get("from_invoice")
            or request.form.get("from_invoice")
            or request.args.get("from_return")
            or request.form.get("from_return")
        ),
    }


def _purchase_invoice_document_type(source_ids: dict[str, str | None]) -> str:
    """Resolve the document type for the purchase invoice."""
    doc_type = PURCHASE_INVOICE
    if source_ids["from_receipt_id"]:
        doc_type = PURCHASE_RETURN
    elif source_ids["from_invoice_id"]:
        doc_type = PURCHASE_CREDIT_NOTE
    return request.args.get("document_type") or request.form.get("document_type") or doc_type


def _purchase_invoice_sources(
    source_ids: dict[str, str | None],
) -> tuple[PurchaseOrder | None, PurchaseReceipt | None, PurchaseInvoice | None]:
    """Load the source documents for the purchase invoice."""
    orden_origen = database.session.get(PurchaseOrder, source_ids["from_order_id"]) if source_ids["from_order_id"] else None
    recepcion_origen = (
        database.session.get(PurchaseReceipt, source_ids["from_receipt_id"]) if source_ids["from_receipt_id"] else None
    )
    factura_origen = (
        database.session.get(PurchaseInvoice, source_ids["from_invoice_id"]) if source_ids["from_invoice_id"] else None
    )
    return orden_origen, recepcion_origen, factura_origen


def _purchase_invoice_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Load the catalogs reused by purchase invoices."""
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items_disponibles, uoms_disponibles


def _purchase_invoice_transaction_config(
    *,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    columns: list[dict[str, str | bool | int]],
) -> dict[str, object]:
    """Build the transaction configuration for purchase invoices."""
    return {
        "formKey": FORMKEY_PURCHASE_INVOICE,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "columns": columns,
        "availableSourceTypes": [
            {"value": "purchase_order", "label": _(LABEL_ORDEN_COMPRA)},
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "purchase_invoice", "label": _(LABEL_FACTURA_COMPRA_LONG)},
        ],
    }


def _compute_base_amounts(amount: Decimal, exchange_rate: Decimal | None = None) -> tuple[Decimal, Decimal]:
    """S2P-09: Calcula monto base aplicando tipo de cambio. Retorna (base_amount, effective_rate)."""
    rate = exchange_rate if exchange_rate and exchange_rate > 0 else Decimal("1")
    return (amount * rate).quantize(Decimal("0.0001")), rate


def _purchase_exchange_rate(company: str | None, posting_date: Any, transaction_currency: str | None) -> Decimal:
    """S2P-09: Resuelve tipo de cambio para documento de compra.

    Devuelve ``Decimal("1")`` (tasa 1:1) cuando no se puede determinar la
    moneda base de la compania o no existe una tasa registrada, asumiendo la
    moneda de transaccion equivalente a la moneda local.
    """
    if not company or not transaction_currency:
        return Decimal("1")
    from cacao_accounting.database import Entity

    entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalars().first()
    if not entity or not entity.currency:
        return Decimal("1")
    if transaction_currency == entity.currency:
        return Decimal("1")
    from cacao_accounting.contabilidad.posting import _lookup_exchange_rate

    try:
        return _lookup_exchange_rate(transaction_currency, entity.currency, posting_date)
    except PostingError:
        logger.warning("No exchange rate found for %s -> %s on %s", transaction_currency, entity.currency, posting_date)
        return Decimal("1")


def _capture_purchase_state(registro: Any) -> dict[str, Any]:
    """CROSS-01: Captura estado de documento de compras para auditoría."""
    return {
        "supplier_id": getattr(registro, "supplier_id", None),
        "company": getattr(registro, "company", None),
        "posting_date": str(getattr(registro, "posting_date", "")),
        "total": str(getattr(registro, "total", "")),
        "remarks": getattr(registro, "remarks", None),
    }


def _validate_supplier_invoice_flags(
    supplier_id: str | None, company: str | None, purchase_order_id: str | None, purchase_receipt_id: str | None
) -> None:
    """S2P-08: Valida flags del proveedor antes de crear/aprobar factura."""
    if not supplier_id or not company:
        return
    from cacao_accounting.database import CompanyParty

    settings = database.session.execute(
        database.select(CompanyParty).filter_by(party_id=supplier_id, company=company)
    ).scalar_one_or_none()
    if settings is None:
        # S2P-09: Validar strictamente cuando CompanyParty es None
        raise PostingError("No se encontró configuración de flags para el proveedor en la compañía.")
    has_order = bool(purchase_order_id)
    has_receipt = bool(purchase_receipt_id)
    if not has_order and not settings.allow_purchase_invoice_without_order:
        raise ValueError("El proveedor no permite crear facturas de compra sin orden de compra.")
    if not has_receipt and not settings.allow_purchase_invoice_without_receipt:
        raise ValueError("El proveedor no permite crear facturas de compra sin recepción.")


def _validate_duplicate_supplier_invoice(
    supplier_id: str | None, supplier_invoice_no: str | None, exclude_id: str | None = None
) -> None:
    """S2P-24: Valida la duplicidad de supplier_invoice_no para un mismo proveedor.

    Valida que no exista otra factura de compra activa (no cancelada, docstatus != 2)
    con el mismo supplier_id y supplier_invoice_no.
    """
    if not supplier_id or not supplier_invoice_no:
        return
    supplier_invoice_no_cleaned = supplier_invoice_no.strip()
    if not supplier_invoice_no_cleaned:
        return

    stmt = database.select(PurchaseInvoice).filter(
        PurchaseInvoice.supplier_id == supplier_id,
        PurchaseInvoice.supplier_invoice_no == supplier_invoice_no_cleaned,
        PurchaseInvoice.docstatus != 2,
    )
    if exclude_id:
        stmt = stmt.filter(PurchaseInvoice.id != exclude_id)

    exists = database.session.execute(stmt).scalars().first()
    if exists:
        raise ValueError(
            _("El número de factura del proveedor '{}' ya está registrado para este proveedor en otra factura activa.").format(
                supplier_invoice_no_cleaned
            )
        )


def _create_purchase_invoice_from_request():
    """Create a purchase invoice from the submitted form."""
    try:
        document_type = request.form.get("document_type") or PURCHASE_INVOICE
        posting_date = _parse_date(request.form.get("posting_date"))
        supplier_id = request.form.get("supplier_id") or None
        company = request.form.get("company") or None
        from_order = request.form.get("from_order") or None
        from_receipt = request.form.get("from_receipt") or None
        _validate_supplier_invoice_flags(supplier_id, company, from_order, from_receipt)
        _validate_duplicate_supplier_invoice(supplier_id, request.form.get("supplier_invoice_no"))
        factura = PurchaseInvoice(
            supplier_id=supplier_id,
            company=company,
            posting_date=posting_date,
            supplier_invoice_no=request.form.get("supplier_invoice_no"),
            document_type=document_type,
            purchase_order_id=from_order,
            purchase_receipt_id=from_receipt,
            is_return=document_type in (PURCHASE_RETURN, PURCHASE_CREDIT_NOTE),
            reversal_of=(
                (request.form.get("from_invoice") or request.form.get("from_return"))
                if document_type in (PURCHASE_CREDIT_NOTE, PURCHASE_DEBIT_NOTE)
                else None
            ),
            remarks=request.form.get("remarks"),
            transaction_currency=request.form.get("transaction_currency") or None,
            docstatus=0,
        )
        database.session.add(factura)
        database.session.flush()
        assign_document_identifier(
            document=factura,
            entity_type="purchase_invoice",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _total_qty, total = _save_purchase_invoice_items(factura.id)
        factura.total = total
        # S2P-09: Aplicar tipo de cambio si transaction_currency está definida
        fx_rate = _purchase_exchange_rate(company, posting_date, request.form.get("transaction_currency"))
        factura.exchange_rate = fx_rate
        base_total, _base = _compute_base_amounts(total, fx_rate)
        base_grand_total, _base2 = _compute_base_amounts(total, fx_rate)
        factura.base_total = base_total
        factura.grand_total = total
        factura.base_grand_total = base_grand_total
        factura.outstanding_amount = total
        factura.base_outstanding_amount = base_grand_total
        _persist_purchase_invoice_fiscal_snapshot(factura)
        log_create(factura)
        database.session.commit()
        flash("Factura de compra creada correctamente.", "success")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=factura.id))
    except (ValueError, DocumentFlowError) as exc:
        database.session.rollback()
        flash_error(exc)
    return None


@compras.route("/purchase-invoice/<invoice_id>")
@modulo_activo("purchases")
@login_required
def compras_factura_compra(invoice_id):
    """Detalle de factura de compra."""
    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    items = database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id)).all()
    titulo = (registro.document_no or invoice_id) + " - " + APPNAME
    document_type_label = DOCUMENT_TYPE_LABELS.get(registro.document_type, FACTURA_DE_COMPRA)
    return render_template(
        "compras/factura_compra.html",
        registro=registro,
        items=items,
        titulo=titulo,
        document_type_label=document_type_label,
    )


@compras.route("/purchase-invoice/<invoice_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_editar(invoice_id: str):
    """Edita una factura de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioFacturaCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioFacturaCompra(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("purchase_invoice", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        return _handle_purchase_invoice_edit_post(registro)

    lineas = database.session.execute(
        database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_INVOICE,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, FORMKEY_PURCHASE_INVOICE),
        "availableSourceTypes": [
            {"value": "purchase_order", "label": _(LABEL_ORDEN_COMPRA)},
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "purchase_invoice", "label": _(LABEL_FACTURA_COMPRA_LONG)},
        ],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.supplier_id or "",
            "party_label": registro.supplier_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
            }
            for item in lineas
        ],
    }
    document_type = registro.document_type or PURCHASE_INVOICE
    formulario.is_return.data = document_type == PURCHASE_RETURN
    return render_template(
        "compras/factura_compra_nuevo.html",
        form=formulario,
        titulo="Editar Factura de Compra - " + APPNAME,
        edit=True,
        registro=registro,
        orden_origen=None,
        recepcion_origen=None,
        factura_origen=None,
        from_order_id=None,
        from_receipt_id=None,
        from_invoice_id=None,
        document_type=document_type,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


def _handle_purchase_invoice_edit_post(registro):
    try:
        before_state = _capture_purchase_state(registro)
        registro.supplier_id = request.form.get("supplier_id") or None
        registro.company = request.form.get("company") or None
        _validate_supplier_invoice_flags(
            registro.supplier_id,
            registro.company,
            request.form.get("from_order") or None,
            request.form.get("from_receipt") or None,
        )
        _validate_duplicate_supplier_invoice(
            registro.supplier_id,
            request.form.get("supplier_invoice_no") or registro.supplier_invoice_no,
            exclude_id=registro.id,
        )
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.supplier_invoice_no = request.form.get("supplier_invoice_no") or registro.supplier_invoice_no
        registro.remarks = request.form.get("remarks")
        for rel in database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="purchase_invoice", target_id=registro.id)
        ).scalars():
            database.session.delete(rel)
        for item in database.session.execute(
            database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=registro.id)
        ).scalars():
            database.session.delete(item)
        _total_qty, total = _save_purchase_invoice_items(registro.id)
        fx_rate = _purchase_exchange_rate(registro.company, registro.posting_date, registro.transaction_currency)
        registro.exchange_rate = fx_rate
        base_total, _base = _compute_base_amounts(total, fx_rate)
        base_grand_total, _base2 = _compute_base_amounts(total, fx_rate)
        registro.total = total
        registro.base_total = base_total
        registro.grand_total = total
        registro.base_grand_total = base_grand_total
        registro.outstanding_amount = total
        registro.base_outstanding_amount = base_grand_total
        _persist_purchase_invoice_fiscal_snapshot(registro)
        after_state = _capture_purchase_state(registro)
        log_update(registro, before=before_state, after=after_state)
        database.session.commit()
        flash(_("Factura de compra actualizada correctamente."), "success")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=registro.id))
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=registro.id))


@compras.route("/purchase-invoice/<invoice_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_duplicar(invoice_id: str):
    """Duplica una factura de compra como borrador nuevo."""
    origen = database.session.get(PurchaseInvoice, invoice_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseInvoice(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        posting_date=origen.posting_date,
        supplier_invoice_no=origen.supplier_invoice_no,
        document_type=origen.document_type,
        is_return=origen.is_return,
        transaction_currency=origen.transaction_currency,
        exchange_rate=origen.exchange_rate,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicada)
    database.session.flush()
    assign_document_identifier(
        document=duplicada,
        entity_type="purchase_invoice",
        posting_date_raw=duplicada.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(
        database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=origen.id)
    ).scalars():
        linea = PurchaseInvoiceItem(
            purchase_invoice_id=duplicada.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
    duplicada.base_grand_total = total
    duplicada.outstanding_amount = total
    duplicada.base_outstanding_amount = total
    log_create(duplicada)
    database.session.commit()
    flash(_("Factura de compra duplicada como nuevo borrador."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=duplicada.id))


@compras.route("/purchase-invoice/<invoice_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_submit(invoice_id: str):
    """Aprueba una factura de compra."""
    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True, require_rate_positive=True)
        _validate_invoice_quantities_against_receipt(invoice_id)
        _validate_invoice_requires_supplier_link(invoice_id)
        _validate_supplier_invoice_flags(
            getattr(registro, "supplier_id", None),
            getattr(registro, "company", None),
            getattr(registro, "purchase_order_id", None),
            getattr(registro, "purchase_receipt_id", None),
        )
        _validate_duplicate_supplier_invoice(
            getattr(registro, "supplier_id", None),
            getattr(registro, "supplier_invoice_no", None),
            exclude_id=registro.id,
        )
        submit_document(registro)
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    flash(_("Factura de compra aprobada y contabilizada."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))


@compras.route("/purchase-invoice/<invoice_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_cancel(invoice_id: str):
    """Cancela una factura de compra."""
    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    from cacao_accounting.database import PaymentReference

    if (
        database.session.execute(
            database.select(PaymentReference.id).filter_by(reference_type="purchase_invoice", reference_id=invoice_id)
        )
        .scalars()
        .first()
        is not None
    ):
        flash(_("No se puede cancelar la factura de compra porque tiene pagos activos."), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    try:
        cancel_document(registro)
        log_cancel(registro)
        revert_relations_for_target("purchase_invoice", invoice_id)
        refresh_source_caches_for_target("purchase_invoice", invoice_id)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    flash(_("Factura de compra cancelada con reverso contable."), "warning")
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))


@compras.route("/supplier/<supplier_id>/habilitar-cliente", methods=["POST"])
@modulo_activo("sales")
@login_required
def compras_proveedor_habilitar_cliente(supplier_id: str):
    """Habilita un proveedor como cliente."""
    try:
        toggle_party_customer_role(supplier_id, enable=True, user_id=current_user.id)
        database.session.commit()
        flash(_("Proveedor habilitado como cliente exitosamente."), "success")
    except PartyRoleToggleError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for("compras.compras_proveedor", supplier_id=supplier_id))


@compras.route("/supplier/<supplier_id>/deshabilitar-cliente", methods=["POST"])
@modulo_activo("sales")
@login_required
def compras_proveedor_deshabilitar_cliente(supplier_id: str):
    """Deshabilita el rol de cliente de un proveedor."""
    try:
        toggle_party_customer_role(supplier_id, enable=False, user_id=current_user.id)
        database.session.commit()
        flash(_("Rol de cliente deshabilitado exitosamente."), "success")
    except PartyRoleToggleError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for("compras.compras_proveedor", supplier_id=supplier_id))


def check_budget_control(
    company: str,
    posting_date: Any,
    supplier_id: str | None,
    document_id: str,
    document_type: str,
    items: Any
) -> None:
    """Valida el control presupuestario de las líneas del documento según la política de la compañía."""
    from cacao_accounting.setup.repository import get_setup_value
    from cacao_accounting.contabilidad.budget_service import BudgetService
    from cacao_accounting.database import AuditTrail
    from flask_login import current_user
    import json
    from datetime import datetime

    # 1. Check if budget control is enabled for this company
    enabled = get_setup_value(f"budget_control_enabled_{company}", "0") == "1"
    if not enabled:
        return

    action_policy = get_setup_value(f"budget_control_action_{company}", "do_nothing")

    # 2. Group item requested amounts by (account_id, cost_center_id)
    budget_service = BudgetService()
    groups: dict[tuple, Decimal] = {}
    for item in items:
        item_code = getattr(item, "item_code", None) or ""
        amount = getattr(item, "base_amount", None) or getattr(item, "amount", None) or Decimal("0")

        acc = budget_service.resolve_expense_account(item_code, company)
        cc = budget_service.resolve_cost_center(item_code, company, supplier_id)

        acc_id = acc.id if acc else ""
        cc_id = cc.id if cc else ""

        key = (acc_id, cc_id)
        groups[key] = groups.get(key, Decimal("0")) + Decimal(str(amount))

    # 3. Validate each group against the budget
    for (acc_id, cc_id), total_requested in groups.items():
        if not acc_id:
            continue  # Skip if no account can be resolved

        result = budget_service.validate_transaction(
            company=company,
            date_val=posting_date,
            account_id=acc_id,
            cost_center_id=cc_id,
            amount=total_requested,
            document_id=document_id,
            document_type=document_type
        )

        if result["exceeded"]:
            # Audit log details
            user_id = None
            user_name = "System"
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                user_name = getattr(current_user, "name", "") or current_user.user

            doc_no = None
            if document_type == "purchase_request":
                from cacao_accounting.database import PurchaseRequest
                doc = database.session.get(PurchaseRequest, document_id)
                doc_no = doc.document_no if doc else None
            elif document_type == "purchase_order":
                from cacao_accounting.database import PurchaseOrder
                doc = database.session.get(PurchaseOrder, document_id)
                doc_no = doc.document_no if doc else None

            action_label = "Approval allowed" if action_policy != "block" else "Approval rejected"

            comment_str = (
                f"Budget exceeded\n\n"
                f"Mode:\n{action_policy}\n\n"
                f"Action:\n{action_label}"
            )

            # Save audit trail
            log_entry = AuditTrail(
                document_type=document_type,
                document_id=document_id,
                document_no=doc_no,
                company=company,
                action="budget_exceeded",
                actor_user_id=user_id,
                actor_name=user_name,
                comment=comment_str,
                timestamp=datetime.now(),
                changes_json=json.dumps({
                    "date": str(posting_date),
                    "user": user_name,
                    "company": company,
                    "document": doc_no or document_id,
                    "account_id": acc_id,
                    "cost_center_id": cc_id,
                    "budget": float(result["budget"]),
                    "available": float(result["available"]),
                    "requested": float(result["requested"]),
                    "excess": float(result["excess"]),
                    "action_executed": action_policy
                }, ensure_ascii=False)
            )
            database.session.add(log_entry)
            database.session.commit()

            # Execute configured policy action
            if action_policy == "block":
                msg = (
                    f"No es posible aprobar el documento.\n\n"
                    f"El monto solicitado excede el presupuesto disponible.\n\n"
                    f"Presupuesto:\n{result['budget']:,.2f}\n\n"
                    f"Disponible:\n{result['available']:,.2f}\n\n"
                    f"Solicitud:\n{result['requested']:,.2f}\n\n"
                    f"Exceso:\n{result['excess']:,.2f}"
                )
                raise ValueError(msg)

            elif action_policy == "notify":
                msg = (
                    f"El monto solicitado excede el presupuesto disponible.\n\n"
                    f"Presupuesto:\n{result['budget']:,.2f}\n\n"
                    f"Disponible:\n{result['available']:,.2f}\n\n"
                    f"Solicitud:\n{result['requested']:,.2f}\n\n"
                    f"Exceso:\n{result['excess']:,.2f}\n\n"
                    f"La aprobación continuará de acuerdo con la configuración de la compañía."
                )
                flash(msg, "warning")

            elif action_policy == "do_nothing":
                # Save and proceed silently
                pass
