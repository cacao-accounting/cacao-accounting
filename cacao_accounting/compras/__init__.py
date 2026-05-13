# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Compras."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from decimal import Decimal

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.compras.purchase_reconciliation_service import (
    get_purchase_reconciliation_panel_groups,
    get_purchase_reconciliation_pending,
)
from cacao_accounting.database import (
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

# < --------------------------------------------------------------------------------------------- >
compras = Blueprint("compras", __name__, template_folder="templates")

PURCHASE_INVOICE = "purchase_invoice"
PURCHASE_DEBIT_NOTE = "purchase_debit_note"
PURCHASE_CREDIT_NOTE = "purchase_credit_note"
PURCHASE_RETURN = "purchase_return"

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    PURCHASE_INVOICE: "Factura de Compra",
    PURCHASE_DEBIT_NOTE: "Nota de Débito de Compra",
    PURCHASE_CREDIT_NOTE: "Nota de Crédito de Compra",
    PURCHASE_RETURN: "Devolución de Compra",
}


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return [("", "")]

    return [("", "")] + [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


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
    consulta = database.paginate(
        database.select(PurchaseOrder),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Ordenes de Compra - " + APPNAME
    return render_template("compras/orden_compra_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-request/list")
@modulo_activo("purchases")
@login_required
def compras_solicitud_compra_lista():
    """Listado de solicitudes de compra internas."""
    consulta = database.paginate(
        database.select(PurchaseRequest),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
    if request.method == "POST":
        try:
            solicitud = PurchaseRequest(
                requested_by=request.form.get("requested_by"),
                department=request.form.get("department"),
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(solicitud)
            database.session.flush()
            assign_document_identifier(
                document=solicitud,
                entity_type="purchase_request",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            total_qty, total = _save_purchase_request_items(solicitud.id)
            solicitud.total = total
            solicitud.base_total = total
            solicitud.grand_total = total
            database.session.commit()
            flash("Solicitud de compra creada correctamente.", "success")
            return redirect(url_for("compras.compras_solicitud_compra", request_id=solicitud.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "compras/solicitud_compra_nueva.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
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
    titulo = (registro.document_no or request_id) + " - " + APPNAME
    return render_template("compras/solicitud_compra.html", registro=registro, items=items, titulo=titulo)


@compras.route("/supplier-quotation/list")
@modulo_activo("purchases")
@login_required
def compras_cotizacion_proveedor_lista():
    """Listado de cotizaciones de proveedor."""
    consulta = database.paginate(
        database.select(SupplierQuotation),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("supplier_quotation", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter_by(party_type="supplier")).all()
    ]
    from_rfq_id = request.args.get("from_rfq") or request.form.get("from_rfq")
    rfq_origen = database.session.get(PurchaseQuotation, from_rfq_id) if from_rfq_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Cotización de Proveedor - " + APPNAME
    if request.method == "POST":
        try:
            supplier_id = request.form.get("supplier_id") or None
            supplier = database.session.get(Party, supplier_id) if supplier_id else None
            cotizacion = SupplierQuotation(
                supplier_id=supplier_id,
                supplier_name=supplier.name if supplier else None,
                purchase_quotation_id=from_rfq_id or None,
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(cotizacion)
            database.session.flush()
            assign_document_identifier(
                document=cotizacion,
                entity_type="supplier_quotation",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            total_qty, total = _save_supplier_quotation_items(cotizacion.id)
            cotizacion.total = total
            cotizacion.base_total = total
            cotizacion.grand_total = total
            database.session.commit()
            flash("Cotización de proveedor creada correctamente.", "success")
            return redirect(url_for("compras.compras_cotizacion_proveedor", quotation_id=cotizacion.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "compras/cotizacion_proveedor_nueva.html",
        form=formulario,
        titulo=titulo,
        rfq_origen=rfq_origen,
        from_rfq_id=from_rfq_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
    )


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


@compras.route("/request-for-quotation/comparison")
@modulo_activo("purchases")
@login_required
def compras_comparativo_ofertas_lista():
    """Listado de comparativos de ofertas para solicitudes de cotización."""
    consulta = database.paginate(
        database.select(PurchaseQuotation),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
    consulta = database.paginate(
        database.select(PurchaseReceipt),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Recepciones de Compra - " + APPNAME
    return render_template("compras/recepcion_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-invoice/list")
@modulo_activo("purchases")
@login_required
def compras_factura_compra_lista():
    """Listado de facturas de compra."""
    consulta = database.paginate(
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_INVOICE),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Facturas de Compra - " + APPNAME
    return render_template("compras/factura_compra_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-invoice/debit-note/list")
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nota_debito_lista():
    """Listado de notas de débito de compra."""
    consulta = database.paginate(
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_DEBIT_NOTE),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Débito de Compra - " + APPNAME
    return render_template(
        "compras/factura_compra_devolucion_lista.html",
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
    consulta = database.paginate(
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_CREDIT_NOTE),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Crédito de Compra - " + APPNAME
    return render_template(
        "compras/factura_compra_devolucion_lista.html",
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
    consulta = database.paginate(
        database.select(PurchaseInvoice).filter_by(document_type=PURCHASE_RETURN),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Devoluciones de Compra - " + APPNAME
    return render_template(
        "compras/factura_compra_devolucion_lista.html",
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
    return redirect(url_for("compras.compras_factura_compra_nuevo", document_type=PURCHASE_DEBIT_NOTE))


@compras.route("/purchase-invoice/credit-note/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nota_credito_nueva():
    """Alias explicito para crear nota de crédito de compra."""
    return redirect(url_for("compras.compras_factura_compra_nuevo", document_type=PURCHASE_CREDIT_NOTE))


@compras.route("/purchase-invoice/return/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_devolucion_nueva():
    """Alias explicito para crear devolución de compra."""
    return redirect(url_for("compras.compras_factura_compra_nuevo", document_type=PURCHASE_RETURN))


@compras.route("/supplier/list")
@modulo_activo("purchases")
@login_required
def compras_proveedor_lista():
    """Listado de proveedores."""
    consulta = database.paginate(
        database.select(Party).filter(Party.party_type == "supplier"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Proveedores - " + APPNAME
    return render_template("compras/proveedor_lista.html", consulta=consulta, titulo=titulo)


@compras.route("/purchase-reconciliation")
@modulo_activo("purchases")
@login_required
def compras_purchase_reconciliation():
    """Reporte operativo de conciliaciones de compra pendientes por linea."""
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
    company_settings = build_party_company_settings("supplier", selected_company) if selected_company else None
    if request.method == "POST":
        proveedor = Party(
            party_type="supplier",
            name=request.form.get("name") or "",
            comercial_name=request.form.get("comercial_name"),
            tax_id=request.form.get("tax_id"),
            classification=request.form.get("classification"),
        )
        try:
            database.session.add(proveedor)
            database.session.flush()
            company = request.form.get("company") or None
            if company:
                upsert_party_company_settings(
                    proveedor.id,
                    "supplier",
                    company,
                    is_active=request.form.get("company_is_active") is not None,
                    receivable_account_id=None,
                    payable_account_id=request.form.get("payable_account_id") or None,
                    tax_template_id=request.form.get("tax_template_id") or None,
                    allow_purchase_invoice_without_order=request.form.get("allow_purchase_invoice_without_order") is not None,
                    allow_purchase_invoice_without_receipt=(
                        request.form.get("allow_purchase_invoice_without_receipt") is not None
                    ),
                )
            database.session.commit()
            return redirect("/buying/supplier/list")
        except ValueError as exc:
            database.session.rollback()
            if selected_company:
                company_settings = draft_party_company_settings("supplier", selected_company, request.form)
            flash(str(exc), "danger")
    return render_template(
        "compras/proveedor_nuevo.html",
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings=company_settings,
    )


@compras.route("/supplier/<supplier_id>")
@modulo_activo("purchases")
@login_required
def compras_proveedor(supplier_id):
    """Detalle de proveedor."""
    from flask import abort

    registro = database.session.execute(database.select(Party).filter_by(id=supplier_id, party_type="supplier")).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    return render_template("compras/proveedor.html", registro=registro[0], titulo=titulo)


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
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            linea = PurchaseOrderItem(
                purchase_order_id=order_id,
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


def _save_purchase_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una solicitud de cotización de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            linea = PurchaseQuotationItem(
                purchase_quotation_id=quotation_id,
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


def _save_purchase_request_items(request_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una solicitud de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
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
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            linea = SupplierQuotationItem(
                supplier_quotation_id=quotation_id,
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


def _save_purchase_receipt_items(receipt_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una recepción de compra desde el formulario."""
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
            linea = PurchaseReceiptItem(
                purchase_receipt_id=receipt_id,
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
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter_by(party_type="supplier")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Orden de Compra - " + APPNAME
    if request.method == "POST":
        try:
            supplier_id = request.form.get("supplier_id") or None
            supplier = database.session.get(Party, supplier_id) if supplier_id else None
            orden = PurchaseOrder(
                supplier_id=supplier_id,
                supplier_name=supplier.name if supplier else None,
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(orden)
            database.session.flush()
            assign_document_identifier(
                document=orden,
                entity_type="purchase_order",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            total_qty, total = _save_purchase_order_items(orden.id)
            orden.total_qty = total_qty
            orden.total = total
            orden.net_total = total
            orden.grand_total = total
            orden.base_total = total
            database.session.commit()
            flash("Orden de compra creada correctamente.", "success")
            return redirect(url_for("compras.compras_orden_compra", order_id=orden.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "compras/orden_compra_nuevo.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
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


@compras.route("/request-for-quotation/list")
@modulo_activo("purchases")
@login_required
def compras_solicitud_cotizacion_lista():
    """Listado de solicitudes de cotización."""
    consulta = database.paginate(
        database.select(PurchaseQuotation),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
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
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("purchase_quotation", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter_by(party_type="supplier")).all()
    ]
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nueva Solicitud de Cotización - " + APPNAME
    if request.method == "POST":
        try:
            supplier_id = request.form.get("supplier_id") or None
            supplier = database.session.get(Party, supplier_id) if supplier_id else None
            cotizacion = PurchaseQuotation(
                supplier_id=supplier_id,
                supplier_name=supplier.name if supplier else None,
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(cotizacion)
            database.session.flush()
            assign_document_identifier(
                document=cotizacion,
                entity_type="purchase_quotation",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            total_qty, total = _save_purchase_quotation_items(cotizacion.id)
            cotizacion.total = total
            cotizacion.base_total = total
            cotizacion.grand_total = total
            database.session.commit()
            flash("Solicitud de cotización creada correctamente.", "success")
            return redirect(url_for("compras.compras_solicitud_cotizacion", quotation_id=cotizacion.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "compras/solicitud_cotizacion_nuevo.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
    )


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
    registro.docstatus = 1
    database.session.commit()
    flash("Orden de compra aprobada.", "success")
    return redirect(url_for("compras.compras_orden_compra", order_id=order_id))


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
    registro.docstatus = 2
    revert_relations_for_target("purchase_order", order_id)
    database.session.commit()
    flash("Orden de compra cancelada.", "warning")
    return redirect(url_for("compras.compras_orden_compra", order_id=order_id))


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
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("purchase_receipt", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter_by(party_type="supplier")).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    orden_origen = database.session.get(PurchaseOrder, from_order_id) if from_order_id else None
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    bodegas_disponibles = [
        {"code": w[0].code, "name": w[0].name} for w in database.session.execute(database.select(Warehouse)).all()
    ]
    titulo = "Nueva Recepción de Compra - " + APPNAME
    if request.method == "POST":
        try:
            recepcion = PurchaseReceipt(
                supplier_id=request.form.get("supplier_id") or None,
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                purchase_order_id=request.form.get("from_order") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(recepcion)
            database.session.flush()
            assign_document_identifier(
                document=recepcion,
                entity_type="purchase_receipt",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_purchase_receipt_items(recepcion.id)
        except (DocumentFlowError, IdentifierConfigurationError) as exc:
            database.session.rollback()
            flash(str(exc), "danger")
            return render_template(
                "compras/recepcion_nuevo.html",
                form=formulario,
                titulo=titulo,
                orden_origen=orden_origen,
                from_order_id=from_order_id,
                items_disponibles=items_disponibles,
                uoms_disponibles=uoms_disponibles,
                bodegas_disponibles=bodegas_disponibles,
            )
        recepcion.total = total
        recepcion.grand_total = total
        database.session.commit()
        flash("Recepción de compra creada correctamente.", "success")
        return redirect(url_for("compras.compras_recepcion", receipt_id=recepcion.id))
    return render_template(
        "compras/recepcion_nuevo.html",
        form=formulario,
        titulo=titulo,
        orden_origen=orden_origen,
        from_order_id=from_order_id,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        bodegas_disponibles=bodegas_disponibles,
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
    titulo = (registro.document_no or registro.id) + " - " + APPNAME
    return render_template("compras/recepcion.html", registro=registro, items=items, titulo=titulo)


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
        submit_document(registro)
        database.session.commit()
        flash("Recepción de compra aprobada.", "success")
    except PostingError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("compras.compras_recepcion", receipt_id=receipt_id))


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
    try:
        cancel_document(registro)
        revert_relations_for_target("purchase_receipt", receipt_id)
        refresh_source_caches_for_target("purchase_receipt", receipt_id)
        database.session.commit()
        flash("Recepción de compra cancelada.", "warning")
    except PostingError as exc:
        database.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("compras.compras_recepcion", receipt_id=receipt_id))


@compras.route("/purchase-invoice/new", methods=["GET", "POST"])
@modulo_activo("purchases")
@login_required
def compras_factura_compra_nuevo():
    """Formulario para crear una factura de compra."""
    from cacao_accounting.compras.forms import FormularioFacturaCompra
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    formulario = FormularioFacturaCompra()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("purchase_invoice", selected_company)
    formulario.supplier_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name)
        for p in database.session.execute(database.select(Party).filter_by(party_type="supplier")).all()
    ]
    from_order_id = request.args.get("from_order") or request.form.get("from_order")
    from_receipt_id = request.args.get("from_receipt") or request.form.get("from_receipt")
    from_invoice_id = (
        request.args.get("from_invoice")
        or request.form.get("from_invoice")
        or request.args.get("from_return")
        or request.form.get("from_return")
    )
    document_type = (
        request.args.get("document_type")
        or request.form.get("document_type")
        or (PURCHASE_RETURN if from_receipt_id else PURCHASE_CREDIT_NOTE if from_invoice_id else PURCHASE_INVOICE)
    )
    formulario.is_return.data = document_type == PURCHASE_RETURN
    orden_origen = database.session.get(PurchaseOrder, from_order_id) if from_order_id else None
    recepcion_origen = database.session.get(PurchaseReceipt, from_receipt_id) if from_receipt_id else None
    factura_origen = database.session.get(PurchaseInvoice, from_invoice_id) if from_invoice_id else None
    document_title = DOCUMENT_TYPE_LABELS.get(document_type, "Factura de Compra")
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    titulo = f"Nueva {document_title} - {APPNAME}"
    if request.method == "POST":
        try:
            document_type = request.form.get("document_type") or PURCHASE_INVOICE
            factura = PurchaseInvoice(
                supplier_id=request.form.get("supplier_id") or None,
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                supplier_invoice_no=request.form.get("supplier_invoice_no"),
                document_type=document_type,
                purchase_order_id=request.form.get("from_order") or None,
                purchase_receipt_id=request.form.get("from_receipt") or None,
                is_return=document_type == PURCHASE_RETURN,
                reversal_of=(
                    (request.form.get("from_invoice") or request.form.get("from_return"))
                    if document_type in (PURCHASE_CREDIT_NOTE, PURCHASE_DEBIT_NOTE)
                    else None
                ),
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(factura)
            database.session.flush()
            assign_document_identifier(
                document=factura,
                entity_type="purchase_invoice",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            _total_qty, total = _save_purchase_invoice_items(factura.id)
        except (DocumentFlowError, IdentifierConfigurationError) as exc:
            database.session.rollback()
            flash(str(exc), "danger")
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
            )
        factura.total = total
        factura.base_total = total
        factura.grand_total = total
        factura.base_grand_total = total
        factura.outstanding_amount = total
        factura.base_outstanding_amount = total
        database.session.commit()
        flash("Factura de compra creada correctamente.", "success")
        return redirect(url_for("compras.compras_factura_compra", invoice_id=factura.id))
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
    )


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
    document_type_label = DOCUMENT_TYPE_LABELS.get(registro.document_type, "Factura de Compra")
    return render_template(
        "compras/factura_compra.html",
        registro=registro,
        items=items,
        titulo=titulo,
        document_type_label=document_type_label,
    )


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
        submit_document(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("compras.compras_factura_compra", invoice_id=invoice_id))
    flash(_("Factura de compra aprobada y contabilizada."), "success")
    return redirect(url_for("compras.compras_factura_compra", invoice_id=invoice_id))


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
    try:
        cancel_document(registro)
        revert_relations_for_target("purchase_invoice", invoice_id)
        refresh_source_caches_for_target("purchase_invoice", invoice_id)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("compras.compras_factura_compra", invoice_id=invoice_id))
    flash(_("Factura de compra cancelada con reverso contable."), "warning")
    return redirect(url_for("compras.compras_factura_compra", invoice_id=invoice_id))
