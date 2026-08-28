"""Modulo de Inventarios."""

import logging

from datetime import date

from decimal import Decimal

from typing import Any, Mapping

from cacao_accounting.exceptions import flash_error

from flask import flash, redirect, render_template, request, url_for

from flask_login import current_user

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

from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.runtime_mode import is_cloud_mode


from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
)

from cacao_accounting.document_flow.status import _

from cacao_accounting.document_flow.context import company_currency

from cacao_accounting.document_identifiers import assign_document_identifier

from cacao_accounting.decorators import exige_acceso_compania

from cacao_accounting.version import APPNAME

from cacao_accounting.audit_trail_service import log_create, log_update

from cacao_accounting.inventario.service import (
    InventoryServiceError,
    ItemParams,
    convert_item_qty,
    parse_item_account_rows,
    parse_item_uom_rows,
    update_item_with_uoms,
)

logger = logging.getLogger(__name__)

INVENTARIO_INVENTARIO_ENTRADA_NUEVO = "inventario.inventario_entrada_nuevo"

INVENTARIO_ENTRADA_LISTA_HTML = "inventario/entrada_lista.html"

INVENTARIO_INVENTARIO_ENTRADA = "inventario.inventario_entrada"

_INVENTORY_STOCK_ENTRY = "inventory.stock_entry"

_LABEL_DOCUMENTO_ORIGEN = "documento origen"

STOCK_ENTRY_PURPOSES = frozenset(
    {
        "material_receipt",
        "material_issue",
        "material_transfer",
        "stock_adjustment",
        "stock_reconciliation",
        "adjustment_positive",
        "adjustment_negative",
    }
)


def _parse_date(value: str | None) -> date | None:
    """Parsea una fecha en formato ISO."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _inventory_company_scoped_select(model: type[Any]):
    """Build an inventory query restricted to assigned companies."""
    permissions = Permisos(
        modulo=obtener_id_modulo_por_nombre("inventory"),
        usuario=current_user.id,
    )
    companies = permissions.obtener_companias_autorizadas() if permissions.consultar else []
    query = database.select(model)
    if not companies:
        return query.where(database.false())
    return query.where(model.company.in_(companies))


def _paginate_list(model: type[Any], search_fields: tuple[Any, ...], query: Any = None, *, include_status: bool = True) -> Any:
    """Pagina un listado de inventario aplicando filtro por período contable."""
    from cacao_accounting.list_filters import (
        apply_list_filters,
        apply_period_filter,
        attach_period_picker,
        require_period_company,
    )

    base_query = query if query is not None else database.select(model)
    if hasattr(model, "company"):
        company = request.args.get("company")
        if company:
            base_query = base_query.filter(model.company == company)
        elif not getattr(current_user, "classification", None) == "admin":
            permissions = Permisos(
                modulo=obtener_id_modulo_por_nombre("inventory"),
                usuario=current_user.id,
            )
            companies = permissions.obtener_companias_autorizadas() if permissions.consultar else []
            if not companies:
                base_query = base_query.where(database.false())
            else:
                base_query = base_query.where(model.company.in_(companies))
    period_from = request.args.get("accounting_period_from") or request.args.get("period_from")
    period_to = request.args.get("accounting_period_to") or request.args.get("period_to")
    if hasattr(model, "posting_date"):
        period_company: str | None = request.args.get("company")
        if not period_company and getattr(current_user, "classification", None) != "admin":
            permissions = Permisos(
                modulo=obtener_id_modulo_por_nombre("inventory"),
                usuario=current_user.id,
            )
            if permissions.consultar:
                authorized_companies: list[str] = list(permissions.obtener_companias_autorizadas())
                if len(authorized_companies) == 1:
                    period_company = authorized_companies[0]
        if period_from or period_to or period_company:
            base_query = apply_period_filter(
                base_query,
                model,
                require_period_company(("inventory",), current_user=current_user, default_company=period_company),
                period_from,
                period_to,
                default_when_missing=True,
            )
    filtered_query = apply_list_filters(base_query, model, search_fields, include_status=include_status)
    paginated = database.paginate(
        filtered_query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    attach_period_picker(paginated, model, "inventory", current_user=current_user)
    return paginated


def _inventory_writable_company_select():
    """Build a query for companies with inventory write access."""
    permissions = Permisos(
        modulo=obtener_id_modulo_por_nombre("inventory"),
        usuario=current_user.id,
    )
    companies = permissions.obtener_companias_autorizadas() if permissions.crear else []
    if not companies:
        return database.select(Entity.code).where(database.false())
    return database.select(Entity.code).where(Entity.code.in_(companies), Entity.enabled.is_(True))


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return []

    return [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


def _item_params_from_form(form) -> ItemParams:
    """Construye ItemParams desde los datos del formulario."""

    def text(name: str, default: str = "") -> str:
        """Obtiene y normaliza un texto del formulario."""
        return str(form.get(name) or default).strip()

    def optional_text(name: str) -> str | None:
        """Obtiene un texto opcional del formulario."""
        return text(name) or None

    def checked(name: str) -> bool:
        """Indica si el checkbox del formulario fue enviado."""
        return form.get(name) is not None

    return ItemParams(
        name=text("name"),
        description=optional_text("description"),
        item_type=text("item_type", "goods"),
        is_stock_item=checked("is_stock_item"),
        is_purchase_item=checked("is_purchase_item"),
        is_sale_item=checked("is_sale_item"),
        item_category_id=optional_text("item_category_id"),
        default_uom=text("default_uom"),
        purchase_uom=optional_text("purchase_uom"),
        sale_uom=optional_text("sale_uom"),
        default_warehouse_id=optional_text("default_warehouse_id"),
        default_supplier_id=optional_text("default_supplier_id"),
        allow_negative_stock=checked("allow_negative_stock"),
        min_stock_qty=_form_decimal("min_stock_qty"),
        max_stock_qty=_form_decimal("max_stock_qty"),
        reorder_level=_form_decimal("reorder_level"),
        standard_rate=_form_decimal("standard_rate"),
        last_purchase_rate=_form_decimal("last_purchase_rate"),
        currency=optional_text("currency"),
        brand=optional_text("brand"),
        model_name=optional_text("model_name"),
        barcode=optional_text("barcode"),
        has_batch=checked("has_batch"),
        has_serial_no=checked("has_serial_no"),
        has_expiry_date=checked("has_expiry_date"),
        uom_rows=parse_item_uom_rows(form),
        account_rows=parse_item_account_rows(form),
    )


def _process_item_edit(item, formulario):
    """Procesa el POST de edición de un artículo."""
    if not formulario.validate():
        flash("Revise los datos del formulario de artículo.", "danger")
        return None
    try:
        update_item_with_uoms(item_code=item.code, params=_item_params_from_form(request.form))
        image_file = request.files.get("image") or request.files.get("product_image") or request.files.get("file")
        if image_file and image_file.filename and is_cloud_mode():
            try:
                from cacao_accounting.attachment_service import upload_item_image
                from flask_login import current_user

                upload_item_image(item.code, image_file, user_id=getattr(current_user, "id", None))
            except Exception as exc:
                flash(f"Imagen no actualizada: {exc}", "warning")
        database.session.commit()
        flash("Artículo actualizado correctamente.", "success")
        return redirect(url_for("inventario.inventario_articulo", item_id=item.code))
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return None


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
    entities = (
        database.session.execute(
            database.select(Entity).where(Entity.code.in_(_inventory_writable_company_select())).order_by(Entity.code)
        )
        .scalars()
        .all()
    )
    return [("", "")] + [(entity.code, entity.name) for entity in entities]


def _account_choices() -> list[dict[str, str]]:
    """Devuelve cuentas activas para la tabla contable del item."""
    accounts = (
        database.session.execute(
            database.select(Accounts)
            .filter_by(active=True, enabled=True, group=False)
            .where(Accounts.entity.in_(_inventory_writable_company_select()))
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
            .where(CostCenter.entity.in_(_inventory_writable_company_select()))
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


def _form_decimal(field_name: str, default: str = "0") -> Decimal:
    """Convierte un valor de formulario a Decimal."""
    value = request.form.get(field_name)
    return Decimal(str(value if value not in (None, "") else default))


def _line_amount(index: int) -> Decimal:
    """Calcula el monto de una línea con datos confiables del servidor."""
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


def _save_stock_entry_item(entry: StockEntry, index: int, item_code: str) -> Decimal:
    """Create one stock movement line and its source relation."""
    _validate_stock_entry_warehouses(entry)
    qty = _form_decimal(f"qty_{index}", "1")
    rate = _form_decimal(f"rate_{index}", "0")
    amount = _line_amount(index)
    default_uom = _item_default_uom(item_code)
    uom = request.form.get(f"uom_{index}") or default_uom
    if not uom:
        raise ValueError(f"La linea del item {item_code} requiere una unidad de medida.")
    qty_in_base_uom = qty
    if uom and default_uom:
        try:
            qty_in_base_uom = convert_item_qty(item_code, qty, uom, default_uom)
        except InventoryServiceError as exc:
            raise ValueError(f"No se pudo convertir {qty} {uom} a {default_uom} para el item {item_code}.") from exc
    line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code=item_code,
        source_warehouse=entry.from_warehouse,
        target_warehouse=entry.to_warehouse,
        qty=qty,
        uom=uom,
        qty_in_base_uom=qty_in_base_uom,
        basic_rate=rate,
        amount=amount,
        batch_id=request.form.get(f"batch_id_{index}") or None,
        serial_no=request.form.get(f"serial_no_{index}") or None,
    )
    database.session.add(line)
    database.session.flush()
    _create_line_relation(index, "stock_entry", entry.id, line.id, qty, uom, rate, amount)
    return amount


def _save_stock_entry_items(entry: StockEntry) -> Decimal:
    """Guarda lineas de un movimiento de inventario."""
    i = 0
    total = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            total += _save_stock_entry_item(entry, i, item_code)
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError("El documento requiere al menos una línea.", 400)
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


def _save_stock_reconciliation_item(entry: StockEntry, index: int, item_code: str, warehouse: str) -> Decimal:
    """Create one reconciliation line from the locked stock snapshot."""
    _validate_stock_entry_warehouses(entry, warehouse)
    current_qty, current_rate, current_value, _reserved_qty = _stock_bin_snapshot(entry.company, item_code, warehouse)
    uom = request.form.get(f"uom_{index}") or _item_default_uom(item_code)
    if not uom:
        raise ValueError(f"La conciliacion del item {item_code} requiere una unidad de medida.")
    default_uom = _item_default_uom(item_code)
    if not default_uom:
        raise ValueError(f"El item {item_code} requiere una UOM base configurada.")
    counted_qty = _form_decimal(f"counted_qty_{index}", str(current_qty))
    if uom != default_uom:
        try:
            counted_qty = convert_item_qty(item_code, counted_qty, uom, default_uom)
        except InventoryServiceError as exc:
            raise ValueError(f"No se pudo convertir {counted_qty} {uom} a {default_uom} para el item {item_code}.") from exc
    target_rate = _form_decimal(f"target_valuation_rate_{index}", str(current_rate))
    target_value = _form_decimal(f"target_stock_value_{index}", str(counted_qty * target_rate))
    qty_difference = counted_qty - current_qty
    value_difference = target_value - current_value
    base_qty = abs(qty_difference)
    line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code=item_code,
        source_warehouse=warehouse,
        target_warehouse=warehouse,
        qty=base_qty,
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
    return abs(value_difference)


def _save_stock_reconciliation_items(entry: StockEntry) -> Decimal:
    """Guarda lineas de conciliacion con snapshot de cantidad y valuacion."""
    i = 0
    total_difference = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "").strip()
        warehouse = request.form.get(f"warehouse_{i}") or entry.to_warehouse or entry.from_warehouse
        if item_code:
            total_difference += _save_stock_reconciliation_item(entry, i, item_code, warehouse)
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError("El documento requiere al menos una línea.", 400)
    return total_difference


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


def _validate_stock_entry_warehouses(entry: StockEntry, *line_warehouses: str | None) -> None:
    """Validate draft warehouses against the entry company and active state.

    Posting repeats this validation, but draft persistence must reject invalid
    cross-company references before they can be stored or displayed.
    """
    warehouse_codes = {
        entry.from_warehouse,
        entry.to_warehouse,
        *line_warehouses,
    }
    for warehouse_code in filter(None, warehouse_codes):
        warehouse = database.session.execute(database.select(Warehouse).filter_by(code=warehouse_code)).scalar_one_or_none()
        if not warehouse or warehouse.company != entry.company:
            raise ValueError(f"La bodega {warehouse_code} no pertenece a la compañía {entry.company}.")
        if not warehouse.is_active:
            raise ValueError(f"La bodega {warehouse_code} está inactiva.")


def _validate_stock_entry_posting_date(form_data: Mapping[str, Any]) -> date:
    """Validate and return the posting date before saving a stock entry draft."""
    posting_date_raw = form_data.get("posting_date")
    posting_date = _parse_date(str(posting_date_raw).strip() if posting_date_raw is not None else "")
    if posting_date is None:
        raise ValueError("La fecha de contabilización es obligatoria y debe tener formato YYYY-MM-DD.")
    return posting_date


def _validate_stock_entry_purpose(value: Any) -> str:
    """Validate the accounting treatment selected for a stock entry."""
    purpose = str(value or "").strip()
    if purpose not in STOCK_ENTRY_PURPOSES:
        raise ValueError("El propósito de la entrada de almacén no es válido.")
    return purpose


def _validate_stock_entry_company(value: Any, action: str) -> str:
    """Validate company presence and the user's inventory ACL."""
    company = str(value or "").strip()
    if not company:
        raise ValueError("La compañía es obligatoria.")
    exige_acceso_compania("inventory", company, action)
    return company


def _handle_stock_entry_new_post(form_data: Mapping[str, Any]):
    try:
        posting_date = _validate_stock_entry_posting_date(form_data)
        posted_purpose = _validate_stock_entry_purpose(form_data.get("purpose") or "material_receipt")
        company = _validate_stock_entry_company(form_data.get("company"), "crear")
        entry = StockEntry(
            purpose=posted_purpose,
            company=company,
            posting_date=posting_date,
            from_warehouse=form_data.get("from_warehouse") or None,
            to_warehouse=form_data.get("to_warehouse") or None,
            adjustment_account_id=form_data.get("adjustment_account_id") or None,
            cost_center_code=form_data.get("cost_center_code") or None,
            unit_code=form_data.get("unit_code") or None,
            project_code=form_data.get("project_code") or None,
            remarks=form_data.get("remarks"),
            transaction_currency=company_currency(company),
            base_currency=company_currency(company),
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
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)


def _source_context(source_type: str | None, source_id: str | None) -> tuple[str | None, str]:
    """Build the source document api context for pre-filling inventory lines."""
    if not source_type or not source_id:
        return None, _LABEL_DOCUMENTO_ORIGEN
    if source_type == "purchase_receipt":
        return f"/api/buying/purchase-receipt/{source_id}/items", "recepción de compra"
    if source_type == "delivery_note":
        return f"/api/sales/delivery-note/{source_id}/items", "remisión de mercadería vendida"
    if source_type == "stock_entry":
        return f"/api/inventory/stock-entry/{source_id}/items", "movimiento de inventario"
    return None, _LABEL_DOCUMENTO_ORIGEN


def _handle_stock_entry_edit_post(registro: StockEntry):
    """Procesa el POST para editar entrada de inventario."""
    try:
        before_state = _capture_stock_entry_state(registro)
        _update_stock_entry_from_form(registro)
        _delete_and_resave_stock_entry_items(registro)
        after_state = _capture_stock_entry_state(registro)
        log_update(registro, before=before_state, after=after_state)
        database.session.commit()
        flash(_("Movimiento de inventario actualizado correctamente."), "success")
        return redirect(url_for(INVENTARIO_INVENTARIO_ENTRADA, entry_id=registro.id))
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)


def _capture_stock_entry_state(registro: StockEntry) -> dict:
    """Captura el estado del registro antes/después de la edición."""
    state = {
        "purpose": registro.purpose,
        "company": registro.company,
        "posting_date": str(registro.posting_date or ""),
        "remarks": registro.remarks or "",
    }

    from cacao_accounting.audit_trail_service import capture_lines_snapshot

    state["items"] = capture_lines_snapshot(registro, StockEntryItem, "stock_entry_id")

    return state


def _update_stock_entry_from_form(registro: StockEntry) -> None:
    """Actualiza campos del registro desde el formulario."""
    purpose = _validate_stock_entry_purpose(request.form.get("purpose") or registro.purpose)
    company = _validate_stock_entry_company(request.form.get("company"), "editar")
    if purpose != registro.purpose:
        raise ValueError("No se puede cambiar el propósito de una entrada de almacén existente.")
    if company != registro.company:
        raise ValueError("No se puede cambiar la compañía de una entrada de almacén existente.")
    registro.purpose = purpose
    registro.company = company
    registro.posting_date = _validate_stock_entry_posting_date(request.form)
    registro.from_warehouse = request.form.get("from_warehouse") or None
    registro.to_warehouse = request.form.get("to_warehouse") or None
    registro.adjustment_account_id = request.form.get("adjustment_account_id") or None
    registro.cost_center_code = request.form.get("cost_center_code") or None
    registro.unit_code = request.form.get("unit_code") or None
    registro.project_code = request.form.get("project_code") or None
    registro.remarks = request.form.get("remarks")
    registro.transaction_currency = registro.transaction_currency or company_currency(company)
    registro.base_currency = company_currency(company)


def _delete_and_resave_stock_entry_items(registro: StockEntry) -> None:
    """Elimina y recrea los items de la entrada de inventario.

    Primero elimina las relaciones documentales existentes (lineas 1229-1232),
    luego los items (linea 1233-1234), y finalmente recrea todo via
    ``_save_stock_entry_items`` que tambien recrea las relaciones.
    Este patron de delete-then-resave es intencional para mantener
    consistencia entre items y relaciones documentales en ediciones.
    """
    # INV-05: Limpiar relaciones documentales huérfanas antes de recrear items
    for rel in database.session.execute(
        database.select(DocumentRelation).filter_by(target_type="stock_entry", target_id=registro.id)
    ).scalars():
        database.session.delete(rel)
    for item in database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars():
        database.session.delete(item)
    if registro.purpose == "stock_reconciliation":
        registro.total_amount = _save_stock_reconciliation_items(registro)
    else:
        registro.total_amount = _save_stock_entry_items(registro)


def _render_stock_entry_edit_form(
    registro: StockEntry,
    items_disponibles: list,
    uoms_disponibles: list,
):
    """Renderiza el formulario de edición de entrada de inventario."""
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    formulario = FormularioEntradaAlmacen(obj=registro)

    lineas = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars()
    transaction_config = {
        "formKey": _INVENTORY_STOCK_ENTRY,
        "viewKey": "draft",
        "enableBatchSerial": True,
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "availableSourceTypes": [
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "delivery_note", "label": _("Remisión de Mercadería Vendida")},
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
                "batch_id": item.batch_id or "",
                "serial_no": item.serial_no or "",
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


def _render_stock_reconciliation_edit_form(
    registro: StockEntry,
    items_disponibles: list,
    uoms_disponibles: list,
):
    """Renderiza el formulario específico para editar una conciliación."""
    from cacao_accounting.inventario.forms import FormularioEntradaAlmacen

    formulario = FormularioEntradaAlmacen(obj=registro)
    lineas = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=registro.id)).scalars()
    reconciliation_config = {
        "header": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "adjustment_account_id": registro.adjustment_account_id or "",
            "cost_center_code": registro.cost_center_code or "",
            "unit_code": registro.unit_code or "",
            "project_code": registro.project_code or "",
            "remarks": registro.remarks or "",
        },
        "lines": [
            {
                "item_code": line.item_code,
                "warehouse": line.target_warehouse or line.source_warehouse or "",
                "uom": line.uom or "",
                "current_qty": str(line.current_qty or 0),
                "counted_qty": str(line.counted_qty or 0),
                "current_valuation_rate": str(line.current_valuation_rate or 0),
                "target_valuation_rate": str(line.target_valuation_rate or 0),
                "current_stock_value": str(line.current_stock_value or 0),
                "target_stock_value": str(line.target_stock_value or 0),
            }
            for line in lineas
        ],
    }
    return render_template(
        "inventario/stock_reconciliation_nuevo.html",
        form=formulario,
        titulo="Editar Conciliación de Inventario - " + APPNAME,
        items_disponibles=items_disponibles,
        uoms_disponibles=uoms_disponibles,
        reconciliation_config=reconciliation_config,
        edit=True,
        registro=registro,
    )
