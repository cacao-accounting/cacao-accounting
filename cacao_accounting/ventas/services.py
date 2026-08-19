"""Modulo de Ventas."""

from datetime import date

from decimal import Decimal

from typing import Any, Sequence

from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from flask_login import current_user

from cacao_accounting.database import (
    Book,
    CompanyParty,
    DeliveryNote,
    DeliveryNoteItem,
    DocumentRelation,
    Item,
    ItemPrice,
    Party,
    PriceList,
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

from sqlalchemy import or_

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ulid import ULID

from cacao_accounting.database.helpers import get_active_naming_series

from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document

from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier

from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
    refresh_source_caches_for_target,
    require_line_relations,
    revert_relations_for_target,
)

from cacao_accounting.document_flow.context import company_currency, effective_currency, validate_immutable_header

from cacao_accounting.document_flow.repository import consumed_qty_for_source

from cacao_accounting.document_flow.status import _

from cacao_accounting.decorators import (  # noqa: F401
    exige_acceso_compania,
    exige_acceso_compania_cualquiera,
    modulo_activo,
    verifica_acceso as verifica_acceso,
    verifica_permiso,
)

from cacao_accounting.auth.permisos import Permisos

from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

from cacao_accounting.fiscal_persistence_service import (
    calculate_document_total_with_taxes,
    persist_document_fiscal_snapshot,
)

from cacao_accounting.inventario.service import InventoryServiceError, convert_item_qty

from cacao_accounting.list_filters import apply_list_filters

from cacao_accounting.party_settings import (
    draft_party_company_settings_rows,
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


from cacao_accounting.audit_trail_service import log_cancel, log_submit, log_update

from cacao_accounting.logistics import copy_logistics, logistics_values

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

DOCUMENT_REQUIRES_LINE_MSG = "El documento requiere al menos una línea."

SOLICITUD_CANCELACION_PENDIENTE_MSG = "Solicitud de cancelación enviada para aprobación (Pendiente de Cancelación)."


def _sales_logistics_values(source: Any = None, form: Any = None) -> dict[str, Any]:
    """Obtiene los datos logísticos comerciales desde un origen o formulario."""
    return logistics_values(source, form, terms_field="sales_terms")


def _copy_sales_logistics(target: Any, source: Any = None, form: Any = None) -> None:
    """Copia el snapshot logístico al documento comercial destino."""
    copy_logistics(target, source, form, terms_field="sales_terms")


def _sales_exchange_rate(company: str | None, posting_date: Any, transaction_currency: str | None) -> Decimal:
    """Resuelve la tasa de conversión de moneda transaccional a funcional."""
    rate = Decimal("1")
    base_currency = company_currency(company)
    if not company or not transaction_currency or not base_currency or transaction_currency == base_currency:
        return rate
    from cacao_accounting.contabilidad.posting import _lookup_exchange_rate

    # Una tasa faltante debe impedir el posting: usar 1:1 altera el libro
    # funcional y oculta una configuración cambiaria incompleta.
    exchange_rate = _lookup_exchange_rate(transaction_currency, base_currency, posting_date)
    if exchange_rate is None or Decimal(str(exchange_rate)) <= 0:
        raise ValueError(f"No existe tipo de cambio para {transaction_currency} -> {base_currency} en {posting_date}.")
    return Decimal(str(exchange_rate))


def _set_sales_document_totals(document: Any, total: Decimal) -> None:
    """Calcula totales funcionales de un documento comercial de ventas."""
    transaction_currency = getattr(document, "transaction_currency", None) or company_currency(document.company)
    document.transaction_currency = transaction_currency
    document.base_currency = company_currency(document.company)
    document.exchange_rate = _sales_exchange_rate(document.company, document.posting_date, transaction_currency)
    document.total = total
    document.base_total = (total * document.exchange_rate).quantize(Decimal("0.0001"))
    document.grand_total = total
    if hasattr(document, "base_grand_total"):
        document.base_grand_total = document.base_total


def _sales_invoice_currency_and_rate(
    company: str | None, posting_date: Any, source: Any | None, requested_currency: str | None
) -> tuple[str | None, str | None, Decimal]:
    """Resuelve moneda, moneda funcional y tasa, conservando la tasa del origen."""
    source_currency = effective_currency(source)
    transaction_currency = source_currency or requested_currency
    base_currency = company_currency(company)
    if source is not None and source_currency == transaction_currency and getattr(source, "exchange_rate", None):
        exchange_rate = Decimal(str(source.exchange_rate))
    else:
        exchange_rate = _sales_exchange_rate(company, posting_date, transaction_currency)
    return transaction_currency, base_currency, exchange_rate


def _set_sales_invoice_totals(invoice: SalesInvoice, total: Decimal, grand_total: Decimal, source: Any | None = None) -> None:
    """Recalcula importes transaccionales y funcionales de una factura de venta."""
    requested_currency = getattr(invoice, "transaction_currency", None)
    transaction_currency, base_currency, exchange_rate = _sales_invoice_currency_and_rate(
        invoice.company, invoice.posting_date, source, requested_currency
    )
    invoice.transaction_currency = transaction_currency
    invoice.base_currency = base_currency
    invoice.exchange_rate = exchange_rate
    invoice.total = total
    invoice.base_total = (total * exchange_rate).quantize(Decimal("0.0001"))
    invoice.grand_total = grand_total
    invoice.base_grand_total = (grand_total * exchange_rate).quantize(Decimal("0.0001"))
    invoice.outstanding_amount = grand_total
    invoice.base_outstanding_amount = invoice.base_grand_total


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


def _stock_bin_or_create(company: str, item_code: str, warehouse: str, for_update: bool = False) -> StockBin:
    """Obtiene o crea un StockBin para item/almacen/compania."""
    query = database.select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse)
    if for_update:
        query = query.with_for_update()
    bin_row = database.session.execute(query).scalar_one_or_none()
    if not bin_row:
        try:
            with database.session.begin_nested():
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
        except IntegrityError:
            # Another transaction may have inserted the unique bin between
            # the SELECT and INSERT. The savepoint keeps the caller's outer
            # transaction usable while the committed row is locked/read.
            retry_query = database.select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse)
            if for_update:
                retry_query = retry_query.with_for_update()
            bin_row = database.session.execute(retry_query).scalar_one_or_none()
            if bin_row is None:
                raise
    return bin_row


def _resolve_item_warehouse(item: SalesOrderItem, item_obj: Item | None) -> str:
    """Resuelve el almacen para un item de orden de venta, creando si es necesario."""
    warehouse = item.warehouse
    if warehouse:
        return warehouse
    if not item_obj:
        return ""
    warehouse = item_obj.default_warehouse_id
    if warehouse:
        item.warehouse = warehouse
        database.session.add(item)
        database.session.flush()
    return warehouse or ""


def _item_by_code(item_code: str) -> Item | None:
    """Busca un artículo por su clave primaria histórica o por código."""
    item = database.session.get(Item, item_code)
    if item is not None:
        return item
    return database.session.execute(database.select(Item).filter_by(code=item_code)).scalars().first()


def _base_qty_for_sales_line(item: Any, item_obj: Item | None) -> Decimal:
    """Convierte la cantidad de una línea de venta a la UOM base del artículo."""
    stored_qty = item.qty_in_base_uom
    if stored_qty is not None and Decimal(str(stored_qty)) > 0:
        return Decimal(str(stored_qty))

    line_qty = Decimal(str(item.qty or 0))
    if item_obj is None:
        item.qty_in_base_uom = line_qty
        database.session.add(item)
        return line_qty
    line_uom = item.uom or item_obj.default_uom
    try:
        base_qty = convert_item_qty(item.item_code, line_qty, line_uom, item_obj.default_uom)
    except InventoryServiceError as exc:
        raise ValueError(str(exc)) from exc
    item.qty_in_base_uom = base_qty
    database.session.add(item)
    return base_qty


def _reservation_warehouse_for_delivery_note(dn: DeliveryNote, item: DeliveryNoteItem, item_obj: Item | None) -> str:
    """Obtiene la bodega de la reserva original de una línea entregada."""
    relation = (
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(
                source_type="sales_order",
                source_id=dn.sales_order_id,
                target_type="delivery_note",
                target_id=dn.id,
                target_item_id=item.id,
                status="active",
            )
            .order_by(DocumentRelation.created.desc())
        )
        .scalars()
        .first()
    )
    if relation and relation.source_item_id:
        source_item = database.session.get(SalesOrderItem, relation.source_item_id)
        if source_item:
            return _resolve_item_warehouse(source_item, item_obj)

    source_item = (
        database.session.execute(
            database.select(SalesOrderItem)
            .filter_by(sales_order_id=dn.sales_order_id, item_code=item.item_code)
            .order_by(SalesOrderItem.created)
        )
        .scalars()
        .first()
    )
    if source_item:
        return _resolve_item_warehouse(source_item, item_obj)
    return item.warehouse or (item_obj.default_warehouse_id if item_obj else None) or ""


def _validate_and_reserve_stock_for_sales_order(so: SalesOrder) -> None:
    """Valida disponibilidad y reserva inventario al aprobar una Orden de Venta.

    Para cada linea de la OV con almacen definido, verifica que
    actual_qty - reserved_qty >= qty. Si hay stock suficiente,
    incrementa reserved_qty en el StockBin correspondiente.
    """
    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=so.id)).scalars().all()

    for item in items:
        item_obj = _item_by_code(item.item_code)
        if item_obj and not item_obj.is_stock_item:
            continue

        warehouse = _resolve_item_warehouse(item, item_obj)
        if not warehouse:
            raise ValueError(f"El item {item.item_code} no tiene almacen asignado en la orden de venta.")

        bin_row = _stock_bin_or_create(company=so.company, item_code=item.item_code, warehouse=warehouse, for_update=True)
        available = Decimal(str(bin_row.actual_qty or 0)) - Decimal(str(bin_row.reserved_qty or 0))

        required_qty = _base_qty_for_sales_line(item, item_obj)
        if available < required_qty:
            raise ValueError(
                f"Stock insuficiente para {item.item_code} en {warehouse}: disponible {available}, requerido {required_qty}."
            )

        bin_row.reserved_qty = Decimal(str(bin_row.reserved_qty or 0)) + required_qty


def _release_reservation_for_sales_order(so: SalesOrder) -> None:
    """Libera la reserva de inventario al cancelar una Orden de Venta.

    Usa la misma resolución de bodega que ``_validate_and_reserve_stock_for_sales_order``
    (incluyendo ``Item.default_warehouse_id``) para que la cancelación libere
    exactamente la bodega efectiva en que se reservó el inventario.
    """
    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=so.id)).scalars().all()

    for item in items:
        item_obj = _item_by_code(item.item_code)
        if item_obj and not item_obj.is_stock_item:
            continue

        warehouse = _resolve_item_warehouse(item, item_obj)
        if not warehouse:
            continue

        bin_row = _stock_bin_or_create(company=so.company, item_code=item.item_code, warehouse=warehouse, for_update=True)
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        new_reserved = max(Decimal("0"), reserved - _base_qty_for_sales_line(item, item_obj))
        bin_row.reserved_qty = new_reserved


def _release_reservation_for_delivery_note(dn: DeliveryNote) -> None:
    """Libera reserva al aprobar una Nota de Entrega vinculada a una OV.

    Es idempotente: si la liberacion ya ocurrio (``reservation_released``)
    no resta la cantidad nuevamente, evitando corromper ``reserved_qty`` en
    reintentos o dobles llamadas.
    """
    if dn.docstatus != 1:
        return
    if not dn.sales_order_id:
        return
    if getattr(dn, "reservation_released", False):
        return

    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=dn.id)).scalars().all()

    for item in items:
        item_obj = _item_by_code(item.item_code)
        if item_obj and not item_obj.is_stock_item:
            continue

        warehouse = _reservation_warehouse_for_delivery_note(dn, item, item_obj)
        if not warehouse:
            continue

        bin_row = _stock_bin_or_create(company=dn.company, item_code=item.item_code, warehouse=warehouse, for_update=True)
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        new_reserved = max(Decimal("0"), reserved - _base_qty_for_sales_line(item, item_obj))
        bin_row.reserved_qty = new_reserved
    dn.reservation_released = True


def _restore_reservation_for_delivery_note(dn: DeliveryNote) -> None:
    """Restaura reserva al cancelar una Nota de Entrega vinculada a una OV.

    Incrementa ``reserved_qty`` sumando ``item.qty`` al valor actual.
    No sobrescribe: lee el valor vigente y le suma la cantidad liberada.
    """
    if not dn.sales_order_id:
        return

    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=dn.id)).scalars().all()

    for item in items:
        item_obj = _item_by_code(item.item_code)
        if item_obj and not item_obj.is_stock_item:
            continue

        warehouse = _reservation_warehouse_for_delivery_note(dn, item, item_obj)
        if not warehouse:
            continue

        bin_row = _stock_bin_or_create(company=dn.company, item_code=item.item_code, warehouse=warehouse, for_update=True)
        reserved = Decimal(str(bin_row.reserved_qty or 0))
        bin_row.reserved_qty = reserved + _base_qty_for_sales_line(item, item_obj)
    dn.reservation_released = False


def _upsert_customer_company_settings_from_request(customer_id: str, form: dict) -> None:
    """Actualiza la configuracion de compania para un cliente desde el formulario."""
    upsert_party_company_settings_rows(customer_id, "customer", form)


def _capture_sales_state(registro: Any) -> dict[str, Any]:
    """CROSS-01: Captura estado de documento de ventas para auditoría."""
    state = {
        "customer_id": getattr(registro, "customer_id", None),
        "company": getattr(registro, "company", None),
        "posting_date": str(getattr(registro, "posting_date", "")),
        "total": str(getattr(registro, "total", "")),
        "remarks": getattr(registro, "remarks", None),
    }

    from cacao_accounting.database import (
        SalesRequest,
        SalesRequestItem,
        SalesQuotation,
        SalesQuotationItem,
        SalesOrder,
        SalesOrderItem,
        DeliveryNote,
        DeliveryNoteItem,
        SalesInvoice,
        SalesInvoiceItem,
    )

    mapping = {
        SalesRequest: (SalesRequestItem, "sales_request_id"),
        SalesQuotation: (SalesQuotationItem, "sales_quotation_id"),
        SalesOrder: (SalesOrderItem, "sales_order_id"),
        DeliveryNote: (DeliveryNoteItem, "delivery_note_id"),
        SalesInvoice: (SalesInvoiceItem, "sales_invoice_id"),
    }

    cls = type(registro)
    if cls in mapping:
        item_cls, fk_name = mapping[cls]
        from cacao_accounting.audit_trail_service import capture_lines_snapshot

        state["items"] = capture_lines_snapshot(registro, item_cls, fk_name)

    return state


def _paginate_list(model, search_fields, query=None, *, include_status: bool = True, access_modules=("sales",)):
    """Pagina un listado aplicando los filtros GET comunes."""
    base_query = query if query is not None else database.select(model)
    if hasattr(model, "company"):
        company = request.args.get("company")
        if company:
            exige_acceso_compania_cualquiera(access_modules, company, "consultar")
            base_query = base_query.filter(model.company == company)
        elif getattr(current_user, "classification", None) != "admin":
            book_ids = set()
            for module in access_modules:
                module_id = obtener_id_modulo_por_nombre(module)
                permissions = Permisos(modulo=module_id, usuario=current_user.id)
                book_ids.update(permissions.obtener_libros_autorizados("can_read"))
            if not book_ids:
                base_query = base_query.where(database.false())
            else:
                accessible_companies = database.select(Book.entity).where(Book.id.in_(book_ids))
                base_query = base_query.where(model.company.in_(accessible_companies))
    filtered_query = apply_list_filters(base_query, model, search_fields, include_status=include_status)
    return database.paginate(
        filtered_query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )


def _require_delivery_note_access(document: DeliveryNote, action: str = "consultar") -> None:
    """Require Sales read access or Inventory write access for a delivery note."""
    if not document.company:
        abort(404)
    if action == "consultar":
        exige_acceso_compania_cualquiera(("sales", "inventory"), str(document.company), action)
        return
    exige_acceso_compania("inventory", str(document.company), action)


def _can_manage_delivery_notes() -> bool:
    """Return whether the current user has Inventory write permission."""
    module_id = obtener_id_modulo_por_nombre("inventory")
    permissions = Permisos(modulo=module_id, usuario=current_user.id)
    return bool(permissions.administrador or permissions.crear)


def _require_sales_document_access(document: Any, action: str = "consultar") -> None:
    """Require granular company access for an O2C document.

    Shares the company-scope check used by the submit/cancel routes so that
    detail, edit and duplicate endpoints cannot read or mutate documents of
    companies outside the user's authorized books.

    Args:
        document: Operational sales document carrying a ``company`` attribute.
        action: Granular action ("consultar", "crear", "editar", "autorizar").

    Raises:
        HTTPException: ``404`` for documents without a company or ``403``
            when the current user lacks access to the document company.
    """
    company = getattr(document, "company", None)
    if not company:
        abort(404)
    exige_acceso_compania("sales", str(company), action)


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
        flash_error(exc)
    return render_template(
        VENTAS_CLIENTE_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(form.get("party_group_id") or None),
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
        flash_error(exc)
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


def _handle_sales_request_update(registro: SalesRequest, form: dict, endpoint: str, request_id: str):
    """Maneja la actualizacion de un pedido de venta desde el formulario POST."""
    before_state = _capture_sales_state(registro)
    revert_relations_for_target("sales_request", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("sales_request", registro.id)
    customer_id = form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    requested_company = form.get("company") or registro.company
    if requested_company != registro.company:
        database.session.rollback()
        flash("La compañía de un documento existente no puede cambiarse.", "danger")
        return redirect(url_for(endpoint, request_id=request_id))
    registro.posting_date = _parse_date(form.get("posting_date"))
    registro.remarks = form.get("remarks")
    for item in database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=registro.id)).scalars():
        database.session.delete(item)
    _total_qty, total = _save_sales_request_items(registro.id)
    _set_sales_document_totals(registro, total)
    after_state = _capture_sales_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Pedido de venta actualizado correctamente."), "success")
    return redirect(url_for(endpoint, request_id=request_id))


def _handle_sales_order_update(registro: SalesOrder, form: dict, endpoint: str, order_id: str):
    """Maneja la actualizacion de una orden de venta desde el formulario POST."""
    before_state = _capture_sales_state(registro)
    revert_relations_for_target("sales_order", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("sales_order", registro.id)
    customer_id = form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    requested_company = form.get("company") or registro.company
    if requested_company != registro.company:
        database.session.rollback()
        flash("La compañía de un documento existente no puede cambiarse.", "danger")
        return redirect(url_for(endpoint, order_id=order_id))
    registro.posting_date = _parse_date(form.get("posting_date"))
    registro.remarks = form.get("remarks")
    for item in database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=registro.id)).scalars():
        database.session.delete(item)
    _total_qty, total = _save_sales_order_items(registro.id)
    _set_sales_document_totals(registro, total)
    after_state = _capture_sales_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Orden de venta actualizada correctamente."), "success")
    return redirect(url_for(endpoint, order_id=order_id))


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


def _save_sales_order_items(order_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una orden de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    seen_item_codes: set[str] = set()
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            if item_code in seen_item_codes:
                raise DocumentFlowError(f"El item {item_code} no puede repetirse en el documento.", 400)
            seen_item_codes.add(item_code)
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            item_obj = _item_by_code(item_code)
            if not item_obj:
                raise ValueError(f"El item {item_code} no existe.")
            if not item_obj.is_active or not item_obj.is_sale_item:
                raise ValueError(f"El item {item_code} no está habilitado para venta.")
            qty_in_base_uom = convert_item_qty(item_code, qty, uom or item_obj.default_uom, item_obj.default_uom)
            linea = SalesOrderItem(
                sales_order_id=order_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                qty_in_base_uom=qty_in_base_uom,
                rate=rate,
                amount=amount,
                warehouse=request.form.get(f"warehouse_{i}") or None,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "sales_order", order_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_sales_request_items(request_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de un pedido de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    seen_item_codes: set[str] = set()
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            if item_code in seen_item_codes:
                raise DocumentFlowError(f"El item {item_code} no puede repetirse en el documento.", 400)
            seen_item_codes.add(item_code)
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
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_sales_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una cotización de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    seen_item_codes: set[str] = set()
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            if item_code in seen_item_codes:
                raise DocumentFlowError(f"El item {item_code} no puede repetirse en el documento.", 400)
            seen_item_codes.add(item_code)
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
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_delivery_note_items(note_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una nota de entrega desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    seen_item_codes: set[str] = set()
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            if item_code in seen_item_codes:
                raise DocumentFlowError(f"El item {item_code} no puede repetirse en el documento.", 400)
            seen_item_codes.add(item_code)
            qty = _form_decimal(f"qty_{i}", "1")
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            warehouse = (
                request.form.get(f"warehouse_{i}")
                or request.form.get("from_warehouse")
                or request.form.get("warehouse")
                or None
            )
            if not warehouse:
                raise DocumentFlowError(f"El item {item_code} requiere un almacén de origen.", 400)
            linea = DeliveryNoteItem(
                delivery_note_id=note_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
                warehouse=warehouse,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "delivery_note", note_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_sales_invoice_items(invoice_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una factura de venta desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    seen_item_codes: set[str] = set()
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            if item_code in seen_item_codes:
                raise DocumentFlowError(f"El item {item_code} no puede repetirse en el documento.", 400)
            seen_item_codes.add(item_code)
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
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
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
        raise PostingError("La factura no tiene ítems para crear la Nota de Entrega.")  # type: ignore[misc]

    dn = DeliveryNote(
        customer_id=invoice.customer_id,
        customer_name=invoice.customer_name,
        company=invoice.company,
        posting_date=invoice.posting_date,
        sales_order_id=invoice.sales_order_id,
        transaction_currency=invoice.transaction_currency or company_currency(invoice.company),
        base_currency=invoice.base_currency or company_currency(invoice.company),
        exchange_rate=invoice.exchange_rate or Decimal("1"),
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
            raise PostingError(  # type: ignore[misc]
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
        database.session.flush()
        source_relation = database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type="sales_invoice", target_id=invoice.id, target_item_id=si_item.id, status="active"
            )
        ).scalar_one_or_none()
        if source_relation:
            create_document_relation(
                source_type=source_relation.source_type,
                source_id=source_relation.source_id,
                source_item_id=source_relation.source_item_id,
                target_type="delivery_note",
                target_id=dn.id,
                target_item_id=dn_item.id,
                qty=si_item.qty,
                uom=si_item.uom,
                rate=si_item.rate or Decimal("0"),
                amount=si_item.amount or Decimal("0"),
            )
        total += si_item.amount or Decimal("0")

    dn.total = total
    dn.grand_total = total

    _validate_delivery_quantities_against_so(dn.id)
    submit_document(dn)  # type: ignore[misc]
    _release_reservation_for_delivery_note(dn)
    log_submit(dn)

    invoice.delivery_note_id = dn.id
    return dn


def _load_sales_tolerance_config(company: str) -> tuple[str, Decimal, bool]:
    """Carga la configuracion de tolerancia de precios para una compania."""
    config = database.session.execute(database.select(SalesMatchingConfig).filter_by(company=company)).scalar_one_or_none()

    if config is None:
        return "percentage", Decimal("0"), False

    return (
        config.price_tolerance_type or "percentage",
        config.price_tolerance_value or Decimal("0"),
        config.allow_price_difference,
    )


def _calculate_price_variance(so_rate: Decimal, si_rate: Decimal, tolerance_type: str) -> Decimal:
    """Calcula la varianza de precio entre orden de venta y factura."""
    if tolerance_type == "absolute":
        return abs(si_rate - so_rate)
    return abs(si_rate - so_rate) / so_rate * Decimal("100")


def _validate_single_item_price(
    si_item: SalesInvoiceItem,
    so_rate: Decimal,
    tolerance_type: str,
    tolerance_value: Decimal,
    allow_diff: bool,
    raise_on_violation: bool,
    reference_label: str = _LABEL_ORDEN_VENTA,
) -> str | None:
    """Valida el precio de un item individual contra la orden de venta.

    Retorna un mensaje de advertencia/error o None si es valido.
    """
    si_rate = Decimal(str(si_item.rate or 0))

    if so_rate <= 0:
        return None

    variance = _calculate_price_variance(so_rate, si_rate, tolerance_type)
    if variance <= tolerance_value:
        return None

    unit = "%" if tolerance_type == "percentage" else ""
    msg = (
        f"El precio del item {si_item.item_code} (${si_rate}) "
        f"difiere del precio en {reference_label} (${so_rate}) "
        f"en {variance:.2f}{unit}. "
        f"Tolerancia permitida: {tolerance_value}{unit}."
    )
    if allow_diff:
        return msg
    if raise_on_violation:
        raise ValueError(msg)
    return msg


def _validate_invoice_prices_against_source(invoice: SalesInvoice, raise_on_violation: bool = True) -> list[str]:
    """Valida precios de factura contra la Orden de Venta origen.

    Retorna una lista de mensajes de advertencia si ``allow_price_difference``
    es ``True`` y el precio excede la tolerancia. Si ``allow_price_difference``
    es ``False`` y el precio excede la tolerancia, lanza ``ValueError`` salvo
    que ``raise_on_violation`` sea ``False`` (p.ej. al guardar un borrador), en
    cuyo caso se agrega a las advertencias sin bloquear el guardado.
    """
    tolerance_type, tolerance_value, allow_diff = _load_sales_tolerance_config(invoice.company)

    invoice_items = (
        database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id)).scalars().all()
    )

    warnings: list[str] = []
    for si_item in invoice_items:
        so_rate = _resolve_source_item_rate(si_item, invoice.id)
        reference_label = _LABEL_ORDEN_VENTA
        if so_rate is None:
            so_rate = _resolve_catalog_sales_rate(invoice, si_item)
            reference_label = "la Lista de Precios"
        if so_rate is None:
            continue

        warning = _validate_single_item_price(
            si_item,
            so_rate,
            tolerance_type,
            tolerance_value,
            allow_diff,
            raise_on_violation,
            reference_label=reference_label,
        )
        if warning:
            warnings.append(warning)

    return warnings


def _resolve_sales_price_list(company: str, customer_id: str | None) -> PriceList | None:
    """Obtiene la lista de venta del cliente o la predeterminada de la compañía."""
    company_party = None
    if customer_id:
        company_party = database.session.execute(
            database.select(CompanyParty).filter_by(company=company, party_id=customer_id, is_active=True)
        ).scalar_one_or_none()
    configured_id = getattr(company_party, "default_price_list_id", None)
    if configured_id:
        configured = database.session.get(PriceList, configured_id)
        if configured and configured.is_active and configured.is_selling and configured.company in (None, company):
            return configured
    return (
        database.session.execute(
            database.select(PriceList)
            .where(
                PriceList.is_active.is_(True),
                PriceList.is_default.is_(True),
                PriceList.is_selling.is_(True),
                or_(PriceList.company == company, PriceList.company.is_(None)),
            )
            .order_by(PriceList.company.is_(None), PriceList.name)
        )
        .scalars()
        .first()
    )


def _resolve_catalog_sales_rate(invoice: SalesInvoice, item: SalesInvoiceItem) -> Decimal | None:
    """Resuelve el precio vigente del catálogo para una línea sin documento fuente."""
    price_list = _resolve_sales_price_list(invoice.company, invoice.customer_id)
    if not price_list or not invoice.posting_date:
        return None
    query = (
        database.select(ItemPrice)
        .where(
            ItemPrice.item_code == item.item_code,
            ItemPrice.price_list_id == price_list.id,
            (ItemPrice.valid_from.is_(None) | (ItemPrice.valid_from <= invoice.posting_date)),
            (ItemPrice.valid_upto.is_(None) | (ItemPrice.valid_upto >= invoice.posting_date)),
            (ItemPrice.min_qty.is_(None) | (ItemPrice.min_qty <= item.qty)),
        )
        .order_by(ItemPrice.min_qty.desc().nullslast(), ItemPrice.valid_from.desc().nullslast())
    )
    if item.uom:
        query = query.where(or_(ItemPrice.uom.is_(None), ItemPrice.uom == item.uom))
    catalog_price = database.session.execute(query).scalars().first()
    return Decimal(str(catalog_price.price)) if catalog_price else None


def _resolve_source_item_rate(si_item: SalesInvoiceItem, invoice_id: str) -> Decimal | None:
    """Resuelve la tasa del item fuente para un item de factura."""
    relation = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type="sales_invoice",
                target_id=invoice_id,
                target_item_id=si_item.id,
                status="active",
            )
        )
        .scalars()
        .first()
    )
    if not relation or not relation.source_item_id:
        return None
    source_models = {
        "sales_order": SalesOrderItem,
        "delivery_note": DeliveryNoteItem,
        "sales_invoice": SalesInvoiceItem,
    }
    source_model = source_models.get(relation.source_type)
    source_item: Any = database.session.get(source_model, relation.source_item_id) if source_model else None
    if source_item is None:
        return None
    return Decimal(str(source_item.rate or 0))


def _validate_delivery_quantities_against_so(note_id: str) -> None:
    """Valida que las cantidades entregadas no excedan las ordenadas en la Orden de Venta."""
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="delivery_note",
            target_id=note_id,
            status="active",
        )
    ).scalars()
    for rel in relations:
        if rel.source_type != "sales_order" or not rel.source_item_id:
            continue
        so_item = database.session.get(SalesOrderItem, rel.source_item_id)
        if not so_item:
            continue
        consumed = consumed_qty_for_source(
            "sales_order",
            rel.source_id,
            rel.source_item_id,
            "delivery_note",
            exclude_draft_targets=True,
            include_target_id=note_id,
        )
        ordered = (
            Decimal(str(so_item.qty_in_base_uom)) if so_item.qty_in_base_uom is not None else Decimal(str(so_item.qty or 0))
        )
        if consumed > ordered:
            raise ValueError(
                _("Sobre-entrega: cantidad entregada {} excede la ordenada {} para el artículo {}.").format(
                    consumed, ordered, so_item.item_code
                )
            )


def _validate_sales_invoice_quantities(invoice_id: str) -> None:
    """Valida cantidades facturadas contra Nota de Entrega u Orden de Venta."""
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="sales_invoice",
            target_id=invoice_id,
            status="active",
        )
    ).scalars()
    for rel in relations:
        if rel.source_item_id:
            _validate_sales_invoice_relation(rel, invoice_id=invoice_id)


def _validate_sales_invoice_line_amounts(invoice: SalesInvoice, items: Sequence[SalesInvoiceItem]) -> None:
    """Reject inconsistent or negative amounts on ordinary sales invoices."""
    if getattr(invoice, "is_return", False) or getattr(invoice, "document_type", "") in {
        "sales_credit_note",
        "sales_debit_note",
    }:
        return
    tolerance = Decimal("0.01")
    for item in items:
        qty = Decimal(str(item.qty or 0))
        rate = Decimal(str(item.rate or 0))
        amount = Decimal(str(item.amount or 0))
        expected = qty * rate
        if amount <= 0:
            raise ValueError(f"La línea {item.item_code} debe tener un monto positivo.")
        if abs(amount - expected) > tolerance:
            raise ValueError(
                f"El monto de la línea {item.item_code} no coincide con cantidad por precio "
                f"({amount} frente a {expected})."
            )


def _validate_sales_source_link(document: Any, source_type: str, source_id: str, items: Sequence[Any] | None = None) -> Any:
    """Valida estado, compañía, cliente y relaciones de un origen O2C."""
    source_models = {
        "sales_request": SalesRequest,
        "sales_quotation": SalesQuotation,
        "sales_order": SalesOrder,
        "delivery_note": DeliveryNote,
    }
    source_model = source_models.get(source_type)
    source = database.session.get(source_model, source_id) if source_model else None
    if not source:
        raise ValueError(f"El documento origen '{source_id}' no existe.")
    if source.docstatus != 1:
        raise ValueError(f"El documento origen '{source_id}' debe estar aprobado.")
    if source.company != document.company:
        raise ValueError("El documento origen y el documento destino deben pertenecer a la misma compañía.")
    customer_id = getattr(source, "customer_id", None)
    if customer_id and customer_id != document.customer_id:
        raise ValueError("El documento origen y el documento destino deben pertenecer al mismo cliente.")
    target_currency = getattr(document, "transaction_currency", None)
    if target_currency and effective_currency(source) != target_currency:
        raise ValueError("El documento origen y el documento destino deben usar la misma moneda.")
    if source_type == "delivery_note" and getattr(document, "sales_order_id", None):
        if getattr(source, "sales_order_id", None) != document.sales_order_id:
            raise ValueError("La nota de entrega no pertenece a la orden de venta indicada.")
    if items is not None:
        target_types = {
            SalesQuotation: "sales_quotation",
            SalesOrder: "sales_order",
            DeliveryNote: "delivery_note",
            SalesInvoice: "sales_invoice",
        }
        require_line_relations(
            target_type=target_types[type(document)],
            target_id=document.id,
            source_type=source_type,
            source_id=source_id,
            items=list(items),
        )
    return source


def _validate_sales_invoice_source_links(invoice: SalesInvoice, items: Sequence[Any] | None = None) -> Any | None:
    """Valida y reconcilia los vínculos de orden y nota de entrega."""
    order = None
    delivery = None
    if invoice.sales_order_id:
        order = _validate_sales_source_link(invoice, "sales_order", invoice.sales_order_id, items)
    if invoice.delivery_note_id:
        delivery = _validate_sales_source_link(invoice, "delivery_note", invoice.delivery_note_id, items)
    if order is not None and delivery is not None and delivery.sales_order_id != order.id:
        raise ValueError("La orden y la nota de entrega de la factura no pertenecen al mismo flujo.")
    return order or delivery


def _validate_sales_order_requirement(invoice: SalesInvoice, items: Sequence[Any] | None = None) -> None:
    """Rechaza facturas sin orden de venta cuando la compañía lo exige."""
    if invoice.document_type in {"sales_credit_note", "sales_debit_note", "sales_return"} or invoice.is_return:
        return
    if invoice.sales_order_id or invoice.delivery_note_id:
        source = _validate_sales_invoice_source_links(invoice, items)
        if invoice.sales_order_id or getattr(source, "sales_order_id", None):
            return
    config = database.session.execute(
        database.select(SalesMatchingConfig).filter_by(company=invoice.company)
    ).scalar_one_or_none()
    if not config or not config.require_sales_order:
        return
    linked_order = database.session.execute(
        database.select(DocumentRelation.id)
        .where(
            DocumentRelation.source_type == "sales_order",
            DocumentRelation.source_id.is_not(None),
            DocumentRelation.target_type == "sales_invoice",
            DocumentRelation.target_id == invoice.id,
            DocumentRelation.status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    if linked_order:
        return
    raise ValueError("La factura debe estar vinculada a una Orden de Venta aprobada.")


def _validate_sales_invoice_relation(relation: DocumentRelation, invoice_id: str | None = None) -> None:
    """Valida una relación de factura contra su documento fuente."""
    sources = {
        "delivery_note": (DeliveryNoteItem, "entregada"),
        "sales_order": (SalesOrderItem, "ordenada"),
        "sales_invoice": (SalesInvoiceItem, "facturada"),
    }
    source = sources.get(relation.source_type)
    if not source or not relation.source_item_id:
        return
    item: Any = database.session.get(source[0], relation.source_item_id)
    if not item:
        return
    if relation.source_type == "sales_invoice" and item.sales_invoice_id != relation.source_id:
        raise ValueError("La línea de la factura origen no pertenece al documento indicado.")
    consumed = consumed_qty_for_source(
        relation.source_type,
        relation.source_id,
        relation.source_item_id,
        "sales_invoice",
        exclude_draft_targets=True,
        include_target_id=invoice_id,
    )
    available = (
        Decimal(str(item.qty_in_base_uom))
        if getattr(item, "qty_in_base_uom", None) is not None
        else Decimal(str(item.qty or 0))
    )
    if consumed > available:
        raise ValueError(
            _("Sobre-facturación: cantidad facturada {} excede la {} para el artículo {}.").format(
                consumed, source[1], item.item_code
            )
        )


def _persist_sales_invoice_fiscal_snapshot(invoice: SalesInvoice) -> None:
    """Persist the editable fiscal snapshot captured in the form."""
    items = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id)).scalars()
    subtotal = sum((Decimal(str(item.amount or "0")) for item in items), Decimal("0"))
    persist_document_fiscal_snapshot(
        company=str(invoice.company or ""),
        document_type=invoice.document_type or "sales_invoice",
        document_id=invoice.id,
        currency=effective_currency(invoice),
        tax_lines=request.form.get("tax_lines_payload"),
        tax_summary=request.form.get("tax_summary_payload"),
        server_subtotal=subtotal,
        server_total=Decimal(str(invoice.grand_total or "0")),
    )


def _sales_order_initial_source_type(from_request_id: str | None, from_quotation_id: str | None) -> str:
    """Resolve the initial source type for a sales order form."""
    if from_request_id:
        return "sales_request"
    if from_quotation_id:
        return "sales_quotation"
    return ""


def _build_sales_order_transaction_config(
    items_disponibles, uoms_disponibles, bodegas_disponibles, source_origen, initial_source_type
):

    transaction_config = {
        "formKey": _FORMKEY_SALES_ORDER,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "warehouses": bodegas_disponibles,
        "availableSourceTypes": [
            {"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)},
            {"value": "sales_quotation", "label": _("Cotización de Venta")},
        ],
        "initialSourceType": initial_source_type,
    }
    if source_origen:
        transaction_config["initialHeader"] = {
            "company": source_origen.company or "",
            "currency": effective_currency(source_origen) or "",
            "party": getattr(source_origen, "customer_id", None) or "",
            "party_label": getattr(source_origen, "customer_name", None) or "",
            "posting_date": str(date.today()),
            **_sales_logistics_values(source_origen),
        }
    return transaction_config


def _sales_order_source(
    from_quotation_id: str | None, from_request_id: str | None
) -> tuple[str | None, str | None, SalesQuotation | SalesRequest | None]:
    """Resuelve el tipo, identificador y documento origen de una orden de venta."""
    source_type = _sales_order_initial_source_type(from_request_id, from_quotation_id) or None
    source_id = from_quotation_id or from_request_id
    source = database.session.get(SalesQuotation, from_quotation_id) if from_quotation_id else None
    if from_request_id:
        source = database.session.get(SalesRequest, from_request_id)
    return source_type, source_id, source


def _handle_sales_order_new_post(from_quotation_id, from_request_id):

    try:
        customer_id = request.form.get("customer_id") or None
        customer = database.session.get(Party, customer_id) if customer_id else None
        posting_date = _parse_date(request.form.get("posting_date"))
        source_type, source_id, source = _sales_order_source(from_quotation_id, from_request_id)
        company, transaction_currency = validate_immutable_header(
            source,
            request.form.get("company") or None,
            request.form.get("currency") or request.form.get("transaction_currency") or None,
        )
        exige_acceso_compania("sales", company, "crear")
        orden = SalesOrder(
            customer_id=customer_id,
            customer_name=customer.name if customer else None,
            sales_quotation_id=from_quotation_id or None,
            company=company,
            posting_date=posting_date,
            transaction_currency=transaction_currency,
            base_currency=company_currency(company),
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        _copy_sales_logistics(orden, source, request.form)
        database.session.add(orden)
        database.session.flush()
        assign_document_identifier(
            document=orden,
            entity_type="sales_order",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _total_qty, total = _save_sales_order_items(orden.id)
        if source_type and source_id:
            order_items = (
                database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=orden.id)).scalars().all()
            )
            _validate_sales_source_link(orden, source_type, source_id, order_items)
        _set_sales_document_totals(orden, total)
        database.session.commit()
        flash("Orden de venta creada correctamente.", "success")
        return redirect(url_for(_ENDPOINT_ORDEN_VENTA, order_id=orden.id))
    except IdentifierConfigurationError as exc:
        database.session.rollback()
        flash_error(exc)
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
    except SQLAlchemyError as exc:
        database.session.rollback()
        flash(_("Error inesperado al crear la orden de venta: ") + str(exc), "danger")


def _handle_sales_quotation_edit_post(registro):
    before_state = _capture_sales_state(registro)
    revert_relations_for_target("sales_quotation", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("sales_quotation", registro.id)
    customer_id = request.form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    requested_company = request.form.get("company") or registro.company
    if requested_company != registro.company:
        database.session.rollback()
        flash("La compañía de un documento existente no puede cambiarse.", "danger")
        return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=registro.id))
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    for item in database.session.execute(
        database.select(SalesQuotationItem).filter_by(sales_quotation_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _total_qty, total = _save_sales_quotation_items(registro.id)
    _set_sales_document_totals(registro, total)
    after_state = _capture_sales_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Cotización de venta actualizada correctamente."), "success")
    return redirect(url_for(_ENDPOINT_COTIZACION, quotation_id=registro.id))


def _handle_delivery_note_edit_post(registro):
    before_state = _capture_sales_state(registro)
    revert_relations_for_target("delivery_note", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("delivery_note", registro.id)
    customer_id = request.form.get("customer_id") or None
    customer = database.session.get(Party, customer_id) if customer_id else None
    registro.customer_id = customer_id
    registro.customer_name = customer.name if customer else None
    requested_company = request.form.get("company") or registro.company
    if requested_company != registro.company:
        database.session.rollback()
        flash("La compañía de un documento existente no puede cambiarse.", "danger")
        return redirect(url_for(_ENDPOINT_ENTREGA, note_id=registro.id))
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    for item in database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=registro.id)).scalars():
        database.session.delete(item)
    _total_qty, total = _save_delivery_note_items(registro.id)
    _set_sales_document_totals(registro, total)
    after_state = _capture_sales_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Nota de entrega actualizada correctamente."), "success")
    return redirect(url_for(_ENDPOINT_ENTREGA, note_id=registro.id))


def _execute_delivery_note_cancellation(registro: DeliveryNote, note_id: str) -> None:
    """Ejecuta la cancelacion de una nota de entrega y restaura reservas."""
    cancel_document(registro)  # type: ignore[misc]
    _restore_reservation_for_delivery_note(registro)
    revert_relations_for_target("delivery_note", note_id)
    refresh_source_caches_for_target("delivery_note", note_id)
    log_cancel(registro)
    database.session.commit()


def _sales_invoice_sources_and_type(formulario) -> dict[str, Any]:
    f_order = request.args.get("from_order") or request.form.get("from_order")
    f_note = request.args.get("from_note") or request.form.get("from_note")
    f_invoice = request.args.get("from_invoice") or request.form.get("from_invoice")
    f_return = request.args.get("from_return") or request.form.get("from_return")
    f_invoice_id = f_invoice or f_return
    doc_type = (
        request.args.get("document_type")
        or request.form.get("document_type")
        or ("sales_invoice" if not f_invoice_id else "sales_credit_note")
    )
    formulario.is_return.data = doc_type in ("sales_credit_note", "sales_return")
    return {
        "from_order_id": f_order,
        "from_note_id": f_note,
        "from_invoice_id": f_invoice_id,
        "from_return_id": f_return,
        "document_type": doc_type,
        "orden_origen": database.session.get(SalesOrder, f_order) if f_order else None,
        "entrega_origen": database.session.get(DeliveryNote, f_note) if f_note else None,
        "factura_origen": database.session.get(SalesInvoice, f_invoice_id) if f_invoice_id else None,
    }


def _sales_invoice_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    items = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items, uoms


def _sales_invoice_source(invoice: SalesInvoice, reversal_of: str | None) -> SalesOrder | DeliveryNote | SalesInvoice | None:
    """Obtiene el primer documento origen asociado a una factura de venta."""
    source = database.session.get(SalesOrder, invoice.sales_order_id) if invoice.sales_order_id else None
    if not source and invoice.delivery_note_id:
        source = database.session.get(DeliveryNote, invoice.delivery_note_id)
    if not source and reversal_of:
        source = database.session.get(SalesInvoice, reversal_of)
    return source


def _create_sales_invoice_from_form():
    """Crea una factura de venta desde los datos del formulario."""
    factura = None
    try:
        document_type = request.form.get("document_type") or "sales_invoice"
        posting_date = _parse_date(request.form.get("posting_date"))
        reversal_of = _sales_reversal_source(document_type)
        source_company = request.form.get("company") or None
        source_id = request.form.get("from_order") or request.form.get("from_note") or reversal_of
        source_model = (
            SalesOrder if request.form.get("from_order") else DeliveryNote if request.form.get("from_note") else SalesInvoice
        )
        source_document = database.session.get(source_model, source_id) if source_id else None
        source_company = getattr(source_document, "company", None) or source_company
        exige_acceso_compania("sales", source_company, "crear")
        if reversal_of:
            _validate_reversal_of(reversal_of, request.form.get("customer_id"), request.form.get("company"))
        factura = SalesInvoice(
            customer_id=request.form.get("customer_id") or None,
            company=request.form.get("company") or None,
            posting_date=posting_date,
            document_type=document_type,
            sales_order_id=request.form.get("from_order") or None,
            delivery_note_id=request.form.get("from_note") or None,
            transaction_currency=request.form.get("transaction_currency") or request.form.get("currency") or None,
            update_inventory=bool(request.form.get("update_inventory"))
            and document_type not in ("sales_credit_note", "sales_return"),
            is_return=document_type in ("sales_credit_note", "sales_return"),
            reversal_of=reversal_of,
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        source = _sales_invoice_source(factura, reversal_of)
        _copy_sales_logistics(factura, source, request.form)
        database.session.add(factura)
        database.session.flush()
        assign_document_identifier(
            document=factura,
            entity_type="sales_invoice",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _total_qty, total = _save_sales_invoice_items(factura.id)
        items = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=factura.id)).scalars().all()
        )
        source = _validate_sales_invoice_source_links(factura, items) or source
        grand_total = calculate_document_total_with_taxes(factura, total, items, request.form.get("tax_summary_payload"))
        _set_sales_invoice_totals(factura, total, grand_total, source)
        if reversal_of:
            _validate_reversal_of(
                reversal_of,
                factura.customer_id,
                factura.company,
                note_amount=grand_total,
                document_type=document_type,
                posting_date=factura.posting_date,
            )
        _persist_sales_invoice_fiscal_snapshot(factura)
        database.session.commit()
        flash("Factura de venta creada correctamente.", "success")
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=factura.id))
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=factura.id if factura else ""))


def _sales_reversal_source(document_type: str) -> str | None:
    """Obtiene la factura origen para una nota de crédito o débito."""
    if document_type not in ("sales_credit_note", "sales_debit_note"):
        return None
    return request.form.get("from_invoice") or request.form.get("from_return") or None


def _persist_sales_reversal_relation(invoice: SalesInvoice) -> None:
    """Persist the invoice-to-credit-note relation used by AR outstanding."""
    if invoice.document_type not in {"sales_credit_note", "sales_debit_note"} or not invoice.reversal_of:
        return
    target_type = invoice.document_type
    relation = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_type="sales_invoice",
                source_id=invoice.reversal_of,
                target_type=target_type,
                target_id=invoice.id,
                relation_type="invoice_reversal",
            )
        )
        .scalars()
        .first()
    )
    amount = Decimal(str(invoice.grand_total or "0"))
    if relation:
        relation.qty = Decimal("1")
        relation.amount = amount
        relation.status = "active"
        from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache

        source = database.session.get(SalesInvoice, invoice.reversal_of)
        if source:
            refresh_outstanding_amount_cache(source)
        return
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=invoice.reversal_of,
            source_item_id=None,
            target_type=target_type,
            target_id=invoice.id,
            target_item_id=None,
            company=invoice.company,
            qty=Decimal("1"),
            uom=None,
            rate=amount,
            amount=amount,
            relation_type="invoice_reversal",
            status="active",
        )
    )
    from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache

    source = database.session.get(SalesInvoice, invoice.reversal_of)
    if source:
        refresh_outstanding_amount_cache(source)


def _handle_sales_invoice_edit_post(registro):
    """Maneja edicion de factura de venta.

    ``is_return`` y ``reversal_of`` no se modifican aqui. Son campos
    inmutables despues de la creacion; se preservan del registro existente.
    """
    try:
        before_state = _capture_sales_state(registro)
        revert_relations_for_target("sales_invoice", registro.id, reason="draft_edited")
        refresh_source_caches_for_target("sales_invoice", registro.id)
        registro.customer_id = request.form.get("customer_id") or None
        registro.company = request.form.get("company") or None
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.remarks = request.form.get("remarks")
        registro.update_inventory = bool(request.form.get("update_inventory")) and not registro.is_return
        if registro.reversal_of and (
            before_state.get("customer_id") != registro.customer_id or before_state.get("company") != registro.company
        ):
            _validate_reversal_of(registro.reversal_of, registro.customer_id, registro.company)
        for item in database.session.execute(
            database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)
        ).scalars():
            database.session.delete(item)
        _total_qty, total = _save_sales_invoice_items(registro.id)
        registro.total = total
        registro.base_total = total
        items = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=registro.id)).scalars().all()
        )
        source = None
        source = _validate_sales_invoice_source_links(registro, items)
        if source is None and registro.reversal_of:
            source = database.session.get(SalesInvoice, registro.reversal_of)
        grand_total = calculate_document_total_with_taxes(registro, total, items, request.form.get("tax_summary_payload"))
        _set_sales_invoice_totals(registro, total, grand_total, source)
        if registro.reversal_of:
            _validate_reversal_of(
                registro.reversal_of,
                registro.customer_id,
                registro.company,
                note_amount=grand_total,
                document_type=registro.document_type,
                posting_date=registro.posting_date,
            )
        warnings = _validate_invoice_prices_against_source(registro, raise_on_violation=False)
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
        flash_error(exc)
        return redirect(url_for(_ENDPOINT_FACTURA_VENTA, invoice_id=registro.id))


def _cancel_linked_delivery_note(invoice: SalesInvoice) -> None:
    """Cancela la Nota de Entrega vinculada si update_inventory esta activo."""
    if not (invoice.update_inventory and invoice.delivery_note_id):
        return
    dn = database.session.get(DeliveryNote, invoice.delivery_note_id)
    if not dn or dn.docstatus != 1:
        return
    cancel_document(dn)  # type: ignore[misc]
    _restore_reservation_for_delivery_note(dn)
    log_cancel(dn)
    flash(
        _("Se ha cancelado la Nota de Entrega %s asociada.") % (dn.document_no or dn.id),
        "info",
    )


def _validate_credit_limit_and_overdue(
    company: str, customer_id: str | None, current_doc_total: Decimal, current_document: Any | None = None
) -> None:
    """Valida el límite de crédito y facturas vencidas de un cliente antes de submit."""
    if not customer_id or not company:
        return

    from cacao_accounting.database import CompanyParty
    from cacao_accounting.document_flow.service import compute_outstanding_amount

    company_party = database.session.execute(
        database.select(CompanyParty).filter_by(company=company, party_id=customer_id)
    ).scalar_one_or_none()

    if not company_party:
        return

    invoices = _approved_customer_invoices(company, customer_id)
    if company_party.block_overdue:
        _reject_overdue_invoices(invoices, company_party.payment_terms_id, compute_outstanding_amount)
    if company_party.credit_limit is not None:
        outstanding = sum(
            (
                _sales_base_amount(
                    inv,
                    compute_outstanding_amount(inv),
                    use_stored_total=False,
                )
                for inv in invoices
            ),
            Decimal("0"),
        )
        order_exposure = _approved_customer_order_exposure(company, customer_id, current_document)
        current_doc_base = (
            _sales_base_amount(current_document, current_doc_total) if current_document is not None else current_doc_total
        )
        exposure = outstanding + order_exposure + current_doc_base
        limit = Decimal(str(company_party.credit_limit))
        if exposure > limit:
            raise ValueError(
                f"El límite de crédito para el cliente ha sido excedido. Límite: {limit}, "
                f"Saldo actual: {outstanding + order_exposure}, Monto del documento: {current_doc_total}, "
                f"Exposición total: {exposure}."
            )


def _approved_customer_invoices(company: str, customer_id: str) -> list[SalesInvoice]:
    """Obtiene facturas aprobadas del cliente y compañía."""
    query = (
        database.select(SalesInvoice)
        .filter_by(
            company=company,
            customer_id=customer_id,
            docstatus=1,
            is_return=False,
        )
        .where(SalesInvoice.document_type != "sales_debit_note")
    )
    return list(database.session.execute(query).scalars().all())


def _sales_base_amount(document: Any, amount: Decimal, *, use_stored_total: bool = True) -> Decimal:
    """Convierte un monto comercial a la moneda funcional del documento.

    Los totales base almacenados representan el documento completo y no deben
    sustituir un monto parcial calculado, como el saldo pendiente de una
    factura. ``use_stored_total=False`` fuerza la conversión del monto recibido
    usando la tasa histórica del documento.
    """
    if use_stored_total:
        base_amount = getattr(document, "base_grand_total", None)
        if base_amount is None:
            base_amount = getattr(document, "base_total", None)
        if base_amount is not None:
            return Decimal(str(base_amount))
    transaction_currency = effective_currency(document) or company_currency(getattr(document, "company", None))
    base_currency = company_currency(getattr(document, "company", None))
    if not transaction_currency or transaction_currency == base_currency:
        return Decimal(str(amount))
    exchange_rate = getattr(document, "exchange_rate", None)
    if exchange_rate is None or Decimal(str(exchange_rate)) <= 0:
        raise ValueError(
            f"El documento {getattr(document, 'document_no', None) or getattr(document, 'id', '')} "
            f"no tiene una tasa válida para {transaction_currency} -> {base_currency}."
        )
    return (Decimal(str(amount)) * Decimal(str(exchange_rate))).quantize(Decimal("0.0001"))


def _approved_customer_order_exposure(company: str, customer_id: str, current_document: Any | None = None) -> Decimal:
    """Calculate approved sales-order value not yet covered by invoices."""
    orders = database.session.execute(
        database.select(SalesOrder).filter_by(company=company, customer_id=customer_id, docstatus=1)
    ).scalars()
    exposure = Decimal("0")
    current_order_id = getattr(current_document, "sales_order_id", None)
    current_dn_id = getattr(current_document, "delivery_note_id", None) if current_document else None
    if not current_order_id and current_dn_id:
        delivery_note = database.session.get(DeliveryNote, current_dn_id)
        current_order_id = delivery_note.sales_order_id if delivery_note else None
    for order in orders:
        order_total = _sales_base_amount(order, Decimal(str(order.grand_total or "0")))
        delivery_note_ids = database.select(DeliveryNote.id).filter_by(sales_order_id=order.id)
        billed_invoices = database.session.execute(
            database.select(SalesInvoice).where(
                SalesInvoice.company == company,
                SalesInvoice.customer_id == customer_id,
                SalesInvoice.docstatus == 1,
                SalesInvoice.is_return.is_(False),
                SalesInvoice.document_type != "sales_debit_note",
                or_(
                    SalesInvoice.sales_order_id == order.id,
                    SalesInvoice.delivery_note_id.in_(delivery_note_ids),
                ),
            )
        ).scalars()
        billed_total = sum(
            (_sales_base_amount(invoice, Decimal(str(invoice.grand_total or "0"))) for invoice in billed_invoices),
            Decimal("0"),
        )
        pending = max(Decimal("0"), order_total - billed_total)
        if order.id == current_order_id:
            pending = max(
                Decimal("0"),
                pending - _sales_base_amount(current_document, Decimal(str(getattr(current_document, "grand_total", 0) or 0))),
            )
        exposure += pending
    return exposure


def _reject_overdue_invoices(invoices, payment_terms_id, outstanding_getter) -> None:
    """Rechaza si existe una factura pendiente y vencida."""
    from cacao_accounting.database import PaymentTerms
    from datetime import date, timedelta

    terms = database.session.get(PaymentTerms, payment_terms_id) if payment_terms_id else None
    due_days = terms.due_days or 0 if terms else 0
    today = date.today()
    for invoice in invoices:
        if outstanding_getter(invoice) <= 0 or not invoice.posting_date:
            continue
        due_date = invoice.posting_date + timedelta(days=due_days)
        if today > due_date:
            raise ValueError(
                f"El cliente tiene facturas vencidas y su configuración bloquea nuevas ventas. "
                f"Factura vencida: {invoice.document_no or invoice.id} (Vencimiento: {due_date})."
            )


def _validate_reversal_of(
    reversal_of: str,
    customer_id: str | None,
    company: str | None,
    *,
    note_amount: Decimal | None = None,
    document_type: str | None = None,
    posting_date: date | None = None,
    lock_source: bool = False,
) -> None:
    """Valida origen y limite acumulado de una nota de credito.

    Las notas de debito incrementan la cuenta por cobrar y no se limitan al
    saldo de la factura origen. Las notas de credito, en cambio, no pueden
    superar el saldo pendiente de la factura considerando notas y pagos ya
    aplicados.
    """
    source_query = database.select(SalesInvoice).where(SalesInvoice.id == reversal_of)
    if lock_source:
        source_query = source_query.with_for_update()
    source = database.session.execute(source_query).scalar_one_or_none()
    if not source:
        raise ValueError(f"La factura origen '{reversal_of}' no existe.")
    if source.docstatus != 1:
        raise ValueError(f"La factura origen '{reversal_of}' no esta aprobada.")
    if customer_id and source.customer_id != customer_id:
        raise ValueError(f"La factura origen '{reversal_of}' no pertenece al mismo cliente.")
    if company and source.company != company:
        raise ValueError(f"La factura origen '{reversal_of}' no pertenece a la misma compania.")
    if document_type == "sales_credit_note" and note_amount is not None:
        from cacao_accounting.document_flow.payment import compute_outstanding_amount

        outstanding = compute_outstanding_amount(source, as_of_date=posting_date)
        if note_amount > outstanding:
            raise ValueError(
                f"La nota de credito ({note_amount}) excede el saldo pendiente de la factura origen ({outstanding})."
            )
