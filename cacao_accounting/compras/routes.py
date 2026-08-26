"""Modulo de Compras."""

import json

from datetime import date

from decimal import Decimal

from logging import getLogger


from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from sqlalchemy.exc import SQLAlchemyError

from flask_login import current_user, login_required

from cacao_accounting.compras.purchase_reconciliation_service import (
    emit_goods_received_cancelled,
    get_purchase_order_status_report,
    get_purchase_reconciliation_panel_groups,
    get_purchase_reconciliation_pending,
    get_unlinked_purchase_invoices,
    get_unlinked_purchase_receipts_summary,
)

from cacao_accounting.compras.purchase_order_comparison_service import (
    current_purchase_order_comparison_round,
    open_purchase_order_comparison_round,
    purchase_request_for_comparison,
    purchase_order_comparison_rows,
    purchase_orders_for_request,
    purchase_order_comparison_round_orders,
)

from cacao_accounting.compras.purchase_request_comparison_service import (
    comparison_recommendations,
    create_purchase_orders_from_comparison,
    create_purchase_request_comparison,
    finalize_purchase_request_comparison,
    purchase_request_is_ready_to_close,
    purchase_request_line_closure_reasons,
    save_purchase_request_comparison_draft,
    supplier_quotations_for_comparison,
    supplier_quotations_for_request,
)

from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    close_purchase_quotation_comparison,
    create_purchase_quotation_award,
    current_negotiation_round,
    get_purchase_sourcing_config,
    is_purchase_manager,
    is_purchase_sourcing_authorizer,
    open_negotiation_round,
    offer_line_for_item,
    submitted_supplier_quotations,
)

from cacao_accounting.database import (
    DocumentRelation,
    ImportLandedCost,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderComparison,
    PurchaseOrderComparisonOrder,
    PurchaseOrderComparisonRound,
    PurchaseOrderComparisonRoundOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    PurchaseRequestComparisonLine,
    PurchaseRequestItem,
    PaymentEntry,
    PaymentReference,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    database,
)


from cacao_accounting.audit_trail_service import (
    format_document_timeline,
    log_cancel,
    log_create,
    log_line_closure,
    log_submit,
    log_update,
)

from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document

from cacao_accounting.contabilidad.budget_service import BudgetError


from cacao_accounting.decorators import (  # noqa: F401
    exige_acceso_compania,
    exige_acceso_compania_cualquiera,
    modulo_activo,
    verifica_acceso as verifica_acceso,
    verifica_permiso,
)

from cacao_accounting.document_flow import (
    DocumentFlowError,
    get_target_line_source,
    get_create_actions,
    refresh_source_caches_for_target,
    revert_relations_for_target,
    validate_submit_prerequisites,
)

from cacao_accounting.document_flow.context import company_currency, effective_currency

from cacao_accounting.document_flow.repository import has_active_source_relations


from cacao_accounting.document_flow.status import _

from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier


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
    party_company_settings_rows,
    upsert_party_company_settings_rows,
)

from cacao_accounting.version import APPNAME

from cacao_accounting.compras.services import (
    _logistics_values,
    _copy_logistics,
    _landed_cost_snapshot,
    _parse_date,
    _series_choices,
    _party_or_404,
    _paginate_list,
    _require_purchase_document_access,
    _require_requested_purchase_company_access,
    _can_manage_purchase_receipts,
    _supplier_quotation_origin_ids,
    _create_supplier_quotation_from_request,
    _validate_supplier_quotation_origin,
    _supplier_quotation_selected_company,
    _purchase_quotation_selected_company,
    _supplier_quotation_supplier_choices,
    _supplier_quotation_catalogs,
    _supplier_quotation_transaction_config,
    _supplier_quotation_initial_source_type,
    _supplier_quotation_sources,
    _handle_supplier_quotation_update,
    _handle_supplier_create,
    _handle_supplier_update,
    _create_purchase_orders_from_award,
    _save_purchase_request_items,
    _build_purchase_order_transaction_config,
    _purchase_order_source_type,
    _purchase_order_selected_company,
    _purchase_order_supplier_choices,
    _purchase_order_catalogs,
    _purchase_order_transaction_config,
    _create_purchase_order_from_request,
    _update_purchase_order_from_request,
    _purchase_quotation_origin_id,
    _purchase_quotation_supplier_choices,
    _purchase_quotation_catalogs,
    _purchase_quotation_transaction_config,
    _create_purchase_quotation_from_request,
    _handle_purchase_quotation_edit_post,
    _create_purchase_receipt_from_form,
    _handle_purchase_receipt_edit_post,
    _set_purchase_document_totals,
    _set_purchase_receipt_totals,
    _validate_receipt_quantities_against_po,
    _validate_invoice_quantities_against_receipt,
    _validate_invoice_requires_supplier_link,
    _purchase_invoice_selected_company,
    _purchase_invoice_supplier_choices,
    _purchase_invoice_source_ids,
    _purchase_invoice_document_type,
    _purchase_invoice_sources,
    _purchase_invoice_catalogs,
    _purchase_invoice_transaction_config,
    _capture_purchase_state,
    _validate_supplier_invoice_flags,
    _validate_duplicate_supplier_invoice,
    _validate_purchase_reversal_of,
    _persist_purchase_reversal_relation,
    _has_active_purchase_reversal_notes,
    _create_purchase_invoice_from_request,
    _handle_purchase_invoice_edit_post,
    _create_import_landed_cost_from_request,
    _get_import_landed_cost_items,
    _get_import_landed_cost_charges,
    check_budget_control,
)

logger = getLogger(__name__)

compras = Blueprint("compras", __name__, template_folder="templates")

PURCHASE_INVOICE = "purchase_invoice"

PURCHASE_DEBIT_NOTE = "purchase_debit_note"

PURCHASE_CREDIT_NOTE = "purchase_credit_note"

PURCHASE_RETURN = "purchase_return"

FACTURA_COMPRA_LABEL = "Factura de Compra"

COMPRAS_IMPORT_LANDED_COST_ENDPOINT = "compras.compras_import_landed_cost"

COMPRAS_PROVEEDOR_ENDPOINT = "compras.compras_proveedor"

COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT = "compras.compras_comparativo_ofertas"

DOCUMENT_REQUIRES_LINE_MSG = "El documento requiere al menos una línea."

SOLICITUD_CANCELACION_PENDIENTE_MSG = "Solicitud de cancelación enviada para aprobación (Pendiente de Cancelación)."

FACTURA_DE_COMPRA = FACTURA_COMPRA_LABEL

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

ROUTE_COMPRAS_PROVEEDOR = COMPRAS_PROVEEDOR_ENDPOINT

LABEL_SOLICITUD_COMPRA = "Solicitud de Compra"

LABEL_SOLICITUD_COTIZACION = "Solicitud de Cotización"

LABEL_ORDEN_COMPRA = "Orden de Compra"

LABEL_FACTURA_COMPRA_LONG = FACTURA_COMPRA_LABEL

IMPORT_LANDED_COST = "import_landed_cost"

IMPORT_LANDED_COST_LABEL = "Costo de Importación"

COMPARATIVO_OFERTAS_TITULO = "Comparativo de Ofertas - "

COMPRAS_COMPARATIVO_ORDENES = "compras.compras_comparativo_ordenes"

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    PURCHASE_INVOICE: FACTURA_DE_COMPRA,
    PURCHASE_DEBIT_NOTE: "Nota de Débito de Compra",
    PURCHASE_CREDIT_NOTE: "Nota de Crédito de Compra",
    PURCHASE_RETURN: "Devolución de Compra",
    IMPORT_LANDED_COST: IMPORT_LANDED_COST_LABEL,
}


@compras.route("/")
@compras.route("/compras")
@compras.route("/buying")
@modulo_activo("purchases")
@login_required
def compras_():
    """Pantalla principal del modulo de compras."""
    return render_template("compras.html")


@compras.route("/purchase-order/list")
@modulo_activo(("purchases", "inventory"))
@login_required
def compras_orden_compra_lista():
    """Listado de ordenes de compra."""
    consulta = _paginate_list(
        PurchaseOrder,
        (PurchaseOrder.document_no, PurchaseOrder.supplier_name, PurchaseOrder.supplier_invoice_no, PurchaseOrder.remarks),
        access_modules=("purchases", "inventory"),
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
        (PurchaseRequest.document_no, PurchaseRequest.requested_by, PurchaseRequest.remarks),
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
        "showPricing": False,
        "availableSourceTypes": [],
    }
    if request.method == "POST":
        try:
            posting_date = _parse_date(request.form.get("posting_date"))
            company = request.form.get("company") or None
            exige_acceso_compania("purchases", company, "crear")
            solicitud = PurchaseRequest(
                requested_by=getattr(current_user, "user", None) or str(current_user.id),
                company=company,
                transaction_currency=request.form.get("transaction_currency") or request.form.get("currency") or None,
                base_currency=company_currency(company),
                posting_date=posting_date,
                remarks=request.form.get("remarks"),
                docstatus=0,
                created_by=str(current_user.id),
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
            _set_purchase_document_totals(solicitud, total)
            log_create(solicitud)
            database.session.commit()
            flash("Solicitud de compra creada correctamente.", "success")
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=solicitud.id))
        except (IdentifierConfigurationError, DocumentFlowError, ValueError) as exc:
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
    _require_purchase_document_access(registro)
    items = database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=request_id)).all()
    create_actions = get_create_actions("purchase_request", request_id)
    create_actions_json = json.dumps(create_actions, ensure_ascii=False)
    titulo = (registro.document_no or request_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("purchase_request", registro.id)
    can_close = registro.docstatus == 1 and registro.status != "closed" and purchase_request_is_ready_to_close(registro)
    return render_template(
        "compras/solicitud_compra.html",
        registro=registro,
        items=items,
        titulo=titulo,
        create_actions_json=create_actions_json,
        audit_timeline=audit_timeline,
        can_close=can_close,
    )


@compras.route("/purchase-request/<request_id>/close", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_solicitud_compra_close(request_id: str):
    """Close a purchase request whose lines are compared or directly ordered."""
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 1 or registro.status == "closed":
        abort(400)
    if not purchase_request_is_ready_to_close(registro):
        flash(
            "La Solicitud de Compra requiere comparativos cerrados u órdenes de compra activas para todas sus líneas.",
            "danger",
        )
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    before = {"status": registro.status}
    registro.status = "closed"
    log_update(registro, before=before, after={"status": registro.status})
    request_items = {
        item.id: item
        for item in database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=registro.id))
        .scalars()
        .all()
    }
    for item_id, reason in sorted(purchase_request_line_closure_reasons(registro).items()):
        item = request_items.get(item_id)
        label = (item.item_code or item.id) if item else item_id
        log_line_closure(registro, f"Cierre de línea {label}: {reason}")
    database.session.commit()
    flash("Solicitud de Compra cerrada correctamente.", "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))


@compras.route("/purchase-request/<request_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_editar(request_id: str):
    """Edita una solicitud de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioSolicitudCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "editar")
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
        _require_requested_purchase_company_access(registro)
        try:
            before_state = _capture_purchase_state(registro)
            registro.requested_by = request.form.get("requested_by")
            registro.company = request.form.get("company") or None
            registro.posting_date = _parse_date(request.form.get("posting_date"))
            registro.remarks = request.form.get("remarks")
            for item in database.session.execute(
                database.select(PurchaseRequestItem).filter_by(purchase_request_id=registro.id)
            ).scalars():
                database.session.delete(item)
            _qty, total = _save_purchase_request_items(registro.id)
            _set_purchase_document_totals(registro, total)
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
    _require_purchase_document_access(origen, "crear")
    duplicada = PurchaseRequest(
        requested_by=getattr(current_user, "user", None) or str(current_user.id),
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
        created_by=str(current_user.id),
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
    _set_purchase_document_totals(duplicada, total)
    log_create(duplicada)
    database.session.commit()
    flash("Solicitud de compra duplicada como nuevo borrador.", "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=duplicada.id))


@compras.route("/purchase-request/<request_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_solicitud_compra_submit(request_id: str):
    """Aprueba una solicitud de compra.

    ``require_party=False`` es intencional: una solicitud de compra interna
    puede aprobarse sin proveedor asignado. El proveedor se asigna al
    convertir en cotización u orden de compra.
    """
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=False, require_rate_positive=False)
        check_budget_control(
            company=registro.company,
            posting_date=registro.posting_date,
            supplier_id=None,
            document_id=registro.id,
            document_type="purchase_request",
            items=items,
        )
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Solicitud de compra"):
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))

        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except (ValueError, BudgetError) as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    flash("Solicitud de compra aprobada.", "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))


@compras.route("/purchase-request/<request_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "anular")
def compras_solicitud_compra_cancel(request_id: str):
    """Cancela una solicitud de compra."""
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_request", request_id):
        flash("No se puede cancelar la solicitud de compra porque tiene órdenes de compra o cotizaciones activas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
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
    if from_request_id and from_rfq_id:
        abort(400, "No se pueden combinar dos documentos origen.")
    negotiation_round = current_negotiation_round(from_rfq_id) if from_rfq_id else None
    if negotiation_round and negotiation_round.status != "open":
        negotiation_round = None
    solicitud_origen, rfq_origen = _supplier_quotation_sources(from_request_id, from_rfq_id)
    _validate_supplier_quotation_origin(solicitud_origen or rfq_origen)
    items_disponibles, uoms_disponibles = _supplier_quotation_catalogs()
    titulo = "Nueva Cotización de Proveedor - " + APPNAME
    transaction_config = _supplier_quotation_transaction_config(
        form_key=FORMKEY_SUPPLIER_QUOTATION,
        items=items_disponibles,
        uoms=uoms_disponibles,
        initial_source_type=_supplier_quotation_initial_source_type(from_request_id, from_rfq_id),
    )
    source = solicitud_origen or rfq_origen
    if source:
        transaction_config["initialHeader"] = {
            "company": source.company or "",
            "currency": effective_currency(source) or "",
            "posting_date": str(date.today()),
        }
        transaction_config["initialHeader"].update(_logistics_values(source))
        if rfq_origen:
            transaction_config["initialHeader"].update(
                {
                    "party": rfq_origen.supplier_id or "",
                    "party_label": rfq_origen.supplier_name or "",
                }
            )
    return render_template(
        "compras/cotizacion_proveedor_nueva.html",
        form=formulario,
        titulo=titulo,
        solicitud_origen=solicitud_origen,
        from_request_id=from_request_id,
        rfq_origen=rfq_origen,
        from_rfq_id=from_rfq_id,
        negotiation_round_id=negotiation_round.id if negotiation_round else None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/supplier-quotation/<quotation_id>")
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor(quotation_id: str):
    """Detalle de una cotización de proveedor."""
    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro)
    items = database.session.execute(
        database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=quotation_id)
    ).all()
    titulo = (registro.document_no or quotation_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("supplier_quotation", registro.id)
    return render_template(
        "compras/cotizacion_proveedor.html", registro=registro, items=items, titulo=titulo, audit_timeline=audit_timeline
    )


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
    _require_purchase_document_access(registro, "editar")
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioCotizacionProveedor(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("supplier_quotation", selected_company)
    formulario.supplier_id.choices = _supplier_quotation_supplier_choices()
    items_disponibles, uoms_disponibles = _supplier_quotation_catalogs()

    if request.method == "POST":
        _require_requested_purchase_company_access(registro)
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
            **_logistics_values(registro),
        },
        initial_lines=[
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
                **get_target_line_source("supplier_quotation", item.id),
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


@compras.route("/supplier-quotation/<quotation_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_duplicar(quotation_id: str):
    """Duplica una cotizacion de proveedor como borrador nuevo."""
    origen = database.session.get(SupplierQuotation, quotation_id)
    if not origen:
        abort(404)
    _require_purchase_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicada = SupplierQuotation(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        purchase_quotation_id=None,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    _copy_logistics(duplicada, origen)
    duplicada.landed_cost_estimates_json = _landed_cost_snapshot(source=origen)
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
    _set_purchase_document_totals(duplicada, total)
    log_create(duplicada)
    database.session.commit()
    flash(_("Cotizacion de proveedor duplicada como nuevo borrador."), "success")
    return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=duplicada.id))


@compras.route("/supplier-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_cotizacion_proveedor_submit(quotation_id: str):
    """Aprueba una cotizacion de proveedor."""
    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True, require_rate_positive=True)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Cotización de proveedor"):
            return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))

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
@verifica_permiso("purchases", "anular")
def compras_cotizacion_proveedor_cancel(quotation_id: str):
    """Cancela una cotizacion de proveedor."""
    registro = database.session.get(SupplierQuotation, quotation_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("supplier_quotation", quotation_id):
        flash("No se puede cancelar la cotización de proveedor porque tiene solicitudes de cotización activas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
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
    """List approved purchase requests and their current comparison status."""
    consulta = _paginate_list(
        PurchaseRequest,
        (PurchaseRequest.document_no, PurchaseRequest.requested_by, PurchaseRequest.remarks),
        query=database.select(PurchaseRequest).where(PurchaseRequest.docstatus == 1),
    )
    comparisons_by_request: dict[str, PurchaseRequestComparison] = {}
    request_ids = [item.id for item in consulta.items]
    if request_ids:
        comparisons = database.session.execute(
            database.select(PurchaseRequestComparison)
            .where(PurchaseRequestComparison.purchase_request_id.in_(request_ids))
            .order_by(PurchaseRequestComparison.created.desc(), PurchaseRequestComparison.id.desc())
        ).scalars()
        for comparison in comparisons:
            comparisons_by_request.setdefault(comparison.purchase_request_id, comparison)
    titulo = COMPARATIVO_OFERTAS_TITULO + APPNAME
    return render_template(
        "compras/comparativo_ofertas_lista.html",
        consulta=consulta,
        comparisons_by_request=comparisons_by_request,
        titulo=titulo,
    )


@compras.route("/request-for-quotation/comparison/new")
@modulo_activo("purchases")
@login_required
def compras_comparativo_ofertas_nueva():
    """Display eligible purchase requests to start a new comparison."""
    return compras_comparativo_ofertas_lista()


@compras.route("/request-for-quotation/comparison/purchase-request/<purchase_request_id>", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_comparativo_ordenes_seleccionar(purchase_request_id: str):
    """Select supplier quotations associated with a purchase request."""
    purchase_request = database.session.get(PurchaseRequest, purchase_request_id)
    if not purchase_request or purchase_request.docstatus != 1:
        abort(404)
    _require_purchase_document_access(purchase_request)
    candidates = supplier_quotations_for_request(purchase_request)
    candidate_ids = {quotation.id for quotation in candidates}
    if request.method == "POST":
        exige_acceso_compania("purchases", purchase_request.company, "crear")
        participant_ids = request.form.getlist("supplier_quotation_ids")
        if not participant_ids or not set(participant_ids).issubset(candidate_ids):
            flash_error("Seleccione únicamente cotizaciones de proveedor de la misma Solicitud de Compra.")
            return redirect(
                url_for(
                    "compras.compras_comparativo_ordenes_seleccionar",
                    purchase_request_id=purchase_request_id,
                )
            )
        try:
            comparison = create_purchase_request_comparison(purchase_request, participant_ids, current_user.id)
            database.session.commit()
            return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison.id))
        except (IdentifierConfigurationError, SQLAlchemyError) as exc:
            database.session.rollback()
            flash_error(exc)
    return render_template(
        "compras/comparativo_ordenes_seleccionar.html",
        purchase_request=purchase_request,
        candidates=candidates,
        titulo="Crear comparativo de ofertas - " + APPNAME,
    )


@compras.route("/request-for-quotation/comparison/<comparison_id>/draft", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_comparativo_guardar_borrador(comparison_id: str):
    """Save per-line selections without finalizing the comparison."""
    comparison = database.session.get(PurchaseRequestComparison, comparison_id)
    if not comparison:
        abort(404)
    exige_acceso_compania("purchases", comparison.company, "crear")
    selections = {
        key.removeprefix("selection_"): value or None for key, value in request.form.items() if key.startswith("selection_")
    }
    reasons = {
        key.removeprefix("override_reason_"): value or None
        for key, value in request.form.items()
        if key.startswith("override_reason_")
    }
    try:
        save_purchase_request_comparison_draft(comparison, selections, reasons, current_user.id)
        database.session.commit()
        flash(_("Borrador del comparativo guardado correctamente."), "success")
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison_id))


@compras.route("/request-for-quotation/comparison/<comparison_id>/negotiation-round", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_comparativo_solicitud_abrir_ronda(comparison_id: str):
    """Open a negotiation round for one RFQ participating in a request comparison."""
    request_comparison = database.session.get(PurchaseRequestComparison, comparison_id)
    if not request_comparison:
        abort(404)
    exige_acceso_compania("purchases", request_comparison.company, "autorizar")
    rfq_id = request.form.get("rfq_id") or ""
    rfq = database.session.get(PurchaseQuotation, rfq_id)
    participant = database.session.execute(
        database.select(PurchaseRequestComparisonOffer)
        .join(SupplierQuotation, SupplierQuotation.id == PurchaseRequestComparisonOffer.supplier_quotation_id)
        .where(
            PurchaseRequestComparisonOffer.comparison_id == request_comparison.id,
            SupplierQuotation.purchase_quotation_id == rfq_id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if not rfq or not participant or rfq.company != request_comparison.company or rfq.docstatus != 1:
        abort(404)
    _require_purchase_document_access(rfq, "crear")
    try:
        open_negotiation_round(rfq.id, current_user.id)
        database.session.commit()
        flash("Nueva ronda de negociación abierta para la Solicitud de Cotización.", "success")
    except (PurchaseSourcingError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison_id))


@compras.route("/request-for-quotation/comparison/<comparison_id>/finalize", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_comparativo_finalizar(comparison_id: str):
    """Authorize and finalize a purchase-request comparison."""
    comparison = database.session.get(PurchaseRequestComparison, comparison_id)
    if not comparison:
        abort(404)
    exige_acceso_compania("purchases", comparison.company, "autorizar")
    selections = {
        key.removeprefix("selection_"): value or None for key, value in request.form.items() if key.startswith("selection_")
    }
    reasons = {
        key.removeprefix("override_reason_"): value or None
        for key, value in request.form.items()
        if key.startswith("override_reason_")
    }
    try:
        save_purchase_request_comparison_draft(comparison, selections, reasons, current_user.id)
        finalize_purchase_request_comparison(
            comparison,
            current_user.id,
            is_purchase_sourcing_authorizer(current_user.id),
        )
        database.session.commit()
        flash(_("Comparativo autorizado y finalizado correctamente."), "success")
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison_id))


@compras.route("/request-for-quotation/comparison/<comparison_id>/place-purchase-orders", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_comparativo_colocar_ordenes_solicitud(comparison_id: str):
    """Create purchase orders grouped by supplier from a finalized comparison."""
    comparison = database.session.get(PurchaseRequestComparison, comparison_id)
    if not comparison:
        abort(404)
    exige_acceso_compania("purchases", comparison.company, "crear")
    try:
        orders = create_purchase_orders_from_comparison(comparison)
        database.session.commit()
        flash(_("Se crearon {} Órdenes de Compra correctamente.").format(len(orders)), "success")
    except (DocumentFlowError, IdentifierConfigurationError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison_id))


@compras.route("/request-for-quotation/comparison/<comparison_id>/round", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_comparativo_ordenes_abrir_ronda(comparison_id: str):
    """Open an authorized immutable round with an explicit order snapshot."""
    comparison = database.session.get(PurchaseOrderComparison, comparison_id)
    if not comparison:
        abort(404)
    exige_acceso_compania("purchases", comparison.company, "autorizar")
    purchase_request = purchase_request_for_comparison(comparison)
    if not purchase_request:
        abort(404)
    assert purchase_request is not None
    candidate_orders = purchase_orders_for_request(purchase_request)
    candidate_ids = {order.id for order in candidate_orders}
    participant_ids = set(request.form.getlist("participant_ids"))
    if not participant_ids.issubset(candidate_ids):
        flash_error("Seleccione únicamente órdenes de compra de la misma Solicitud de Compra.")
        return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison.id))
    try:
        round_record = open_purchase_order_comparison_round(comparison, purchase_request, participant_ids, current_user.id)
        database.session.commit()
        flash("Nueva ronda de negociación abierta.", "success")
        return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison.id, round_id=round_record.id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_COMPARATIVO_ORDENES, comparison_id=comparison.id))


@compras.route("/request-for-quotation/comparison/<comparison_id>")
@modulo_activo("purchases")
@login_required
def compras_comparativo_ordenes(comparison_id: str):
    """Display a persisted order comparison, with legacy offer fallback."""
    comparison = database.session.get(PurchaseOrderComparison, comparison_id)
    request_comparison = database.session.get(PurchaseRequestComparison, comparison_id)
    if comparison is None and request_comparison:
        exige_acceso_compania("purchases", request_comparison.company, "consultar")
        purchase_request = database.session.get(PurchaseRequest, request_comparison.purchase_request_id)
        offers = supplier_quotations_for_comparison(request_comparison.id)
        if not purchase_request or not offers:
            abort(404)
        for offer in offers:
            _require_purchase_document_access(offer)
        negotiation_rfqs = []
        rfq_ids = {offer.purchase_quotation_id for offer in offers if offer.purchase_quotation_id}
        for rfq_id in sorted(rfq_ids):
            rfq = database.session.get(PurchaseQuotation, rfq_id)
            if rfq:
                negotiation_rfqs.append({"rfq": rfq, "round": current_negotiation_round(rfq.id)})
        comparison_lines = list(
            database.session.execute(
                database.select(PurchaseRequestComparisonLine)
                .where(PurchaseRequestComparisonLine.comparison_id == request_comparison.id)
                .order_by(PurchaseRequestComparisonLine.id)
            )
            .scalars()
            .all()
        )
        try:
            recommendations = comparison_recommendations(request_comparison)
        except ValueError:
            recommendations = []
        return render_template(
            "compras/comparativo_solicitud.html",
            comparison=request_comparison,
            purchase_request=purchase_request,
            offers=offers,
            recommendations=recommendations,
            comparison_lines=comparison_lines,
            negotiation_rfqs=negotiation_rfqs,
            is_purchase_sourcing_authorizer=is_purchase_sourcing_authorizer(current_user.id),
            titulo=COMPARATIVO_OFERTAS_TITULO + (request_comparison.document_no or request_comparison.id or ""),
        )

    if not comparison:
        abort(404)
    exige_acceso_compania("purchases", comparison.company, "consultar")
    purchase_request = purchase_request_for_comparison(comparison)
    selected_round = None
    requested_round_id = request.args.get("round_id")
    if requested_round_id:
        selected_round = database.session.get(PurchaseOrderComparisonRound, requested_round_id)
        if not selected_round or selected_round.comparison_id != comparison.id:
            abort(404)
    else:
        selected_round = current_purchase_order_comparison_round(comparison.id)
    participant_rows: list[PurchaseOrderComparisonRoundOrder | PurchaseOrderComparisonOrder] = (
        list(purchase_order_comparison_round_orders(selected_round.id)) if selected_round else []
    )
    if not participant_rows:
        participant_rows = list(
            database.session.execute(
                database.select(PurchaseOrderComparisonOrder)
                .where(PurchaseOrderComparisonOrder.comparison_id == comparison.id)
                .order_by(PurchaseOrderComparisonOrder.is_base.desc(), PurchaseOrderComparisonOrder.created)
            )
            .scalars()
            .all()
        )
    orders: list[PurchaseOrder] = []
    for row in participant_rows:
        order = database.session.get(PurchaseOrder, row.purchase_order_id)
        if order is not None:
            orders.append(order)
    for order in orders:
        _require_purchase_document_access(order)
    base_order = database.session.get(PurchaseOrder, comparison.base_purchase_order_id)
    if not base_order:
        abort(404)
    order_items = {
        order.id: list(
            database.session.execute(
                database.select(PurchaseOrderItem)
                .where(PurchaseOrderItem.purchase_order_id == order.id)
                .order_by(PurchaseOrderItem.id)
            )
            .scalars()
            .all()
        )
        for order in orders
    }
    comparison_rows = purchase_order_comparison_rows(orders, order_items)
    rounds = list(
        database.session.execute(
            database.select(PurchaseOrderComparisonRound)
            .where(PurchaseOrderComparisonRound.comparison_id == comparison.id)
            .order_by(PurchaseOrderComparisonRound.round_number.desc())
        )
        .scalars()
        .all()
    )
    participant_order_ids = {row.purchase_order_id for row in participant_rows}
    return render_template(
        "compras/comparativo_ordenes.html",
        comparison=comparison,
        purchase_request=purchase_request,
        base_order=base_order,
        orders=orders,
        comparison_rows=comparison_rows,
        candidate_orders=purchase_orders_for_request(purchase_request) if purchase_request else [],
        participant_order_ids=participant_order_ids,
        rounds=rounds,
        selected_round=selected_round,
        titulo=COMPARATIVO_OFERTAS_TITULO + (comparison.id or ""),
    )


@compras.route("/request-for-quotation/<rfq_id>/offers")
@modulo_activo("purchases")
@login_required
def compras_comparativo_ofertas(rfq_id: str):
    """Comparativo de ofertas para una solicitud de cotización específica."""
    registro = database.session.get(PurchaseQuotation, rfq_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro)
    offers = submitted_supplier_quotations(rfq_id)
    rfq_items = (
        database.session.execute(database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=rfq_id))
        .scalars()
        .all()
    )
    offer_lines = {
        offer.id: {item.id: offer_line_for_item(offer.id, item, rfq_items) for item in rfq_items} for offer in offers
    }
    award = database.session.execute(
        database.select(PurchaseQuotationAward)
        .filter_by(purchase_quotation_id=rfq_id)
        .order_by(PurchaseQuotationAward.created.desc())
    ).scalar_one_or_none()
    award_lines = (
        database.session.execute(database.select(PurchaseQuotationAwardItem).filter_by(award_id=award.id)).scalars().all()
        if award
        else []
    )
    titulo = COMPARATIVO_OFERTAS_TITULO + (registro.document_no or rfq_id)
    return render_template(
        "compras/comparativo_ofertas.html",
        registro=registro,
        offers=offers,
        rfq_items=rfq_items,
        offer_lines=offer_lines,
        sourcing_config=get_purchase_sourcing_config(),
        is_purchase_manager=is_purchase_manager(current_user.id),
        is_purchase_sourcing_authorizer=is_purchase_sourcing_authorizer(current_user.id),
        award=award,
        award_lines=award_lines,
        negotiation_round=current_negotiation_round(rfq_id),
        titulo=titulo,
    )


@compras.route("/request-for-quotation/<rfq_id>/negotiation-round", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_comparativo_abrir_ronda(rfq_id: str):
    """Open the next supplier negotiation round for an RFQ."""
    registro = database.session.get(PurchaseQuotation, rfq_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "crear")
    try:
        open_negotiation_round(rfq_id, current_user.id)
        database.session.commit()
        flash("Nueva ronda de negociación abierta.", "success")
    except PurchaseSourcingError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT, rfq_id=rfq_id))


@compras.route("/request-for-quotation/<rfq_id>/award", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_comparativo_ofertas_adjudicar(rfq_id: str):
    """Adjudica líneas del comparativo y registra excepciones autorizadas."""
    registro = database.session.get(PurchaseQuotation, rfq_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "autorizar")
    selections = {
        key.removeprefix("award_item_"): value
        for key, value in request.form.items()
        if key.startswith("award_item_") and value
    }
    reason = request.form.get("authorization_reason") or None
    try:
        create_purchase_quotation_award(registro, selections, current_user.id, reason)
        database.session.commit()
        flash(_("Comparativo confirmado y finalizado correctamente."), "success")
        return redirect(url_for(COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT, rfq_id=rfq_id))
    except PurchaseSourcingError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT, rfq_id=rfq_id))


@compras.route("/request-for-quotation/<rfq_id>/close", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_comparativo_ofertas_cerrar(rfq_id: str):
    """Close an RFQ comparison manually with an authorization reason."""
    registro = database.session.get(PurchaseQuotation, rfq_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "autorizar")
    reason = request.form.get("authorization_reason") or None
    try:
        close_purchase_quotation_comparison(registro, current_user.id, reason)
        database.session.commit()
        flash(_("Comparativo cerrado manualmente con justificación."), "success")
    except PurchaseSourcingError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT, rfq_id=rfq_id))


@compras.route("/request-for-quotation/<rfq_id>/place-purchase-orders", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "crear")
def compras_comparativo_colocar_ordenes(rfq_id: str):
    """Place all purchase orders from a finalized quotation award."""
    registro = database.session.get(PurchaseQuotation, rfq_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "crear")
    award = database.session.execute(
        database.select(PurchaseQuotationAward)
        .filter_by(purchase_quotation_id=rfq_id)
        .order_by(PurchaseQuotationAward.created.desc())
    ).scalar_one_or_none()
    if not award or award.status != "finalized":
        flash_error(PurchaseSourcingError("El comparativo debe estar finalizado antes de colocar las órdenes."))
        return redirect(url_for(COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT, rfq_id=rfq_id))
    try:
        orders = _create_purchase_orders_from_award(award)
        database.session.commit()
        flash(_("Se colocaron {} Órdenes de Compra correctamente.").format(len(orders)), "success")
    except (PurchaseSourcingError, SQLAlchemyError, DocumentFlowError, IdentifierConfigurationError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPARATIVO_OFERTAS_ENDPOINT, rfq_id=rfq_id))


@compras.route("/purchase-receipt/list")
@modulo_activo(("purchases", "inventory"))
@login_required
def compras_recepcion_lista():
    """Listado de recepciones de compra."""
    consulta = _paginate_list(
        PurchaseReceipt,
        (PurchaseReceipt.document_no, PurchaseReceipt.supplier_name, PurchaseReceipt.remarks),
        access_modules=("purchases", "inventory"),
    )
    titulo = "Listado de Recepciones de Compra - " + APPNAME
    return render_template(
        "compras/recepcion_lista.html",
        consulta=consulta,
        titulo=titulo,
        can_manage_receipts=_can_manage_purchase_receipts(),
    )


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
    exige_acceso_compania("purchases", company, "consultar")
    rows = get_purchase_reconciliation_pending(company=company)
    order_status_report = get_purchase_order_status_report(company=company)
    unlinked_invoices = get_unlinked_purchase_invoices(company=company)
    unlinked_receipts = get_unlinked_purchase_receipts_summary(company=company)
    titulo = _("Conciliación de Compras") + " - " + APPNAME
    return render_template(
        "compras/purchase_reconciliation.html",
        rows=rows,
        order_status_report=order_status_report,
        unlinked_invoices=unlinked_invoices,
        unlinked_receipts=unlinked_receipts,
        company=company,
        titulo=titulo,
    )


@compras.route("/purchase-reconciliation/panel")
@modulo_activo("purchases")
@login_required
def compras_reconciliation_panel():
    """Panel de conciliacion de compras agrupado por orden de compra."""
    company = request.args.get("company", "cacao")
    exige_acceso_compania("purchases", company, "consultar")
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
    return render_template(
        "compras/proveedor.html",
        registro=registro[0],
        detail=detail,
        company_settings_rows=party_company_settings_rows(registro[0].id, None, role="supplier"),
        company_settings_form_action=url_for("compras.compras_proveedor_configuracion_compania", supplier_id=registro[0].id),
        titulo=titulo,
    )


@compras.route("/supplier/<supplier_id>/company-settings", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_proveedor_configuracion_compania(supplier_id: str):
    """Crea o actualiza la configuracion por compania de un proveedor."""
    _party_or_404(supplier_id)
    try:
        upsert_party_company_settings_rows(supplier_id, "supplier", request.form)
        database.session.commit()
        flash(_("Configuracion por compania del proveedor guardada correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=supplier_id) + "#party-company-settings")


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
    initial_source_type = _purchase_order_source_type(from_request_id, from_rfq_id, from_supplier_quotation_id)

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
        sourcing_config=get_purchase_sourcing_config(),
        is_purchase_manager=is_purchase_manager(current_user.id),
    )


@compras.route("/purchase-order/<order_id>")
@modulo_activo(("purchases", "inventory"))
@login_required
def compras_orden_compra(order_id):
    """Detalle de orden de compra."""
    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro)
    items = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=order_id)).all()
    titulo = (registro.document_no or order_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("purchase_order", registro.id)
    return render_template(
        "compras/orden_compra.html", registro=registro, items=items, titulo=titulo, audit_timeline=audit_timeline
    )


@compras.route("/purchase-order/<order_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_editar(order_id: str):
    """Edita una orden de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioOrdenCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioOrdenCompra(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = _purchase_order_selected_company(registro.company)
    formulario.naming_series.choices = _series_choices("purchase_order", selected_company)
    formulario.supplier_id.choices = _purchase_order_supplier_choices()
    items_disponibles, uoms_disponibles = _purchase_order_catalogs()

    if request.method == "POST":
        _require_requested_purchase_company_access(registro)
        response = _update_purchase_order_from_request(registro)
        if response is not None:
            return response

    transaction_config = _purchase_order_transaction_config(
        registro=registro,
        items=items_disponibles,
        uoms=uoms_disponibles,
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
        sourcing_config=get_purchase_sourcing_config(),
        is_purchase_manager=is_purchase_manager(current_user.id),
    )


@compras.route("/purchase-order/<order_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_orden_compra_duplicar(order_id: str):
    """Duplica una orden de compra como borrador nuevo."""
    origen = database.session.get(PurchaseOrder, order_id)
    if not origen:
        abort(404)
    _require_purchase_document_access(origen, "crear")
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
    _copy_logistics(duplicada, origen)
    duplicada.landed_cost_estimates_json = _landed_cost_snapshot(source=origen)
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
    duplicada.base_total = (total * Decimal(str(duplicada.exchange_rate or 1))).quantize(Decimal("0.0001"))
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

    formulario = FormularioSolicitudCotizacion()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = _purchase_quotation_selected_company(formulario.company.choices)
    formulario.naming_series.choices = _series_choices("purchase_quotation", selected_company)
    formulario.supplier_id.choices = _purchase_quotation_supplier_choices()
    from_request_id = _purchase_quotation_origin_id()
    solicitud_origen = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
    source_currency = effective_currency(solicitud_origen) if solicitud_origen else None
    items_disponibles, uoms_disponibles = _purchase_quotation_catalogs()
    titulo = "Nueva Solicitud de Cotización - " + APPNAME
    transaction_config = _purchase_quotation_transaction_config(
        items=items_disponibles,
        uoms=uoms_disponibles,
        initial_source_type="purchase_request" if from_request_id else "",
        initial_header=(
            {
                "company": solicitud_origen.company or "",
                "currency": source_currency or "",
                "posting_date": str(date.today()),
            }
            if solicitud_origen
            else None
        ),
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


@compras.route("/request-for-quotation/<quotation_id>")
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion(quotation_id: str):
    """Detalle de solicitud de cotización."""
    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro)
    items = database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=quotation_id)
    ).all()
    offers = database.session.execute(database.select(SupplierQuotation).filter_by(purchase_quotation_id=quotation_id)).all()
    titulo = (registro.document_no or quotation_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("purchase_quotation", registro.id)
    return render_template(
        "compras/solicitud_cotizacion.html",
        registro=registro,
        items=items,
        offers=offers,
        titulo=titulo,
        audit_timeline=audit_timeline,
    )


@compras.route("/request-for-quotation/<quotation_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_editar(quotation_id: str):
    """Edita una solicitud de cotizacion en borrador."""
    from cacao_accounting.compras.forms import FormularioSolicitudCotizacion
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "editar")
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
        _require_requested_purchase_company_access(registro)
        return _handle_purchase_quotation_edit_post(registro)

    lineas = database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_QUOTATION,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "showPricing": False,
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
                **get_target_line_source("purchase_quotation", item.id),
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
    _require_purchase_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseQuotation(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    _copy_logistics(duplicada, origen)
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
    _set_purchase_document_totals(duplicada, total)
    log_create(duplicada)
    database.session.commit()
    flash(_("Solicitud de cotizacion duplicada como nuevo borrador."), "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=duplicada.id))


@compras.route("/request-for-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_solicitud_cotizacion_submit(quotation_id: str):
    """Aprueba una solicitud de cotizacion.

    ``require_party=False`` es intencional: una solicitud de cotización interna
    puede aprobarse sin proveedor asignado. El proveedor se asigna al
    convertir en orden de compra.
    """
    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=False, require_rate_positive=False)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Solicitud de cotización"):
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))

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
@verifica_permiso("purchases", "anular")
def compras_solicitud_cotizacion_cancel(quotation_id: str):
    """Cancela una solicitud de cotizacion."""
    registro = database.session.get(PurchaseQuotation, quotation_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_quotation", quotation_id):
        flash("No se puede cancelar la solicitud de cotización porque tiene órdenes de compra activas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=quotation_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
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
@verifica_permiso("purchases", "autorizar")
def compras_orden_compra_submit(order_id: str):
    """Aprueba una orden de compra."""
    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=registro.id))
            .scalars()
            .all()
        )
        for item in items:
            item_obj = database.session.execute(database.select(Item).filter_by(code=item.item_code)).scalar_one_or_none()
            if not item_obj or not item_obj.is_active or not item_obj.is_purchase_item:
                raise ValueError(f"El item {item.item_code} no está habilitado para compra.")
        validate_submit_prerequisites(registro, items=items, require_party=True, require_rate_positive=True)
        check_budget_control(
            company=registro.company,
            posting_date=registro.posting_date,
            supplier_id=registro.supplier_id,
            document_id=registro.id,
            document_type="purchase_order",
            items=items,
        )
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Orden de compra"):
            return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))

        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except (ValueError, BudgetError) as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))
    flash("Orden de compra aprobada.", "success")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))


@compras.route("/purchase-order/<order_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "anular")
def compras_orden_compra_cancel(order_id: str):
    """Cancela una orden de compra."""
    registro = database.session.get(PurchaseOrder, order_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_order", order_id):
        flash("No se puede cancelar la orden de compra porque tiene recepciones o facturas activas.", "danger")
        return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("purchase_order", order_id)
    refresh_source_caches_for_target("purchase_order", order_id)
    database.session.commit()
    flash("Orden de compra cancelada.", "warning")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=order_id))


@compras.route("/purchase-receipt/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "crear")
def compras_recepcion_nuevo():
    """Formulario para crear una recepción de compra."""
    from cacao_accounting.compras.forms import FormularioRecepcionCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse

    formulario = FormularioRecepcionCompra()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()

    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    orden_origen = database.session.get(PurchaseOrder, from_order_id) if from_order_id else None

    selected_company = (
        (orden_origen.company if orden_origen else None)
        or request.values.get("company")
        or (formulario.company.choices[0][0] if formulario.company.choices else None)
    )
    formulario.naming_series.choices = _series_choices("purchase_receipt", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]
    items_disponibles = [
        {
            "code": item.code,
            "name": item.name,
            "uom": item.default_uom,
            "has_batch": item.has_batch,
            "has_serial_no": item.has_serial_no,
            "has_expiry_date": item.has_expiry_date,
        }
        for (item,) in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    # INV-03: Filtrar almacenes por compañía usando WarehouseCompanyAccount
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name}
        for w in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]
    titulo = "Nueva Recepción de Compra - " + APPNAME
    company_id = (orden_origen.company if orden_origen else None) or request.args.get("company") or selected_company
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_RECEIPT,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "initialSourceType": "purchase_order" if from_order_id else "",
        "availableSourceTypes": [{"value": "purchase_order", "label": _(LABEL_ORDEN_COMPRA)}],
        "initialHeader": {
            "company": company_id or "",
            "posting_date": str(date.today()),
        },
    }
    if orden_origen:
        source_currency = effective_currency(orden_origen)
        transaction_config["initialHeader"] = {
            "company": orden_origen.company or "",
            "currency": source_currency or "",
            "transaction_currency": source_currency or "",
            "party": orden_origen.supplier_id or "",
            "party_label": orden_origen.supplier_name or "",
            "posting_date": str(date.today()),
        }
    if request.method == "POST":
        response = _create_purchase_receipt_from_form()
        if response is not None:
            return response
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
@modulo_activo(("purchases", "inventory"))
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
    _require_purchase_document_access(registro)
    items = database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id)).all()
    create_actions = get_create_actions("purchase_receipt", receipt_id)
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
@modulo_activo("inventory")
@login_required
def compras_recepcion_editar(receipt_id: str):
    """Edita una recepcion de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioRecepcionCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse

    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
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
        {
            "code": item.code,
            "name": item.name,
            "uom": item.default_uom,
            "has_batch": item.has_batch,
            "has_serial_no": item.has_serial_no,
            "has_expiry_date": item.has_expiry_date,
        }
        for (item,) in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    # INV-03: Filtrar almacenes por compañía usando WarehouseCompanyAccount
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name}
        for w in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]

    if request.method == "POST":
        _require_requested_purchase_company_access(registro)
        return _handle_purchase_receipt_edit_post(registro)

    lineas = database.session.execute(
        database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_RECEIPT,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
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
                "batch_id": item.batch_id or "",
                "serial_no": item.serial_no or "",
                **get_target_line_source("purchase_receipt", item.id),
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


@compras.route("/purchase-receipt/<receipt_id>/duplicate", methods=["POST"])
@modulo_activo("inventory")
@login_required
def compras_recepcion_duplicar(receipt_id: str):
    """Duplica una recepcion de compra como borrador nuevo."""
    origen = database.session.get(PurchaseReceipt, receipt_id)
    if not origen:
        abort(404)
    _require_purchase_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseReceipt(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    _copy_logistics(duplicada, origen)
    duplicada.landed_cost_estimates_json = _landed_cost_snapshot(source=origen)
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
            batch_id=item.batch_id,
            serial_no=item.serial_no,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    _set_purchase_receipt_totals(duplicada, total)
    log_create(duplicada)
    database.session.commit()
    flash(_("Recepcion de compra duplicada como nuevo borrador."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=duplicada.id))


@compras.route("/purchase-receipt/<receipt_id>/submit", methods=["POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "autorizar")
def compras_recepcion_submit(receipt_id: str):
    """Aprueba una recepción de compra."""
    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "autorizar")
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
        check_budget_control(
            company=registro.company,
            posting_date=registro.posting_date,
            supplier_id=registro.supplier_id,
            document_id=registro.id,
            document_type="purchase_receipt",
            items=items,
        )
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Recepción de compra"):
            return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))

        submit_document(registro)  # type: ignore[misc]
        log_submit(registro)
        database.session.commit()
        flash("Recepcion de compra aprobada.", "success")
    except (ValueError, BudgetError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))


@compras.route("/purchase-receipt/<receipt_id>/cancel", methods=["POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "anular")
def compras_recepcion_cancel(receipt_id: str):
    """Cancela una recepción de compra."""
    registro = database.session.get(PurchaseReceipt, receipt_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("purchase_receipt", receipt_id):
        flash("No se puede cancelar la recepción de compra porque tiene facturas de compra activas.", "danger")
        return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    try:
        cancel_document(registro)  # type: ignore[misc]
        emit_goods_received_cancelled(receipt_id, registro.company)
        revert_relations_for_target("purchase_receipt", receipt_id)
        refresh_source_caches_for_target("purchase_receipt", receipt_id)
        log_cancel(registro)
        database.session.commit()
        flash("Recepción de compra cancelada.", "warning")
    except PostingError as exc:  # type: ignore[misc]
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

    selected_company = _purchase_invoice_selected_company(formulario.company.choices)
    formulario.naming_series.choices = _series_choices("purchase_invoice", selected_company)
    formulario.supplier_id.choices = _purchase_invoice_supplier_choices()
    source_ids = _purchase_invoice_source_ids()
    from_order_id = source_ids["from_order_id"]
    from_receipt_id = source_ids["from_receipt_id"]
    from_invoice_id = source_ids["from_invoice_id"]
    document_type = _purchase_invoice_document_type(source_ids, request.args.get("document_type"))
    formulario.is_return.data = document_type == PURCHASE_RETURN
    orden_origen, recepcion_origen, factura_origen = _purchase_invoice_sources(source_ids)
    document_title = DOCUMENT_TYPE_LABELS.get(document_type, FACTURA_DE_COMPRA)
    items_disponibles, uoms_disponibles = _purchase_invoice_catalogs()
    titulo = f"Nueva {document_title} - {APPNAME}"
    company_id = (
        (orden_origen.company if orden_origen else None)
        or (recepcion_origen.company if recepcion_origen else None)
        or (factura_origen.company if factura_origen else None)
        or request.args.get("company")
        or selected_company
    )
    transaction_config = _purchase_invoice_transaction_config(
        items=items_disponibles,
        uoms=uoms_disponibles,
        company_id=company_id,
    )
    if from_order_id or from_receipt_id or from_invoice_id:
        initial_source_type = "purchase_invoice"
        if from_order_id:
            initial_source_type = "purchase_order"
        elif from_receipt_id:
            initial_source_type = "purchase_receipt"
        transaction_config["initialSourceType"] = initial_source_type
        source = orden_origen or recepcion_origen or factura_origen
        source_currency = effective_currency(source)
        transaction_config["initialHeader"] = {
            "company": getattr(source, "company", None) or "",
            "currency": source_currency or "",
            "transaction_currency": source_currency or "",
            "posting_date": str(date.today()),
            "party": getattr(source, "supplier_id", None) or "",
            "party_label": getattr(source, "supplier_name", None) or "",
        }
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


@compras.route("/purchase-invoice/<invoice_id>")
@modulo_activo("purchases")
@login_required
def compras_factura_compra(invoice_id):
    """Detalle de factura de compra."""
    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro)
    items = database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id)).all()
    titulo = (registro.document_no or invoice_id) + " - " + APPNAME
    document_type_label = DOCUMENT_TYPE_LABELS.get(registro.document_type, FACTURA_DE_COMPRA)
    audit_timeline = format_document_timeline(registro.document_type or "purchase_invoice", registro.id)
    return render_template(
        "compras/factura_compra.html",
        registro=registro,
        items=items,
        titulo=titulo,
        document_type_label=document_type_label,
        audit_timeline=audit_timeline,
    )


@compras.route("/purchase-invoice/<invoice_id>/edit", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_editar(invoice_id: str):
    """Edita una factura de compra en borrador."""
    from cacao_accounting.compras.forms import FormularioFacturaCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
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
        {
            "code": item.code,
            "name": item.name,
            "uom": item.default_uom,
            "has_batch": item.has_batch,
            "has_serial_no": item.has_serial_no,
            "has_expiry_date": item.has_expiry_date,
        }
        for (item,) in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        _require_requested_purchase_company_access(registro)
        return _handle_purchase_invoice_edit_post(registro)

    lineas = database.session.execute(
        database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=registro.id)
    ).scalars()
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_INVOICE,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
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
                "batch_id": item.batch_id or "",
                "serial_no": item.serial_no or "",
                **get_target_line_source("purchase_invoice", item.id),
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


@compras.route("/purchase-invoice/<invoice_id>/duplicate", methods=["POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_duplicar(invoice_id: str):
    """Duplica una factura de compra como borrador nuevo."""
    origen = database.session.get(PurchaseInvoice, invoice_id)
    if not origen:
        abort(404)
    _require_purchase_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicada = PurchaseInvoice(
        supplier_id=origen.supplier_id,
        supplier_name=origen.supplier_name,
        company=origen.company,
        posting_date=origen.posting_date,
        supplier_invoice_no=origen.supplier_invoice_no,
        document_type=origen.document_type,
        tax_template_id=origen.tax_template_id,
        is_return=origen.is_return,
        transaction_currency=origen.transaction_currency,
        exchange_rate=origen.exchange_rate,
        remarks=origen.remarks,
        docstatus=0,
    )
    _copy_logistics(duplicada, origen)
    duplicada.landed_cost_estimates_json = _landed_cost_snapshot(source=origen)
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
            batch_id=item.batch_id,
            serial_no=item.serial_no,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    exchange_rate = Decimal(str(duplicada.exchange_rate or 1))
    base_total = (total * exchange_rate).quantize(Decimal("0.0001"))
    duplicada.base_total = base_total
    duplicada.grand_total = total
    duplicada.base_grand_total = base_total
    duplicada.outstanding_amount = total
    duplicada.base_outstanding_amount = base_total
    log_create(duplicada)
    database.session.commit()
    flash(_("Factura de compra duplicada como nuevo borrador."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=duplicada.id))


@compras.route("/purchase-invoice/<invoice_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_factura_compra_submit(invoice_id: str):
    """Aprueba una factura de compra."""
    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
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
            getattr(registro, "document_type", None),
        )
        _validate_duplicate_supplier_invoice(
            getattr(registro, "supplier_id", None),
            getattr(registro, "supplier_invoice_no", None),
            exclude_id=registro.id,
        )
        if registro.document_type in {"purchase_return", "purchase_credit_note", "purchase_debit_note"}:
            _validate_purchase_reversal_of(
                registro.reversal_of or "",
                registro.supplier_id,
                registro.company,
                note_amount=Decimal(str(registro.grand_total or "0")),
                document_type=registro.document_type,
                posting_date=registro.posting_date,
                lock_source=True,
            )
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Factura de compra"):
            return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))

        submit_document(registro)  # type: ignore[misc]
        _persist_purchase_reversal_relation(registro)
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
@verifica_permiso("purchases", "anular")
def compras_factura_compra_cancel(invoice_id: str):
    """Cancela una factura de compra."""
    registro = database.session.get(PurchaseInvoice, invoice_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    active_payment = (
        database.select(PaymentReference.id)
        .join(
            DocumentRelation,
            (DocumentRelation.target_item_id == PaymentReference.id)
            & (DocumentRelation.target_type == "payment_entry")
            & (DocumentRelation.status == "active"),
        )
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            PaymentReference.reference_type == "purchase_invoice",
            PaymentReference.reference_id == invoice_id,
            PaymentEntry.docstatus == 1,
        )
    )
    if database.session.execute(active_payment).scalars().first() is not None:
        flash(_("No se puede cancelar la factura de compra porque tiene pagos activos."), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    if _has_active_purchase_reversal_notes(invoice_id):
        flash(_("No se puede cancelar la factura de compra porque tiene notas de crédito o débito activas."), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    try:
        cancel_document(registro)  # type: ignore[misc]
        log_cancel(registro)
        target_type = registro.document_type or "purchase_invoice"
        revert_relations_for_target(target_type, invoice_id)
        refresh_source_caches_for_target(target_type, invoice_id)
        if registro.reversal_of:
            from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache

            source = database.session.get(PurchaseInvoice, registro.reversal_of)
            if source:
                refresh_outstanding_amount_cache(source)
        database.session.commit()
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    flash(_("Factura de compra cancelada con reverso contable."), "warning")
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))


@compras.route("/import-landed-cost/list")
@modulo_activo("purchases")
@login_required
def compras_import_landed_cost_lista():
    """Listado de costos de importacion."""
    consulta = _paginate_list(
        ImportLandedCost,
        (ImportLandedCost.document_no, ImportLandedCost.supplier_name, ImportLandedCost.remarks),
    )
    titulo = "Listado de Costos de Importacion - " + APPNAME
    return render_template("compras/import_landed_cost_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/import-landed-cost/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_import_landed_cost_nuevo():
    """Formulario para crear un costo de importacion."""
    from cacao_accounting.compras.forms import FormularioImportLandedCost
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioImportLandedCost()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()

    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("import_landed_cost", selected_company)

    from_invoice_id = request.args.get("from_invoice") or request.form.get("from_invoice")
    invoice_origen = None
    if from_invoice_id:
        invoice_origen = database.session.get(PurchaseInvoice, from_invoice_id)

    titulo = f"Nuevo Costo de Importacion - {APPNAME}"
    items_disponibles, uoms_disponibles = _purchase_invoice_catalogs()

    transaction_config = {
        "columns": [
            {"key": "item_code", "label": "Articulo", "type": "select", "required": True},
            {"key": "item_name", "label": "Nombre", "type": "text", "readonly": True},
            {"key": "qty", "label": "Cantidad", "type": "number", "required": True},
            {"key": "uom", "label": "UOM", "type": "select"},
            {"key": "rate", "label": "Tasa", "type": "number"},
            {"key": "amount", "label": "Monto", "type": "number"},
        ],
        "source_api_url": (
            "/api/document-flow/pending-lines"
            "?source_type=purchase_invoice&target_type=import_landed_cost&source_id=" + (from_invoice_id or "")
        ),
        "source_label": FACTURA_COMPRA_LABEL,
    }

    if request.method == "POST":
        response = _create_import_landed_cost_from_request()
        if response is not None:
            return response

    return render_template(
        "compras/import_landed_cost_nuevo.html",
        form=formulario,
        titulo=titulo,
        from_invoice_id=from_invoice_id,
        invoice_origen=invoice_origen,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@compras.route("/import-landed-cost/<landed_cost_id>")
@modulo_activo("purchases")
@login_required
def compras_import_landed_cost(landed_cost_id: str):
    """Detalle de un costo de importacion."""
    registro = database.session.get(ImportLandedCost, landed_cost_id)
    if not registro:
        abort(404)
    _require_purchase_document_access(registro)
    items = _get_import_landed_cost_items(landed_cost_id)
    cargos = _get_import_landed_cost_charges(landed_cost_id)
    titulo = f"Costo de Importacion {registro.document_no or registro.id} - {APPNAME}"
    audit_timeline = format_document_timeline("import_landed_cost", registro.id)
    return render_template(
        "compras/import_landed_cost.html",
        registro=registro,
        items=items,
        cargos=cargos,
        titulo=titulo,
        document_type_label=IMPORT_LANDED_COST_LABEL,
        audit_timeline=audit_timeline,
    )


@compras.route("/import-landed-cost/<landed_cost_id>/submit", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "autorizar")
def compras_import_landed_cost_submit(landed_cost_id: str):
    """Aprueba un costo de importacion."""
    registro = database.session.get(ImportLandedCost, landed_cost_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Costo de importacion"):
            return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=landed_cost_id))
        submit_document(registro)  # type: ignore[misc]
        log_submit(registro)
        database.session.commit()
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=landed_cost_id))
    flash(_("Costo de importacion aprobado y contabilizado."), "success")
    return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=landed_cost_id))


@compras.route("/import-landed-cost/<landed_cost_id>/cancel", methods=["POST"])
@modulo_activo("purchases")
@login_required
@verifica_permiso("purchases", "anular")
def compras_import_landed_cost_cancel(landed_cost_id: str):
    """Cancela un costo de importacion."""
    registro = database.session.get(ImportLandedCost, landed_cost_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_("Solicitud de cancelacion enviada para aprobacion."), "info")
            return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=landed_cost_id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    try:
        cancel_document(registro)  # type: ignore[misc]
        log_cancel(registro)
        revert_relations_for_target("import_landed_cost", landed_cost_id)
        refresh_source_caches_for_target("import_landed_cost", landed_cost_id)
        database.session.commit()
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=landed_cost_id))
    flash(_("Costo de importacion cancelado."), "warning")
    return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=landed_cost_id))


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
    return redirect(url_for(COMPRAS_PROVEEDOR_ENDPOINT, supplier_id=supplier_id))


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
    return redirect(url_for(COMPRAS_PROVEEDOR_ENDPOINT, supplier_id=supplier_id))
