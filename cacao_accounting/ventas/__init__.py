# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Ventas."""

from datetime import date
from decimal import Decimal
from typing import Any

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    DocumentRelation,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesMatchingConfig,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    StockBin,
    UOM,
    database,
)
from ulid import ULID
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
    refresh_source_caches_for_target,
    revert_relations_for_target,
    validate_submit_prerequisites,
)
from cacao_accounting.document_flow.repository import has_active_source_relations
from cacao_accounting.document_flow.status import _
from cacao_accounting.decorators import modulo_activo, verifica_acceso as verifica_acceso  # noqa: F401
from cacao_accounting.fiscal_persistence_service import persist_document_fiscal_snapshot
from cacao_accounting.list_filters import apply_list_filters
from cacao_accounting.party_settings import (
    draft_party_company_settings_rows,
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

ventas = Blueprint("ventas", __name__, template_folder="templates")

# Constantes para rutas y endpoints (S1192 - evitar duplicación de cadenas)
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


def _party_or_404(party_id: str, party_type: str) -> Party:
    """Obtiene un tercero por tipo o aborta."""
    party = database.session.execute(
        database.select(Party).filter_by(id=party_id).filter(Party.is_customer.is_(True))
    ).scalar_one_or_none()
    if not party:
        abort(404)
    return party


# ─── Reserva de inventario para Ordenes de Venta ──────────────────────────────


def _stock_bin_or_create(company: str, item_code: str, warehouse: str) -> StockBin:
    """Obtiene o crea un StockBin para item/almacen/compania."""
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse)
    ).scalar_one_or_none()
    if not bin_row:
        bin_row = StockBin(
            company=company,
            item_code=item_code,
            warehouse=warehouse,
            actual_qty=Decimal("0"),
            reserved_qty=Decimal("0"),
            stock_value=Decimal("0"),
        )
        database.session.add(bin_row)
        database.session.flush()
    return bin_row


def _validate_and_reserve_stock_for_sales_order(so: SalesOrder) -> None:
    """Valida disponibilidad y reserva inventario al aprobar una Orden de Venta.

    Para cada linea de la OV con almacen definido, verifica que
    ``actual_qty - reserved_qty >= qty``. Si hay stock suficiente,
    incrementa ``reserved_qty`` en el StockBin correspondiente.
    """
    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=so.id)).scalars().all()

    for item in items:
        warehouse = item.warehouse
        if not warehouse:
            raise ValueError(f"El item {item.item_code} no tiene almacen asignado en la orden de venta.")

        bin_row = _stock_bin_or_create(company=so.company, item_code=item.item_code, warehouse=warehouse)
        actual = Decimal(str(bin_row.actual_qty or 0))
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        available = actual - reserved

        if available < item.qty:
            raise ValueError(
                f"Stock insuficiente para {item.item_code} en {warehouse}: " f"disponible {available}, requerido {item.qty}."
            )

        bin_row.reserved_qty = reserved + item.qty


def _release_reservation_for_sales_order(so: SalesOrder) -> None:
    """Libera la reserva de inventario al cancelar una Orden de Venta."""
    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=so.id)).scalars().all()

    for item in items:
        warehouse = item.warehouse
        if not warehouse:
            continue

        bin_row = _stock_bin_or_create(company=so.company, item_code=item.item_code, warehouse=warehouse)
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        new_reserved = max(Decimal("0"), reserved - item.qty)
        bin_row.reserved_qty = new_reserved


def _release_reservation_for_delivery_note(dn: DeliveryNote) -> None:
    """Libera reserva al aprobar una Nota de Entrega vinculada a una OV."""
    if not dn.sales_order_id:
        return

    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=dn.id)).scalars().all()

    for item in items:
        warehouse = item.warehouse
        if not warehouse:
            continue

        bin_row = _stock_bin_or_create(company=dn.company, item_code=item.item_code, warehouse=warehouse)
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        new_reserved = max(Decimal("0"), reserved - item.qty)
        bin_row.reserved_qty = new_reserved


def _restore_reservation_for_delivery_note(dn: DeliveryNote) -> None:
    """Restaura reserva al cancelar una Nota de Entrega vinculada a una OV."""
    if not dn.sales_order_id:
        return

    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=dn.id)).scalars().all()

    for item in items:
        warehouse = item.warehouse
        if not warehouse:
            continue

        bin_row = _stock_bin_or_create(company=dn.company, item_code=item.item_code, warehouse=warehouse)
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        bin_row.reserved_qty = reserved + item.qty


def _upsert_customer_company_settings_from_request(customer_id: str, form: dict) -> None:
    """Actualiza la configuracion de compania para un cliente desde el formulario."""
    upsert_party_company_settings_rows(customer_id, "customer", form)


def _capture_sales_state(registro: Any) -> dict[str, Any]:
    """CROSS-01: Captura estado de documento de ventas para auditoría."""
    return {
        "customer_id": getattr(registro, "customer_id", None),
        "company": getattr(registro, "company", None),
        "posting_date": str(getattr(registro, "posting_date", "")),
        "total": str(getattr(registro, "total", "")),
        "remarks": getattr(registro, "remarks", None),
    }


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
    from cacao_accounting.form_preferences import get_column_preferences
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
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_REQUEST),
        "availableSourceTypes": [],
    }
    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id") or None
            customer = database.session.get(Party, customer_id) if customer_id else None
            posting_date = _parse_date(request.form.get("posting_date"))
            pedido = SalesRequest(
                customer_id=customer_id,
                customer_name=customer.name if customer else None,
                company=request.form.get("company") or None,
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
            pedido.total = total
            pedido.base_total = total
            pedido.grand_total = total
            database.session.commit()
            flash("Pedido de venta creado correctamente.", "success")
            return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=pedido.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
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
    items = database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=request_id)).all()
    titulo = (registro.document_no or request_id) + " - " + APPNAME
    return render_template("ventas/solicitud_venta.html", registro=registro, items=items, titulo=titulo)


@ventas.route("/sales-request/<request_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_editar(request_id: str):
    """Edita un pedido de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioPedidoVenta

    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
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
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_REQUEST),
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
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesRequest(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
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
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicado.total = total
    duplicado.base_total = total
    duplicado.grand_total = total
    database.session.commit()
    flash(_("Pedido de venta duplicado como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=duplicado.id))


@ventas.route("/sales-request/<request_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_submit(request_id: str):
    """Aprueba un pedido de venta."""
    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)).scalars().all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=False)
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))
    flash("Pedido de venta aprobado.", "success")
    return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))


@ventas.route("/sales-request/<request_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_cancel(request_id: str):
    """Cancela un pedido de venta."""
    registro = database.session.get(SalesRequest, request_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("sales_request", request_id)
    refresh_source_caches_for_target("sales_request", request_id)
    database.session.commit()
    flash("Pedido de venta cancelado.", "warning")
    return redirect(url_for(_ENDPOINT_PEDIDO_VENTA, request_id=request_id))


@ventas.route("/delivery-note/list")
@modulo_activo("sales")
@login_required
def ventas_entrega_lista():
    """Listado de notas de entrega."""
    consulta = _paginate_list(
        DeliveryNote,
        (DeliveryNote.document_no, DeliveryNote.customer_name, DeliveryNote.remarks),
    )
    titulo = "Listado de Notas de Entrega - " + APPNAME
    return render_template("ventas/entrega_lista.html", consulta=consulta, titulo=titulo)


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


def _handle_cliente_create(
    form: dict,
    selected_company: str | None,
    company_choices: list,
    formulario: Any,
    titulo: str,
):
    """Maneja la creacion de un nuevo cliente desde el formulario POST."""
    cliente = Party(
        code=str(ULID()),
        is_customer=True,
        name=form.get("name") or "",
        comercial_name=form.get("comercial_name"),
        tax_id=form.get("tax_id"),
        fiscal_name=form.get("fiscal_name"),
        is_active=form.get("is_active", "on") is not None,
    )
    try:
        database.session.add(cliente)
        apply_party_group(cliente, form.get("party_group_id") or None, role="customer")
        apply_party_profile(cliente, form)
        database.session.flush()
        cliente.code = generate_party_code(cliente.id, form.get("company"), "customer")
        _upsert_customer_company_settings_from_request(cliente.id, form)
        database.session.commit()
        return redirect("/sales/customer/list")
    except ValueError as exc:
        database.session.rollback()
        company_settings_rows = draft_party_company_settings_rows("customer", form)
        flash(str(exc), "danger")
    return render_template(
        VENTAS_CLIENTE_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(form.get("party_group_id") or None),
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
    return render_template("ventas/cliente.html", registro=registro[0], detail=detail, titulo=titulo)


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


def _handle_cliente_update(
    cliente: Party,
    form: dict,
    selected_company: str | None,
    company_choices: list,
    formulario: Any,
    titulo: str,
):
    """Maneja la actualizacion de un cliente existente desde el formulario POST."""
    try:
        cliente.name = form.get("name") or ""
        cliente.comercial_name = form.get("comercial_name") or None
        cliente.tax_id = form.get("tax_id") or None
        cliente.fiscal_name = form.get("fiscal_name")
        cliente.is_active = form.get("is_active") is not None
        apply_party_group(cliente, form.get("party_group_id") or None, role="customer")
        apply_party_profile(cliente, form)
        _upsert_customer_company_settings_from_request(cliente.id, form)
        database.session.commit()
        flash(_("Cliente actualizado correctamente."), "success")
        return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=cliente.id))
    except ValueError as exc:
        database.session.rollback()
        company_settings_rows = draft_party_company_settings_rows("customer", form)
        flash(str(exc), "danger")
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
        flash(str(exc), "danger")
    return redirect(url_for(_ENDPOINT_CLIENTE, customer_id=customer_id))


def _handle_sales_request_update(registro: SalesRequest, form: dict, endpoint: str, request_id: str):
    """Maneja la actualizacion de un pedido de venta desde el formulario POST."""
    customer_id = form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    registro.company = form.get("company") or None
    registro.posting_date = _parse_date(form.get("posting_date"))
    registro.remarks = form.get("remarks")
    for item in database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)).scalars():
        database.session.delete(item)
    _total_qty, total = _save_sales_request_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    database.session.commit()
    flash(_("Pedido de venta actualizado correctamente."), "success")
    return redirect(url_for(endpoint, request_id=request_id))


def _handle_sales_order_update(registro: SalesOrder, form: dict, endpoint: str, order_id: str):
    """Maneja la actualizacion de una orden de venta desde el formulario POST."""
    customer_id = form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    registro.company = form.get("company") or None
    registro.posting_date = _parse_date(form.get("posting_date"))
    registro.remarks = form.get("remarks")
    for item in database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars():
        database.session.delete(item)
    _total_qty, total = _save_sales_order_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    database.session.commit()
    flash(_("Orden de venta actualizada correctamente."), "success")
    return redirect(url_for(endpoint, order_id=order_id))


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
        flash(str(exc), "danger")
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
        flash(str(exc), "danger")
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
        flash(str(exc), "danger")
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


def _save_sales_order_items(order_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una orden de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = SalesOrderItem(
                sales_order_id=order_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "sales_order", order_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_sales_request_items(request_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de un pedido de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = SalesRequestItem(
                sales_request_id=request_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "sales_request", request_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_sales_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una cotización de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = SalesQuotationItem(
                sales_quotation_id=quotation_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "sales_quotation", quotation_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_delivery_note_items(note_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una nota de entrega desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = DeliveryNoteItem(
                delivery_note_id=note_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
                warehouse=request.form.get(f"warehouse_{i}") or None,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "delivery_note", note_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _save_sales_invoice_items(invoice_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una factura de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = SalesInvoiceItem(
                sales_invoice_id=invoice_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
                warehouse=request.form.get(f"warehouse_{i}") or None,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "sales_invoice", invoice_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


def _create_delivery_note_from_invoice(invoice: SalesInvoice) -> DeliveryNote:
    """Crea y aprueba una Nota de Entrega desde una factura de venta.

    Se utiliza cuando ``update_inventory=True`` y la factura no tiene una
    Nota de Entrega previa vinculada. La DN se crea con los mismos ítems
    de la factura, usando la bodega predeterminada de cada ítem.
    """
    from cacao_accounting.database import Item as ItemModel

    items = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id)).scalars().all()
    if not items:
        raise PostingError("La factura no tiene ítems para crear la Nota de Entrega.")

    dn = DeliveryNote(
        customer_id=invoice.customer_id,
        customer_name=invoice.customer_name,
        company=invoice.company,
        posting_date=invoice.posting_date,
        sales_order_id=invoice.sales_order_id,
        remarks=f"Nota de Entrega auto-generada desde factura {invoice.document_no or invoice.id}",
        docstatus=0,
    )
    database.session.add(dn)
    database.session.flush()

    assign_document_identifier(
        document=dn,
        entity_type="delivery_note",
        posting_date_raw=invoice.posting_date,
        naming_series_id=None,
    )

    total = Decimal("0")
    for si_item in items:
        item_obj = database.session.get(ItemModel, si_item.item_code)
        warehouse = si_item.warehouse or (item_obj.default_warehouse_id if item_obj else None)
        if not warehouse:
            raise PostingError(
                f"El ítem {si_item.item_code} no tiene bodega predeterminada. "
                "Configure la bodega del ítem o cree la nota de entrega manualmente."
            )
        dn_item = DeliveryNoteItem(
            delivery_note_id=dn.id,
            item_code=si_item.item_code,
            item_name=si_item.item_name,
            qty=si_item.qty,
            uom=si_item.uom,
            qty_in_base_uom=si_item.qty_in_base_uom,
            rate=si_item.rate,
            amount=si_item.amount,
            warehouse=warehouse,
        )
        database.session.add(dn_item)
        total += si_item.amount or Decimal("0")

    dn.total = total
    dn.grand_total = total

    submit_document(dn)
    log_submit(dn)

    invoice.delivery_note_id = dn.id
    return dn


def _validate_invoice_prices_against_source(invoice: SalesInvoice) -> list[str]:
    """Valida precios de factura contra la Orden de Venta origen.

    Retorna una lista de mensajes de advertencia si ``allow_price_difference``
    es ``True`` y el precio excede la tolerancia. Si ``allow_price_difference``
    es ``False`` y el precio excede la tolerancia, lanza ``ValueError``.
    """
    config = database.session.execute(
        database.select(SalesMatchingConfig).filter_by(company=invoice.company)
    ).scalar_one_or_none()

    if config is None:
        tolerance_type = "percentage"
        tolerance_value = Decimal("0")
        allow_diff = False
    else:
        tolerance_type = config.price_tolerance_type or "percentage"
        tolerance_value = config.price_tolerance_value or Decimal("0")
        allow_diff = config.allow_price_difference

    invoice_items = (
        database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id)).scalars().all()
    )

    warnings: list[str] = []
    for si_item in invoice_items:
        relation = (
            database.session.execute(
                database.select(DocumentRelation).filter_by(
                    target_type="sales_invoice",
                    target_id=invoice.id,
                    target_item_id=si_item.id,
                    status="active",
                )
            )
            .scalars()
            .first()
        )
        if not relation or not relation.source_item_id:
            continue
        if relation.source_type != "sales_order":
            continue

        so_item = database.session.get(SalesOrderItem, relation.source_item_id)
        if not so_item:
            continue

        so_rate = Decimal(str(so_item.rate or 0))
        si_rate = Decimal(str(si_item.rate or 0))

        if so_rate <= 0:
            continue

        if tolerance_type == "absolute":
            variance = abs(si_rate - so_rate)
        else:
            variance = abs(si_rate - so_rate) / so_rate * Decimal("100")

        if variance > tolerance_value:
            msg = (
                f"El precio del ítem {si_item.item_code} (${si_rate}) "
                f"difiere del precio en la Orden de Venta (${so_rate}) "
                f"en {variance:.2f}{'%' if tolerance_type == 'percentage' else ''}. "
                f"Tolerancia permitida: {tolerance_value}{'%' if tolerance_type == 'percentage' else ''}."
            )
            if allow_diff:
                warnings.append(msg)
            else:
                raise ValueError(msg)
    return warnings


def _persist_sales_invoice_fiscal_snapshot(invoice: SalesInvoice) -> None:
    """Persist the editable fiscal snapshot captured in the form."""
    persist_document_fiscal_snapshot(
        company=str(invoice.company or ""),
        document_type=invoice.document_type or "sales_invoice",
        document_id=invoice.id,
        currency=None,
        tax_lines=request.form.get("tax_lines_payload"),
        tax_summary=request.form.get("tax_summary_payload"),
    )


def _sales_order_initial_source_type(from_request_id: str | None, from_quotation_id: str | None) -> str:
    """Resolve the initial source type for a sales order form."""
    if from_request_id:
        return "sales_request"
    if from_quotation_id:
        return "sales_quotation"
    return ""


def _build_sales_order_transaction_config(items_disponibles, uoms_disponibles, source_origen, initial_source_type):
    from cacao_accounting.form_preferences import get_column_preferences

    transaction_config = {
        "formKey": _FORMKEY_SALES_ORDER,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_ORDER),
        "availableSourceTypes": [
            {"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)},
            {"value": "sales_quotation", "label": _("Cotización de Venta")},
        ],
        "initialSourceType": initial_source_type,
    }
    if source_origen:
        transaction_config["initialHeader"] = {
            "company": source_origen.company or "",
            "posting_date": str(date.today()),
        }
    return transaction_config


def _handle_sales_order_new_post(from_quotation_id, from_request_id):
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    try:
        customer_id = request.form.get("customer_id") or None
        customer = database.session.get(Party, customer_id) if customer_id else None
        posting_date = _parse_date(request.form.get("posting_date"))
        orden = SalesOrder(
            customer_id=customer_id,
            customer_name=customer.name if customer else None,
            sales_quotation_id=from_quotation_id or None,
            company=request.form.get("company") or None,
            posting_date=posting_date,
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        database.session.add(orden)
        database.session.flush()
        assign_document_identifier(
            document=orden,
            entity_type="sales_order",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _total_qty, total = _save_sales_order_items(orden.id)
        orden.total = total
        orden.base_total = total
        orden.grand_total = total
        database.session.commit()
        flash("Orden de venta creada correctamente.", "success")
        return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=orden.id))
    except IdentifierConfigurationError as exc:
        database.session.rollback()
        flash(str(exc), "danger")


@ventas.route("/sales-order/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
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
    titulo = "Nueva Orden de Venta - " + APPNAME
    initial_source_type = _sales_order_initial_source_type(from_request_id, from_quotation_id)
    source_origen = solicitud_origen or cotizacion_origen
    transaction_config = _build_sales_order_transaction_config(
        items_disponibles, uoms_disponibles, source_origen, initial_source_type
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
    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=order_id)).all()
    titulo = (registro.document_no or order_id) + " - " + APPNAME
    return render_template("ventas/orden_venta.html", registro=registro, items=items, titulo=titulo)


@ventas.route("/sales-order/<order_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_editar(order_id: str):
    """Edita una orden de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioOrdenVenta

    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
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

    if request.method == "POST":
        return _handle_sales_order_update(registro, request.form, _ENDPOINT_ORDEN_VENTA, order_id)

    lineas = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_SALES_ORDER,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_ORDER),
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
                "amount": str(item.amount or 0),
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
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesOrder(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
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
    duplicado.total = total
    duplicado.base_total = total
    duplicado.grand_total = total
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
    from cacao_accounting.form_preferences import get_column_preferences
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
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_QUOTATION),
        "availableSourceTypes": [{"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)}],
    }
    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id") or None
            customer = database.session.get(Party, customer_id) if customer_id else None
            posting_date = _parse_date(request.form.get("posting_date"))
            cotizacion = SalesQuotation(
                customer_id=customer_id,
                customer_name=customer.name if customer else None,
                sales_request_id=from_request_id or None,
                company=request.form.get("company") or None,
                posting_date=posting_date,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(cotizacion)
            database.session.flush()
            assign_document_identifier(
                document=cotizacion,
                entity_type="sales_quotation",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_sales_quotation_items(cotizacion.id)
            cotizacion.total = total
            cotizacion.base_total = total
            cotizacion.grand_total = total
            database.session.commit()
            flash("Cotización creada correctamente.", "success")
            return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=cotizacion.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
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
    items = database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=quotation_id)).all()
    titulo = (registro.document_no or quotation_id) + " - " + APPNAME
    return render_template("ventas/cotizacion.html", registro=registro, items=items, titulo=titulo)


@ventas.route("/sales-quotation/<quotation_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_editar(quotation_id: str):
    """Edita una cotizacion de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioCotizacionVenta

    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
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
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_QUOTATION),
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
                "amount": str(item.amount or 0),
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


def _handle_sales_quotation_edit_post(registro):
    before_state = _capture_sales_state(registro)
    customer_id = request.form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    for item in database.session.execute(
        database.select(SalesQuotationItem).filter_by(sales_quotation_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _total_qty, total = _save_sales_quotation_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    after_state = _capture_sales_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Cotización de venta actualizada correctamente."), "success")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=registro.id))


@ventas.route("/sales-quotation/<quotation_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_duplicar(quotation_id: str):
    """Duplica una cotizacion de venta como borrador nuevo."""
    origen = database.session.get(SalesQuotation, quotation_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicado = SalesQuotation(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
        posting_date=origen.posting_date,
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
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicado.total = total
    duplicado.base_total = total
    duplicado.grand_total = total
    database.session.commit()
    flash(_("Cotización de venta duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=duplicado.id))


@ventas.route("/sales-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_submit(quotation_id: str):
    """Aprueba una cotizacion de venta."""
    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=registro.id))
            .scalars()
            .all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True)
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))
    flash("Cotizacion de venta aprobada.", "success")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))


@ventas.route("/sales-quotation/<quotation_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_cancel(quotation_id: str):
    """Cancela una cotización de venta."""
    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("sales_quotation", quotation_id)
    refresh_source_caches_for_target("sales_quotation", quotation_id)
    database.session.commit()
    flash("Cotización de venta cancelada.", "warning")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=quotation_id))


@ventas.route("/sales-order/<order_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_submit(order_id: str):
    """Aprueba una orden de venta y reserva inventario."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars().all()
        validate_submit_prerequisites(registro, items=items, require_party=True)
        _validate_and_reserve_stock_for_sales_order(registro)
        registro.docstatus = 1
        log_submit(registro)
        database.session.commit()
        flash("Orden de venta aprobada con reserva de inventario.", "success")
    except ValueError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))


@ventas.route("/sales-order/<order_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_cancel(order_id: str):
    """Cancela una orden de venta y libera la reserva de inventario."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    if has_active_source_relations("sales_order", order_id):
        flash("No se puede cancelar la orden de venta porque tiene notas de entrega o facturas activas.", "danger")
        return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))
    _release_reservation_for_sales_order(registro)
    registro.docstatus = 2
    log_cancel(registro)
    revert_relations_for_target("sales_order", order_id)
    refresh_source_caches_for_target("sales_order", order_id)
    database.session.commit()
    flash("Orden de venta cancelada y reserva liberada.", "warning")
    return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=order_id))


@ventas.route("/delivery-note/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_entrega_nuevo():
    """Formulario para crear una nota de entrega."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioEntregaVenta

    formulario = FormularioEntregaVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("delivery_note", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    orden_origen = database.session.get(SalesOrder, from_order_id) if from_order_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name} for w in database.session.execute(database.select(Warehouse)).all()
    ]
    titulo = "Nueva Nota de Entrega - " + APPNAME
    transaction_config = {
        "formKey": _FORMKEY_DELIVERY_NOTE,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_DELIVERY_NOTE),
        "availableSourceTypes": [{"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)}],
    }
    if request.method == "POST":
        try:
            posting_date = _parse_date(request.form.get("posting_date"))
            customer_id = request.form.get("customer_id") or None
            customer = database.session.get(Party, customer_id) if customer_id else None
            entrega = DeliveryNote(
                customer_id=customer_id,
                customer_name=customer.name if customer else None,
                company=request.form.get("company") or None,
                posting_date=posting_date,
                sales_order_id=request.form.get("from_order") or None,
                is_return=bool(request.form.get("is_return")),
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(entrega)
            database.session.flush()
            assign_document_identifier(
                document=entrega,
                entity_type="delivery_note",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_delivery_note_items(entrega.id)
            entrega.total = total
            entrega.grand_total = total
            log_create(entrega)
            database.session.commit()
            flash("Nota de entrega creada correctamente.", "success")
            return redirect(url_for(_ENDPOINT_ENTREGA, note_id=entrega.id))
        except (DocumentFlowError, IdentifierConfigurationError) as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "ventas/entrega_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        from_order_id=from_order_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
        transaction_config=transaction_config,
    )


@ventas.route("/delivery-note/<note_id>")
@modulo_activo("sales")
@login_required
def ventas_entrega(note_id):
    """Detalle de nota de entrega."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
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
@modulo_activo("sales")
@login_required
def ventas_entrega_editar(note_id: str):
    """Edita una nota de entrega en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import Warehouse
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioEntregaVenta

    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
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
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name} for w in database.session.execute(database.select(Warehouse)).all()
    ]

    if request.method == "POST":
        return _handle_delivery_note_edit_post(registro)

    lineas = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_DELIVERY_NOTE,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_DELIVERY_NOTE),
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


def _handle_delivery_note_edit_post(registro):
    before_state = _capture_sales_state(registro)
    customer_id = request.form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    for item in database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars():
        database.session.delete(item)
    _total_qty, total = _save_delivery_note_items(registro.id)
    registro.total = total
    registro.grand_total = total
    after_state = _capture_sales_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Nota de entrega actualizada correctamente."), "success")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=registro.id))


@ventas.route("/delivery-note/<note_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_entrega_duplicar(note_id: str):
    """Duplica una nota de entrega como borrador nuevo."""
    origen = database.session.get(DeliveryNote, note_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicado = DeliveryNote(
        customer_id=origen.customer_id,
        customer_name=origen.customer_name,
        company=origen.company,
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
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicado.total = total
    duplicado.grand_total = total
    database.session.commit()
    flash(_("Nota de entrega duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=duplicado.id))


@ventas.route("/delivery-note/<note_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_entrega_submit(note_id: str):
    """Aprueba una nota de entrega y libera la reserva de inventario."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars().all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True)
        submit_document(registro)
        _release_reservation_for_delivery_note(registro)
        log_submit(registro)
        database.session.commit()
        flash("Nota de entrega aprobada.", "success")
    except (PostingError, ValueError) as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))


@ventas.route("/delivery-note/<note_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_entrega_cancel(note_id: str):
    """Cancela una nota de entrega y restaura la reserva de inventario."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    try:
        cancel_document(registro)
        _restore_reservation_for_delivery_note(registro)
        revert_relations_for_target("delivery_note", note_id)
        refresh_source_caches_for_target("delivery_note", note_id)
        log_cancel(registro)
        database.session.commit()
        flash("Nota de entrega cancelada.", "warning")
    except PostingError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=note_id))


@ventas.route("/sales-invoice/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_factura_venta_nuevo():
    """Formulario para crear una factura de venta."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
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
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    from_note_id = request.args.get("from_note") or request.form.get("from_note")
    from_invoice = request.args.get("from_invoice") or request.form.get("from_invoice")
    from_return_id = request.args.get("from_return") or request.form.get("from_return")
    from_invoice_id = from_invoice or from_return_id
    document_type = (
        request.args.get("document_type")
        or request.form.get("document_type")
        or ("sales_invoice" if not from_invoice_id else "sales_credit_note")
    )
    formulario.is_return.data = document_type in ("sales_credit_note", "sales_return")
    orden_origen = database.session.get(SalesOrder, from_order_id) if from_order_id else None
    entrega_origen = database.session.get(DeliveryNote, from_note_id) if from_note_id else None
    factura_origen = database.session.get(SalesInvoice, from_invoice_id) if from_invoice_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Factura de Venta - " + APPNAME
    transaction_config = {
        "formKey": _FORMKEY_SALES_INVOICE,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_INVOICE),
        "availableSourceTypes": [
            {"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)},
            {"value": "delivery_note", "label": _("Nota de Entrega")},
            {"value": "sales_invoice", "label": _("Factura de Venta")},
        ],
    }
    if request.method == "POST":
        try:
            document_type = request.form.get("document_type") or "sales_invoice"
            posting_date = _parse_date(request.form.get("posting_date"))
            factura = SalesInvoice(
                customer_id=request.form.get("customer_id") or None,
                company=request.form.get("company") or None,
                posting_date=posting_date,
                document_type=document_type,
                sales_order_id=request.form.get("from_order") or None,
                delivery_note_id=request.form.get("from_note") or None,
                update_inventory=bool(request.form.get("update_inventory")),
                is_return=document_type in ("sales_credit_note", "sales_return"),
                reversal_of=(
                    (request.form.get("from_invoice") or request.form.get("from_return"))
                    if document_type in ("sales_credit_note", "sales_debit_note")
                    else None
                ),
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(factura)
            database.session.flush()
            assign_document_identifier(
                document=factura,
                entity_type="sales_invoice",
                posting_date_raw=posting_date,
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_sales_invoice_items(factura.id)
            factura.total = total
            factura.base_total = total
            factura.grand_total = total
            factura.base_grand_total = total
            factura.outstanding_amount = total
            factura.base_outstanding_amount = total
            _persist_sales_invoice_fiscal_snapshot(factura)
            database.session.commit()
            flash("Factura de venta creada correctamente.", "success")
            return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=factura.id))
        except ValueError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "ventas/factura_venta_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        entrega_origen=entrega_origen,
        factura_origen=factura_origen,
        from_order_id=from_order_id,
        from_note_id=from_note_id,
        from_invoice_id=from_invoice_id,
        from_return_id=from_return_id,
        document_type=document_type,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        transaction_config=transaction_config,
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
    items = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice_id)).all()
    titulo = (registro.document_no or invoice_id) + " - " + APPNAME
    return render_template("ventas/factura_venta.html", registro=registro, items=items, titulo=titulo)


@ventas.route("/sales-invoice/<invoice_id>/edit", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_factura_venta_editar(invoice_id: str):
    """Edita una factura de venta en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioFacturaVenta

    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
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
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        return _handle_sales_invoice_edit_post(registro)

    lineas = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _FORMKEY_SALES_INVOICE,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _FORMKEY_SALES_INVOICE),
        "availableSourceTypes": [
            {"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)},
            {"value": "delivery_note", "label": _("Nota de Entrega")},
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
        update_inventory_checked=registro.update_inventory,
    )


def _handle_sales_invoice_edit_post(registro):
    try:
        before_state = _capture_sales_state(registro)
        registro.customer_id = request.form.get("customer_id") or None
        registro.company = request.form.get("company") or None
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.remarks = request.form.get("remarks")
        registro.update_inventory = bool(request.form.get("update_inventory"))
        for item in database.session.execute(
            database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)
        ).scalars():
            database.session.delete(item)
        _total_qty, total = _save_sales_invoice_items(registro.id)
        registro.total = total
        registro.base_total = total
        registro.grand_total = total
        registro.base_grand_total = total
        registro.outstanding_amount = total
        registro.base_outstanding_amount = total
        warnings = _validate_invoice_prices_against_source(registro)
        _persist_sales_invoice_fiscal_snapshot(registro)
        after_state = _capture_sales_state(registro)
        log_update(registro, before=before_state, after=after_state)
        database.session.commit()
        for w in warnings:
            flash(_(w), "warning")
        flash(_("Factura de venta actualizada correctamente."), "success")
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=registro.id))
    except ValueError as exc:
        database.session.rollback()
        flash(str(exc), "danger")


@ventas.route("/sales-invoice/<invoice_id>/duplicate", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_factura_venta_duplicar(invoice_id: str):
    """Duplica una factura de venta como borrador nuevo."""
    origen = database.session.get(SalesInvoice, invoice_id)
    if not origen:
        abort(404)
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
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicado.total = total
    duplicado.base_total = total
    duplicado.grand_total = total
    duplicado.base_grand_total = total
    duplicado.outstanding_amount = total
    duplicado.base_outstanding_amount = total
    database.session.commit()
    flash(_("Factura de venta duplicada como nuevo borrador."), "success")
    return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=duplicado.id))


@ventas.route("/sales-invoice/<invoice_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_factura_venta_submit(invoice_id: str):
    """Aprueba una factura de venta."""
    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        items = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)).scalars().all()
        )
        validate_submit_prerequisites(registro, items=items, require_party=True)
        warnings = _validate_invoice_prices_against_source(registro)
        submit_document(registro)
        if registro.update_inventory and not registro.delivery_note_id:
            dn = _create_delivery_note_from_invoice(registro)
            flash(
                _("Se ha creado y aprobado la Nota de Entrega %s asociada a esta factura.") % (dn.document_no or dn.id),
                "info",
            )
        log_submit(registro)
        database.session.commit()
    except (PostingError, ValueError) as exc:
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
def ventas_factura_venta_cancel(invoice_id: str):
    """Cancela una factura de venta."""
    registro = database.session.get(SalesInvoice, invoice_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    try:
        if registro.update_inventory and registro.delivery_note_id:
            dn = database.session.get(DeliveryNote, registro.delivery_note_id)
            if dn and dn.docstatus == 1:
                cancel_document(dn)
                log_cancel(dn)
                flash(
                    _("Se ha cancelado la Nota de Entrega %s asociada.") % (dn.document_no or dn.id),
                    "info",
                )
        cancel_document(registro)
        log_cancel(registro)
        revert_relations_for_target("sales_invoice", invoice_id)
        refresh_source_caches_for_target("sales_invoice", invoice_id)
        database.session.commit()
    except PostingError as exc:
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
