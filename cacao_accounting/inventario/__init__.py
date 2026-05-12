# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes


"""Modulo de Inventarios."""

from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from cacao_accounting.database import Item, StockEntry, StockEntryItem, UOM, Warehouse, database
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document
from cacao_accounting.document_flow import revert_relations_for_target
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.version import APPNAME

inventario = Blueprint("inventario", __name__, template_folder="templates")


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return [("", "")]

    return [("", "")] + [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


@inventario.route("/")
@inventario.route("/inventario")
@inventario.route("/inventory")
@modulo_activo("inventory")
@login_required
def inventario_():
    """Definición de vista principal de inventarios."""
    return render_template("inventario.html")


@inventario.route("/item/list")
@modulo_activo("inventory")
@login_required
def inventario_articulo_lista():
    """Listado de articulos."""
    consulta = database.paginate(
        database.select(Item),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Articulos - " + APPNAME
    return render_template("inventario/articulo_lista.html", consulta=consulta, titulo=titulo)


@inventario.route("/uom/list")
@modulo_activo("inventory")
@login_required
def inventario_uom_lista():
    """Listado de unidades de medida."""
    consulta = database.paginate(
        database.select(UOM),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Unidades de Medida - " + APPNAME
    return render_template("inventario/uom_lista.html", consulta=consulta, titulo=titulo)


@inventario.route("/warehouse/list")
@modulo_activo("inventory")
@login_required
def inventario_bodega_lista():
    """Listado de bodegas."""
    consulta = database.paginate(
        database.select(Warehouse),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Bodegas - " + APPNAME
    return render_template("inventario/bodega_lista.html", consulta=consulta, titulo=titulo)


@inventario.route("/stock-entry/list")
@modulo_activo("inventory")
@login_required
def inventario_entrada_lista():
    """Listado de entradas de almacen."""
    consulta = database.paginate(
        database.select(StockEntry),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Movimientos de Inventario - " + APPNAME
    new_url = url_for("inventario.inventario_entrada_nuevo")
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_entrada_lista",
        new_url=new_url,
    )


@inventario.route("/stock-entry/material-receipt/list")
@modulo_activo("inventory")
@login_required
def inventario_material_receipt_lista():
    """Listado de recepciones de material."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="material_receipt"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Recepciones de Material - " + APPNAME
    new_url = url_for("inventario.inventario_entrada_nuevo", purpose="material_receipt")
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_material_receipt_lista",
        new_url=new_url,
    )


@inventario.route("/stock-entry/material-issue/list")
@modulo_activo("inventory")
@login_required
def inventario_material_issue_lista():
    """Listado de salidas de material."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="material_issue"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Salidas de Material - " + APPNAME
    new_url = url_for("inventario.inventario_entrada_nuevo", purpose="material_issue")
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_material_issue_lista",
        new_url=new_url,
    )


@inventario.route("/stock-entry/material-transfer/list")
@modulo_activo("inventory")
@login_required
def inventario_material_transfer_lista():
    """Listado de transferencias de material."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="material_transfer"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Transferencias de Material - " + APPNAME
    new_url = url_for("inventario.inventario_entrada_nuevo", purpose="material_transfer")
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_material_transfer_lista",
        new_url=new_url,
    )


@inventario.route("/stock-entry/adjustment/list")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_lista():
    """Listado de ajustes de inventario."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="stock_adjustment"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Ajustes de Inventario - " + APPNAME
    new_url = url_for("inventario.inventario_ajuste_nuevo")
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_ajuste_lista",
        new_url=new_url,
    )


@inventario.route("/stock-entry/reconciliation/list")
@modulo_activo("inventory")
@login_required
def inventario_reconciliacion_lista():
    """Listado de conciliaciones físicas de inventario."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="stock_reconciliation"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Conciliaciones de Inventario - " + APPNAME
    new_url = url_for("inventario.inventario_reconciliacion_nueva")
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_reconciliacion_lista",
        new_url=new_url,
    )


@inventario.route("/stock-entry/adjustment-positive/list")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_positivo_lista():
    """Listado de ajustes positivos de inventario."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="adjustment_positive"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Ajustes Positivos - " + APPNAME
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_ajuste_positivo_lista",
        new_url=url_for("inventario.inventario_ajuste_positivo_nuevo"),
    )


@inventario.route("/stock-entry/adjustment-negative/list")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_negativo_lista():
    """Listado de ajustes negativos de inventario."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="adjustment_negative"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Ajustes Negativos - " + APPNAME
    return render_template(
        "inventario/entrada_lista.html",
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_ajuste_negativo_lista",
        new_url=url_for("inventario.inventario_ajuste_negativo_nuevo"),
    )


@inventario.route("/item/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_articulo_nuevo():
    """Formulario para crear un nuevo artículo."""
    from cacao_accounting.inventario.forms import FormularioArticulo

    formulario = FormularioArticulo()
    formulario.default_uom.choices = [(u[0].code, u[0].name) for u in database.session.execute(database.select(UOM)).all()]
    titulo = "Nuevo Artículo - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        articulo = Item(
            code=request.form.get("code"),
            name=request.form.get("name"),
            description=request.form.get("description"),
            item_type=request.form.get("item_type", "goods"),
            is_stock_item=bool(request.form.get("is_stock_item")),
            default_uom=request.form.get("default_uom"),
        )
        database.session.add(articulo)
        database.session.commit()
        return redirect("/inventory/item/list")
    return render_template("inventario/articulo_nuevo.html", form=formulario, titulo=titulo)


@inventario.route("/item/<item_id>")
@modulo_activo("inventory")
@login_required
def inventario_articulo(item_id):
    """Detalle de artículo."""
    from flask import abort

    registro = database.session.execute(database.select(Item).filter_by(code=item_id)).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    return render_template("inventario/articulo.html", registro=registro[0], titulo=titulo)


@inventario.route("/uom/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_uom_nuevo():
    """Formulario para crear una nueva unidad de medida."""
    from cacao_accounting.inventario.forms import FormularioUOM

    formulario = FormularioUOM()
    titulo = "Nueva Unidad de Medida - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        uom = UOM(
            code=request.form.get("code"),
            name=request.form.get("name"),
        )
        database.session.add(uom)
        database.session.commit()
        return redirect("/inventory/uom/list")
    return render_template("inventario/uom_nuevo.html", form=formulario, titulo=titulo)


@inventario.route("/uom/<uom_id>")
@modulo_activo("inventory")
@login_required
def inventario_uom(uom_id):
    """Detalle de unidad de medida."""
    from flask import abort

    registro = database.session.execute(database.select(UOM).filter_by(code=uom_id)).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    return render_template("inventario/uom.html", registro=registro[0], titulo=titulo)


@inventario.route("/warehouse/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_bodega_nuevo():
    """Formulario para crear una nueva bodega."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.inventario.forms import FormularioBodega

    formulario = FormularioBodega()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    titulo = "Nueva Bodega - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        bodega = Warehouse(
            code=request.form.get("code"),
            name=request.form.get("name"),
            company=request.form.get("company"),
        )
        database.session.add(bodega)
        database.session.commit()
        return redirect("/inventory/warehouse/list")
    return render_template("inventario/bodega_nuevo.html", form=formulario, titulo=titulo)


@inventario.route("/warehouse/<warehouse_id>")
@modulo_activo("inventory")
@login_required
def inventario_bodega(warehouse_id):
    """Detalle de bodega."""
    from flask import abort

    registro = database.session.execute(database.select(Warehouse).filter_by(code=warehouse_id)).first()
    if not registro:
        abort(404)
    titulo = registro[0].name + " - " + APPNAME
    return render_template("inventario/bodega.html", registro=registro[0], titulo=titulo)


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


def _save_stock_entry_items(entry: StockEntry) -> Decimal:
    """Guarda lineas de un movimiento de inventario."""
    i = 0
    total = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            line = StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item_code,
                source_warehouse=entry.from_warehouse,
                target_warehouse=entry.to_warehouse,
                qty=qty,
                uom=request.form.get(f"uom_{i}") or None,
                basic_rate=rate,
                amount=amount,
            )
            database.session.add(line)
            total += amount
        i += 1
    return total


@inventario.route("/stock-entry/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/material-receipt/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/material-issue/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/material-transfer/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/adjustment/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/reconciliation/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/adjustment-positive/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/adjustment-negative/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_nuevo():
    """Formulario para crear una entrada de almacén."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    formulario = FormularioEntradaAlmacen()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("stock_entry", selected_company)
    warehouse_choices = [("", "")] + [
        (w[0].code, w[0].name) for w in database.session.execute(database.select(Warehouse).filter_by(is_active=True)).all()
    ]
    formulario.from_warehouse.choices = warehouse_choices
    formulario.to_warehouse.choices = warehouse_choices
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    purpose = request.args.get("purpose") or _infer_stock_entry_purpose(request.path)
    formulario.purpose.data = purpose or formulario.purpose.data
    source_api_url, source_label = _source_context(request.args.get("source_type"), request.args.get("source_id"))
    titulo = _stock_entry_title(purpose)
    if request.method == "POST":
        try:
            entry = StockEntry(
                purpose=request.form.get("purpose") or "material_receipt",
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                from_warehouse=request.form.get("from_warehouse") or None,
                to_warehouse=request.form.get("to_warehouse") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            database.session.add(entry)
            database.session.flush()
            assign_document_identifier(
                document=entry,
                entity_type="stock_entry",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
            )
            entry.total_amount = _save_stock_entry_items(entry)
            database.session.commit()
            flash("Entrada de almacén creada correctamente.", "success")
            return redirect(url_for("inventario.inventario_entrada", entry_id=entry.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "inventario/entrada_nuevo.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        source_api_url=source_api_url,
        source_label=source_label,
    )


def _infer_stock_entry_purpose(path: str) -> str | None:
    """Infers purpose from the specific stock entry creation path."""
    if path.endswith("/material-receipt/new"):
        return "material_receipt"
    if path.endswith("/material-issue/new"):
        return "material_issue"
    if path.endswith("/material-transfer/new"):
        return "material_transfer"
    if path.endswith("/adjustment/new"):
        return "stock_adjustment"
    if path.endswith("/reconciliation/new"):
        return "stock_reconciliation"
    if path.endswith("/adjustment-positive/new"):
        return "adjustment_positive"
    if path.endswith("/adjustment-negative/new"):
        return "adjustment_negative"
    return None


def _stock_entry_title(purpose: str | None) -> str:
    """Build a human friendly title for the stock entry creation page."""
    labels: dict[str, str] = {
        "material_receipt": "Nueva Recepción de Material",
        "material_issue": "Nueva Salida de Material",
        "material_transfer": "Nueva Transferencia de Material",
        "stock_adjustment": "Nuevo Ajuste de Inventario",
        "stock_reconciliation": "Nueva Conciliación de Inventario",
        "adjustment_positive": "Nuevo Ajuste Positivo de Inventario",
        "adjustment_negative": "Nuevo Ajuste Negativo de Inventario",
    }
    return labels.get(purpose or "", "Nueva Entrada de Almacén") + " - " + APPNAME


@inventario.route("/stock-entry/adjustment/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_nuevo():
    """Alias para crear ajuste de inventario."""
    return redirect(url_for("inventario.inventario_entrada_nuevo", purpose="stock_adjustment"))


@inventario.route("/stock-entry/reconciliation/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_reconciliacion_nueva():
    """Alias para crear conciliación física de inventario."""
    return redirect(url_for("inventario.inventario_entrada_nuevo", purpose="stock_reconciliation"))


@inventario.route("/stock-entry/adjustment-positive/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_positivo_nuevo():
    """Alias para crear ajuste positivo."""
    return redirect(url_for("inventario.inventario_entrada_nuevo", purpose="adjustment_positive"))


@inventario.route("/stock-entry/adjustment-negative/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_negativo_nuevo():
    """Alias para crear ajuste negativo."""
    return redirect(url_for("inventario.inventario_entrada_nuevo", purpose="adjustment_negative"))


def _source_context(source_type: str | None, source_id: str | None) -> tuple[str | None, str]:
    """Build the source document api context for pre-filling inventory lines."""
    if not source_type or not source_id:
        return None, "documento origen"
    if source_type == "purchase_receipt":
        return f"/api/buying/purchase-receipt/{source_id}/items", "recepción de compra"
    if source_type == "delivery_note":
        return f"/api/sales/delivery-note/{source_id}/items", "nota de entrega"
    return None, "documento origen"


@inventario.route("/stock-entry/<entry_id>")
@modulo_activo("inventory")
@login_required
def inventario_entrada(entry_id):
    """Detalle de entrada de almacén."""
    from flask import abort

    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    items = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entry_id)).all()
    titulo = (registro.document_no or entry_id) + " - " + APPNAME
    return render_template("inventario/entrada.html", registro=registro, items=items, titulo=titulo)


@inventario.route("/stock-entry/<entry_id>/submit", methods=["POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_submit(entry_id: str):
    """Aprueba una entrada de almacen y genera Stock Ledger/GL."""
    registro = database.session.get(StockEntry, entry_id)
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
        return redirect(url_for("inventario.inventario_entrada", entry_id=entry_id))
    flash(_("Entrada de almacen aprobada y contabilizada."), "success")
    return redirect(url_for("inventario.inventario_entrada", entry_id=entry_id))


@inventario.route("/stock-entry/<entry_id>/cancel", methods=["POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_cancel(entry_id: str):
    """Cancela una entrada de almacen."""
    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    try:
        cancel_document(registro)
        revert_relations_for_target("stock_entry", entry_id)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("inventario.inventario_entrada", entry_id=entry_id))
    flash(_("Entrada de almacen cancelada con reverso contable."), "warning")
    return redirect(url_for("inventario.inventario_entrada", entry_id=entry_id))
