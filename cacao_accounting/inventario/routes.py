"""Modulo de Inventarios."""

import logging


from decimal import Decimal


from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from flask_login import current_user, login_required

from cacao_accounting.database import (
    Accounts,
    Batch,
    Item,
    ItemCategory,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)


from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document

from cacao_accounting.document_flow import (
    revert_relations_for_target,
    validate_submit_prerequisites,
)

from cacao_accounting.document_flow.status import _

from cacao_accounting.document_identifiers import assign_document_identifier

from cacao_accounting.decorators import exige_acceso_compania, modulo_activo, verifica_permiso
from cacao_accounting.runtime_mode import is_cloud_mode

from cacao_accounting.list_filters import apply_list_filters

from cacao_accounting.version import APPNAME

from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_create, log_submit

from cacao_accounting.inventario.service import (
    InventoryServiceError,
    BatchParams,
    batch_balance_rows,
    create_batch,
    create_item_with_uoms,
    list_item_account_rows,
    list_item_uom_conversions,
)

from cacao_accounting.inventario.services import (
    _inventory_company_scoped_select,
    _paginate_list,
    _series_choices,
    _item_params_from_form,
    _lote_item_choices,
    _process_item_edit,
    _uom_choices,
    _item_uom_rows_for_template,
    _company_choices,
    _account_choices,
    _cost_center_choices,
    _item_account_rows_for_template,
    _item_category_choices,
    _currency_choices,
    _warehouse_company_rows_for_template,
    _validate_warehouse_company_rows,
    _save_warehouse_company_rows,
    _infer_stock_entry_purpose,
    _stock_entry_title,
    _handle_stock_entry_new_post,
    _source_context,
    _handle_stock_entry_edit_post,
    _render_stock_entry_edit_form,
    _render_stock_reconciliation_edit_form,
)

logger = logging.getLogger(__name__)

inventario = Blueprint("inventario", __name__, template_folder="templates")

INVENTARIO_INVENTARIO_ENTRADA_NUEVO = "inventario.inventario_entrada_nuevo"

INVENTARIO_ENTRADA_LISTA_HTML = "inventario/entrada_lista.html"

INVENTARIO_INVENTARIO_ENTRADA = "inventario.inventario_entrada"

_INVENTORY_STOCK_ENTRY = "inventory.stock_entry"

_LABEL_DOCUMENTO_ORIGEN = "documento origen"


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
        _inventory_company_scoped_select(Warehouse),
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
    consulta = _paginate_list(StockEntry, (StockEntry.document_no,))
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
    consulta = _paginate_list(
        StockEntry,
        (StockEntry.document_no,),
        _inventory_company_scoped_select(StockEntry).filter_by(purpose="material_receipt"),
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
    consulta = _paginate_list(
        StockEntry, (StockEntry.document_no,), _inventory_company_scoped_select(StockEntry).filter_by(purpose="material_issue")
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
    consulta = _paginate_list(
        StockEntry,
        (StockEntry.document_no,),
        _inventory_company_scoped_select(StockEntry).filter_by(purpose="material_transfer"),
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
    consulta = _paginate_list(
        StockEntry,
        (StockEntry.document_no,),
        _inventory_company_scoped_select(StockEntry).filter_by(purpose="stock_adjustment"),
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
    consulta = _paginate_list(
        StockEntry,
        (StockEntry.document_no,),
        _inventory_company_scoped_select(StockEntry).filter_by(purpose="stock_reconciliation"),
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
    consulta = _paginate_list(
        StockEntry,
        (StockEntry.document_no,),
        _inventory_company_scoped_select(StockEntry).filter_by(purpose="adjustment_positive"),
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
    consulta = _paginate_list(
        StockEntry,
        (StockEntry.document_no,),
        _inventory_company_scoped_select(StockEntry).filter_by(purpose="adjustment_negative"),
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
@verifica_permiso("inventory", "crear")
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
                params = _item_params_from_form(request.form)
                item = create_item_with_uoms(params)
                image_file = request.files.get("image") or request.files.get("product_image") or request.files.get("file")
                if image_file and image_file.filename and is_cloud_mode():
                    try:
                        from cacao_accounting.attachment_service import upload_item_image

                        upload_item_image(item.code, image_file, user_id=str(current_user.id))
                    except Exception as exc:
                        flash(f"Imagen no subida: {exc}", "warning")
                database.session.commit()
                return redirect("/inventory/item/list")
            except InventoryServiceError as exc:
                database.session.rollback()
                flash_error(exc)
            except ValueError as exc:
                database.session.rollback()
                flash_error(exc)
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
@verifica_permiso("inventory", "editar")
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
        response = _process_item_edit(item, formulario)
        if response is not None:
            return response

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
@verifica_permiso("inventory", "crear")
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
@verifica_permiso("inventory", "crear")
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
            for row in company_rows:
                exige_acceso_compania("inventory", row["company"], "crear")
        except ValueError as exc:
            flash_error(exc)
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


@inventario.route("/warehouse/<warehouse_id>")
@modulo_activo("inventory")
@login_required
def inventario_bodega(warehouse_id):
    """Detalle de bodega."""
    from flask import abort

    registro = database.session.execute(database.select(Warehouse).filter_by(code=warehouse_id)).first()
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro[0].company, "consultar")
    titulo = registro[0].name + " - " + APPNAME
    company_accounts = (
        database.session.execute(
            _inventory_company_scoped_select(WarehouseCompanyAccount)
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


@inventario.route("/batch/list")
@modulo_activo("inventory")
@login_required
def inventario_lote_lista():
    """Listado de lotes de inventario."""
    consulta = database.paginate(
        apply_list_filters(
            database.select(Batch),
            Batch,
            (Batch.batch_no, Batch.item_code),
            include_status=False,
        ),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Lotes - " + APPNAME
    return render_template("inventario/lote_lista.html", consulta=consulta, titulo=titulo)


@inventario.route("/batch/new", methods=["GET", "POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "crear")
def inventario_lote_nuevo():
    """Formulario para crear un lote de inventario."""
    from cacao_accounting.inventario.forms import FormularioLote

    formulario = FormularioLote()
    formulario.item_code.choices = _lote_item_choices()
    titulo = "Nuevo Lote - " + APPNAME
    if request.method == "POST":
        if formulario.validate():
            try:
                lote = create_batch(
                    BatchParams(
                        item_code=formulario.item_code.data,
                        batch_no=formulario.batch_no.data or "",
                        expiry_date=formulario.expiry_date.data,
                        manufacturing_date=formulario.manufacturing_date.data,
                        description=formulario.description.data or None,
                        is_active=formulario.is_active.data,
                    )
                )
                log_create(lote)
                database.session.commit()
                flash(_("Lote creado correctamente."), "success")
                return redirect(url_for("inventario.inventario_lote", batch_id=lote.id))
            except InventoryServiceError as exc:
                database.session.rollback()
                flash_error(exc)
        else:
            flash(_("Revise los datos del formulario de lote."), "danger")
    return render_template("inventario/lote_nuevo.html", form=formulario, titulo=titulo)


@inventario.route("/batch/<batch_id>")
@modulo_activo("inventory")
@login_required
def inventario_lote(batch_id):
    """Detalle de lote con saldo por bodega y movimientos."""
    registro = database.session.get(Batch, batch_id)
    if not registro:
        abort(404)
    item = database.session.execute(database.select(Item).filter_by(code=registro.item_code)).scalars().first()
    balances = batch_balance_rows(registro.id)
    movimientos = (
        database.session.execute(
            database.select(StockLedgerEntry)
            .filter_by(batch_id=registro.id)
            .order_by(StockLedgerEntry.posting_date.desc(), StockLedgerEntry.created.desc(), StockLedgerEntry.id.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    titulo = (registro.batch_no or "") + " - " + APPNAME
    return render_template(
        "inventario/lote.html",
        registro=registro,
        item=item,
        balances=balances,
        movimientos=movimientos,
        titulo=titulo,
    )


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
@verifica_permiso("inventory", "crear")
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
    # INV-03: Filtrar bodegas por compañía
    warehouse_choices = [("", "")] + [
        (w[0].code, w[0].name)
        for w in database.session.execute(database.select(Warehouse).filter_by(is_active=True, company=selected_company)).all()
    ]
    formulario.from_warehouse.choices = warehouse_choices
    formulario.to_warehouse.choices = warehouse_choices
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
    purpose = request.args.get("purpose") or _infer_stock_entry_purpose(request.path)
    formulario.purpose.data = purpose or formulario.purpose.data
    source_api_url, source_label = _source_context(request.args.get("source_type"), request.args.get("source_id"))
    titulo = _stock_entry_title(_infer_stock_entry_purpose(request.path))
    transaction_config = {
        "formKey": _INVENTORY_STOCK_ENTRY,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "initialSourceType": request.args.get("source_type") or "",
        "availableSourceTypes": [
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "delivery_note", "label": _("Remisión de Mercadería Vendida")},
        ],
    }
    if request.method == "POST":
        if formulario.validate():
            return _handle_stock_entry_new_post(request.form)
        flash("Revise los datos de la entrada de almacén.", "danger")

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


@inventario.route("/stock-entry/<entry_id>")
@modulo_activo("inventory")
@login_required
def inventario_entrada(entry_id):
    """Detalle de entrada de almacén."""
    from flask import abort

    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "consultar")
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
@verifica_permiso("inventory", "editar")
def inventario_entrada_editar(entry_id: str):
    """Edita un movimiento de inventario en borrador."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "editar")
    from cacao_accounting.approval_engine import ApprovalEngine

    try:
        ApprovalEngine.ensure_document_editable(registro)
    except ValueError:
        abort(409)
    if registro.docstatus != 0:
        abort(400)

    formulario = FormularioEntradaAlmacen(obj=registro)
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or registro.company
    formulario.naming_series.choices = _series_choices("stock_entry", selected_company)
    # INV-03: Filtrar bodegas por compañía
    warehouse_choices = [("", "")] + [
        (w[0].code, w[0].name)
        for w in database.session.execute(database.select(Warehouse).filter_by(is_active=True, company=selected_company)).all()
    ]
    formulario.from_warehouse.choices = warehouse_choices
    formulario.to_warehouse.choices = warehouse_choices
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
        if formulario.validate():
            return _handle_stock_entry_edit_post(registro)
        flash("Revise los datos de la entrada de almacén.", "danger")

    if registro.purpose == "stock_reconciliation":
        return _render_stock_reconciliation_edit_form(registro, items_disponibles, uoms_disponibles)
    return _render_stock_entry_edit_form(registro, items_disponibles, uoms_disponibles)


@inventario.route("/stock-entry/<entry_id>/duplicate", methods=["POST"])
@modulo_activo("inventory")
@login_required
def inventario_entrada_duplicar(entry_id: str):
    """Duplica un movimiento de inventario como borrador nuevo."""
    origen = database.session.get(StockEntry, entry_id)
    if not origen:
        abort(404)
    exige_acceso_compania("inventory", origen.company, "crear")
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
            qty_in_base_uom=item.qty_in_base_uom,
            valuation_rate=item.valuation_rate,
            current_qty=item.current_qty,
            counted_qty=item.counted_qty,
            qty_difference=item.qty_difference,
            current_valuation_rate=item.current_valuation_rate,
            target_valuation_rate=item.target_valuation_rate,
            current_stock_value=item.current_stock_value,
            target_stock_value=item.target_stock_value,
            stock_value_difference=item.stock_value_difference,
            batch_id=item.batch_id,
            serial_no=item.serial_no,
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
@verifica_permiso("inventory", "autorizar")
def inventario_entrada_submit(entry_id: str):
    """Aprueba una entrada de almacen y genera Stock Ledger/GL.

    ``require_party=False`` es intencional: una entrada de stock interna
    puede aprobarse sin proveedor/cliente asignado. El proveedor se asigna
    al recibir desde compra, y el cliente al entregar por venta.
    """
    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        items = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars().all()
        validate_submit_prerequisites(
            registro,
            items=items,
            require_party=False,
            require_warehouse=True,
            require_qty_positive=registro.purpose != "stock_reconciliation",
        )
        from cacao_accounting.inventario.service import validate_batch_serial_draft

        validate_batch_serial_draft(items)
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Movimiento de inventario"):
            return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))

        submit_document(registro)
        log_submit(registro)
        database.session.commit()
    except ValueError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
    flash(_("Entrada de almacen aprobada y contabilizada."), "success")
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))


@inventario.route("/stock-entry/<entry_id>/cancel", methods=["POST"])
@modulo_activo("inventory")
@login_required
@verifica_permiso("inventory", "anular")
def inventario_entrada_cancel(entry_id: str):
    """Cancela una entrada de almacen."""
    registro = database.session.get(StockEntry, entry_id)
    if not registro:
        abort(404)
    exige_acceso_compania("inventory", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash(_("Debe indicar el motivo de la anulación."), "danger")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(
                registro,
                reason=reason,
                cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
            )
            database.session.commit()
            flash(_("Solicitud de cancelación enviada para aprobación (Pendiente de Cancelación)."), "info")
            return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))

        cancel_document(
            registro,
            reason=reason,
            actor_user_id=str(current_user.id),
            cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
        )
        revert_relations_for_target("stock_entry", entry_id)
        log_cancel(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
    flash(_("Entrada de almacen cancelada con reverso contable."), "warning")
    return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=entry_id))
