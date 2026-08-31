"""Modulo de Ventas."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from decimal import Decimal


from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from flask_login import current_user, login_required

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    UOM,
    Warehouse,
    database,
)


from sqlalchemy.exc import SQLAlchemyError


from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document

from cacao_accounting.document_identifiers import assign_document_identifier

from cacao_accounting.document_flow import (
    close_document_balances,
    get_target_line_source,
    refresh_source_caches_for_target,
    revert_relations_for_target,
    validate_submit_prerequisites,
)

from cacao_accounting.document_flow.context import company_currency, effective_currency, validate_immutable_header

from cacao_accounting.document_flow.repository import has_active_source_relations

from cacao_accounting.document_flow.status import _

from cacao_accounting.decorators import (  # noqa: F401
    exige_acceso_compania,
    exige_acceso_compania_cualquiera,
    modulo_activo,
    verifica_acceso as verifica_acceso,
    verifica_permiso,
)


from cacao_accounting.party_settings import (
    party_company_settings_rows,
    upsert_party_company_settings_rows,
)

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
    toggle_party_customer_role as toggle_party_customer_role,  # noqa: F401
    toggle_party_supplier_role,
    PartyRoleToggleError,
    update_party_address,
    update_party_contact,
)

from cacao_accounting.version import APPNAME

from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_create, log_submit, log_update

from cacao_accounting.ventas.services import (
    _sales_logistics_values,
    _copy_sales_logistics,
    _parse_date,
    _series_choices,
    _party_or_404,
    _item_by_code,
    _validate_and_reserve_stock_for_sales_order,
    _release_reservation_for_sales_order,
    _release_reservation_for_closed_sales_order,
    _release_reservation_for_delivery_note,
    _paginate_list,
    _require_delivery_note_access,
    _can_manage_delivery_notes,
    _require_sales_document_access,
    _handle_cliente_create,
    _handle_cliente_update,
    _handle_sales_request_update,
    _handle_sales_order_update,
    _save_sales_request_items,
    _save_sales_quotation_items,
    _save_delivery_note_items,
    _create_delivery_note_from_invoice,
    _validate_invoice_prices_against_source,
    _validate_delivery_quantities_against_so,
    _validate_sales_invoice_quantities,
    _validate_sales_invoice_line_amounts,
    _validate_sales_source_link,
    _validate_sales_order_requirement,
    _sales_order_initial_source_type,
    _build_sales_order_transaction_config,
    _handle_sales_order_new_post,
    _handle_sales_quotation_edit_post,
    _handle_delivery_note_edit_post,
    _set_sales_document_totals,
    _execute_delivery_note_cancellation,
    _sales_invoice_sources_and_type,
    _sales_invoice_catalogs,
    _create_sales_invoice_from_form,
    _persist_sales_reversal_relation,
    _handle_sales_invoice_edit_post,
    _cancel_linked_delivery_note,
    _validate_credit_limit_and_overdue,
    _validate_reversal_of,
    is_sales_price_editor,
    sales_order_is_ready_to_close,
    sales_order_line_closure_reasons,
)

ventas = Blueprint("ventas", __name__, template_folder="templates")

VENTAS_CLIENTE_NUEVO_TEMPLATE = "ventas/cliente_nuevo.html"

_ENDPOINT_CLIENTE = "ventas.ventas_cliente"

_ENDPOINT_PEDIDO_VENTA = "ventas.ventas_pedido_venta"

_ENDPOINT_COTIZACION = "ventas.ventas_cotizacion"

_ENDPOINT_ORDEN_VENTA = "ventas.ventas_orden_venta"

_ENDPOINT_ENTREGA = "ventas.ventas_entrega"

_ENDPOINT_FACTURA_VENTA = "ventas.ventas_factura_venta"

_FORMKEY_SALES_REQUEST = "sales.sales_request"

_FORMKEY_SALES_ORDER = "sales.sales_order"

_FORMKEY_SALES_QUOTATION = "sales.sales_quotation"

_FORMKEY_SALES_INVOICE = "sales.sales_invoice"

_FORMKEY_DELIVERY_NOTE = "sales.delivery_note"

_LABEL_PEDIDO_VENTA = "Pedido de Venta"

_LABEL_ORDEN_VENTA = "Orden de Venta"

_LABEL_NOTA_ENTREGA = "Nota de Entrega"

DOCUMENT_REQUIRES_LINE_MSG = "El documento requiere al menos una línea."

SOLICITUD_CANCELACION_PENDIENTE_MSG = "Solicitud de cancelación enviada para aprobación (Pendiente de Cancelación)."


@dataclass(frozen=True)
class _DeliveryNoteNewContext:
    """Datos preparados para renderizar el formulario de una nota de entrega nueva."""

    form: Any
    title: str
    order_source: Any
    delivery_source: Any
    from_order_id: str | None
    from_note_id: str | None
    items: list[dict[str, Any]]
    uoms: list[dict[str, Any]]
    warehouses: list[dict[str, Any]]
    transaction_config: dict[str, Any]


def _load_delivery_note_sources(from_order_id: str | None, from_note_id: str | None) -> tuple[Any, Any]:
    """Load optional sales-order and delivery-note sources for the new form."""
    order_source = database.session.get(SalesOrder, from_order_id) if from_order_id else None
    delivery_source = database.session.get(DeliveryNote, from_note_id) if from_note_id else None
    return order_source, delivery_source


def _delivery_note_catalogs(
    selected_company: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load item, unit, and warehouse selectors for a delivery note."""
    from cacao_accounting.database import Warehouse

    items = [
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
    uoms = [{"code": uom.code, "name": uom.name} for (uom,) in database.session.execute(database.select(UOM)).all()]
    warehouses = [
        {"code": warehouse.code, "name": warehouse.name}
        for (warehouse,) in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]
    return items, uoms, warehouses


def _build_delivery_note_transaction_config(
    items: list[dict[str, Any]],
    uoms: list[dict[str, Any]],
    warehouses: list[dict[str, Any]],
    initial_source_type: str,
) -> dict[str, Any]:
    """Build the Alpine configuration used by the delivery-note form."""
    return {
        "formKey": _FORMKEY_DELIVERY_NOTE,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items,
        "uoms": uoms,
        "warehouses": warehouses,
        "initialSourceType": initial_source_type,
        "availableSourceTypes": [
            {"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)},
            {"value": "delivery_note", "label": _(_LABEL_NOTA_ENTREGA)},
        ],
    }


def _build_delivery_note_new_context() -> _DeliveryNoteNewContext:
    """Prepare form data, catalogs, and source defaults for a new delivery note."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioEntregaVenta

    formulario = FormularioEntregaVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("delivery_note", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(party.id), party.name)
        for (party,) in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    from_note_id = request.args.get("from_note") or request.form.get("from_note")
    order_source, delivery_source = _load_delivery_note_sources(from_order_id, from_note_id)
    source_document = order_source or delivery_source
    if source_document:
        selected_company = source_document.company
        formulario.naming_series.choices = _series_choices("delivery_note", selected_company)
    if from_note_id:
        formulario.is_return.data = True
    items, uoms, warehouses = _delivery_note_catalogs(selected_company)
    initial_source_type = "sales_order" if from_order_id else "delivery_note" if from_note_id else ""
    transaction_config = _build_delivery_note_transaction_config(items, uoms, warehouses, initial_source_type)
    if source_document:
        transaction_config["initialHeader"] = {
            "company": source_document.company or "",
            "currency": effective_currency(source_document) or "",
            "party": source_document.customer_id or "",
            "party_label": source_document.customer_name or "",
            "posting_date": str(date.today()),
            **_sales_logistics_values(source_document),
        }
    return _DeliveryNoteNewContext(
        form=formulario,
        title="Nueva Nota de Entrega - " + APPNAME,
        order_source=order_source,
        delivery_source=delivery_source,
        from_order_id=from_order_id,
        from_note_id=from_note_id,
        items=items,
        uoms=uoms,
        warehouses=warehouses,
        transaction_config=transaction_config,
    )


def _load_delivery_note_post_source(from_order: str | None, from_note: str | None) -> Any:
    """Load the source selected when a new delivery note is submitted."""
    source = database.session.get(SalesOrder, from_order) if from_order else None
    return database.session.get(DeliveryNote, from_note) if from_note else source


def _validate_new_delivery_note_source(entrega: DeliveryNote, from_note: str | None) -> None:
    """Validate source-line quantities for a newly created delivery note."""
    if not (from_note or entrega.sales_order_id):
        return
    delivery_items = (
        database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=entrega.id)).scalars().all()
    )
    if from_note:
        _validate_sales_source_link(entrega, "delivery_note", from_note, delivery_items)
    elif entrega.sales_order_id:
        _validate_sales_source_link(entrega, "sales_order", entrega.sales_order_id, delivery_items)


def _handle_delivery_note_new_post() -> ResponseReturnValue:
    """Create a delivery note from submitted form data."""
    posting_date = _parse_date(request.form.get("posting_date"))
    customer_id = request.form.get("customer_id") or None
    from_order = request.form.get("from_order") or None
    from_note = request.form.get("from_note") or None
    source = _load_delivery_note_post_source(from_order, from_note)
    is_return = bool(request.form.get("is_return")) or bool(from_note)
    if from_note and (not source or source.docstatus != 1 or source.is_return or not is_return):
        raise ValueError("La devolución debe referenciar una nota de entrega aprobada que no sea devolución.")
    from_order = from_order or getattr(source, "sales_order_id", None)
    company, source_currency = validate_immutable_header(
        source,
        request.form.get("company") or None,
        request.form.get("currency") or request.form.get("transaction_currency") or None,
    )
    exige_acceso_compania("sales", company, "crear")
    customer_id = customer_id or getattr(source, "customer_id", None)
    customer = database.session.get(Party, customer_id) if customer_id else None
    entrega = DeliveryNote(
        customer_id=customer_id,
        customer_name=customer.name if customer else None,
        company=company,
        transaction_currency=source_currency,
        base_currency=company_currency(company),
        posting_date=posting_date,
        sales_order_id=from_order,
        is_return=is_return,
        reversal_of=from_note,
        remarks=request.form.get("remarks"),
        docstatus=0,
    )
    _copy_sales_logistics(entrega, source, request.form)
    database.session.add(entrega)
    database.session.flush()
    assign_document_identifier(
        document=entrega,
        entity_type="delivery_note",
        posting_date_raw=posting_date,
        naming_series_id=request.form.get("naming_series") or None,
    )
    _total_qty, total = _save_delivery_note_items(entrega.id)
    _validate_new_delivery_note_source(entrega, from_note)
    _set_sales_document_totals(entrega, total)
    log_create(entrega)
    database.session.commit()
    flash("Nota de entrega creada correctamente.", "success")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=entrega.id))


@ventas.route("/")
@ventas.route("/ventas")
@ventas.route("/sales")
@modulo_activo("sales")
@login_required
def ventas_():
    """Modulo de ventas."""
    return render_template("ventas.html")


@ventas.route("/sales-order/list")
@modulo_activo("sales")
@login_required
def ventas_orden_venta_lista():
    """Listado de ordenes de venta."""
    consulta = _paginate_list(
        SalesOrder,
        (SalesOrder.document_no, SalesOrder.customer_name, SalesOrder.remarks),
    )
    titulo = "Listado de Ordenes de Venta - " + APPNAME
    return render_template("ventas/orden_venta_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/sales-request/list")
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_lista():
    """Listado de pedidos de venta."""
    consulta = _paginate_list(
        SalesRequest,
        (SalesRequest.document_no, SalesRequest.customer_name, SalesRequest.remarks),
    )
    titulo = "Listado de Pedidos de Venta - " + APPNAME
    return render_template("ventas/solicitud_venta_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/sales-request/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_nuevo():
    """Formulario para crear un pedido de venta."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioPedidoVenta

    formulario = FormularioPedidoVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("sales_request", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nuevo Pedido de Venta - " + APPNAME
    transaction_config = {
        "formKey": _FORMKEY_SALES_REQUEST,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "availableSourceTypes": [],
    }
    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id") or None
            customer = database.session.get(Party, customer_id) if customer_id else None
            posting_date = _parse_date(request.form.get("posting_date"))
            company, transaction_currency = validate_immutable_header(
                None,
                request.form.get("company") or None,
                request.form.get("currency") or request.form.get("transaction_currency") or None,
            )
            exige_acceso_compania("sales", company, "crear")
            pedido = SalesRequest(
                customer_id=customer_id,
                customer_name=customer.name if customer else None,
                company=company,
                transaction_currency=transaction_currency,
                base_currency=company_currency(company),
                posting_date=posting_date,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(pedido)
            database.session.flush()
            assign_document_identifier(
                document=pedido,
                entity_type="sales_request",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_sales_request_items(pedido.id)
            _set_sales_document_totals(pedido, total)
            database.session.commit()
            flash("Pedido de venta creado correctamente.", "success")
            return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=pedido.id))
        except ValueError as exc:
            database.session.rollback()
            flash_error(exc)
    return render_template(
        "ventas/solicitud_venta_nuevo.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/sales-request/<request_id>")
@modulo_activo("sales")
@login_required
def ventas_pedido_venta(request_id: str):
    """Detalle de un pedido de venta."""
    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "consultar")
    items = database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=request_id)).all()
    titulo = (registro.document_no or request_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("sales_request", registro.id)
    return render_template(
        "ventas/solicitud_venta.html", registro=registro, items=items, titulo=titulo, audit_timeline=audit_timeline
    )


@ventas.route("/sales-request/<request_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_editar(request_id: str):
    """Edita un pedido de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioPedidoVenta

    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioPedidoVenta(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("sales_request", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        return _handle_sales_request_update(registro, request.form, _ENDPOINT_PEDIDO_VENTA, request_id)

    lineas = database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_SALES_REQUEST,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "availableSourceTypes": [],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.customer_id or "",
            "party_label": registro.customer_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "amount": str(item.amount or 0),
                **get_target_line_source("sales_request", item.id),
            }
            for item in lineas
        ],
    }
    return render_template(
        "ventas/solicitud_venta_nuevo.html",
        form=formulario,
        titulo="Editar Pedido de Venta - " + APPNAME,
        edit=True,
        registro=registro,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/sales-request/<request_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_duplicar(request_id: str):
    """Duplica un pedido de venta como borrador nuevo."""
    origen = database.session.get(SalesRequest, request_id)
    if not origen:
        abort(404)
    _require_sales_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesRequest(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicado)
    database.session.flush()
    assign_document_identifier(
        document=duplicado,
        entity_type="sales_request",
        posting_date_raw=duplicado.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=origen.id)).scalars():
        linea = SalesRequestItem(
            sales_request_id=duplicado.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
            discount_percentage=item.discount_percentage,
            discount_amount=item.discount_amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    _set_sales_document_totals(duplicado, total)
    log_create(duplicado)
    database.session.commit()
    flash(_("Pedido de venta duplicado como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=duplicado.id))


@ventas.route("/sales-request/<request_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "autorizar")
def ventas_pedido_venta_submit(request_id: str):
    """Aprueba un pedido de venta.

    ``require_party=False`` es intencional: un pedido de venta interno
    puede aprobarse sin cliente asignado. El cliente se asigna al
    convertir en cotizacion u orden de venta.
    """
    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)).scalars().all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=False, require_rate_positive=True)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Pedido de venta"):
            return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))

        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))
    flash("Pedido de venta aprobado.", "success")
    return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))


@ventas.route("/sales-request/<request_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "anular")
def ventas_pedido_venta_cancel(request_id: str):
    """Cancela un pedido de venta."""
    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("sales_request", request_id):
        flash("No se puede cancelar el pedido de venta porque tiene cotizaciones u órdenes de venta activas.", "danger")
        return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))

        registro.docstatus = 2
        log_cancel(registro)
        revert_relations_for_target("sales_request", request_id)
        refresh_source_caches_for_target("sales_request", request_id)
        database.session.commit()
    except SQLAlchemyError as exc:
        database.session.rollback()
        flash_error(exc)
    flash("Pedido de venta cancelado.", "warning")
    return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))


@ventas.route("/delivery-note/list")
@modulo_activo(("sales", "inventory"))
@login_required
def ventas_entrega_lista():
    """Listado de notas de entrega."""
    consulta = _paginate_list(
        DeliveryNote,
        (DeliveryNote.document_no, DeliveryNote.customer_name, DeliveryNote.remarks),
        access_modules=("sales", "inventory"),
    )
    titulo = "Listado de Remisiones de Mercadería Vendida - " + APPNAME
    return render_template(
        "ventas/entrega_lista.html",
        consulta=consulta,
        titulo=titulo,
        can_manage_delivery_notes=_can_manage_delivery_notes(),
    )


@ventas.route("/sales-invoice/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_lista():
    """Listado de facturas de venta."""
    consulta = _paginate_list(
        SalesInvoice,
        (SalesInvoice.document_no, SalesInvoice.customer_name, SalesInvoice.remarks),
        database.select(SalesInvoice).filter_by(document_type="sales_invoice"),
    )
    titulo = "Listado de Facturas de Venta - " + APPNAME
    return render_template("ventas/factura_venta_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/sales-invoice/debit-note/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_nota_debito_lista():
    """Listado de notas de débito de venta."""
    consulta = _paginate_list(
        SalesInvoice,
        (SalesInvoice.document_no, SalesInvoice.customer_name, SalesInvoice.remarks),
        database.select(SalesInvoice).filter_by(document_type="sales_debit_note"),
    )
    titulo = "Listado de Notas de Débito de Venta - " + APPNAME
    return render_template(
        "ventas/factura_venta_devolucion_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Notas de Débito de Venta",
        new_button_label="Nueva Nota de Débito",
        page_caption="Listado de notas de débito de venta.",
        new_document_type="sales_debit_note",
    )


@ventas.route("/sales-invoice/return/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_devolucion_lista():
    """Listado de devoluciones y notas de crédito de venta."""
    consulta = _paginate_list(
        SalesInvoice,
        (SalesInvoice.document_no, SalesInvoice.customer_name, SalesInvoice.remarks),
        database.select(SalesInvoice).filter(SalesInvoice.document_type.in_(["sales_credit_note", "sales_return"])),
    )
    titulo = "Listado de Devoluciones de Venta - " + APPNAME
    return render_template(
        "ventas/factura_venta_devolucion_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Devoluciones de Venta",
        new_button_label="Nueva Devolución",
        page_caption="Listado de devoluciones y notas de crédito de venta.",
        new_document_type="sales_return",
    )


@ventas.route("/sales-invoice/credit-note/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_nota_credito_lista():
    """Alias explicito para listado de notas de crédito de venta."""
    return ventas_factura_venta_devolucion_lista()


@ventas.route("/sales-invoice/return/new")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_devolucion_nueva():
    """Redirige al formulario de factura de venta como devolucion (sales_return)."""
    return redirect(url_for("ventas.ventas_factura_venta_nuevo", document_type="sales_return"))


@ventas.route("/customer/list")
@modulo_activo("sales")
@login_required
def ventas_cliente_lista():
    """Listado de clientes."""
    consulta = _paginate_list(
        Party,
        (Party.code, Party.name, Party.comercial_name, Party.tax_id),
        database.select(Party).filter(Party.is_customer.is_(True)),
        include_status=False,
    )
    titulo = "Listado de Clientes - " + APPNAME
    return render_template("ventas/cliente_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/customer/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_nuevo():
    """Formulario para crear un nuevo cliente."""
    from cacao_accounting.ventas.forms import FormularioCliente
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioCliente()
    titulo = "Nuevo Cliente - " + APPNAME
    company_choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (company_choices[0][0] if company_choices else None)
    company_settings_rows = party_company_settings_rows(None, selected_company, role="customer")
    if request.method == "POST":
        return _handle_cliente_create(request.form, selected_company, company_choices, formulario, titulo)
    return render_template(
        VENTAS_CLIENTE_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(request.form.get("party_group_id") or None),
    )


@ventas.route("/customer/<customer_id>")
@modulo_activo("sales")
@login_required
def ventas_cliente(customer_id):
    """Detalle de cliente."""
    registro = database.session.execute(
        database.select(Party).filter_by(id=customer_id).filter(Party.is_customer.is_(True))
    ).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    detail = build_party_detail_context(registro[0])
    return render_template(
        "ventas/cliente.html",
        registro=registro[0],
        detail=detail,
        company_settings_rows=party_company_settings_rows(registro[0].id, None, role="customer"),
        company_settings_form_action=url_for("ventas.ventas_cliente_configuracion_compania", customer_id=registro[0].id),
        titulo=titulo,
    )


@ventas.route("/customer/<customer_id>/company-settings", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_configuracion_compania(customer_id: str):
    """Crea o actualiza la configuracion por compania de un cliente."""
    registro = database.session.execute(
        database.select(Party).filter_by(id=customer_id).filter(Party.is_customer.is_(True))
    ).scalar_one_or_none()
    if not registro:
        abort(404)
    try:
        upsert_party_company_settings_rows(customer_id, "customer", request.form)
        database.session.commit()
        flash(_("Configuracion por compania del cliente guardada correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for("ventas.ventas_cliente", customer_id=customer_id) + "#party-company-settings")


@ventas.route("/customer/<customer_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_editar(customer_id: str):
    """Formulario para editar un cliente."""
    from cacao_accounting.ventas.forms import FormularioCliente
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    cliente = database.session.execute(
        database.select(Party).filter_by(id=customer_id).filter(Party.is_customer.is_(True))
    ).scalar_one_or_none()
    if not cliente:
        abort(404)
    formulario = FormularioCliente(obj=cliente)
    titulo = f"Editar Cliente - {APPNAME}"
    company_choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (company_choices[0][0] if company_choices else None)
    company_settings_rows = party_company_settings_rows(cliente.id, selected_company, role="customer")
    if request.method == "POST":
        return _handle_cliente_update(cliente, request.form, selected_company, company_choices, formulario, titulo)
    return render_template(
        VENTAS_CLIENTE_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        edit=True,
        registro=cliente,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(cliente.party_group_id),
    )


@ventas.route("/customer/<customer_id>/contacts", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_contacto_crear(customer_id: str):
    """Crea un contacto para un cliente."""
    _party_or_404(customer_id, "customer")
    try:
        create_party_contact(customer_id, request.form)
        database.session.commit()
        flash(_("Contacto agregado correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/customer/<customer_id>/contacts/<link_id>/edit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_contacto_editar(customer_id: str, link_id: str):
    """Edita un contacto de cliente."""
    _party_or_404(customer_id, "customer")
    try:
        update_party_contact(customer_id, link_id, request.form)
        database.session.commit()
        flash(_("Contacto actualizado correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/customer/<customer_id>/contacts/<link_id>/deactivate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_contacto_desactivar(customer_id: str, link_id: str):
    """Desactiva un contacto de cliente."""
    _party_or_404(customer_id, "customer")
    deactivate_party_contact(customer_id, link_id)
    database.session.commit()
    flash(_("Contacto desactivado correctamente."), "success")
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/customer/<customer_id>/addresses", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_direccion_crear(customer_id: str):
    """Crea una direccion para un cliente."""
    _party_or_404(customer_id, "customer")
    try:
        create_party_address(customer_id, request.form)
        database.session.commit()
        flash(_("Direccion agregada correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/customer/<customer_id>/addresses/<link_id>/edit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_direccion_editar(customer_id: str, link_id: str):
    """Edita una direccion de cliente."""
    _party_or_404(customer_id, "customer")
    try:
        update_party_address(customer_id, link_id, request.form)
        database.session.commit()
        flash(_("Direccion actualizada correctamente."), "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/customer/<customer_id>/addresses/<link_id>/deactivate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cliente_direccion_desactivar(customer_id: str, link_id: str):
    """Desactiva una direccion de cliente."""
    _party_or_404(customer_id, "customer")
    deactivate_party_address(customer_id, link_id)
    database.session.commit()
    flash(_("Direccion desactivada correctamente."), "success")
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/sales-order/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "crear")
def ventas_orden_venta_nuevo():
    """Formulario para crear una orden de venta."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioOrdenVenta

    formulario = FormularioOrdenVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("sales_order", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    from_request_id = request.args.get("from_request") or request.form.get("from_request")
    from_quotation_id = request.args.get("from_quotation") or request.form.get("from_quotation")
    orden_origen = database.session.get(SalesOrder, from_order_id) if from_order_id else None
    solicitud_origen = database.session.get(SalesRequest, from_request_id) if from_request_id else None
    cotizacion_origen = database.session.get(SalesQuotation, from_quotation_id) if from_quotation_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    from cacao_accounting.database import Warehouse

    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name}
        for w in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]
    titulo = "Nueva Orden de Venta - " + APPNAME
    initial_source_type = _sales_order_initial_source_type(from_request_id, from_quotation_id)
    source_origen = solicitud_origen or cotizacion_origen
    transaction_config = _build_sales_order_transaction_config(
        items_disponibles, uoms_disponibles, bodegas_disponibles, source_origen, initial_source_type
    )
    if request.method == "POST":
        result = _handle_sales_order_new_post(from_quotation_id, from_request_id)
        if result is not None:
            return result
    return render_template(
        "ventas/orden_venta_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        solicitud_origen=solicitud_origen,
        cotizacion_origen=cotizacion_origen,
        from_order_id=from_order_id,
        from_request_id=from_request_id,
        from_quotation_id=from_quotation_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/sales-order/<order_id>")
@modulo_activo("sales")
@login_required
def ventas_orden_venta(order_id):
    """Detalle de orden de venta."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "consultar")
    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=order_id)).all()
    titulo = (registro.document_no or order_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("sales_order", registro.id)
    can_close = registro.docstatus == 1 and registro.status != "closed" and sales_order_is_ready_to_close(registro)
    return render_template(
        "ventas/orden_venta.html",
        registro=registro,
        items=items,
        titulo=titulo,
        audit_timeline=audit_timeline,
        can_close=can_close,
    )


@ventas.route("/sales-order/<order_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_editar(order_id: str):
    """Edita una orden de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioOrdenVenta

    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioOrdenVenta(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("sales_order", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    from cacao_accounting.database import Warehouse

    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name}
        for w in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]

    if request.method == "POST":
        return _handle_sales_order_update(registro, request.form, _ENDPOINT_ORDEN_VENTA, order_id)

    lineas = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_SALES_ORDER,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "enableLineDiscounts": True,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "availableSourceTypes": [
            {"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)},
            {"value": "sales_quotation", "label": _("Cotización de Venta")},
        ],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.customer_id or "",
            "party_label": registro.customer_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "discount_percentage": str(item.discount_percentage or 0),
                "amount": str(item.amount or 0),
                "warehouse": item.warehouse or "",
                **get_target_line_source("sales_order", item.id),
            }
            for item in lineas
        ],
    }
    return render_template(
        "ventas/orden_venta_nuevo.html",
        form=formulario,
        titulo="Editar Orden de Venta - " + APPNAME,
        edit=True,
        registro=registro,
        orden_origen=None,
        cotizacion_origen=None,
        from_order_id=None,
        from_quotation_id=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/sales-order/<order_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_duplicar(order_id: str):
    """Duplica una orden de venta como borrador nuevo."""
    origen = database.session.get(SalesOrder, order_id)
    if not origen:
        abort(404)
    _require_sales_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesOrder(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicado)
    database.session.flush()
    assign_document_identifier(
        document=duplicado,
        entity_type="sales_order",
        posting_date_raw=duplicado.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=origen.id)).scalars():
        linea = SalesOrderItem(
            sales_order_id=duplicado.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    _set_sales_document_totals(duplicado, total)
    log_create(duplicado)
    database.session.commit()
    flash(_("Orden de venta duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=duplicado.id))


@ventas.route("/quotation/list")
@ventas.route("/request-for-quotation/list")
@modulo_activo("sales")
@login_required
def ventas_cotizacion_lista():
    """Listado de cotizaciones de venta."""
    consulta = _paginate_list(
        SalesQuotation,
        (SalesQuotation.document_no, SalesQuotation.customer_name, SalesQuotation.remarks),
    )
    titulo = "Listado de Cotizaciones de Venta - " + APPNAME
    return render_template("ventas/cotizacion_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/quotation/new", methods=["GET", "POST"])
@ventas.route("/request-for-quotation/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_nueva():
    """Formulario para crear una cotización de venta."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioCotizacionVenta

    formulario = FormularioCotizacionVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("sales_quotation", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    from_request_id = request.args.get("from_request") or request.form.get("from_request")
    solicitud_origen = database.session.get(SalesRequest, from_request_id) if from_request_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Cotización - " + APPNAME
    transaction_config = {
        "formKey": _FORMKEY_SALES_QUOTATION,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "enableLineDiscounts": True,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "initialSourceType": "sales_request" if from_request_id else "",
        "availableSourceTypes": [{"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)}],
    }
    if solicitud_origen:
        transaction_config["initialHeader"] = {
            "company": solicitud_origen.company or "",
            "currency": effective_currency(solicitud_origen) or "",
            "party": getattr(solicitud_origen, "customer_id", None) or "",
            "party_label": getattr(solicitud_origen, "customer_name", None) or "",
            "posting_date": str(date.today()),
            **_sales_logistics_values(solicitud_origen),
        }
    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id") or None
            customer = database.session.get(Party, customer_id) if customer_id else None
            posting_date = _parse_date(request.form.get("posting_date"))
            source = solicitud_origen
            company, transaction_currency = validate_immutable_header(
                source,
                request.form.get("company") or None,
                request.form.get("currency") or request.form.get("transaction_currency") or None,
            )
            exige_acceso_compania("sales", company, "crear")
            cotizacion = SalesQuotation(
                customer_id=customer_id,
                customer_name=customer.name if customer else None,
                sales_request_id=from_request_id or None,
                company=company,
                transaction_currency=transaction_currency,
                base_currency=company_currency(company),
                posting_date=posting_date,
                valid_until=_parse_date(request.form.get("valid_until")) if request.form.get("valid_until") else None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            _copy_sales_logistics(cotizacion, source, request.form)
            database.session.add(cotizacion)
            database.session.flush()
            assign_document_identifier(
                document=cotizacion,
                entity_type="sales_quotation",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_sales_quotation_items(cotizacion.id)
            quotation_items = (
                database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=cotizacion.id))
                .scalars()
                .all()
            )
            if from_request_id:
                _validate_sales_source_link(cotizacion, "sales_request", from_request_id, quotation_items)
            _set_sales_document_totals(cotizacion, total)
            database.session.commit()
            flash("Cotización creada correctamente.", "success")
            return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=cotizacion.id))
        except ValueError as exc:
            database.session.rollback()
            flash_error(exc)
    return render_template(
        "ventas/cotizacion_nuevo.html",
        form=formulario,
        titulo=titulo,
        solicitud_origen=solicitud_origen,
        from_request_id=from_request_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/quotation/<quotation_id>")
@modulo_activo("sales")
@login_required
def ventas_cotizacion(quotation_id: str):
    """Detalle de cotización de venta."""
    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "consultar")
    items = database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=quotation_id)).all()
    titulo = (registro.document_no or quotation_id) + " - " + APPNAME
    audit_timeline = format_document_timeline("sales_quotation", registro.id)
    return render_template(
        "ventas/cotizacion.html", registro=registro, items=items, titulo=titulo, audit_timeline=audit_timeline
    )


@ventas.route("/sales-quotation/<quotation_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_editar(quotation_id: str):
    """Edita una cotizacion de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioCotizacionVenta

    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "editar")
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioCotizacionVenta(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("sales_quotation", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        return _handle_sales_quotation_edit_post(registro)

    lineas = database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_SALES_QUOTATION,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "enableLineDiscounts": True,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "availableSourceTypes": [{"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)}],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.customer_id or "",
            "party_label": registro.customer_name or "",
        },
        "initialLines": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": str(item.qty),
                "uom": item.uom or "",
                "rate": str(item.rate or 0),
                "discount_percentage": str(item.discount_percentage or 0),
                "discount_amount": str(item.discount_amount or 0),
                "amount": str(item.amount or 0),
                **get_target_line_source("sales_quotation", item.id),
            }
            for item in lineas
        ],
    }
    return render_template(
        "ventas/cotizacion_nuevo.html",
        form=formulario,
        titulo="Editar Cotización de Venta - " + APPNAME,
        edit=True,
        registro=registro,
        solicitud_origen=None,
        from_request_id=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/sales-quotation/<quotation_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_duplicar(quotation_id: str):
    """Duplica una cotizacion de venta como borrador nuevo."""
    origen = database.session.get(SalesQuotation, quotation_id)
    if not origen:
        abort(404)
    _require_sales_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesQuotation(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        valid_until=origen.valid_until,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicado)
    database.session.flush()
    assign_document_identifier(
        document=duplicado,
        entity_type="sales_quotation",
        posting_date_raw=duplicado.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(
        database.select(SalesQuotationItem).filter_by(sales_quotation_id=origen.id)
    ).scalars():
        linea = SalesQuotationItem(
            sales_quotation_id=duplicado.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
            discount_percentage=item.discount_percentage,
            discount_amount=item.discount_amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    _set_sales_document_totals(duplicado, total)
    log_create(duplicado)
    database.session.commit()
    flash(_("Cotización de venta duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=duplicado.id))


@ventas.route("/sales-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "autorizar")
def ventas_cotizacion_submit(quotation_id: str):
    """Aprueba una cotizacion de venta."""
    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(
            registro, items=items, require_party=True, require_rate_positive=True, require_amount_nonzero=True
        )
        if registro.sales_request_id:
            _validate_sales_source_link(registro, "sales_request", registro.sales_request_id, items)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Cotización de venta"):
            return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))

        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))
    flash("Cotizacion de venta aprobada.", "success")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))


@ventas.route("/sales-quotation/<quotation_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "anular")
def ventas_cotizacion_cancel(quotation_id: str):
    """Cancela una cotización de venta."""
    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("sales_quotation", quotation_id):
        flash("No se puede cancelar la cotización de venta porque tiene órdenes de venta activas.", "danger")
        return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))

        registro.docstatus = 2
        log_cancel(registro)
        revert_relations_for_target("sales_quotation", quotation_id)
        refresh_source_caches_for_target("sales_quotation", quotation_id)
        database.session.commit()
    except SQLAlchemyError as exc:
        database.session.rollback()
        flash_error(exc)
    flash("Cotización de venta cancelada.", "warning")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))


@ventas.route("/sales-order/<order_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "autorizar")
def ventas_orden_venta_submit(order_id: str):
    """Aprueba una orden de venta y reserva inventario de forma atómica."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars().all()
        for item in items:
            item_obj = _item_by_code(item.item_code)
            if not item_obj or not item_obj.is_active or not item_obj.is_sale_item:
                raise ValueError(f"El item {item.item_code} no está habilitado para venta.")
        validate_submit_prerequisites(
            registro, items=items, require_party=True, require_rate_positive=True, require_amount_nonzero=True
        )
        if registro.sales_quotation_id:
            _validate_sales_source_link(registro, "sales_quotation", registro.sales_quotation_id, items)
        if not getattr(registro, "is_return", False):
            _validate_credit_limit_and_overdue(
                registro.company, registro.customer_id, registro.grand_total or Decimal("0"), current_document=registro
            )
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Orden de venta"):
            return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))

        # Atomic transaction: stock reservation must succeed or entire submission rolls back
        with database.session.begin_nested():
            _validate_and_reserve_stock_for_sales_order(registro)
            registro.docstatus = 1
            log_submit(registro)
        database.session.commit()
        flash("Orden de venta aprobada con reserva de inventario.", "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))


@ventas.route("/sales-order/<order_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "anular")
def ventas_orden_venta_cancel(order_id: str):
    """Cancela una orden de venta y libera la reserva de inventario."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("sales_order", order_id):
        flash("No se puede cancelar la orden de venta porque tiene notas de entrega o facturas activas.", "danger")
        return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(registro)
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))

        _release_reservation_for_sales_order(registro)
        registro.docstatus = 2
        log_cancel(registro)
        revert_relations_for_target("sales_order", order_id)
        refresh_source_caches_for_target("sales_order", order_id)
        database.session.commit()
    except SQLAlchemyError as exc:
        database.session.rollback()
        flash_error(exc)
    flash("Orden de venta cancelada y reserva liberada.", "warning")
    return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))


@ventas.route("/sales-order/<order_id>/close", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "autorizar")
def ventas_orden_venta_close(order_id: str):
    """Cierra manualmente una orden de venta cuyas lineas fueron entregadas o facturadas."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "autorizar")
    if registro.docstatus != 1 or registro.status == "closed":
        abort(400)
    if not sales_order_is_ready_to_close(registro):
        flash(
            "La Orden de Venta requiere Notas de Entrega o Facturas aprobadas para todas sus lineas.",
            "danger",
        )
        return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))
    close_reason = "Orden de Venta cerrada manualmente."
    close_document_balances(
        source_type="sales_order",
        source_id=registro.id,
        target_type="delivery_note",
        reason=close_reason,
    )
    close_document_balances(
        source_type="sales_order",
        source_id=registro.id,
        target_type="sales_invoice",
        reason=close_reason,
    )
    _release_reservation_for_closed_sales_order(registro)
    before = {"status": registro.status}
    registro.status = "closed"
    log_update(registro, before=before, after={"status": registro.status})
    order_items = {
        item.id: item
        for item in database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id))
        .scalars()
        .all()
    }
    for item_id, reason in sorted(sales_order_line_closure_reasons(registro).items()):
        item = order_items.get(item_id)
        label = (item.item_code or item.id) if item else item_id
        log_update(registro, before={"line": label}, after={"closure_reason": reason})
    database.session.commit()
    flash("Orden de Venta cerrada correctamente.", "success")
    return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))


@ventas.route("/delivery-note/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "crear")
def ventas_entrega_nuevo():
    """Formulario para crear una nota de entrega."""
    context = _build_delivery_note_new_context()
    if request.method == "POST":
        try:
            return _handle_delivery_note_new_post()
        except ValueError as exc:
            database.session.rollback()
            flash_error(exc)
    return render_template(
        "ventas/entrega_nuevo.html",
        form=context.form,
        titulo=context.title,
        orden_origen=context.order_source,
        entrega_origen=context.delivery_source,
        from_order_id=context.from_order_id,
        from_note_id=context.from_note_id,
        items_disponibles=context.items,
        uoms_disponibles=context.uoms,
        bodegas_disponibles=context.warehouses,
        transaction_config=context.transaction_config,
    )


@ventas.route("/delivery-note/<note_id>")
@modulo_activo(("sales", "inventory"))
@login_required
def ventas_entrega(note_id):
    """Detalle de nota de entrega."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    _require_delivery_note_access(registro)
    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=note_id)).all()
    titulo = (registro.document_no or note_id) + " - " + APPNAME
    return render_template(
        "ventas/entrega.html",
        registro=registro,
        items=items,
        titulo=titulo,
        audit_timeline=format_document_timeline("delivery_note", registro.id),
    )


@ventas.route("/delivery-note/<note_id>/edit", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def ventas_entrega_editar(note_id: str):
    """Edita una nota de entrega en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse
    from cacao_accounting.ventas.forms import FormularioEntregaVenta

    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    _require_delivery_note_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioEntregaVenta(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("delivery_note", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
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
        return _handle_delivery_note_edit_post(registro)

    lineas = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_DELIVERY_NOTE,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "availableSourceTypes": [{"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)}],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.customer_id or "",
            "party_label": registro.customer_name or "",
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
                **get_target_line_source("delivery_note", item.id),
            }
            for item in lineas
        ],
    }
    return render_template(
        "ventas/entrega_nuevo.html",
        form=formulario,
        titulo="Editar Nota de Entrega - " + APPNAME,
        edit=True,
        registro=registro,
        orden_origen=None,
        from_order_id=None,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/delivery-note/<note_id>/duplicate", methods=["POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "crear")
def ventas_entrega_duplicar(note_id: str):
    """Duplica una nota de entrega como borrador nuevo."""
    origen = database.session.get(DeliveryNote, note_id)
    if not origen:
        abort(404)
    _require_delivery_note_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicado = DeliveryNote(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        posting_date=origen.posting_date,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicado)
    database.session.flush()
    assign_document_identifier(
        document=duplicado,
        entity_type="delivery_note",
        posting_date_raw=duplicado.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=origen.id)).scalars():
        linea = DeliveryNoteItem(
            delivery_note_id=duplicado.id,
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
    _set_sales_document_totals(duplicado, total)
    log_create(duplicado)
    database.session.commit()
    flash(_("Nota de entrega duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=duplicado.id))


@ventas.route("/delivery-note/<note_id>/submit", methods=["POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "autorizar")
def ventas_entrega_submit(note_id: str):
    """Aprueba una nota de entrega y libera la reserva de inventario.

    ``submit_document(registro)`` ejecuta la cadena de posting que
    decrementa ``actual_qty`` en StockBin via ``_upsert_stock_bin``
    en posting.py. La reduccion de ``actual_qty`` no ocurre aqui
    directamente, sino dentro del motor de posting.
    """
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars().all()
        )
        validate_submit_prerequisites(
            registro,
            items=items,
            require_party=True,
            require_warehouse=True,
            require_rate_positive=True,
            require_amount_nonzero=True,
        )
        if registro.sales_order_id:
            _validate_sales_source_link(registro, "sales_order", registro.sales_order_id, items)
        _validate_sales_invoice_line_amounts(registro, items)
        _validate_delivery_quantities_against_so(note_id)
        from cacao_accounting.inventario.service import validate_batch_serial_draft

        validate_batch_serial_draft(items)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Nota de entrega"):
            return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))

        submit_document(registro)  # type: ignore[misc]
        _release_reservation_for_delivery_note(registro)
        log_submit(registro)
        database.session.commit()
        flash("Nota de entrega aprobada.", "success")
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))


@ventas.route("/delivery-note/<note_id>/cancel", methods=["POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "anular")
def ventas_entrega_cancel(note_id: str):
    """Cancela una nota de entrega y restaura la reserva de inventario."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash(_("Debe indicar el motivo de la anulación."), "danger")
        return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))
    if has_active_source_relations("delivery_note", note_id):
        flash("No se puede cancelar la nota de entrega porque tiene facturas de venta activas.", "danger")
        return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(
                registro,
                reason=reason,
                cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
            )
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))

        _execute_delivery_note_cancellation(
            registro,
            note_id,
            reason=reason,
            actor_user_id=str(current_user.id),
            cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
        )
        flash("Nota de entrega cancelada.", "warning")
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))


@ventas.route("/sales-invoice/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "crear")
def ventas_factura_venta_nuevo():
    """Formulario para crear una factura de venta."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioFacturaVenta

    formulario = FormularioFacturaVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("sales_invoice", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]

    src = _sales_invoice_sources_and_type(formulario)
    items_disponibles, uoms_disponibles = _sales_invoice_catalogs()
    titulo = "Nueva Factura de Venta - " + APPNAME

    company_id = (
        next((o.company for o in (src["orden_origen"], src["entrega_origen"], src["factura_origen"]) if o), None)
        or request.args.get("company")
        or selected_company
    )
    source_origen = src["orden_origen"] or src["entrega_origen"] or src["factura_origen"]
    initial_source_type = ""
    if src["from_order_id"]:
        initial_source_type = "sales_order"
    elif src["from_note_id"]:
        initial_source_type = "delivery_note"
    elif src["from_invoice_id"]:
        initial_source_type = "sales_invoice"

    bodegas_disponibles = [
        {"code": warehouse.code, "name": warehouse.name}
        for (warehouse,) in database.session.execute(database.select(Warehouse).filter_by(company=company_id)).all()
    ]

    transaction_config = {
        "formKey": _FORMKEY_SALES_INVOICE,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "enableLineDiscounts": True,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": [{"field": "warehouse", "label": _("Almacén"), "visible": True, "width": 2}],
        "initialSourceType": initial_source_type,
        "availableSourceTypes": [
            {"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)},
            {"value": "delivery_note", "label": _(_LABEL_NOTA_ENTREGA)},
            {"value": "sales_invoice", "label": _("Factura de Venta")},
        ],
        "initialHeader": {"company": company_id or "", "posting_date": str(date.today())},
    }
    if source_origen:
        transaction_config["initialHeader"] = {
            "company": source_origen.company or "",
            "currency": effective_currency(source_origen) or "",
            "party": getattr(source_origen, "customer_id", None) or "",
            "party_label": getattr(source_origen, "customer_name", None) or "",
            "posting_date": str(date.today()),
        }
    if request.method == "POST":
        return _create_sales_invoice_from_form()
    return render_template(
        "ventas/factura_venta_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=src["orden_origen"],
        entrega_origen=src["entrega_origen"],
        factura_origen=src["factura_origen"],
        from_order_id=src["from_order_id"],
        from_note_id=src["from_note_id"],
        from_invoice_id=src["from_invoice_id"],
        from_return_id=src["from_return_id"],
        document_type=src["document_type"],
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
        bodegas_disponibles=bodegas_disponibles,
        update_inventory_checked=formulario.update_inventory.data,
    )


@ventas.route("/sales-invoice/<invoice_id>")
@modulo_activo("sales")
@login_required
def ventas_factura_venta(invoice_id):
    """Detalle de factura de venta."""
    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "consultar")
    items = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice_id)).all()
    titulo = (registro.document_no or invoice_id) + " - " + APPNAME
    audit_timeline = format_document_timeline(registro.document_type or "sales_invoice", registro.id)
    return render_template(
        "ventas/factura_venta.html", registro=registro, items=items, titulo=titulo, audit_timeline=audit_timeline
    )


@ventas.route("/sales-invoice/<invoice_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_factura_venta_editar(invoice_id: str):
    """Edita una factura de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.ventas.forms import FormularioFacturaVenta

    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
    _require_sales_document_access(registro, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioFacturaVenta(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("sales_invoice", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
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
    bodegas_disponibles = [
        {"code": warehouse.code, "name": warehouse.name}
        for (warehouse,) in database.session.execute(database.select(Warehouse).filter_by(company=selected_company)).all()
    ]

    if request.method == "POST":
        return _handle_sales_invoice_edit_post(registro)

    lineas = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_SALES_INVOICE,
        "canEditPrices": is_sales_price_editor(str(current_user.id)),
        "enableLineDiscounts": True,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": [{"field": "warehouse", "label": _("Almacén"), "visible": True, "width": 2}],
        "availableSourceTypes": [
            {"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)},
            {"value": "delivery_note", "label": _(_LABEL_NOTA_ENTREGA)},
            {"value": "sales_invoice", "label": _("Factura de Venta")},
        ],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.customer_id or "",
            "party_label": registro.customer_name or "",
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
                **get_target_line_source("sales_invoice", item.id),
            }
            for item in lineas
        ],
    }
    document_type = registro.document_type or "sales_invoice"
    formulario.is_return.data = document_type == "sales_credit_note"
    return render_template(
        "ventas/factura_venta_nuevo.html",
        form=formulario,
        titulo="Editar Factura de Venta - " + APPNAME,
        edit=True,
        registro=registro,
        orden_origen=None,
        entrega_origen=None,
        factura_origen=None,
        from_order_id=None,
        from_note_id=None,
        from_invoice_id=None,
        from_return_id=None,
        document_type=document_type,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
        bodegas_disponibles=bodegas_disponibles,
        update_inventory_checked=registro.update_inventory,
    )


@ventas.route("/sales-invoice/<invoice_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_factura_venta_duplicar(invoice_id: str):
    """Duplica una factura de venta como borrador nuevo."""
    origen = database.session.get(SalesInvoice, invoice_id)
    if not origen:
        abort(404)
    _require_sales_document_access(origen, "crear")
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesInvoice(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
        posting_date=origen.posting_date,
        document_type=origen.document_type,
        is_return=origen.is_return,
        remarks=origen.remarks,
        docstatus=0,
        transaction_currency=origen.transaction_currency,
        base_currency=origen.base_currency,
        exchange_rate=origen.exchange_rate,
        tax_template_id=origen.tax_template_id,
        sales_order_id=origen.sales_order_id,
        delivery_note_id=origen.delivery_note_id,
        reversal_of=origen.reversal_of,
    )
    database.session.add(duplicado)
    database.session.flush()
    assign_document_identifier(
        document=duplicado,
        entity_type="sales_invoice",
        posting_date_raw=duplicado.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=origen.id)).scalars():
        linea = SalesInvoiceItem(
            sales_invoice_id=duplicado.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            uom=item.uom,
            rate=item.rate,
            amount=item.amount,
            warehouse=getattr(item, "warehouse", None),
            batch_id=item.batch_id,
            serial_no=item.serial_no,
            income_account_id=getattr(item, "income_account_id", None),
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicado.total = total
    duplicado.base_total = origen.base_total
    duplicado.grand_total = origen.grand_total
    duplicado.base_grand_total = origen.base_grand_total
    duplicado.outstanding_amount = origen.grand_total
    duplicado.base_outstanding_amount = origen.base_grand_total
    log_create(duplicado)
    database.session.commit()
    flash(_("Factura de venta duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=duplicado.id))


@ventas.route("/sales-invoice/<invoice_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "autorizar")
def ventas_factura_venta_submit(invoice_id: str):
    """Aprueba una factura de venta."""
    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)).scalars().all()
        )
        validate_submit_prerequisites(
            registro,
            items=items,
            require_party=True,
            require_warehouse=bool(registro.update_inventory),
            require_rate_positive=True,
            require_amount_nonzero=True,
        )
        if not getattr(registro, "is_return", False):
            _validate_credit_limit_and_overdue(
                registro.company, registro.customer_id, registro.grand_total or Decimal("0"), current_document=registro
            )
        _validate_sales_order_requirement(registro, items)
        _validate_sales_invoice_quantities(invoice_id)
        _validate_sales_invoice_line_amounts(registro, items)
        warnings = _validate_invoice_prices_against_source(registro)
        if registro.document_type in ("sales_credit_note", "sales_debit_note") and registro.reversal_of:
            note_amount = Decimal(str(registro.grand_total or "0")) if registro.document_type == "sales_credit_note" else None
            _validate_reversal_of(
                registro.reversal_of,
                registro.customer_id,
                registro.company,
                note_amount=note_amount,
                document_type=registro.document_type,
                posting_date=registro.posting_date,
                lock_source=True,
            )
        from cacao_accounting.inventario.service import validate_batch_serial_draft

        validate_batch_serial_draft(items)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Factura de venta"):
            return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))

        submit_document(registro)  # type: ignore[misc]
        _persist_sales_reversal_relation(registro)
        if registro.update_inventory and not registro.is_return and not registro.delivery_note_id:
            dn = _create_delivery_note_from_invoice(registro)
            flash(
                _("Se ha creado y aprobado la Nota de Entrega %s asociada a esta factura.") % (dn.document_no or dn.id),
                "info",
            )
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))
    for w in warnings:
        flash(_(w), "warning")
    flash(_("Factura de venta aprobada y contabilizada."), "success")
    return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))


@ventas.route("/sales-invoice/<invoice_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
@verifica_permiso("sales", "anular")
def ventas_factura_venta_cancel(invoice_id: str):
    """Cancela una factura de venta."""
    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
    exige_acceso_compania("sales", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash(_("Debe indicar el motivo de la anulación."), "danger")
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))
    if has_active_source_relations("sales_invoice", invoice_id):
        flash("No se puede cancelar la factura de venta porque tiene documentos financieros activos.", "danger")
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(
                registro,
                reason=reason,
                cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
            )
            database.session.commit()
            flash(_(SOLICITUD_CANCELACION_PENDIENTE_MSG), "info")
            return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))

        _cancel_linked_delivery_note(
            registro,
            reason=reason,
            actor_user_id=str(current_user.id),
            cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
        )
        cancel_document(
            registro,
            reason=reason,
            actor_user_id=str(current_user.id),
            cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
        )  # type: ignore[misc]
        log_cancel(registro)
        target_type = registro.document_type or "sales_invoice"
        revert_relations_for_target(target_type, invoice_id)
        refresh_source_caches_for_target(target_type, invoice_id)
        if registro.reversal_of:
            from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache

            source = database.session.get(SalesInvoice, registro.reversal_of)
            if source:
                refresh_outstanding_amount_cache(source)
        database.session.commit()
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))
    flash(_("Factura de venta cancelada con reverso contable."), "warning")
    return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=invoice_id))


@ventas.route("/cliente/<customer_id>/habilitar-proveedor", methods=["POST"])
@modulo_activo("purchases")
@login_required
def ventas_cliente_habilitar_proveedor(customer_id: str):
    """Habilita un cliente como proveedor."""
    try:
        toggle_party_supplier_role(customer_id, enable=True, user_id=current_user.id)
        database.session.commit()
        flash(_("Cliente habilitado como proveedor exitosamente."), "success")
    except PartyRoleToggleError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


@ventas.route("/cliente/<customer_id>/deshabilitar-proveedor", methods=["POST"])
@modulo_activo("purchases")
@login_required
def ventas_cliente_deshabilitar_proveedor(customer_id: str):
    """Deshabilita el rol de proveedor de un cliente."""
    try:
        toggle_party_supplier_role(customer_id, enable=False, user_id=current_user.id)
        database.session.commit()
        flash(_("Rol de proveedor deshabilitado exitosamente."), "success")
    except PartyRoleToggleError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))
