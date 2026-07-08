# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes


"""Modulo de Inventarios."""

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from cacao_accounting.database import (
    Accounts,
    CostCenter,
    DocumentRelation,
    Entity,
    Item,
    ItemCategory,
    StockBin,
    StockEntry,
    StockEntryItem,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document
from cacao_accounting.document_flow import create_document_relation, revert_relations_for_target, validate_submit_prerequisites
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.list_filters import apply_list_filters
from cacao_accounting.version import APPNAME
from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_create, log_submit, log_update
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    convert_item_qty,
    create_item_with_uoms,
    list_item_account_rows,
    list_item_uom_conversions,
    parse_item_account_rows,
    parse_item_uom_rows,
    update_item_with_uoms,
)

inventario = Blueprint("inventario", __name__, template_folder="templates")


def _parse_date(value: str | None) -> date | None:
    """Parsea una fecha en formato ISO."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


INVENTARIO_INVENTARIO_ENTRADA_NUEVO = "inventario.inventario_entrada_nuevo"
INVENTARIO_ENTRADA_LISTA_HTML = "inventario/entrada_lista.html"
INVENTARIO_INVENTARIO_ENTRADA = "inventario.inventario_entrada"
_INVENTORY_STOCK_ENTRY = "inventory.stock_entry"
_LABEL_DOCUMENTO_ORIGEN = "documento origen"


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
    """Listado de articulos con busqueda."""
    consulta = database.paginate(
        apply_list_filters(
            database.select(Item),
            Item,
            (Item.code, Item.name),
            include_status=False,
        ),
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
    new_url = url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO)
    return render_template(
        INVENTARIO_ENTRADA_LISTA_HTML,
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
    new_url = url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="material_receipt")
    return render_template(
        INVENTARIO_ENTRADA_LISTA_HTML,
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
    new_url = url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="material_issue")
    return render_template(
        INVENTARIO_ENTRADA_LISTA_HTML,
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
    new_url = url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="material_transfer")
    return render_template(
        INVENTARIO_ENTRADA_LISTA_HTML,
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
        INVENTARIO_ENTRADA_LISTA_HTML,
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
        INVENTARIO_ENTRADA_LISTA_HTML,
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
        INVENTARIO_ENTRADA_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_ajuste_positivo_lista",
        new_url=url_for("inventario.inventario_ajuste_positivo_nuevo"),
    )


@inventario.route("/stock-entry/inventory-issue/list")
@modulo_activo("inventory")
@login_required
def inventario_salida_inventario_lista():
    """Listado de salidas de inventario (incluyendo ajustes negativos)."""
    consulta = database.paginate(
        database.select(StockEntry).filter_by(purpose="adjustment_negative"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Salidas de Inventario - " + APPNAME
    return render_template(
        INVENTARIO_ENTRADA_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        vista="inventario.inventario_salida_inventario_lista",
        new_url=url_for("inventario.inventario_salida_inventario_nuevo"),
    )


@inventario.route("/item/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_articulo_nuevo():
    """Formulario para crear un nuevo artículo (codigo auto-generado)."""
    from cacao_accounting.inventario.forms import FormularioArticulo

    formulario = FormularioArticulo()
    formulario.default_uom.choices = _uom_choices()
    formulario.item_category_id.choices = _item_category_choices()
    formulario.currency.choices = _currency_choices()
    titulo = "Nuevo Artículo - " + APPNAME
    uom_rows = [{"uom_code": "", "conversion_factor": ""}]
    account_rows = [{"company": "", "expense_account_id": "", "cost_center_code": ""}]

    if request.method == "POST":
        uom_rows = _item_uom_rows_for_template(request.form)
        account_rows = _item_account_rows_for_template(request.form)
        if formulario.validate():
            try:
                create_item_with_uoms(
                    name=str(request.form.get("name") or "").strip(),
                    description=(request.form.get("description") or "").strip() or None,
                    item_type=str(request.form.get("item_type") or "goods").strip(),
                    is_stock_item=request.form.get("is_stock_item") is not None,
                    is_purchase_item=request.form.get("is_purchase_item") is not None,
                    is_sale_item=request.form.get("is_sale_item") is not None,
                    item_category_id=(request.form.get("item_category_id") or "").strip() or None,
                    default_uom=str(request.form.get("default_uom") or "").strip(),
                    purchase_uom=(request.form.get("purchase_uom") or "").strip() or None,
                    sale_uom=(request.form.get("sale_uom") or "").strip() or None,
                    default_warehouse_id=(request.form.get("default_warehouse_id") or "").strip() or None,
                    default_supplier_id=(request.form.get("default_supplier_id") or "").strip() or None,
                    allow_negative_stock=request.form.get("allow_negative_stock") is not None,
                    min_stock_qty=_form_decimal("min_stock_qty"),
                    max_stock_qty=_form_decimal("max_stock_qty"),
                    reorder_level=_form_decimal("reorder_level"),
                    standard_rate=_form_decimal("standard_rate"),
                    last_purchase_rate=_form_decimal("last_purchase_rate"),
                    currency=(request.form.get("currency") or "").strip() or None,
                    brand=(request.form.get("brand") or "").strip() or None,
                    model_name=(request.form.get("model_name") or "").strip() or None,
                    barcode=(request.form.get("barcode") or "").strip() or None,
                    has_batch=request.form.get("has_batch") is not None,
                    has_serial_no=request.form.get("has_serial_no") is not None,
                    has_expiry_date=request.form.get("has_expiry_date") is not None,
                    uom_rows=parse_item_uom_rows(request.form),
                    account_rows=parse_item_account_rows(request.form),
                )
                database.session.commit()
                return redirect("/inventory/item/list")
            except InventoryServiceError as exc:
                database.session.rollback()
                flash(str(exc), "danger")
            except ValueError as exc:
                database.session.rollback()
                flash(str(exc), "danger")
        else:
            flash("Revise los datos del formulario de artículo.", "danger")

    return render_template(
        "inventario/articulo_nuevo.html",
        form=formulario,
        titulo=titulo,
        uom_rows=uom_rows,
        account_rows=account_rows,
        uom_choices=_uom_choices(),
        company_choices=_company_choices(),
        account_choices=_account_choices(),
        cost_center_choices=_cost_center_choices(),
        category_choices=_item_category_choices(),
        currency_choices=_currency_choices(),
    )


@inventario.route("/item/<item_id>/edit", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_articulo_editar(item_id):
    """Formulario para editar un artículo existente."""
    from cacao_accounting.inventario.forms import FormularioArticulo

    registro = database.session.execute(database.select(Item).filter_by(code=item_id)).first()
    if not registro:
        abort(404)
    item = registro[0]

    formulario = FormularioArticulo(obj=item)
    formulario.default_uom.choices = _uom_choices()
    formulario.item_category_id.choices = _item_category_choices()
    formulario.currency.choices = _currency_choices()
    titulo = f"Editar {item.name} - " + APPNAME

    existing_uom_rows = [
        {"uom_code": c.from_uom, "conversion_factor": str(c.conversion_factor)} for c in list_item_uom_conversions(item.code)
    ] or [{"uom_code": "", "conversion_factor": ""}]
    existing_account_rows = [
        {
            "company": a.company,
            "expense_account_id": a.expense_account_id or "",
            "income_account_id": a.income_account_id or "",
            "cogs_account_id": a.cogs_account_id or "",
            "stock_adjustment_account_id": a.stock_adjustment_account_id or "",
            "cost_center_code": a.cost_center_code or "",
        }
        for a in list_item_account_rows(item.code)
    ] or [
        {
            "company": "",
            "expense_account_id": "",
            "income_account_id": "",
            "cogs_account_id": "",
            "stock_adjustment_account_id": "",
            "cost_center_code": "",
        }
    ]

    uom_rows = existing_uom_rows
    account_rows = existing_account_rows

    if request.method == "POST":
        uom_rows = _item_uom_rows_for_template(request.form)
        account_rows = _item_account_rows_for_template(request.form)
        if formulario.validate():
            try:
                update_item_with_uoms(
                    item_code=item.code,
                    name=str(request.form.get("name") or "").strip(),
                    description=(request.form.get("description") or "").strip() or None,
                    item_type=str(request.form.get("item_type") or "goods").strip(),
                    is_stock_item=request.form.get("is_stock_item") is not None,
                    is_purchase_item=request.form.get("is_purchase_item") is not None,
                    is_sale_item=request.form.get("is_sale_item") is not None,
                    item_category_id=(request.form.get("item_category_id") or "").strip() or None,
                    default_uom=str(request.form.get("default_uom") or "").strip(),
                    purchase_uom=(request.form.get("purchase_uom") or "").strip() or None,
                    sale_uom=(request.form.get("sale_uom") or "").strip() or None,
                    default_warehouse_id=(request.form.get("default_warehouse_id") or "").strip() or None,
                    default_supplier_id=(request.form.get("default_supplier_id") or "").strip() or None,
                    allow_negative_stock=request.form.get("allow_negative_stock") is not None,
                    min_stock_qty=_form_decimal("min_stock_qty"),
                    max_stock_qty=_form_decimal("max_stock_qty"),
                    reorder_level=_form_decimal("reorder_level"),
                    standard_rate=_form_decimal("standard_rate"),
                    last_purchase_rate=_form_decimal("last_purchase_rate"),
                    currency=(request.form.get("currency") or "").strip() or None,
                    brand=(request.form.get("brand") or "").strip() or None,
                    model_name=(request.form.get("model_name") or "").strip() or None,
                    barcode=(request.form.get("barcode") or "").strip() or None,
                    has_batch=request.form.get("has_batch") is not None,
                    has_serial_no=request.form.get("has_serial_no") is not None,
                    has_expiry_date=request.form.get("has_expiry_date") is not None,
                    uom_rows=parse_item_uom_rows(request.form),
                    account_rows=parse_item_account_rows(request.form),
                )
                database.session.commit()
                flash("Artículo actualizado correctamente.", "success")
                return redirect(url_for("inventario.inventario_articulo", item_id=item.code))
            except InventoryServiceError as exc:
                database.session.rollback()
                flash(str(exc), "danger")
            except ValueError as exc:
                database.session.rollback()
                flash(str(exc), "danger")
        else:
            flash("Revise los datos del formulario de artículo.", "danger")

    return render_template(
        "inventario/articulo_nuevo.html",
        form=formulario,
        titulo=titulo,
        edit=True,
        registro=item,
        uom_rows=uom_rows,
        account_rows=account_rows,
        uom_choices=_uom_choices(),
        company_choices=_company_choices(),
        account_choices=_account_choices(),
        cost_center_choices=_cost_center_choices(),
        category_choices=_item_category_choices(),
        currency_choices=_currency_choices(),
    )


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
    item_category = None
    if registro[0].item_category_id:
        item_category = database.session.get(ItemCategory, registro[0].item_category_id)
    from cacao_accounting.database import Warehouse as WarehouseModel

    item = registro[0]
    default_warehouse = None
    default_supplier = None
    if item.default_warehouse_id:
        default_warehouse = database.session.get(WarehouseModel, item.default_warehouse_id)
    if item.default_supplier_id:
        from cacao_accounting.database import Party

        default_supplier = database.session.get(Party, item.default_supplier_id)
    return render_template(
        "inventario/articulo.html",
        registro=item,
        titulo=titulo,
        item_category=item_category,
        default_warehouse=default_warehouse,
        default_supplier=default_supplier,
        uom_conversions=list_item_uom_conversions(item.code),
        item_accounts=list_item_account_rows(item.code),
    )


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


def _uom_choices() -> list[tuple[str, str]]:
    """Devuelve las UOM disponibles para el formulario de articulo."""
    return [(u.code, u.name) for u in database.session.execute(database.select(UOM).order_by(UOM.name)).scalars().all()]


def _item_uom_rows_for_template(form_data: Mapping[str, Any]) -> list[dict[str, str]]:
    """Normaliza filas de UOM para re-renderizar el formulario."""
    parsed_rows = parse_item_uom_rows(form_data)
    if not parsed_rows:
        return [{"uom_code": "", "conversion_factor": ""}]
    return [{"uom_code": row.uom_code, "conversion_factor": str(row.conversion_factor)} for row in parsed_rows]


def _company_choices() -> list[tuple[str, str]]:
    """Devuelve companias disponibles para el formulario de item."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    return obtener_lista_entidades_por_id_razonsocial()


def _account_choices() -> list[dict[str, str]]:
    """Devuelve cuentas activas para la tabla contable del item."""
    accounts = (
        database.session.execute(
            database.select(Accounts)
            .filter_by(active=True, enabled=True, group=False)
            .order_by(Accounts.entity, Accounts.code)
        )
        .scalars()
        .all()
    )
    return [{"id": account.id, "label": f"{account.entity} - {account.code} - {account.name}"} for account in accounts]


def _cost_center_choices() -> list[dict[str, str]]:
    """Devuelve centros de costo activos para la tabla contable del item."""
    cost_centers = (
        database.session.execute(
            database.select(CostCenter)
            .filter_by(active=True, enabled=True, group=False)
            .order_by(CostCenter.entity, CostCenter.code)
        )
        .scalars()
        .all()
    )
    return [
        {"code": cost_center.code, "label": f"{cost_center.entity} - {cost_center.code} - {cost_center.name}"}
        for cost_center in cost_centers
    ]


def _item_account_rows_for_template(form_data: Mapping[str, Any]) -> list[dict[str, str]]:
    """Normaliza filas contables para re-renderizar el formulario."""
    parsed_rows = parse_item_account_rows(form_data)
    if not parsed_rows:
        return [
            {
                "company": "",
                "expense_account_id": "",
                "income_account_id": "",
                "cogs_account_id": "",
                "stock_adjustment_account_id": "",
                "cost_center_code": "",
            }
        ]
    return [
        {
            "company": row.company,
            "expense_account_id": row.expense_account_id or "",
            "income_account_id": row.income_account_id or "",
            "cogs_account_id": row.cogs_account_id or "",
            "stock_adjustment_account_id": row.stock_adjustment_account_id or "",
            "cost_center_code": row.cost_center_code or "",
        }
        for row in parsed_rows
    ]


def _item_category_choices() -> list[tuple[str, str]]:
    """Devuelve categorias de articulo disponibles para el formulario."""
    categories = (
        database.session.execute(database.select(ItemCategory).filter_by(is_active=True).order_by(ItemCategory.name))
        .scalars()
        .all()
    )
    return [("", "")] + [(cat.id, cat.name) for cat in categories]


def _currency_choices() -> list[tuple[str, str]]:
    """Devuelve monedas disponibles para el formulario de item."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_monedas_activas

    return obtener_lista_monedas_activas()


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
    from cacao_accounting.inventario.forms import FormularioBodega

    formulario = FormularioBodega()
    titulo = "Nueva Bodega - " + APPNAME
    warehouse_company_rows = [{"company": "", "company_label": "", "inventory_account_id": "", "inventory_account_label": ""}]
    if formulario.validate_on_submit() or request.method == "POST":
        warehouse_company_rows = _warehouse_company_rows_for_template(request.form)
        company_rows = [row for row in warehouse_company_rows if row["company"]]
        try:
            _validate_warehouse_company_rows(company_rows)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "inventario/bodega_nuevo.html",
                form=formulario,
                titulo=titulo,
                warehouse_company_rows=warehouse_company_rows,
            )
        bodega = Warehouse(
            code=request.form.get("code"),
            name=request.form.get("name"),
            company=company_rows[0]["company"],
        )
        database.session.add(bodega)
        database.session.flush()
        _save_warehouse_company_rows(bodega.code, company_rows)
        database.session.commit()
        return redirect("/inventory/warehouse/list")
    return render_template(
        "inventario/bodega_nuevo.html",
        form=formulario,
        titulo=titulo,
        warehouse_company_rows=warehouse_company_rows,
    )


def _warehouse_company_rows_for_template(form_data: Any) -> list[dict[str, str]]:
    """Reconstruye filas de configuracion de bodega por compañia desde el formulario."""
    companies = form_data.getlist("warehouse_company")
    accounts = form_data.getlist("warehouse_inventory_account_id")
    rows: list[dict[str, str]] = []
    for index, company in enumerate(companies):
        account_id = accounts[index] if index < len(accounts) else ""
        rows.append(
            {
                "company": str(company or "").strip(),
                "company_label": str(company or "").strip(),
                "inventory_account_id": str(account_id or "").strip(),
                "inventory_account_label": str(account_id or "").strip(),
            }
        )
    return rows or [{"company": "", "company_label": "", "inventory_account_id": "", "inventory_account_label": ""}]


def _validate_warehouse_company_rows(rows: list[dict[str, str]]) -> None:
    """Valida filas contables de bodega por compañía."""
    if not rows:
        raise ValueError(_("La bodega requiere al menos una configuración por compañía."))
    seen: set[str] = set()
    for row in rows:
        company = row["company"]
        if company in seen:
            raise ValueError(_("No se puede repetir la misma compañía en la bodega."))
        seen.add(company)
        company_exists = database.session.execute(database.select(Entity).filter_by(code=company)).scalar_one_or_none()
        if company_exists is None:
            raise ValueError(_("La compañía seleccionada no existe."))
        account_id = row["inventory_account_id"]
        if not account_id:
            continue
        account = database.session.get(Accounts, account_id)
        if account is None or account.entity != company:
            raise ValueError(_("La cuenta de inventario debe pertenecer a la compañía seleccionada."))
        if (account.account_type or "").strip().lower() != "inventory":
            raise ValueError(_("La cuenta seleccionada debe ser de tipo inventario."))


def _save_warehouse_company_rows(warehouse_code: str, rows: list[dict[str, str]]) -> None:
    """Persist warehouse company accounting configuration."""
    for row in rows:
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=warehouse_code,
                company=row["company"],
                inventory_account_id=row["inventory_account_id"] or None,
                is_active=True,
            )
        )


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
    company_accounts = (
        database.session.execute(
            database.select(WarehouseCompanyAccount)
            .filter_by(warehouse_code=registro[0].code)
            .order_by(WarehouseCompanyAccount.company)
        )
        .scalars()
        .all()
    )
    account_ids = [row.inventory_account_id for row in company_accounts if row.inventory_account_id]
    account_map: dict[str, Accounts] = {}
    if account_ids:
        account_map = {
            account.id: account
            for account in database.session.execute(database.select(Accounts).filter(Accounts.id.in_(account_ids))).scalars()
        }
    return render_template(
        "inventario/bodega.html",
        registro=registro[0],
        company_accounts=company_accounts,
        account_map=account_map,
        titulo=titulo,
    )


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
            uom = request.form.get(f"uom_{i}") or None
            line = StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item_code,
                source_warehouse=entry.from_warehouse,
                target_warehouse=entry.to_warehouse,
                qty=qty,
                uom=uom,
                basic_rate=rate,
                amount=amount,
            )
            database.session.add(line)
            database.session.flush()
            _create_line_relation(i, "stock_entry", entry.id, line.id, qty, uom, rate, amount)
            total += amount
        i += 1
    return total


def _stock_bin_snapshot(
    company: str | None, item_code: str, warehouse: str | None
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Devuelve cantidad, tasa, valor y reserva actual para item/bodega."""
    if not company or not warehouse:
        return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
    bin_row = (
        database.session.execute(
            database.select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse)
        )
        .scalars()
        .first()
    )
    if not bin_row:
        return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
    return (
        Decimal(str(bin_row.actual_qty or "0")),
        Decimal(str(bin_row.valuation_rate or "0")),
        Decimal(str(bin_row.stock_value or "0")),
        Decimal(str(bin_row.reserved_qty or "0")),
    )


def _item_default_uom(item_code: str) -> str | None:
    """Devuelve la unidad base del item por codigo."""
    item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalars().first()
    return item.default_uom if item else None


def _save_stock_reconciliation_items(entry: StockEntry) -> Decimal:
    """Guarda lineas de conciliacion con snapshot de cantidad y valuacion."""
    i = 0
    total_difference = Decimal("0")
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "").strip()
        warehouse = request.form.get(f"warehouse_{i}") or entry.to_warehouse or entry.from_warehouse
        if item_code:
            current_qty, current_rate, current_value, _reserved_qty = _stock_bin_snapshot(entry.company, item_code, warehouse)
            counted_qty = _form_decimal(f"counted_qty_{i}", str(current_qty))
            target_rate = _form_decimal(f"target_valuation_rate_{i}", str(current_rate))
            target_value = _form_decimal(f"target_stock_value_{i}", str(counted_qty * target_rate))
            qty_difference = counted_qty - current_qty
            value_difference = target_value - current_value
            uom = request.form.get(f"uom_{i}") or _item_default_uom(item_code)
            try:
                base_qty = convert_item_qty(item_code, abs(qty_difference), uom, _item_default_uom(item_code))
            except InventoryServiceError:
                base_qty = abs(qty_difference)
            line = StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item_code,
                source_warehouse=warehouse,
                target_warehouse=warehouse,
                qty=abs(qty_difference),
                uom=uom,
                qty_in_base_uom=base_qty,
                basic_rate=target_rate,
                amount=abs(value_difference),
                valuation_rate=target_rate,
                current_qty=current_qty,
                counted_qty=counted_qty,
                qty_difference=qty_difference,
                current_valuation_rate=current_rate,
                target_valuation_rate=target_rate,
                current_stock_value=current_value,
                target_stock_value=target_value,
                stock_value_difference=value_difference,
            )
            database.session.add(line)
            database.session.flush()
            total_difference += abs(value_difference)
        i += 1
    return total_difference


@inventario.route("/stock-entry/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/material-receipt/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/material-issue/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/material-transfer/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/adjustment/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/reconciliation/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/adjustment-positive/new", methods=["GET", "POST"])
@inventario.route("/stock-entry/inventory-issue/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_nuevo():
    """Formulario para crear una entrada de almacén."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    formulario = FormularioEntradaAlmacen()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("stock_entry", selected_company)
    # INV-03: Filtrar bodegas por compañía
    warehouse_choices = [("", "")] + [
        (w[0].code, w[0].name)
        for w in database.session.execute(
            database.select(Warehouse).filter_by(is_active=True, company=selected_company)
        ).all()
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
    titulo = _stock_entry_title(_infer_stock_entry_purpose(request.path))
    transaction_config = {
        "formKey": _INVENTORY_STOCK_ENTRY,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _INVENTORY_STOCK_ENTRY),
        "availableSourceTypes": [
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "delivery_note", "label": _("Nota de Entrega")},
        ],
    }
    if request.method == "POST":
        return _handle_stock_entry_new_post(request.form)

    if purpose == "stock_reconciliation":
        return render_template(
            "inventario/stock_reconciliation_nuevo.html",
            form=formulario,
            titulo=titulo,
            items_disponibles=items_disponibles,
            uoms_disponibles=uoms_disponibles,
            transaction_config=transaction_config,
        )
    return render_template(
        "inventario/entrada_nuevo.html",
        form=formulario,
        titulo=titulo,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        source_api_url=source_api_url,
        source_label=source_label,
        transaction_config=transaction_config,
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
    if path.endswith("/inventory-issue/new"):
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


def _handle_stock_entry_new_post(form_data):
    try:
        posting_date = _parse_date(form_data.get("posting_date"))
        posted_purpose = form_data.get("purpose") or "material_receipt"
        entry = StockEntry(
            purpose=posted_purpose,
            company=form_data.get("company") or None,
            posting_date=posting_date,
            from_warehouse=form_data.get("from_warehouse") or None,
            to_warehouse=form_data.get("to_warehouse") or None,
            adjustment_account_id=form_data.get("adjustment_account_id") or None,
            cost_center_code=form_data.get("cost_center_code") or None,
            unit_code=form_data.get("unit_code") or None,
            project_code=form_data.get("project_code") or None,
            remarks=form_data.get("remarks"),
            docstatus=0,
        )
        database.session.add(entry)
        database.session.flush()
        assign_document_identifier(
            document=entry,
            entity_type="stock_entry",
            posting_date_raw=posting_date,
            naming_series_id=form_data.get("naming_series") or None,
        )
        if posted_purpose == "stock_reconciliation":
            entry.total_amount = _save_stock_reconciliation_items(entry)
        else:
            entry.total_amount = _save_stock_entry_items(entry)
        log_create(entry)
        database.session.commit()
        flash("Entrada de almacén creada correctamente.", "success")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry.id))
    except IdentifierConfigurationError as exc:
        database.session.rollback()
        flash(str(exc), "danger")


@inventario.route("/stock-entry/adjustment/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_nuevo():
    """Alias para crear ajuste de inventario."""
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="stock_adjustment"))


@inventario.route("/stock-entry/reconciliation/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_reconciliacion_nueva():
    """Alias para crear conciliación física de inventario."""
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="stock_reconciliation"))


@inventario.route("/stock-entry/adjustment-positive/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_ajuste_positivo_nuevo():
    """Alias para crear ajuste positivo."""
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="adjustment_positive"))


@inventario.route("/stock-entry/inventory-issue/new-shortcut")
@modulo_activo("inventory")
@login_required
def inventario_salida_inventario_nuevo():
    """Alias para crear salida de inventario."""
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA_NUEVO, purpose="adjustment_negative"))


def _source_context(source_type: str | None, source_id: str | None) -> tuple[str | None, str]:
    """Build the source document api context for pre-filling inventory lines."""
    if not source_type or not source_id:
        return None, _LABEL_DOCUMENTO_ORIGEN
    if source_type == "purchase_receipt":
        return f"/api/buying/purchase-receipt/{source_id}/items", "recepción de compra"
    if source_type == "delivery_note":
        return f"/api/sales/delivery-note/{source_id}/items", "nota de entrega"
    if source_type == "stock_entry":
        return f"/api/inventory/stock-entry/{source_id}/items", "movimiento de inventario"
    return None, _LABEL_DOCUMENTO_ORIGEN


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
    return render_template(
        "inventario/entrada.html",
        registro=registro,
        items=items,
        titulo=titulo,
        audit_timeline=format_document_timeline("stock_entry", registro.id),
    )


@inventario.route("/stock-entry/<entry_id>/edit", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_editar(entry_id: str):
    """Edita un movimiento de inventario en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioEntradaAlmacen(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("stock_entry", selected_company)
    # INV-03: Filtrar bodegas por compañía
    warehouse_choices = [("", "")] + [
        (w[0].code, w[0].name)
        for w in database.session.execute(
            database.select(Warehouse).filter_by(is_active=True, company=selected_company)
        ).all()
    ]
    formulario.from_warehouse.choices = warehouse_choices
    formulario.to_warehouse.choices = warehouse_choices
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]

    if request.method == "POST":
        return _handle_stock_entry_edit_post(registro)

    return _render_stock_entry_edit_form(registro, items_disponibles, uoms_disponibles)


def _handle_stock_entry_edit_post(registro: StockEntry):
    """Procesa el POST para editar entrada de inventario."""
    before_state = _capture_stock_entry_state(registro)
    _update_stock_entry_from_form(registro)
    _delete_and_resave_stock_entry_items(registro)
    after_state = _capture_stock_entry_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Movimiento de inventario actualizado correctamente."), "success")
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=registro.id))


def _capture_stock_entry_state(registro: StockEntry) -> dict:
    """Captura el estado del registro antes/después de la edición."""
    return {
        "purpose": registro.purpose,
        "company": registro.company,
        "posting_date": str(registro.posting_date or ""),
        "remarks": registro.remarks or "",
    }


def _update_stock_entry_from_form(registro: StockEntry) -> None:
    """Actualiza campos del registro desde el formulario."""
    registro.purpose = request.form.get("purpose") or registro.purpose
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.from_warehouse = request.form.get("from_warehouse") or None
    registro.to_warehouse = request.form.get("to_warehouse") or None
    registro.remarks = request.form.get("remarks")


def _delete_and_resave_stock_entry_items(registro: StockEntry) -> None:
    """Elimina y recrea los items de la entrada de inventario."""
    # INV-05: Limpiar relaciones documentales huérfanas antes de recrear items
    for rel in database.session.execute(
        database.select(DocumentRelation).filter_by(target_type="stock_entry", target_id=registro.id)
    ).scalars():
        database.session.delete(rel)
    for item in database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars():
        database.session.delete(item)
    registro.total_amount = _save_stock_entry_items(registro)


def _render_stock_entry_edit_form(
    registro: StockEntry,
    items_disponibles: list,
    uoms_disponibles: list,
):
    """Renderiza el formulario de edición de entrada de inventario."""
    from cacao_accounting.form_preferences import get_column_preferences
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    formulario = FormularioEntradaAlmacen(obj=registro)

    lineas = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _INVENTORY_STOCK_ENTRY,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "columns": get_column_preferences(current_user.id, _INVENTORY_STOCK_ENTRY),
        "availableSourceTypes": [
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "delivery_note", "label": _("Nota de Entrega")},
        ],
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
                "rate": str(item.basic_rate or 0),
                "amount": str(item.amount or 0),
            }
            for item in lineas
        ],
    }
    titulo = _stock_entry_title(registro.purpose)
    return render_template(
        "inventario/entrada_nuevo.html",
        form=formulario,
        titulo=titulo,
        edit=True,
        registro=registro,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        source_api_url=None,
        source_label=_LABEL_DOCUMENTO_ORIGEN,
        transaction_config=transaction_config,
    )


@inventario.route("/stock-entry/<entry_id>/duplicate", methods=["POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_duplicar(entry_id: str):
    """Duplica un movimiento de inventario como borrador nuevo."""
    origen = database.session.get(StockEntry, entry_id)
    if not origen:
        abort(404)
    if origen.docstatus == 2:
        abort(400)

    duplicado = StockEntry(
        purpose=origen.purpose,
        company=origen.company,
        posting_date=origen.posting_date,
        from_warehouse=origen.from_warehouse,
        to_warehouse=origen.to_warehouse,
        remarks=origen.remarks,
        docstatus=0,
    )
    database.session.add(duplicado)
    database.session.flush()
    assign_document_identifier(
        document=duplicado,
        entity_type="stock_entry",
        posting_date_raw=duplicado.posting_date,
        naming_series_id=None,
    )
    total = Decimal("0")
    for item in database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=origen.id)).scalars():
        linea = StockEntryItem(
            stock_entry_id=duplicado.id,
            item_code=item.item_code,
            source_warehouse=item.source_warehouse,
            target_warehouse=item.target_warehouse,
            qty=item.qty,
            uom=item.uom,
            basic_rate=item.basic_rate,
            amount=item.amount,
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicado.total_amount = total
    database.session.commit()
    flash(_("Movimiento de inventario duplicado como nuevo borrador."), "success")
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=duplicado.id))


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
        items = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars().all()
        validate_submit_prerequisites(registro, items=items, require_party=False)
        submit_document(registro)
        log_submit(registro)
        database.session.commit()
    except (PostingError, ValueError) as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
    flash(_("Entrada de almacen aprobada y contabilizada."), "success")
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))


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
        log_cancel(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
    flash(_("Entrada de almacen cancelada con reverso contable."), "warning")
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
