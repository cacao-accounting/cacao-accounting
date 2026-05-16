# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Ventas."""

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
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
    database,
)
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
    refresh_source_caches_for_target,
    revert_relations_for_target,
)
from cacao_accounting.document_flow.status import _
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.party_settings import (
    build_party_company_settings,
    draft_party_company_settings,
    upsert_party_company_settings,
)
from cacao_accounting.version import APPNAME

ventas = Blueprint("ventas", __name__, template_folder="templates")


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
    consulta = database.paginate(
        database.select(SalesOrder),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Ordenes de Venta - " + APPNAME
    return render_template("ventas/orden_venta_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/sales-request/list")
@modulo_activo("sales")
@login_required
def ventas_pedido_venta_lista():
    """Listado de pedidos de venta."""
    consulta = database.paginate(
        database.select(SalesRequest),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nuevo Pedido de Venta - " + APPNAME
    transaction_config = {
        "formKey": "sales.sales_request",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_request"),
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
            return redirect(url_for("ventas.ventas_pedido_venta", request_id=pedido.id))
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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        customer_id = request.form.get("customer_id") or None
        customer = database.session.get(Party, customer_id) if customer_id else None
        registro.customer_id = customer_id
        registro.customer_name = customer.name if customer else None
        registro.company = request.form.get("company") or None
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.remarks = request.form.get("remarks")
        for item in database.session.execute(
            database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)
        ).scalars():
            database.session.delete(item)
        _total_qty, total = _save_sales_request_items(registro.id)
        registro.total = total
        registro.base_total = total
        registro.grand_total = total
        database.session.commit()
        flash(_("Pedido de venta actualizado correctamente."), "success")
        return redirect(url_for("ventas.ventas_pedido_venta", request_id=registro.id))

    lineas = database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)).scalars()
    transaction_config = {
        "formKey": "sales.sales_request",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_request"),
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
    return redirect(url_for("ventas.ventas_pedido_venta", request_id=duplicado.id))


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
    registro.docstatus = 1
    database.session.commit()
    flash("Pedido de venta aprobado.", "success")
    return redirect(url_for("ventas.ventas_pedido_venta", request_id=request_id))


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
    database.session.commit()
    flash("Pedido de venta cancelado.", "warning")
    return redirect(url_for("ventas.ventas_pedido_venta", request_id=request_id))


@ventas.route("/delivery-note/list")
@modulo_activo("sales")
@login_required
def ventas_entrega_lista():
    """Listado de notas de entrega."""
    consulta = database.paginate(
        database.select(DeliveryNote),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Entrega - " + APPNAME
    return render_template("ventas/entrega_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/sales-invoice/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_lista():
    """Listado de facturas de venta."""
    consulta = database.paginate(
        database.select(SalesInvoice).filter_by(document_type="sales_invoice"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Facturas de Venta - " + APPNAME
    return render_template("ventas/factura_venta_lista.html", consulta=consulta, titulo=titulo)


@ventas.route("/sales-invoice/debit-note/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_nota_debito_lista():
    """Listado de notas de débito de venta."""
    consulta = database.paginate(
        database.select(SalesInvoice).filter_by(document_type="sales_debit_note"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
    """Listado de notas de crédito de venta."""
    consulta = database.paginate(
        database.select(SalesInvoice).filter_by(document_type="sales_credit_note"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Crédito de Venta - " + APPNAME
    return render_template(
        "ventas/factura_venta_devolucion_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Notas de Crédito de Venta",
        new_button_label="Nueva Nota de Crédito",
        page_caption="Listado de notas de crédito de venta.",
        new_document_type="sales_credit_note",
    )


@ventas.route("/sales-invoice/credit-note/list")
@modulo_activo("sales")
@login_required
def ventas_factura_venta_nota_credito_lista():
    """Alias explicito para listado de notas de crédito de venta."""
    return ventas_factura_venta_devolucion_lista()


@ventas.route("/customer/list")
@modulo_activo("sales")
@login_required
def ventas_cliente_lista():
    """Listado de clientes."""
    consulta = database.paginate(
        database.select(Party).filter(Party.party_type == "customer"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
    company_settings = build_party_company_settings("customer", selected_company) if selected_company else None
    if request.method == "POST":
        cliente = Party(
            party_type="customer",
            name=request.form.get("name") or "",
            comercial_name=request.form.get("comercial_name"),
            tax_id=request.form.get("tax_id"),
            classification=request.form.get("classification"),
        )
        try:
            database.session.add(cliente)
            database.session.flush()
            company = request.form.get("company") or None
            if company:
                upsert_party_company_settings(
                    cliente.id,
                    "customer",
                    company,
                    is_active=request.form.get("company_is_active") is not None,
                    receivable_account_id=request.form.get("receivable_account_id") or None,
                    payable_account_id=None,
                    tax_template_id=request.form.get("tax_template_id") or None,
                    allow_purchase_invoice_without_order=False,
                    allow_purchase_invoice_without_receipt=False,
                )
            database.session.commit()
            return redirect("/sales/customer/list")
        except ValueError as exc:
            database.session.rollback()
            if selected_company:
                company_settings = draft_party_company_settings("customer", selected_company, request.form)
            flash(str(exc), "danger")
    return render_template(
        "ventas/cliente_nuevo.html",
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings=company_settings,
    )


@ventas.route("/customer/<customer_id>")
@modulo_activo("sales")
@login_required
def ventas_cliente(customer_id):
    """Detalle de cliente."""
    registro = database.session.execute(database.select(Party).filter_by(id=customer_id, party_type="customer")).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    return render_template("ventas/cliente.html", registro=registro[0], titulo=titulo)


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
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "sales_invoice", invoice_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
        i += 1
    return total_qty, total


@ventas.route("/sales-order/new", methods=["GET", "POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_nuevo():
    """Formulario para crear una orden de venta."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.ventas.forms import FormularioOrdenVenta

    formulario = FormularioOrdenVenta()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("sales_order", selected_company)
    formulario.customer_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    from_quotation_id = request.args.get("from_quotation") or request.form.get("from_quotation")
    orden_origen = database.session.get(SalesOrder, from_order_id) if from_order_id else None
    cotizacion_origen = database.session.get(SalesQuotation, from_quotation_id) if from_quotation_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Orden de Venta - " + APPNAME
    transaction_config = {
        "formKey": "sales.sales_order",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_order"),
        "availableSourceTypes": [
            {"value": "sales_request", "label": _("Pedido de Venta")},
            {"value": "sales_quotation", "label": _("Cotización de Venta")},
        ],
    }
    if request.method == "POST":
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
            return redirect(url_for("ventas.ventas_orden_venta", order_id=orden.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "ventas/orden_venta_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        cotizacion_origen=cotizacion_origen,
        from_order_id=from_order_id,
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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        customer_id = request.form.get("customer_id") or None
        customer = database.session.get(Party, customer_id) if customer_id else None
        registro.customer_id = customer_id
        registro.customer_name = customer.name if customer else None
        registro.company = request.form.get("company") or None
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.remarks = request.form.get("remarks")
        for item in database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars():
            database.session.delete(item)
        _total_qty, total = _save_sales_order_items(registro.id)
        registro.total = total
        registro.base_total = total
        registro.grand_total = total
        database.session.commit()
        flash(_("Orden de venta actualizada correctamente."), "success")
        return redirect(url_for("ventas.ventas_orden_venta", order_id=registro.id))

    lineas = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars()
    transaction_config = {
        "formKey": "sales.sales_order",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_order"),
        "availableSourceTypes": [
            {"value": "sales_request", "label": _("Pedido de Venta")},
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
    return redirect(url_for("ventas.ventas_orden_venta", order_id=duplicado.id))


@ventas.route("/quotation/list")
@ventas.route("/request-for-quotation/list")
@modulo_activo("sales")
@login_required
def ventas_cotizacion_lista():
    """Listado de cotizaciones de venta."""
    consulta = database.paginate(
        database.select(SalesQuotation),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
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
        "formKey": "sales.sales_quotation",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_quotation"),
        "availableSourceTypes": [{"value": "sales_request", "label": _("Pedido de Venta")}],
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
            return redirect(url_for("ventas.ventas_cotizacion", quotation_id=cotizacion.id))
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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
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
        database.session.commit()
        flash(_("Cotización de venta actualizada correctamente."), "success")
        return redirect(url_for("ventas.ventas_cotizacion", quotation_id=registro.id))

    lineas = database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=registro.id)).scalars()
    transaction_config = {
        "formKey": "sales.sales_quotation",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_quotation"),
        "availableSourceTypes": [{"value": "sales_request", "label": _("Pedido de Venta")}],
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
    return redirect(url_for("ventas.ventas_cotizacion", quotation_id=duplicado.id))


@ventas.route("/sales-quotation/<quotation_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_cotizacion_submit(quotation_id: str):
    """Aprueba una cotización de venta."""
    registro = database.session.get(SalesQuotation, quotation_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    registro.docstatus = 1
    database.session.commit()
    flash("Cotización de venta aprobada.", "success")
    return redirect(url_for("ventas.ventas_cotizacion", quotation_id=quotation_id))


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
    revert_relations_for_target("sales_quotation", quotation_id)
    database.session.commit()
    flash("Cotización de venta cancelada.", "warning")
    return redirect(url_for("ventas.ventas_cotizacion", quotation_id=quotation_id))


@ventas.route("/sales-order/<order_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_submit(order_id: str):
    """Aprueba una orden de venta."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    registro.docstatus = 1
    database.session.commit()
    flash("Orden de venta aprobada.", "success")
    return redirect(url_for("ventas.ventas_orden_venta", order_id=order_id))


@ventas.route("/sales-order/<order_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_orden_venta_cancel(order_id: str):
    """Cancela una orden de venta."""
    registro = database.session.get(SalesOrder, order_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    registro.docstatus = 2
    revert_relations_for_target("sales_order", order_id)
    database.session.commit()
    flash("Orden de venta cancelada.", "warning")
    return redirect(url_for("ventas.ventas_orden_venta", order_id=order_id))


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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
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
        "formKey": "sales.delivery_note",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.delivery_note"),
        "availableSourceTypes": [{"value": "sales_order", "label": _("Orden de Venta")}],
    }
    if request.method == "POST":
        try:
            posting_date = _parse_date(request.form.get("posting_date"))
            entrega = DeliveryNote(
                customer_id=request.form.get("customer_id") or None,
                company=request.form.get("company") or None,
                posting_date=posting_date,
                sales_order_id=request.form.get("from_order") or None,
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
            database.session.commit()
            flash("Nota de entrega creada correctamente.", "success")
            return redirect(url_for("ventas.ventas_entrega", note_id=entrega.id))
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
    return render_template("ventas/entrega.html", registro=registro, items=items, titulo=titulo)


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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
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
        registro.customer_id = request.form.get("customer_id") or None
        registro.company = request.form.get("company") or None
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.remarks = request.form.get("remarks")
        for item in database.session.execute(
            database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)
        ).scalars():
            database.session.delete(item)
        _total_qty, total = _save_delivery_note_items(registro.id)
        registro.total = total
        registro.grand_total = total
        database.session.commit()
        flash(_("Nota de entrega actualizada correctamente."), "success")
        return redirect(url_for("ventas.ventas_entrega", note_id=registro.id))

    lineas = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars()
    transaction_config = {
        "formKey": "sales.delivery_note",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.delivery_note"),
        "availableSourceTypes": [{"value": "sales_order", "label": _("Orden de Venta")}],
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
    return redirect(url_for("ventas.ventas_entrega", note_id=duplicado.id))


@ventas.route("/delivery-note/<note_id>/submit", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_entrega_submit(note_id: str):
    """Aprueba una nota de entrega."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        submit_document(registro)
        database.session.commit()
        flash("Nota de entrega aprobada.", "success")
    except PostingError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("ventas.ventas_entrega", note_id=note_id))


@ventas.route("/delivery-note/<note_id>/cancel", methods=["POST"])
@modulo_activo("sales")
@login_required
def ventas_entrega_cancel(note_id: str):
    """Cancela una nota de entrega."""
    registro = database.session.get(DeliveryNote, note_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    try:
        cancel_document(registro)
        revert_relations_for_target("delivery_note", note_id)
        refresh_source_caches_for_target("delivery_note", note_id)
        database.session.commit()
        flash("Nota de entrega cancelada.", "warning")
    except PostingError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("ventas.ventas_entrega", note_id=note_id))


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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
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
    formulario.is_return.data = document_type == "sales_credit_note"
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
        "formKey": "sales.sales_invoice",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_invoice"),
        "availableSourceTypes": [
            {"value": "sales_order", "label": _("Orden de Venta")},
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
                is_return=document_type == "sales_credit_note",
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
            database.session.commit()
            flash("Factura de venta creada correctamente.", "success")
            return redirect(url_for("ventas.ventas_factura_venta", invoice_id=factura.id))
        except (DocumentFlowError, IdentifierConfigurationError) as exc:
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
        for p in database.session.execute(database.select(Party).filter_by(party_type="customer")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        registro.customer_id = request.form.get("customer_id") or None
        registro.company = request.form.get("company") or None
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.remarks = request.form.get("remarks")
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
        database.session.commit()
        flash(_("Factura de venta actualizada correctamente."), "success")
        return redirect(url_for("ventas.ventas_factura_venta", invoice_id=registro.id))

    lineas = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)).scalars()
    transaction_config = {
        "formKey": "sales.sales_invoice",
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, "sales.sales_invoice"),
        "availableSourceTypes": [
            {"value": "sales_order", "label": _("Orden de Venta")},
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
    )


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
    return redirect(url_for("ventas.ventas_factura_venta", invoice_id=duplicado.id))


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
        submit_document(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("ventas.ventas_factura_venta", invoice_id=invoice_id))
    flash(_("Factura de venta aprobada y contabilizada."), "success")
    return redirect(url_for("ventas.ventas_factura_venta", invoice_id=invoice_id))


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
        cancel_document(registro)
        revert_relations_for_target("sales_invoice", invoice_id)
        refresh_source_caches_for_target("sales_invoice", invoice_id)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("ventas.ventas_factura_venta", invoice_id=invoice_id))
    flash(_("Factura de venta cancelada con reverso contable."), "warning")
    return redirect(url_for("ventas.ventas_factura_venta", invoice_id=invoice_id))
