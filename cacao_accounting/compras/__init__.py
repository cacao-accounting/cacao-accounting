# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Compras."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
import json
from datetime import date
from decimal import Decimal
from logging import getLogger
from typing import Any

from sqlalchemy import update

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from cacao_accounting.exceptions import flash_error
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from flask_login import current_user, login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.compras.purchase_reconciliation_service import (
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
    purchase_request_comparison_is_closed,
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
    CompanyParty,
    Book,
    DocumentRelation,
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
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
    PurchaseNegotiationRound,
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
    TaxTemplate,
    UOM,
    database,
)

# Librerias de terceros
from ulid import ULID

# Recursos locales
from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_create, log_submit, log_update
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document
from cacao_accounting.contabilidad.budget_service import BudgetError
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.decorators import (  # noqa: F401
    exige_acceso_compania,
    exige_acceso_compania_cualquiera,
    modulo_activo,
    verifica_acceso as verifica_acceso,
    verifica_permiso,
)
from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
    get_create_actions,
    refresh_source_caches_for_target,
    require_line_relations,
    revert_relations_for_target,
    validate_submit_prerequisites,
)
from cacao_accounting.document_flow.context import company_currency, effective_currency, validate_immutable_header
from cacao_accounting.document_flow.repository import consumed_qty_for_source, has_active_source_relations
from cacao_accounting.document_flow.service import _relation_qty_in_base_uom
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.fiscal_persistence_service import (
    calculate_document_total_with_taxes,
    persist_document_fiscal_snapshot,
)
from cacao_accounting.list_filters import apply_list_filters
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
    draft_party_company_settings_rows,
    party_company_settings_rows,
    upsert_party_company_settings_rows,
)
from cacao_accounting.version import APPNAME
from cacao_accounting.logistics import copy_logistics, logistics_values

logger = getLogger(__name__)


def _logistics_values(source: Any = None, form: Any = None) -> dict[str, Any]:
    """Obtiene datos logísticos desde un documento o un formulario."""
    return logistics_values(source, form, terms_field="purchase_terms")


def _copy_logistics(target: Any, source: Any = None, form: Any = None) -> None:
    """Copia datos logísticos a un documento destino."""
    copy_logistics(target, source, form, terms_field="purchase_terms")


def _landed_cost_snapshot(form: Any = None, source: Any = None) -> str | None:
    """Valida y serializa los cargos landed cost estimados."""
    raw = form.get("landed_cost_estimates_json") if form is not None else None
    if not raw and source is not None:
        raw = getattr(source, "landed_cost_estimates_json", None)
    if not raw:
        return None
    try:
        charges = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Los landed costs estimados deben ser un JSON válido.") from exc
    if not isinstance(charges, list):
        raise ValueError("Los landed costs estimados deben ser una lista.")
    for charge in charges:
        if not isinstance(charge, dict) or not charge.get("concept"):
            raise ValueError("Cada landed cost estimado requiere un concepto.")
        try:
            amount = Decimal(str(charge.get("amount", "0")))
        except Exception as exc:
            raise ValueError("El importe de un landed cost estimado no es válido.") from exc
        if amount < 0:
            raise ValueError("Los landed costs estimados no pueden ser negativos.")
    return json.dumps(charges, ensure_ascii=False, separators=(",", ":"))


# < --------------------------------------------------------------------------------------------- >
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

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    PURCHASE_INVOICE: FACTURA_DE_COMPRA,
    PURCHASE_DEBIT_NOTE: "Nota de Débito de Compra",
    PURCHASE_CREDIT_NOTE: "Nota de Crédito de Compra",
    PURCHASE_RETURN: "Devolución de Compra",
    IMPORT_LANDED_COST: IMPORT_LANDED_COST_LABEL,
}


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


def _party_or_404(party_id: str) -> Party:
    """Obtiene un tercero por tipo o aborta."""
    party = database.session.execute(database.select(Party).filter_by(id=party_id, is_supplier=True)).scalar_one_or_none()
    if not party:
        abort(404)
    return party


def _paginate_list(model, search_fields, query=None, *, include_status: bool = True, access_modules=("purchases",)):
    """Pagina un listado aplicando los filtros GET comunes."""
    base_query = query if query is not None else database.select(model)
    if hasattr(model, "company"):
        company = request.args.get("company")
        if company:
            exige_acceso_compania_cualquiera(access_modules, company, "consultar")
            base_query = base_query.filter(model.company == company)
        elif not getattr(current_user, "classification", None) == "admin":
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


def _require_purchase_document_access(document: Any, action: str = "consultar") -> None:
    """Require company-scoped access before exposing a purchase document."""
    company = getattr(document, "company", None)
    if not company:
        abort(404)
    if action == "consultar" and isinstance(document, (PurchaseOrder, PurchaseReceipt)):
        exige_acceso_compania_cualquiera(("purchases", "inventory"), str(company), action)
        return
    module = "inventory" if isinstance(document, PurchaseReceipt) else "purchases"
    exige_acceso_compania(module, str(company), action)


def _require_requested_purchase_company_access(document: Any, action: str = "editar") -> None:
    """Validate access when an edit attempts to move a document to another company."""
    requested_company = request.form.get("company")
    if requested_company and requested_company != getattr(document, "company", None):
        module = "inventory" if isinstance(document, PurchaseReceipt) else "purchases"
        exige_acceso_compania(module, requested_company, action)


def _can_manage_purchase_receipts() -> bool:
    """Return whether the current user has Inventory write permission."""
    module_id = obtener_id_modulo_por_nombre("inventory")
    permissions = Permisos(modulo=module_id, usuario=current_user.id)
    return bool(permissions.administrador or permissions.crear)


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
            solicitud = PurchaseRequest(
                requested_by=getattr(current_user, "user", None) or str(current_user.id),
                company=request.form.get("company") or None,
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
            solicitud.total = total
            solicitud.base_total = total
            solicitud.grand_total = total
            log_create(solicitud)
            database.session.commit()
            flash("Solicitud de compra creada correctamente.", "success")
            return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=solicitud.id))
        except (IdentifierConfigurationError, DocumentFlowError) as exc:
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
    can_close = registro.docstatus == 1 and registro.status != "closed" and purchase_request_comparison_is_closed(registro)
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
    """Close a purchase request after all its lines have closed comparisons."""
    registro = database.session.get(PurchaseRequest, request_id)
    if not registro:
        abort(404)
    exige_acceso_compania("purchases", registro.company, "autorizar")
    if registro.docstatus != 1 or registro.status == "closed":
        abort(400)
    if not purchase_request_comparison_is_closed(registro):
        flash("La Solicitud de Compra requiere comparativos cerrados para todas sus líneas.", "danger")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COMPRA, request_id=request_id))
    before = {"status": registro.status}
    registro.status = "closed"
    log_update(registro, before=before, after={"status": registro.status})
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
            registro.total = total
            registro.base_total = total
            registro.grand_total = total
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
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
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


def _supplier_quotation_origin_ids() -> tuple[str | None, str | None]:
    """Obtiene los identificadores de origen para la cotizacion de proveedor."""
    from_request_id = request.args.get("from_request") or request.form.get("from_request")
    from_rfq_id = request.args.get("from_rfq") or request.form.get("from_rfq")
    return from_request_id, from_rfq_id


def _create_supplier_quotation_from_request():
    """Crea una cotizacion de proveedor a partir del formulario enviado."""
    try:
        from_request_id, from_rfq_id = _supplier_quotation_origin_ids()
        if from_request_id and from_rfq_id:
            raise DocumentFlowError("No se pueden combinar dos documentos origen.", 400)
        source = _supplier_quotation_origin(from_request_id, from_rfq_id)
        company, transaction_currency = _validate_supplier_quotation_header(source)
        negotiation_round_id = request.form.get("negotiation_round_id") or None
        if negotiation_round_id:
            negotiation_round = database.session.get(PurchaseNegotiationRound, negotiation_round_id)
            if (
                not negotiation_round
                or negotiation_round.purchase_quotation_id != from_rfq_id
                or negotiation_round.status != "open"
            ):
                negotiation_round_id = None
        supplier_id = request.form.get("supplier_id") or None
        supplier = database.session.get(Party, supplier_id) if supplier_id else None
        posting_date = _parse_date(request.form.get("posting_date"))
        cotizacion = SupplierQuotation(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            purchase_quotation_id=from_rfq_id or None,
            negotiation_round_id=negotiation_round_id,
            company=company,
            transaction_currency=transaction_currency,
            base_currency=company_currency(company),
            posting_date=posting_date,
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        _copy_logistics(cotizacion, source, request.form)
        cotizacion.landed_cost_estimates_json = _landed_cost_snapshot(form=request.form, source=source)
        database.session.add(cotizacion)
        database.session.flush()
        assign_document_identifier(
            document=cotizacion,
            entity_type="supplier_quotation",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _qty, total = _save_supplier_quotation_items(cotizacion.id)
        cotizacion.total = total
        cotizacion.base_total = total
        cotizacion.grand_total = total
        log_create(cotizacion)
        database.session.commit()
        flash("Cotización de proveedor creada correctamente.", "success")
        return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=cotizacion.id))
    except (IdentifierConfigurationError, DocumentFlowError, PurchaseSourcingError, ValueError) as exc:
        database.session.rollback()
        flash_error(exc)
    return None


def _supplier_quotation_origin(
    from_request_id: str | None, from_rfq_id: str | None
) -> PurchaseRequest | PurchaseQuotation | None:
    """Load and authorize the approved source of a supplier quotation."""
    source = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
    source = database.session.get(PurchaseQuotation, from_rfq_id) if from_rfq_id else source
    _validate_supplier_quotation_origin(source)
    return source


def _validate_supplier_quotation_origin(source: PurchaseRequest | PurchaseQuotation | None) -> None:
    """Require an approved, company-accessible source when one is supplied."""
    if source is None:
        return
    if source.docstatus != 1:
        raise DocumentFlowError("El documento origen debe estar aprobado.", 400)
    _require_purchase_document_access(source, "consultar")


def _validate_supplier_quotation_header(source: PurchaseRequest | PurchaseQuotation | None) -> tuple[str | None, str | None]:
    """Resolve immutable company and currency values from a quotation source."""
    _validate_supplier_quotation_origin(source)
    return _validate_purchase_flow_header(source)


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


def _supplier_quotation_selected_company(choices: list[tuple[str, str]]) -> str | None:
    """Resuelve la compañía seleccionada para la cotización de proveedor."""
    return request.values.get("company") or (choices[0][0] if choices else None)


def _purchase_quotation_selected_company(choices: list[tuple[str, str]]) -> str | None:
    """Resuelve la compañía seleccionada para la solicitud de cotización."""
    return request.values.get("company") or (choices[0][0] if choices else None)


def _supplier_quotation_supplier_choices() -> list[tuple[str, str]]:
    """Construye el listado de proveedores para el formulario."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _supplier_quotation_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Carga catálogos reutilizados por la cotización de proveedor."""
    items_disponibles = [
        {"code": item[0].code, "name": item[0].name, "uom": item[0].default_uom}
        for item in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [
        {"code": uom[0].code, "name": uom[0].name} for uom in database.session.execute(database.select(UOM)).all()
    ]
    return items_disponibles, uoms_disponibles


def _supplier_quotation_transaction_config(
    *,
    form_key: str,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    initial_source_type: str,
    initial_header: dict[str, str] | None = None,
    initial_lines: list[dict[str, str]] | None = None,
    available_source_types: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """Construye la configuración transaccional compartida de cotización."""
    transaction_config: dict[str, object] = {
        "formKey": form_key,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "availableSourceTypes": available_source_types
        or [
            {"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)},
            {"value": "purchase_quotation", "label": _(LABEL_SOLICITUD_COTIZACION)},
        ],
        "initialSourceType": initial_source_type,
    }
    if initial_header:
        transaction_config["initialHeader"] = initial_header
    if initial_lines:
        transaction_config["initialLines"] = initial_lines
    return transaction_config


def _supplier_quotation_initial_source_type(from_request_id: str | None, from_rfq_id: str | None) -> str:
    """Resolve the initial source type for supplier quotations."""
    if from_request_id:
        return "purchase_request"
    if from_rfq_id:
        return "purchase_quotation"
    return ""


def _supplier_quotation_sources(
    from_request_id: str | None,
    from_rfq_id: str | None,
) -> tuple[PurchaseRequest | None, PurchaseQuotation | None]:
    """Resuelve los documentos origen de la cotización de proveedor."""
    solicitud_origen = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
    rfq_origen = database.session.get(PurchaseQuotation, from_rfq_id) if from_rfq_id else None
    return solicitud_origen, rfq_origen


def _handle_supplier_quotation_update(registro: SupplierQuotation, form: dict, quotation_id: str):
    """Maneja la actualizacion de una cotizacion de proveedor desde el formulario POST."""
    before_state = _capture_purchase_state(registro)
    supplier_id = form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = form.get("company") or None
    registro.posting_date = _parse_date(form.get("posting_date"))
    registro.remarks = form.get("remarks")
    _copy_logistics(registro, form=form)
    registro.landed_cost_estimates_json = _landed_cost_snapshot(form=form)
    for item in database.session.execute(
        database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _qty, total = _save_supplier_quotation_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Cotizacion de proveedor actualizada correctamente."), "success")
    return redirect(url_for(ROUTE_COMPRAS_COTIZACION_PROVEEDOR, quotation_id=quotation_id))


def _handle_supplier_create(
    form: dict,
    selected_company: str | None,
    company_choices: list,
    formulario: Any,
    titulo: str,
):
    """Maneja la creacion de un nuevo proveedor desde el formulario POST."""
    proveedor = Party(
        code=str(ULID()),
        is_supplier=True,
        name=form.get("name") or "",
        comercial_name=form.get("comercial_name"),
        tax_id=form.get("tax_id"),
        is_active=form.get("is_active", "on") is not None,
    )
    try:
        database.session.add(proveedor)
        apply_party_group(proveedor, form.get("party_group_id") or None, role="supplier")
        apply_party_profile(proveedor, form)
        database.session.flush()
        proveedor.code = generate_party_code(proveedor.id, selected_company, "supplier")
        upsert_party_company_settings_rows(proveedor.id, "supplier", form)
        database.session.commit()
        return redirect("/buying/supplier/list")
    except ValueError as exc:
        database.session.rollback()
        company_settings_rows = draft_party_company_settings_rows("supplier", form)
        flash_error(exc)
    return render_template(
        COMPRAS_PROVEEDOR_NUEVO_TEMPLATE,
        form=formulario,
        titulo=titulo,
        company_choices=company_choices,
        selected_company=selected_company,
        company_settings_rows=company_settings_rows,
        group_label=party_group_label(form.get("party_group_id") or None),
    )


def _handle_supplier_update(
    proveedor: Party,
    form: dict,
    selected_company: str | None,
    company_choices: list,
    formulario: Any,
    titulo: str,
):
    """Maneja la actualizacion de un proveedor existente desde el formulario POST."""
    try:
        proveedor.name = form.get("name") or ""
        proveedor.comercial_name = form.get("comercial_name") or None
        proveedor.tax_id = form.get("tax_id") or None
        proveedor.is_active = form.get("is_active") is not None
        apply_party_group(proveedor, form.get("party_group_id") or None, role="supplier")
        apply_party_profile(proveedor, form)
        upsert_party_company_settings_rows(proveedor.id, "supplier", form)
        database.session.commit()
        flash(_("Proveedor actualizado correctamente."), "success")
        return redirect(url_for(ROUTE_COMPRAS_PROVEEDOR, supplier_id=proveedor.id))
    except ValueError as exc:
        database.session.rollback()
        company_settings_rows = draft_party_company_settings_rows("supplier", form)
        flash_error(exc)
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
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
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
    titulo = "Comparativo de Ofertas - " + APPNAME
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
            return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison.id))
        except (IdentifierConfigurationError, ValueError, SQLAlchemyError) as exc:
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
    return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison_id))


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
    return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison_id))


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
    return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison_id))


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
    except (ValueError, DocumentFlowError, IdentifierConfigurationError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
    return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison_id))


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
        return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison.id))
    try:
        round_record = open_purchase_order_comparison_round(comparison, purchase_request, participant_ids, current_user.id)
        database.session.commit()
        flash("Nueva ronda de negociación abierta.", "success")
        return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison.id, round_id=round_record.id))
    except (ValueError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for("compras.compras_comparativo_ordenes", comparison_id=comparison.id))


def _comparison_item_key(item: PurchaseOrderItem) -> tuple[str | None, ...]:
    """Build the commercial identity used to match repeated order lines."""
    return (
        item.item_code,
        item.uom,
        str(item.qty_in_base_uom) if item.qty_in_base_uom is not None else None,
        item.warehouse,
        item.description,
    )


def _comparison_item_at_occurrence(
    items: list[PurchaseOrderItem], base_item: PurchaseOrderItem, occurrence: int
) -> PurchaseOrderItem | None:
    """Return the matching line by commercial identity and occurrence."""
    matching_items = [item for item in items if _comparison_item_key(item) == _comparison_item_key(base_item)]
    return matching_items[occurrence] if occurrence < len(matching_items) else None


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
            titulo="Comparativo de Ofertas - " + (request_comparison.document_no or request_comparison.id or ""),
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
        titulo="Comparativo de Ofertas - " + (comparison.id or ""),
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
    titulo = "Comparativo de Ofertas - " + (registro.document_no or rfq_id)
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


def _award_lines_by_supplier(award_id: str) -> dict[str, list[PurchaseQuotationAwardItem]]:
    """Group awarded lines by supplier quotation."""
    award_lines = (
        database.session.execute(database.select(PurchaseQuotationAwardItem).filter_by(award_id=award_id)).scalars().all()
    )
    if not award_lines:
        raise PurchaseSourcingError("La adjudicación no contiene líneas.")
    groups: dict[str, list[PurchaseQuotationAwardItem]] = {}
    for line in award_lines:
        groups.setdefault(line.supplier_quotation_id, []).append(line)
    return groups


def _add_award_order_lines(order: PurchaseOrder, lines: list[PurchaseQuotationAwardItem]) -> tuple[Decimal, Decimal]:
    """Create order lines and source relations for one supplier quotation."""
    total_qty = Decimal("0")
    total = Decimal("0")
    for award_line in lines:
        source = database.session.get(PurchaseQuotationItem, award_line.purchase_quotation_item_id)
        line = PurchaseOrderItem(
            purchase_order_id=order.id,
            item_code=award_line.item_code,
            item_name=source.item_name if source else award_line.item_code,
            qty=award_line.qty,
            uom=source.uom if source else None,
            rate=award_line.rate,
            amount=award_line.amount,
        )
        database.session.add(line)
        database.session.flush()
        create_document_relation(
            source_type="supplier_quotation",
            source_id=award_line.supplier_quotation_id,
            source_item_id=award_line.supplier_quotation_item_id,
            target_type="purchase_order",
            target_id=order.id,
            target_item_id=line.id,
            qty=award_line.qty,
            uom=line.uom,
            rate=award_line.rate,
            amount=award_line.amount,
        )
        total_qty += award_line.qty
        total += award_line.amount
    return total_qty, total


def _create_purchase_orders_from_award(award: PurchaseQuotationAward) -> list[PurchaseOrder]:
    """Create one draft purchase order per supplier from an award."""
    claimed = database.session.execute(
        update(PurchaseQuotationAward)
        .where(PurchaseQuotationAward.id == award.id, PurchaseQuotationAward.status == "finalized")
        .values(status="used")
    )
    if getattr(claimed, "rowcount", 0) != 1:
        raise PurchaseSourcingError("Solo un comparativo finalizado puede colocar Órdenes de Compra.")
    groups = _award_lines_by_supplier(award.id)
    orders: list[PurchaseOrder] = []
    rfq = database.session.get(PurchaseQuotation, award.purchase_quotation_id)
    for supplier_quotation_id, lines in groups.items():
        quotation = database.session.get(SupplierQuotation, supplier_quotation_id)
        if not quotation:
            raise PurchaseSourcingError("La cotización adjudicada ya no existe.")
        order = PurchaseOrder(
            supplier_id=quotation.supplier_id,
            supplier_name=quotation.supplier_name,
            company=award.company,
            posting_date=rfq.posting_date if rfq else None,
            purchase_award_id=award.id,
            transaction_currency=quotation.transaction_currency,
            docstatus=0,
        )
        _copy_logistics(order, quotation or rfq)
        order.landed_cost_estimates_json = _landed_cost_snapshot(source=quotation or rfq)
        database.session.add(order)
        database.session.flush()
        assign_document_identifier(
            document=order,
            entity_type="purchase_order",
            posting_date_raw=order.posting_date,
            naming_series_id=None,
        )
        total_qty, total = _add_award_order_lines(order, lines)
        order.total_qty = total_qty
        order.total = total
        order.net_total = total
        order.grand_total = total
        order.exchange_rate = _purchase_exchange_rate(order.company, order.posting_date, order.transaction_currency)
        order.base_total = (total * order.exchange_rate).quantize(Decimal("0.0001"))
        log_create(order)
        orders.append(order)
    return orders


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


def _create_purchase_request_relation_from_supplier_quotation(
    source_id: str | None,
    source_item_id: str | None,
    target_id: str,
    target_item_id: str,
    qty: Decimal,
    uom: str | None,
    rate: Decimal,
    amount: Decimal,
) -> None:
    """Propagate a supplier quotation line relation back to its purchase request."""
    if not source_id or not source_item_id:
        return
    supplier_relation = database.session.execute(
        database.select(DocumentRelation).filter_by(
            source_type="purchase_quotation",
            target_type="supplier_quotation",
            target_id=source_id,
            target_item_id=source_item_id,
        )
    ).scalar_one_or_none()
    if not supplier_relation:
        return
    request_relation = database.session.execute(
        database.select(DocumentRelation).filter_by(
            source_type="purchase_request",
            target_type="purchase_quotation",
            target_id=supplier_relation.source_id,
            target_item_id=supplier_relation.source_item_id,
        )
    ).scalar_one_or_none()
    if not request_relation:
        return
    create_document_relation(
        source_type="purchase_request",
        source_id=request_relation.source_id,
        source_item_id=request_relation.source_item_id,
        target_type="purchase_order",
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
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            item_obj = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
            if not item_obj:
                raise DocumentFlowError(f"El item {item_code} no existe.", 400)
            if not item_obj.is_active or not item_obj.is_purchase_item:
                raise DocumentFlowError(f"El item {item_code} no está habilitado para compra.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = PurchaseOrderItem(
                purchase_order_id=order_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            linea.qty_in_base_uom = _relation_qty_in_base_uom(linea, qty, uom)
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_order", order_id, linea.id, qty, uom, rate, amount)
            _create_purchase_request_relation_from_supplier_quotation(
                request.form.get(f"source_id_{i}"),
                request.form.get(f"source_item_id_{i}"),
                order_id,
                linea.id,
                qty,
                uom,
                rate,
                amount,
            )
            total_qty += qty
            total += amount
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_purchase_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una solicitud de cotización de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            uom = request.form.get(f"uom_{i}") or None
            linea = PurchaseQuotationItem(
                purchase_quotation_id=quotation_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=Decimal("0"),
                amount=Decimal("0"),
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_quotation", quotation_id, linea.id, qty, uom, Decimal("0"), Decimal("0"))
            total_qty += qty
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_purchase_request_items(request_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una solicitud de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            linea = PurchaseRequestItem(
                purchase_request_id=request_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=request.form.get(f"uom_{i}") or None,
                rate=Decimal("0"),
                amount=Decimal("0"),
            )
            database.session.add(linea)
            total_qty += qty
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_supplier_quotation_items(quotation_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una cotización de proveedor desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            linea = SupplierQuotationItem(
                supplier_quotation_id=quotation_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "supplier_quotation", quotation_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _save_purchase_receipt_items(receipt_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una recepción de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
            rate = _form_decimal(f"rate_{i}", "0")
            amount = _line_amount(i)
            uom = request.form.get(f"uom_{i}") or None
            warehouse_code = (
                request.form.get(f"warehouse_{i}") or request.form.get("to_warehouse") or request.form.get("warehouse") or None
            )
            _validate_receipt_warehouse(warehouse_code)
            linea = PurchaseReceiptItem(
                purchase_receipt_id=receipt_id,
                item_code=item_code,
                item_name=request.form.get(f"item_name_{i}", ""),
                qty=qty,
                uom=uom,
                rate=rate,
                amount=amount,
                warehouse=warehouse_code,
            )
            database.session.add(linea)
            database.session.flush()
            _create_line_relation(i, "purchase_receipt", receipt_id, linea.id, qty, uom, rate, amount)
            total_qty += qty
            total += amount
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _validate_receipt_warehouse(warehouse_code: str | None) -> None:
    """Valida la bodega indicada en una recepción."""
    if not warehouse_code:
        return
    from cacao_accounting.database import Warehouse

    warehouse = database.session.execute(database.select(Warehouse).filter_by(code=warehouse_code)).scalar_one_or_none()
    if warehouse is None:
        raise DocumentFlowError(f"Almacén '{warehouse_code}' no encontrado.", 404)
    if not warehouse.is_active:
        raise DocumentFlowError(f"Almacén '{warehouse_code}' está inactivo.", 409)


def _save_purchase_invoice_items(invoice_id: str) -> tuple[Decimal, Decimal]:
    """Guarda las líneas de una factura de compra desde el formulario."""
    i = 0
    total_qty = Decimal("0")
    total = Decimal("0")
    line_count = 0
    while request.form.get(f"item_code_{i}"):
        item_code = request.form.get(f"item_code_{i}", "")
        if item_code.strip():
            qty = _form_decimal(f"qty_{i}", "1")
            if qty <= 0:
                raise DocumentFlowError(f"La cantidad del item {item_code} debe ser mayor a cero.", 400)
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
            line_count += 1
        i += 1
    if line_count == 0:
        raise DocumentFlowError(DOCUMENT_REQUIRES_LINE_MSG, 400)
    return total_qty, total


def _persist_purchase_invoice_fiscal_snapshot(invoice: PurchaseInvoice) -> None:
    """Persist the editable fiscal snapshot captured in the form."""
    persist_document_fiscal_snapshot(
        company=str(invoice.company or ""),
        document_type=invoice.document_type or PURCHASE_INVOICE,
        document_id=invoice.id,
        currency=None,
        tax_lines=request.form.get("tax_lines_payload"),
        tax_summary=request.form.get("tax_summary_payload"),
    )


def _build_purchase_order_transaction_config(items_disponibles, uoms_disponibles, source_origen, initial_source_type):
    transaction_config = {
        "formKey": FORMKEY_PURCHASE_ORDER,
        "viewKey": "draft",
        "items": items_disponibles,
        "uoms": uoms_disponibles,
        "availableSourceTypes": [
            {"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)},
            {"value": "purchase_quotation", "label": _(LABEL_SOLICITUD_COTIZACION)},
            {"value": "supplier_quotation", "label": _("Cotización de Proveedor")},
        ],
        "initialSourceType": initial_source_type,
    }
    if source_origen:
        source_currency = effective_currency(source_origen)
        transaction_config["initialHeader"] = {
            "company": source_origen.company or "",
            "currency": source_currency or "",
            "transaction_currency": source_currency or "",
            "party": getattr(source_origen, "supplier_id", None) or "",
            "party_label": getattr(source_origen, "supplier_name", None) or "",
            "posting_date": str(date.today()),
        }
    return transaction_config


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


def _purchase_order_source_type(request_id: str | None, rfq_id: str | None, quotation_id: str | None) -> str:
    """Resuelve el tipo de documento fuente de una orden de compra."""
    if request_id:
        return "purchase_request"
    if rfq_id:
        return "purchase_quotation"
    if quotation_id:
        return "supplier_quotation"
    return ""


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


def _purchase_order_selected_company(default_company: str | None) -> str | None:
    """Resuelve la compañía seleccionada para la orden de compra."""
    return request.values.get("company") or default_company


def _purchase_order_supplier_choices() -> list[tuple[str, str]]:
    """Construye el listado de proveedores para órdenes de compra."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _purchase_order_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Carga catálogos reutilizados por órdenes de compra."""
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items_disponibles, uoms_disponibles


def _purchase_order_transaction_config(
    *,
    registro: PurchaseOrder,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    columns: list[dict[str, str | bool | int]] | None = None,
) -> dict[str, object]:
    """Construye la configuración transaccional para la edición de órdenes de compra."""
    lineas = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=registro.id)).scalars()
    return {
        "formKey": FORMKEY_PURCHASE_ORDER,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "columns": columns or [],
        "availableSourceTypes": [
            {"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)},
            {"value": "supplier_quotation", "label": _("Cotización de Proveedor")},
        ],
        "initialHeader": {
            "company": registro.company or "",
            "posting_date": str(registro.posting_date or ""),
            "remarks": registro.remarks or "",
            "party": registro.supplier_id or "",
            "party_label": registro.supplier_name or "",
            **_logistics_values(registro),
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


def _purchase_order_context(form: dict):
    """Validate sourcing data and resolve the context for a purchase order."""
    award_id = form.get("purchase_award_id") or None
    exception_reason = form.get("comparison_exception_reason") or None
    sourcing_config = get_purchase_sourcing_config()
    source = None
    for model, key in (
        (PurchaseRequest, "from_request"),
        (PurchaseQuotation, "from_rfq"),
        (SupplierQuotation, "from_supplier_quotation"),
    ):
        source_id = form.get(key)
        if source_id:
            source = database.session.get(model, source_id)
            break
    direct_supplier_quotation = isinstance(source, SupplierQuotation) and bool(source.purchase_quotation_id)
    if sourcing_config.require_comparison and not award_id:
        if not direct_supplier_quotation and not (is_purchase_manager(current_user.id) and exception_reason):
            flash_error(
                PurchaseSourcingError(
                    "La Orden de Compra debe originarse en un comparativo o incluir una excepción autorizada."
                )
            )
            return None
    award = database.session.get(PurchaseQuotationAward, award_id) if award_id else None
    if award_id and (not award or award.status != "finalized"):
        flash_error(PurchaseSourcingError("La adjudicación seleccionada no es válida."))
        return None
    supplier_id = form.get("supplier_id") or None
    if award and award.company != (form.get("company") or None):
        flash_error(PurchaseSourcingError("La adjudicación no pertenece a la compañía seleccionada."))
        return None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    posting_date = _parse_date(form.get("posting_date"))
    comparison_open = False
    if isinstance(source, SupplierQuotation) and source.purchase_quotation_id:
        comparison_open = (
            database.session.execute(
                database.select(PurchaseQuotationAward.id)
                .where(PurchaseQuotationAward.purchase_quotation_id == source.purchase_quotation_id)
                .where(PurchaseQuotationAward.status.in_(("finalized", "used", "closed")))
            ).scalar_one_or_none()
            is None
        )
    company, transaction_currency = _validate_purchase_flow_header(source, form)
    transaction_currency = transaction_currency or form.get("transaction_currency") or form.get("currency") or None
    return award_id, supplier_id, supplier, posting_date, company, transaction_currency, comparison_open


def _create_purchase_order_from_request(form: dict):
    """Crea una orden de compra desde el formulario enviado."""
    context = _purchase_order_context(form)
    if context is None:
        return None
    award_id, supplier_id, supplier, posting_date, company, transaction_currency, comparison_open = context
    orden = PurchaseOrder(
        supplier_id=supplier_id,
        supplier_name=supplier.name if supplier else None,
        company=company,
        posting_date=posting_date,
        remarks=form.get("remarks"),
        transaction_currency=transaction_currency,
        base_currency=company_currency(company),
        purchase_award_id=award_id,
        docstatus=0,
    )
    source = None
    for model, key in (
        (PurchaseRequest, "from_request"),
        (PurchaseQuotation, "from_rfq"),
        (SupplierQuotation, "from_supplier_quotation"),
    ):
        if form.get(key):
            source = database.session.get(model, form.get(key))
            break
    _copy_logistics(orden, source, form)
    orden.landed_cost_estimates_json = _landed_cost_snapshot(form=form, source=source)
    try:
        database.session.add(orden)
        database.session.flush()
        assign_document_identifier(
            document=orden,
            entity_type="purchase_order",
            posting_date_raw=posting_date,
            naming_series_id=form.get("naming_series") or None,
        )
        total_qty, total = _save_purchase_order_items(orden.id)
        if source:
            source_type = {
                PurchaseRequest: "purchase_request",
                PurchaseQuotation: "purchase_quotation",
                SupplierQuotation: "supplier_quotation",
            }[type(source)]
            order_items = database.session.execute(
                database.select(PurchaseOrderItem).filter_by(purchase_order_id=orden.id)
            ).scalars().all()
            _validate_purchase_source_link(orden, source_type, source.id, order_items)
        orden.total_qty = total_qty
        orden.total = total
        orden.net_total = total
        orden.grand_total = total
        orden.exchange_rate = _purchase_exchange_rate(company, posting_date, transaction_currency)
        orden.base_total = (total * orden.exchange_rate).quantize(Decimal("0.0001"))
        log_create(orden)
        database.session.commit()
        flash("Orden de compra creada correctamente.", "success")
        if comparison_open:
            flash(
                "Advertencia: la orden se creó desde una cotización de proveedor mientras el comparativo sigue abierto. ",
                "warning",
            )
        return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=orden.id))
    except (IdentifierConfigurationError, DocumentFlowError, ValueError) as exc:
        database.session.rollback()
        flash_error(exc)
        return None


def _update_purchase_order_from_request(registro: PurchaseOrder):
    """Actualiza una orden de compra desde el formulario enviado."""
    before_state = _capture_purchase_state(registro)
    revert_relations_for_target("purchase_order", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("purchase_order", registro.id)
    supplier_id = request.form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    _copy_logistics(registro, form=request.form)
    registro.landed_cost_estimates_json = _landed_cost_snapshot(form=request.form)
    registro.transaction_currency = request.form.get("transaction_currency") or None
    for item in database.session.execute(
        database.select(PurchaseOrderItem).filter_by(purchase_order_id=registro.id)
    ).scalars():
        database.session.delete(item)
    total_qty, total = _save_purchase_order_items(registro.id)
    registro.total_qty = total_qty
    registro.total = total
    registro.net_total = total
    registro.grand_total = total
    registro.exchange_rate = _purchase_exchange_rate(registro.company, registro.posting_date, registro.transaction_currency)
    registro.base_total = (total * registro.exchange_rate).quantize(Decimal("0.0001"))
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Orden de compra actualizada correctamente."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_ORDEN_COMPRA, order_id=registro.id))


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


def _validate_purchase_flow_header(source: object | None, form_data: Any | None = None) -> tuple[str | None, str | None]:
    """Validate immutable company/currency values for a downstream purchase document."""
    values = form_data or request.form
    company = values.get("company") or None
    currency = values.get("currency") or values.get("transaction_currency") or None
    return validate_immutable_header(source, company, currency)


def _purchase_quotation_origin_id() -> str | None:
    """Obtiene el documento origen para una solicitud de cotización."""
    return request.args.get("from_request") or request.form.get("from_request")


def _purchase_quotation_supplier_choices() -> list[tuple[str, str]]:
    """Construye las opciones de proveedores para solicitudes de cotización."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _purchase_quotation_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Carga los catálogos de ítems y unidades usados en solicitudes de cotización."""
    items = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items, uoms


def _purchase_quotation_transaction_config(
    *,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    initial_source_type: str,
    initial_header: dict[str, str] | None = None,
    columns: list[dict[str, str | bool | int]] | None = None,
) -> dict[str, Any]:
    """Construye la configuración transaccional para solicitudes de cotización."""
    transaction_config: dict[str, Any] = {
        "formKey": FORMKEY_PURCHASE_QUOTATION,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "showPricing": False,
        "columns": columns or [],
        "availableSourceTypes": [{"value": "purchase_request", "label": _(LABEL_SOLICITUD_COMPRA)}],
        "initialSourceType": initial_source_type,
    }
    if initial_header:
        transaction_config["initialHeader"] = initial_header
    return transaction_config


def _create_purchase_quotation_from_request():
    """Crea una solicitud de cotización a partir del formulario enviado."""
    try:
        supplier_id = request.form.get("supplier_id") or None
        supplier = database.session.get(Party, supplier_id) if supplier_id else None
        posting_date = _parse_date(request.form.get("posting_date"))
        from_request_id = _purchase_quotation_origin_id()
        source = database.session.get(PurchaseRequest, from_request_id) if from_request_id else None
        company, transaction_currency = _validate_purchase_flow_header(source)
        cotizacion = PurchaseQuotation(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            company=company,
            transaction_currency=transaction_currency,
            base_currency=company_currency(company),
            posting_date=posting_date,
            remarks=request.form.get("remarks"),
            docstatus=0,
        )
        _copy_logistics(cotizacion, form=request.form)
        database.session.add(cotizacion)
        database.session.flush()
        assign_document_identifier(
            document=cotizacion,
            entity_type="purchase_quotation",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _qty, total = _save_purchase_quotation_items(cotizacion.id)
        if source:
            quotation_items = database.session.execute(
                database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=cotizacion.id)
            ).scalars().all()
            _validate_purchase_source_link(cotizacion, "purchase_request", source.id, quotation_items)
        cotizacion.total = total
        cotizacion.base_total = total
        cotizacion.grand_total = total
        log_create(cotizacion)
        database.session.commit()
        flash("Solicitud de cotización creada correctamente.", "success")
        return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=cotizacion.id))
    except (IdentifierConfigurationError, DocumentFlowError) as exc:
        database.session.rollback()
        flash_error(exc)
    return None


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


def _handle_purchase_quotation_edit_post(registro):
    from cacao_accounting.database import Party

    before_state = _capture_purchase_state(registro)
    revert_relations_for_target("purchase_quotation", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("purchase_quotation", registro.id)
    supplier_id = request.form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")
    _copy_logistics(registro, form=request.form)
    for item in database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _qty, total = _save_purchase_quotation_items(registro.id)
    registro.total = total
    registro.base_total = total
    registro.grand_total = total
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Solicitud de cotizacion actualizada correctamente."), "success")
    return redirect(url_for(ROUTE_COMPRAS_SOLICITUD_COTIZACION, quotation_id=registro.id))


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
    duplicada.total = total
    duplicada.base_total = total
    duplicada.grand_total = total
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
            item_obj = (
                database.session.execute(database.select(Item).filter_by(code=item.item_code)).scalar_one_or_none()
            )
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
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
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


def _create_purchase_receipt_from_form():
    """Crea una recepción de compra desde el formulario."""
    try:
        posting_date = _parse_date(request.form.get("posting_date"))
        supplier_id = request.form.get("supplier_id") or None
        from_order = request.form.get("from_order") or None
        source = database.session.get(PurchaseOrder, from_order) if from_order else None
        company, transaction_currency = _validate_purchase_flow_header(source)
        supplier_id = supplier_id or getattr(source, "supplier_id", None)
        supplier = database.session.get(Party, supplier_id) if supplier_id else None
        receipt = PurchaseReceipt(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            company=company,
            posting_date=posting_date,
            purchase_order_id=from_order,
            remarks=request.form.get("remarks"),
            transaction_currency=transaction_currency,
            docstatus=0,
        )
        _copy_logistics(receipt, source, request.form)
        receipt.landed_cost_estimates_json = _landed_cost_snapshot(source=source, form=request.form)
        database.session.add(receipt)
        database.session.flush()
        assign_document_identifier(
            document=receipt,
            entity_type="purchase_receipt",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _total_qty, total = _save_purchase_receipt_items(receipt.id)
        if receipt.purchase_order_id:
            receipt_items = (
                database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id))
                .scalars()
                .all()
            )
            _validate_purchase_source_link(receipt, "purchase_order", receipt.purchase_order_id, receipt_items)
        _set_purchase_receipt_totals(receipt, total)
        log_create(receipt)
        database.session.commit()
        flash("Recepción de compra creada correctamente.", "success")
        return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt.id))
    except (DocumentFlowError, IdentifierConfigurationError, ValueError) as exc:
        database.session.rollback()
        flash_error(exc)
        return None


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
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
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


def _handle_purchase_receipt_edit_post(registro):
    before_state = _capture_purchase_state(registro)
    revert_relations_for_target("purchase_receipt", registro.id, reason="draft_edited")
    refresh_source_caches_for_target("purchase_receipt", registro.id)
    supplier_id = request.form.get("supplier_id") or None
    supplier = database.session.get(Party, supplier_id) if supplier_id else None
    registro.supplier_id = supplier_id
    registro.supplier_name = supplier.name if supplier else None
    registro.company = request.form.get("company") or None
    registro.posting_date = _parse_date(request.form.get("posting_date"))
    registro.remarks = request.form.get("remarks")

    for item in database.session.execute(
        database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=registro.id)
    ).scalars():
        database.session.delete(item)
    _total_qty, total = _save_purchase_receipt_items(registro.id)
    _set_purchase_receipt_totals(registro, total)
    after_state = _capture_purchase_state(registro)
    log_update(registro, before=before_state, after=after_state)
    database.session.commit()
    flash(_("Recepcion de compra actualizada correctamente."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=registro.id))


def _set_purchase_receipt_totals(receipt: PurchaseReceipt, total: Decimal) -> None:
    """Recalcula importes transaccionales y funcionales de una recepción."""
    receipt.total = receipt.grand_total = total
    receipt.base_currency = company_currency(receipt.company)
    receipt.exchange_rate = _purchase_exchange_rate(receipt.company, receipt.posting_date, receipt.transaction_currency)
    receipt.base_total = (total * receipt.exchange_rate).quantize(Decimal("0.0001"))


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
        )
        database.session.add(linea)
        total += item.amount or Decimal("0")
    duplicada.total = total
    duplicada.grand_total = total
    log_create(duplicada)
    database.session.commit()
    flash(_("Recepcion de compra duplicada como nuevo borrador."), "success")
    return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=duplicada.id))


def _validate_purchase_source_link(document: Any, source_type: str, source_id: str, items: list[Any] | None = None) -> Any:
    """Valida estado, compañía, proveedor y relaciones de un origen S2P."""
    source_models = {
        "purchase_request": PurchaseRequest,
        "purchase_quotation": PurchaseQuotation,
        "supplier_quotation": SupplierQuotation,
        "purchase_order": PurchaseOrder,
        "purchase_receipt": PurchaseReceipt,
    }
    source_model = source_models.get(source_type)
    source = database.session.get(source_model, source_id) if source_model else None
    if not source:
        raise ValueError(f"El documento origen '{source_id}' no existe.")
    if source.docstatus != 1:
        raise ValueError(f"El documento origen '{source_id}' debe estar aprobado.")
    if source.company != document.company:
        raise ValueError("El documento origen y el documento destino deben pertenecer a la misma compañía.")
    if source.supplier_id and source.supplier_id != document.supplier_id:
        raise ValueError("El documento origen y el documento destino deben pertenecer al mismo proveedor.")
    target_currency = getattr(document, "transaction_currency", None)
    if target_currency and effective_currency(source) != target_currency:
        raise ValueError("El documento origen y el documento destino deben usar la misma moneda.")
    if source_type == "purchase_receipt" and getattr(document, "purchase_order_id", None):
        if source.purchase_order_id != document.purchase_order_id:
            raise ValueError("La recepción no pertenece a la orden de compra indicada.")
    if items is not None:
        target_types = {
            PurchaseQuotation: "purchase_quotation",
            PurchaseOrder: "purchase_order",
            PurchaseReceipt: "purchase_receipt",
            PurchaseInvoice: "purchase_invoice",
        }
        require_line_relations(
            target_type=target_types[type(document)],
            target_id=document.id,
            source_type=source_type,
            source_id=source_id,
            items=list(items),
        )
    return source


def _validate_receipt_quantities_against_po(receipt_id: str) -> None:
    """Valida que las cantidades recibidas no excedan las ordenadas en la OC."""
    receipt = database.session.get(PurchaseReceipt, receipt_id)
    if receipt and receipt.purchase_order_id:
        receipt_items = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id))
            .scalars()
            .all()
        )
        _validate_purchase_source_link(receipt, "purchase_order", receipt.purchase_order_id, receipt_items)
        purchase_order = database.session.get(PurchaseOrder, receipt.purchase_order_id)
        if purchase_order and purchase_order.supplier_id != receipt.supplier_id:
            raise ValueError(_("El proveedor de la recepción no coincide con el proveedor de la orden de compra."))
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="purchase_receipt",
            target_id=receipt_id,
            status="active",
        )
    ).scalars()
    for rel in relations:
        if rel.source_type != "purchase_order" or not rel.source_item_id:
            continue
        po_item = database.session.get(PurchaseOrderItem, rel.source_item_id)
        if not po_item:
            continue
        consumed = consumed_qty_for_source(
            "purchase_order",
            rel.source_id,
            rel.source_item_id,
            "purchase_receipt",
            exclude_draft_targets=True,
            include_target_id=receipt_id,
        )
        ordered = (
            Decimal(str(po_item.qty_in_base_uom)) if po_item.qty_in_base_uom is not None else Decimal(str(po_item.qty or 0))
        )
        if consumed > ordered:
            raise ValueError(
                _("Sobre-recepción: cantidad recibida {} excede la ordenada {} para el artículo {}.").format(
                    consumed, ordered, po_item.item_code
                )
            )


def _validate_invoice_quantities_against_receipt(invoice_id: str) -> None:
    """Valida que las cantidades facturadas no excedan las recibidas/recepcionadas (3-way match).

    Cuando la factura se vincula directamente a una OC (sin recepción),
    valida contra la cantidad ordenada en la OC.
    """
    invoice = database.session.get(PurchaseInvoice, invoice_id)
    if invoice:
        invoice_items = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id))
            .scalars()
            .all()
        )
        if invoice.purchase_receipt_id:
            _validate_purchase_source_link(invoice, "purchase_receipt", invoice.purchase_receipt_id, invoice_items)
        elif invoice.purchase_order_id:
            _validate_purchase_source_link(invoice, "purchase_order", invoice.purchase_order_id, invoice_items)
    relations = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="purchase_invoice",
            target_id=invoice_id,
            status="active",
        )
    ).scalars()
    for rel in relations:
        if rel.source_item_id:
            _validate_purchase_invoice_relation(rel, invoice_id=invoice_id)


def _validate_purchase_invoice_relation(relation: DocumentRelation, invoice_id: str | None = None) -> None:
    """Valida una relación de factura de compra contra su fuente."""
    sources = {"purchase_receipt": (PurchaseReceiptItem, "recibida"), "purchase_order": (PurchaseOrderItem, "ordenada")}
    source = sources.get(relation.source_type)
    if not source or not relation.source_item_id:
        return
    item: Any = database.session.get(source[0], relation.source_item_id)
    if not item:
        return
    consumed = consumed_qty_for_source(
        relation.source_type,
        relation.source_id,
        relation.source_item_id,
        "purchase_invoice",
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


def _validate_invoice_requires_supplier_link(invoice_id: str) -> None:
    """Exige vínculo a recepción/orden según la configuración del proveedor.

    Si el proveedor no permite facturar sin recepción (o sin orden), la
    factura debe estar vinculada explícitamente, de lo contrario se omite
    la validación de 3-way match y se podrían facturar cantidades sin control.
    """
    invoice = database.session.get(PurchaseInvoice, invoice_id)
    if not invoice or not invoice.supplier_id:
        return
    cp = database.session.execute(
        database.select(CompanyParty).filter_by(party_id=invoice.supplier_id, company=invoice.company)
    ).scalar_one_or_none()
    if not cp:
        return
    relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="purchase_invoice", target_id=invoice_id, status="active")
        )
        .scalars()
        .all()
    )
    has_receipt_link = any(r.source_type == "purchase_receipt" for r in relations)
    has_order_link = any(r.source_type == "purchase_order" for r in relations)
    if not cp.allow_purchase_invoice_without_receipt and not has_receipt_link:
        raise ValueError(_("La factura debe estar vinculada a una recepción de compra según la configuración del proveedor."))
    if not cp.allow_purchase_invoice_without_order and not has_receipt_link and not has_order_link:
        raise ValueError(
            _("La factura debe estar vinculada a una orden o recepción de compra según la configuración del proveedor.")
        )


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
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Recepción de compra"):
            return redirect(url_for(COMPRAS_COMPRAS_RECEPCION, receipt_id=receipt_id))

        submit_document(registro)
        log_submit(registro)
        database.session.commit()
        flash("Recepcion de compra aprobada.", "success")
    except ValueError as exc:
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
        cancel_document(registro)
        revert_relations_for_target("purchase_receipt", receipt_id)
        refresh_source_caches_for_target("purchase_receipt", receipt_id)
        log_cancel(registro)
        database.session.commit()
        flash("Recepción de compra cancelada.", "warning")
    except PostingError as exc:
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
    document_type = _purchase_invoice_document_type(source_ids)
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


def _purchase_invoice_selected_company(choices: list[tuple[str, str]]) -> str | None:
    """Resolve the selected company for the purchase invoice."""
    return request.values.get("company") or (choices[0][0] if choices else None)


def _purchase_invoice_supplier_choices() -> list[tuple[str, str]]:
    """Build the supplier choices list for purchase invoices."""
    return [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party).filter_by(is_supplier=True)).all()
    ]


def _purchase_invoice_source_ids() -> dict[str, str | None]:
    """Get the source identifiers used by the purchase invoice."""
    return {
        "from_order_id": request.args.get("from_order") or request.form.get("from_order"),
        "from_receipt_id": request.args.get("from_receipt") or request.form.get("from_receipt"),
        "from_invoice_id": (
            request.args.get("from_invoice")
            or request.form.get("from_invoice")
            or request.args.get("from_return")
            or request.form.get("from_return")
        ),
    }


def _purchase_invoice_document_type(source_ids: dict[str, str | None]) -> str:
    """Resolve the document type for the purchase invoice."""
    doc_type = PURCHASE_INVOICE
    if source_ids.get("from_receipt_id"):
        doc_type = PURCHASE_RETURN
    elif source_ids.get("from_invoice_id"):
        doc_type = PURCHASE_CREDIT_NOTE
    return request.args.get("document_type") or request.form.get("document_type") or doc_type


def _purchase_invoice_sources(
    source_ids: dict[str, str | None],
) -> tuple[PurchaseOrder | None, PurchaseReceipt | None, PurchaseInvoice | None]:
    """Load the source documents for the purchase invoice."""
    orden_origen = database.session.get(PurchaseOrder, source_ids["from_order_id"]) if source_ids["from_order_id"] else None
    recepcion_origen = (
        database.session.get(PurchaseReceipt, source_ids["from_receipt_id"]) if source_ids["from_receipt_id"] else None
    )
    factura_origen = (
        database.session.get(PurchaseInvoice, source_ids["from_invoice_id"]) if source_ids["from_invoice_id"] else None
    )
    return orden_origen, recepcion_origen, factura_origen


def _purchase_invoice_catalogs() -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Load the catalogs reused by purchase invoices."""
    items_disponibles = [
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
    ]
    uoms_disponibles = [{"code": u[0].code, "name": u[0].name} for u in database.session.execute(database.select(UOM)).all()]
    return items_disponibles, uoms_disponibles


def _purchase_invoice_transaction_config(
    *,
    items: list[dict[str, str | None]],
    uoms: list[dict[str, str]],
    company_id: str | None = None,
) -> dict[str, object]:
    """Build the transaction configuration for purchase invoices."""
    return {
        "formKey": FORMKEY_PURCHASE_INVOICE,
        "viewKey": "draft",
        "items": items,
        "uoms": uoms,
        "availableSourceTypes": [
            {"value": "purchase_order", "label": _(LABEL_ORDEN_COMPRA)},
            {"value": "purchase_receipt", "label": _("Recepción de Compra")},
            {"value": "purchase_invoice", "label": _(LABEL_FACTURA_COMPRA_LONG)},
        ],
        "initialHeader": {
            "company": company_id or "",
            "posting_date": str(date.today()),
        },
    }


def _compute_base_amounts(amount: Decimal, exchange_rate: Decimal | None = None) -> tuple[Decimal, Decimal]:
    """S2P-09: Calcula monto base aplicando tipo de cambio. Retorna (base_amount, effective_rate)."""
    rate = exchange_rate if exchange_rate and exchange_rate > 0 else Decimal("1")
    return (amount * rate).quantize(Decimal("0.0001")), rate


def _purchase_exchange_rate(company: str | None, posting_date: Any, transaction_currency: str | None) -> Decimal:
    """S2P-09: Resuelve tipo de cambio para documento de compra.

    Devuelve ``Decimal("1")`` (tasa 1:1) cuando no se puede determinar la
    moneda base de la compania o no existe una tasa registrada, asumiendo la
    moneda de transaccion equivalente a la moneda local.
    """
    if not company or not transaction_currency:
        return Decimal("1")
    from cacao_accounting.database import Entity

    entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalars().first()
    if not entity or not entity.currency:
        return Decimal("1")
    if transaction_currency == entity.currency:
        return Decimal("1")
    from cacao_accounting.contabilidad.posting import _lookup_exchange_rate

    try:
        return _lookup_exchange_rate(transaction_currency, entity.currency, posting_date)
    except PostingError:
        logger.warning("No exchange rate found for %s -> %s on %s", transaction_currency, entity.currency, posting_date)
        return Decimal("1")


def _capture_purchase_state(registro: Any) -> dict[str, Any]:
    """CROSS-01: Captura estado de documento de compras para auditoría."""
    state = {
        "supplier_id": getattr(registro, "supplier_id", None),
        "company": getattr(registro, "company", None),
        "posting_date": str(getattr(registro, "posting_date", "")),
        "total": str(getattr(registro, "total", "")),
        "remarks": getattr(registro, "remarks", None),
    }

    from cacao_accounting.database import (
        PurchaseRequest,
        PurchaseRequestItem,
        PurchaseQuotation,
        PurchaseQuotationItem,
        SupplierQuotation,
        SupplierQuotationItem,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        PurchaseInvoice,
        PurchaseInvoiceItem,
    )

    mapping = {
        PurchaseRequest: (PurchaseRequestItem, "purchase_request_id"),
        PurchaseQuotation: (PurchaseQuotationItem, "purchase_quotation_id"),
        SupplierQuotation: (SupplierQuotationItem, "supplier_quotation_id"),
        PurchaseOrder: (PurchaseOrderItem, "purchase_order_id"),
        PurchaseReceipt: (PurchaseReceiptItem, "purchase_receipt_id"),
        PurchaseInvoice: (PurchaseInvoiceItem, "purchase_invoice_id"),
    }

    cls = type(registro)
    if cls in mapping:
        item_cls, fk_name = mapping[cls]
        from cacao_accounting.audit_trail_service import capture_lines_snapshot

        state["items"] = capture_lines_snapshot(registro, item_cls, fk_name)

    return state


def _validate_supplier_invoice_flags(
    supplier_id: str | None,
    company: str | None,
    purchase_order_id: str | None,
    purchase_receipt_id: str | None,
    document_type: str | None = None,
) -> None:
    """S2P-08: Valida flags del proveedor antes de crear/aprobar factura."""
    if not supplier_id or not company:
        return
    from cacao_accounting.database import CompanyParty

    settings = database.session.execute(
        database.select(CompanyParty).filter_by(party_id=supplier_id, company=company)
    ).scalar_one_or_none()
    if settings is None:
        # S2P-09: Validar strictamente cuando CompanyParty es None
        raise PostingError("No se encontró configuración de flags para el proveedor en la compañía.")
    has_order = bool(purchase_order_id)
    has_receipt = bool(purchase_receipt_id)
    if not has_order and not settings.allow_purchase_invoice_without_order:
        raise ValueError("El proveedor no permite crear facturas de compra sin orden de compra.")
    if not has_receipt and not settings.allow_purchase_invoice_without_receipt:
        raise ValueError("El proveedor no permite crear facturas de compra sin recepción.")

    if not has_order and document_type not in {PURCHASE_CREDIT_NOTE, PURCHASE_DEBIT_NOTE, PURCHASE_RETURN}:
        from cacao_accounting.compras.purchase_reconciliation_service import get_matching_config

        matching_config = get_matching_config(company)
        if matching_config.require_purchase_order:
            raise ValueError("La configuración de la compañía requiere una orden de compra para las facturas de compra.")


def _validate_purchase_tax_template(company: str, template_id: str | None, currency: str | None) -> None:
    """Validate a purchase tax template before storing it on the invoice."""
    if not template_id:
        return
    template = database.session.get(TaxTemplate, template_id)
    if template is None or not template.is_active:
        raise ValueError("La plantilla de impuestos seleccionada no existe o está inactiva.")
    if template.company not in (None, company):
        raise ValueError("La plantilla de impuestos debe pertenecer a la misma compañía.")
    if template.template_type != "buying":
        raise ValueError("La plantilla seleccionada no corresponde a compras.")
    if template.currency and currency and template.currency != currency:
        raise ValueError("La moneda de la plantilla no coincide con la moneda de la factura.")


def _validate_duplicate_supplier_invoice(
    supplier_id: str | None, supplier_invoice_no: str | None, exclude_id: str | None = None
) -> None:
    """S2P-24: Valida la duplicidad de supplier_invoice_no para un mismo proveedor.

    Valida que no exista otra factura de compra activa (no cancelada, docstatus != 2)
    con el mismo supplier_id y supplier_invoice_no.
    """
    if not supplier_id or not supplier_invoice_no:
        return
    supplier_invoice_no_cleaned = supplier_invoice_no.strip()
    if not supplier_invoice_no_cleaned:
        return

    supplier = database.session.get(Party, supplier_id, with_for_update=True)
    if supplier is None:
        raise ValueError("El proveedor indicado no existe.")

    stmt = database.select(PurchaseInvoice).filter(
        PurchaseInvoice.supplier_id == supplier_id,
        PurchaseInvoice.supplier_invoice_no == supplier_invoice_no_cleaned,
        PurchaseInvoice.docstatus != 2,
    )
    if exclude_id:
        stmt = stmt.filter(PurchaseInvoice.id != exclude_id)

    exists = database.session.execute(stmt).scalars().first()
    if exists:
        raise ValueError(
            _("El número de factura del proveedor '{}' ya está registrado para este proveedor en otra factura activa.").format(
                supplier_invoice_no_cleaned
            )
        )


def _validate_purchase_reversal_of(
    reversal_of: str,
    supplier_id: str | None,
    company: str | None,
    *,
    note_amount: Decimal | None = None,
    document_type: str | None = None,
    posting_date: date | None = None,
    lock_source: bool = False,
) -> None:
    """Valida origen y limite acumulado de una nota de credito de compra."""
    source_query = database.select(PurchaseInvoice).where(PurchaseInvoice.id == reversal_of)
    if lock_source:
        source_query = source_query.with_for_update()
    source = database.session.execute(source_query).scalar_one_or_none()
    if not source:
        raise ValueError(f"La factura origen '{reversal_of}' no existe.")
    if source.docstatus != 1:
        raise ValueError(f"La factura origen '{reversal_of}' no esta aprobada.")
    if supplier_id and source.supplier_id != supplier_id:
        raise ValueError(f"La factura origen '{reversal_of}' no pertenece al mismo proveedor.")
    if company and source.company != company:
        raise ValueError(f"La factura origen '{reversal_of}' no pertenece a la misma compañía.")
    if document_type == "purchase_credit_note" and note_amount is not None:
        from cacao_accounting.document_flow.payment import compute_outstanding_amount

        outstanding = compute_outstanding_amount(source, as_of_date=posting_date)
        if note_amount > outstanding:
            raise ValueError(
                f"La nota de credito ({note_amount}) excede el saldo pendiente de la factura origen ({outstanding})."
            )


def _persist_purchase_reversal_relation(invoice: PurchaseInvoice) -> None:
    """Persist the invoice-to-credit-note relation used by AP outstanding."""
    if invoice.document_type not in {"purchase_credit_note", "purchase_debit_note"} or not invoice.reversal_of:
        return
    target_type = invoice.document_type
    relation = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_type="purchase_invoice",
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

        source = database.session.get(PurchaseInvoice, invoice.reversal_of)
        if source:
            refresh_outstanding_amount_cache(source)
        return
    database.session.add(
        DocumentRelation(
            source_type="purchase_invoice",
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

    source = database.session.get(PurchaseInvoice, invoice.reversal_of)
    if source:
        refresh_outstanding_amount_cache(source)


def _has_active_purchase_reversal_notes(invoice_id: str) -> bool:
    """Indica si una factura tiene notas de crédito/débito activas downstream."""
    active_note = (
        database.select(DocumentRelation.id)
        .join(PurchaseInvoice, PurchaseInvoice.id == DocumentRelation.target_id)
        .where(
            DocumentRelation.source_type == "purchase_invoice",
            DocumentRelation.source_id == invoice_id,
            DocumentRelation.target_type.in_(("purchase_credit_note", "purchase_debit_note")),
            DocumentRelation.status == "active",
            PurchaseInvoice.docstatus != 2,
        )
    )
    return database.session.execute(active_note).scalar_one_or_none() is not None


def _create_purchase_invoice_from_request():
    """Create a purchase invoice from the submitted form."""
    try:
        document_type = request.form.get("document_type") or PURCHASE_INVOICE
        posting_date = _parse_date(request.form.get("posting_date"))
        supplier_id = request.form.get("supplier_id") or None
        company = request.form.get("company") or None
        from_order = request.form.get("from_order") or None
        from_receipt = request.form.get("from_receipt") or None
        if from_receipt and not from_order:
            receipt = database.session.get(PurchaseReceipt, from_receipt)
            if receipt:
                from_order = receipt.purchase_order_id
        from_invoice = request.form.get("from_invoice") or request.form.get("from_return") or None
        source_order, source_receipt, source_invoice = _purchase_invoice_sources(
            {
                "from_order_id": from_order,
                "from_receipt_id": from_receipt,
                "from_invoice_id": from_invoice,
            }
        )
        source = source_order or source_receipt or source_invoice
        if document_type in (PURCHASE_CREDIT_NOTE, PURCHASE_DEBIT_NOTE) and source_invoice is not None:
            from_order = from_order or source_invoice.purchase_order_id
            from_receipt = from_receipt or source_invoice.purchase_receipt_id
        company, transaction_currency = _validate_purchase_flow_header(source)
        tax_template_id = request.form.get("tax_template_id") or getattr(source, "tax_template_id", None)
        _validate_purchase_tax_template(company, tax_template_id, transaction_currency)
        supplier_id = supplier_id or getattr(source, "supplier_id", None)
        supplier = database.session.get(Party, supplier_id) if supplier_id else None
        transaction_currency = transaction_currency or request.form.get("transaction_currency") or None
        _validate_supplier_invoice_flags(supplier_id, company, from_order, from_receipt, document_type)
        _validate_duplicate_supplier_invoice(supplier_id, request.form.get("supplier_invoice_no"))
        reversal_of = (
            (request.form.get("from_invoice") or request.form.get("from_return"))
            if document_type in (PURCHASE_CREDIT_NOTE, PURCHASE_DEBIT_NOTE)
            else None
        )
        if reversal_of:
            _validate_purchase_reversal_of(reversal_of, supplier_id, company)
        factura = PurchaseInvoice(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else getattr(source, "supplier_name", None),
            company=company,
            posting_date=posting_date,
            supplier_invoice_no=request.form.get("supplier_invoice_no"),
            document_type=document_type,
            purchase_order_id=from_order,
            purchase_receipt_id=from_receipt,
            tax_template_id=tax_template_id,
            is_return=document_type in (PURCHASE_RETURN, PURCHASE_CREDIT_NOTE),
            reversal_of=reversal_of,
            remarks=request.form.get("remarks"),
            transaction_currency=transaction_currency,
            base_currency=company_currency(company),
            docstatus=0,
        )
        _copy_logistics(factura, source, request.form)
        factura.landed_cost_estimates_json = _landed_cost_snapshot(source=source, form=request.form)
        database.session.add(factura)
        database.session.flush()
        assign_document_identifier(
            document=factura,
            entity_type="purchase_invoice",
            posting_date_raw=posting_date,
            naming_series_id=request.form.get("naming_series") or None,
        )
        _total_qty, total = _save_purchase_invoice_items(factura.id)
        invoice_items = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=factura.id))
            .scalars()
            .all()
        )
        if factura.purchase_receipt_id:
            _validate_purchase_source_link(factura, "purchase_receipt", factura.purchase_receipt_id, invoice_items)
        elif factura.purchase_order_id:
            _validate_purchase_source_link(factura, "purchase_order", factura.purchase_order_id, invoice_items)
        factura.total = total
        # S2P-09: Aplicar tipo de cambio si transaction_currency está definida
        fx_rate = _purchase_exchange_rate(company, posting_date, transaction_currency)
        factura.exchange_rate = fx_rate
        base_total, _base = _compute_base_amounts(total, fx_rate)
        items = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=factura.id))
            .scalars()
            .all()
        )
        grand_total = calculate_document_total_with_taxes(factura, total, items, request.form.get("tax_summary_payload"))
        base_grand_total, _base2 = _compute_base_amounts(grand_total, fx_rate)
        factura.base_total = base_total
        factura.grand_total = grand_total
        factura.base_grand_total = base_grand_total
        factura.outstanding_amount = grand_total
        factura.base_outstanding_amount = base_grand_total
        if reversal_of:
            _validate_purchase_reversal_of(
                reversal_of,
                factura.supplier_id,
                factura.company,
                note_amount=grand_total,
                document_type=document_type,
                posting_date=factura.posting_date,
            )
        _persist_purchase_invoice_fiscal_snapshot(factura)
        log_create(factura)
        database.session.commit()
        flash("Factura de compra creada correctamente.", "success")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=factura.id))
    except (ValueError, DocumentFlowError) as exc:
        database.session.rollback()
        flash_error(exc)
    return None


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
        {"code": i[0].code, "name": i[0].name, "uom": i[0].default_uom}
        for i in database.session.execute(database.select(Item)).all()
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


def _handle_purchase_invoice_edit_post(registro):
    try:
        before_state = _capture_purchase_state(registro)
        revert_relations_for_target("purchase_invoice", registro.id, reason="draft_edited")
        refresh_source_caches_for_target("purchase_invoice", registro.id)
        registro.supplier_id = request.form.get("supplier_id") or None
        registro.company = request.form.get("company") or None
        purchase_order_id = request.form.get("from_order") or getattr(registro, "purchase_order_id", None)
        purchase_receipt_id = request.form.get("from_receipt") or getattr(registro, "purchase_receipt_id", None)
        _validate_supplier_invoice_flags(
            registro.supplier_id,
            registro.company,
            purchase_order_id,
            purchase_receipt_id,
            getattr(registro, "document_type", None),
        )
        _validate_duplicate_supplier_invoice(
            registro.supplier_id,
            request.form.get("supplier_invoice_no") or registro.supplier_invoice_no,
            exclude_id=registro.id,
        )
        registro.posting_date = _parse_date(request.form.get("posting_date"))
        registro.supplier_invoice_no = request.form.get("supplier_invoice_no") or registro.supplier_invoice_no
        if "tax_template_id" in request.form:
            registro.tax_template_id = request.form.get("tax_template_id") or None
        _validate_purchase_tax_template(
            registro.company,
            registro.tax_template_id,
            registro.transaction_currency,
        )
        registro.remarks = request.form.get("remarks")
        for item in database.session.execute(
            database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=registro.id)
        ).scalars():
            database.session.delete(item)
        _total_qty, total = _save_purchase_invoice_items(registro.id)
        fx_rate = _purchase_exchange_rate(registro.company, registro.posting_date, registro.transaction_currency)
        registro.exchange_rate = fx_rate
        base_total, _base = _compute_base_amounts(total, fx_rate)
        items = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=registro.id))
            .scalars()
            .all()
        )
        grand_total = calculate_document_total_with_taxes(registro, total, items, request.form.get("tax_summary_payload"))
        base_grand_total, _base2 = _compute_base_amounts(grand_total, fx_rate)
        registro.total = total
        registro.base_total = base_total
        registro.grand_total = grand_total
        registro.base_grand_total = base_grand_total
        registro.outstanding_amount = grand_total
        registro.base_outstanding_amount = base_grand_total
        _persist_purchase_invoice_fiscal_snapshot(registro)
        after_state = _capture_purchase_state(registro)
        log_update(registro, before=before_state, after=after_state)
        database.session.commit()
        flash(_("Factura de compra actualizada correctamente."), "success")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=registro.id))
    except ValueError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=registro.id))


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
        if registro.document_type in {"purchase_credit_note", "purchase_debit_note"}:
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

        submit_document(registro)
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
        cancel_document(registro)
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
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))
    flash(_("Factura de compra cancelada con reverso contable."), "warning")
    return redirect(url_for(COMPRAS_COMPRAS_FACTURA_COMPRA, invoice_id=invoice_id))


# < --------------------------------------------------------------------------------------------- >
# Import Landed Cost — Costos de Importacion
# < --------------------------------------------------------------------------------------------- >


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


def _resolve_supplier_from_invoice(from_invoice_id: str | None) -> tuple[str | None, str | None]:
    """Resuelve proveedor y nombre desde una factura de compra referenciada."""
    if not from_invoice_id:
        return None, None
    invoice = database.session.get(PurchaseInvoice, from_invoice_id)
    if not invoice:
        return None, None
    return invoice.supplier_id, invoice.supplier_name


def _parse_grid_rows_from_form(prefix: str, fields: list[str]) -> dict[str, dict[str, Any]]:
    """Parsea filas de una grilla HTML agrupadas por prefijo e índice."""
    grouped: dict[str, dict[str, Any]] = {}
    for key, value in request.form.items():
        for field in fields:
            token = f"{prefix}_{field}_"
            if key.startswith(token):
                idx = key[len(token) :]
                grouped.setdefault(idx, {})[field] = value
                break
    return grouped


def _save_import_landed_cost_items(registro: ImportLandedCost) -> Decimal:
    """Guarda las lineas de items del costo de importacion desde el formulario."""
    items_agrupados = _parse_grid_rows_from_form(
        "item",
        ["item_code", "item_name", "qty", "uom", "rate", "amount", "warehouse"],
    )
    total = Decimal("0")
    for data in items_agrupados.values():
        item_code = data.get("item_code", "").strip()
        if not item_code:
            continue
        qty = Decimal(str(data.get("qty", "1")))
        rate = Decimal(str(data.get("rate", "0")))
        amount = Decimal(str(data.get("amount", str(qty * rate))))
        total += amount
        database.session.add(
            ImportLandedCostItem(
                import_landed_cost_id=registro.id,
                item_code=item_code,
                item_name=data.get("item_name", ""),
                qty=qty,
                uom=data.get("uom", ""),
                rate=rate,
                amount=amount,
                base_rate=rate,
                base_amount=amount,
                warehouse=data.get("warehouse", ""),
            )
        )
    return total


def _save_import_landed_cost_charges(registro: ImportLandedCost) -> Decimal:
    """Guarda los cargos del costo de importacion desde el formulario."""
    cargos_agrupados = _parse_grid_rows_from_form("charge", ["concept", "amount", "charge_type", "account_id"])
    total = Decimal("0")
    for data in cargos_agrupados.values():
        concept = data.get("concept", "").strip()
        if not concept:
            continue
        amount = Decimal(str(data.get("amount", "0")))
        total += amount
        database.session.add(
            ImportLandedCostCharge(
                import_landed_cost_id=registro.id,
                concept=concept,
                charge_type=data.get("charge_type", "charge"),
                amount=amount,
                base_amount=amount,
                allocation_method=None,
                account_id=data.get("account_id"),
            )
        )
    return total


def _link_landed_cost_to_invoice(
    registro: ImportLandedCost,
    from_invoice_id: str,
    company: str,
) -> None:
    """Crea relaciones documentales entre la factura de compra y el costo de importacion."""
    from cacao_accounting.document_flow import create_document_relation

    invoice_items = (
        database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=from_invoice_id))
        .scalars()
        .all()
    )
    for item in invoice_items:
        our_item = (
            database.session.execute(
                database.select(ImportLandedCostItem).filter_by(import_landed_cost_id=registro.id, item_code=item.item_code)
            )
            .scalars()
            .first()
        )
        if our_item:
            create_document_relation(
                source_type="purchase_invoice",
                source_id=from_invoice_id,
                source_item_id=item.id,
                target_type="import_landed_cost",
                target_id=registro.id,
                target_item_id=our_item.id,
                qty=item.qty,
            )


def _create_import_landed_cost_from_request():
    """Crea un documento de costo de importacion desde el formulario."""
    company = request.form.get("company", "").strip()
    posting_date = _parse_date(request.form.get("posting_date"))
    from_invoice_id = request.form.get("from_invoice", "").strip() or None
    allocation_method = request.form.get("allocation_method", "by_value")
    remarks = request.form.get("remarks", "").strip()

    if not company or not posting_date:
        flash(_("Compania y fecha son obligatorios."), "danger")
        return None

    exige_acceso_compania("purchases", company, "crear")

    if from_invoice_id:
        source_invoice = database.session.get(PurchaseInvoice, from_invoice_id)
        if not source_invoice:
            flash(_("La factura de compra seleccionada no existe."), "danger")
            return None
        if source_invoice.company != company:
            flash(_("La factura de compra no pertenece a la compañía indicada."), "danger")
            return None
        if getattr(source_invoice, "docstatus", 0) != 1:
            flash(_("La factura de compra debe estar aprobada para capitalizar costos."), "danger")
            return None

    supplier_id, supplier_name = _resolve_supplier_from_invoice(from_invoice_id)

    registro = ImportLandedCost(
        company=company,
        posting_date=posting_date,
        document_date=posting_date,
        document_type=IMPORT_LANDED_COST,
        allocation_method=allocation_method,
        purchase_invoice_id=from_invoice_id,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        remarks=remarks,
    )
    database.session.add(registro)
    database.session.flush()

    assign_document_identifier(
        document=registro,
        entity_type="import_landed_cost",
        posting_date_raw=registro.posting_date,
        naming_series_id=request.form.get("naming_series") or None,
    )
    database.session.flush()

    total_item_amount = _save_import_landed_cost_items(registro)
    registro.total_base_amount = total_item_amount
    registro.grand_total = total_item_amount

    total_charges = _save_import_landed_cost_charges(registro)
    registro.total_charges_amount = total_charges
    registro.total_inventory_value = total_item_amount + total_charges
    registro.grand_total = total_item_amount + total_charges

    if from_invoice_id:
        _link_landed_cost_to_invoice(registro, from_invoice_id, company)

    database.session.commit()
    log_create(registro)
    flash(_("Costo de importacion creado exitosamente."), "success")
    return redirect(url_for(COMPRAS_IMPORT_LANDED_COST_ENDPOINT, landed_cost_id=registro.id))


def _get_import_landed_cost_items(landed_cost_id: str):
    """Devuelve las lineas de item de un costo de importacion."""
    return (
        database.session.execute(database.select(ImportLandedCostItem).filter_by(import_landed_cost_id=landed_cost_id))
        .scalars()
        .all()
    )


def _get_import_landed_cost_charges(landed_cost_id: str):
    """Devuelve los cargos de un costo de importacion."""
    return (
        database.session.execute(database.select(ImportLandedCostCharge).filter_by(import_landed_cost_id=landed_cost_id))
        .scalars()
        .all()
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
        submit_document(registro)
        log_submit(registro)
        database.session.commit()
    except PostingError as exc:
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
        cancel_document(registro)
        log_cancel(registro)
        revert_relations_for_target("import_landed_cost", landed_cost_id)
        refresh_source_caches_for_target("import_landed_cost", landed_cost_id)
        database.session.commit()
    except PostingError as exc:
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


def _group_items_by_budget_dimensions(items: Any, company: str, supplier_id: str | None) -> dict[tuple, Decimal]:
    """Agrupa montos por cuenta, centro y dimensiones analíticas."""
    from cacao_accounting.contabilidad.budget_service import BudgetService

    budget_service = BudgetService()
    groups: dict[tuple, Decimal] = {}
    for item in items:
        item_code = getattr(item, "item_code", None) or ""
        amount = getattr(item, "base_amount", None) or getattr(item, "amount", None) or Decimal("0")
        acc = budget_service.resolve_expense_account(item_code, company)
        cc = budget_service.resolve_cost_center(item_code, company, supplier_id)
        key = (
            acc.id if acc else "",
            cc.id if cc else "",
            getattr(item, "business_unit_id", None),
            getattr(item, "project_id", None),
        )
        groups[key] = groups.get(key, Decimal("0")) + Decimal(str(amount))
    return groups


def _resolve_document_no_for_budget(document_type: str, document_id: str) -> str | None:
    """Resuelve el numero de documento para el registro de auditoria presupuestaria."""
    model_map = {
        "purchase_request": "PurchaseRequest",
        "purchase_order": "PurchaseOrder",
    }
    model_name = model_map.get(document_type)
    if not model_name:
        return None
    from cacao_accounting.database import PurchaseOrder, PurchaseRequest

    model_classes = {"PurchaseRequest": PurchaseRequest, "PurchaseOrder": PurchaseOrder}
    doc = database.session.get(model_classes[model_name], document_id)
    return doc.document_no if doc else None


def _build_budget_exceeded_message(result: dict, action_policy: str) -> str:
    """Construye el mensaje de exceso de presupuesto segun la politica."""
    base = (
        f"El monto solicitado excede el presupuesto disponible.\n\n"
        f"Presupuesto:\n{result['budget']:,.2f}\n\n"
        f"Disponible:\n{result['available']:,.2f}\n\n"
        f"Solicitud:\n{result['requested']:,.2f}\n\n"
        f"Exceso:\n{result['excess']:,.2f}"
    )
    if action_policy == "block":
        return f"No es posible aprobar el documento.\n\n{base}"
    if action_policy == "notify":
        return f"{base}\n\nLa aprobacion continuara de acuerdo con la configuracion de la compania."
    return base


def _log_budget_exceeded(
    company: str,
    document_type: str,
    document_id: str,
    doc_no: str | None,
    posting_date: Any,
    acc_id: str,
    cc_id: str,
    result: dict,
    action_policy: str,
) -> None:
    """Registra un evento de exceso de presupuesto en la auditoria."""
    import json
    from datetime import datetime
    from cacao_accounting.database import AuditTrail
    from flask_login import current_user

    user_id = None
    user_name = "System"
    if current_user and current_user.is_authenticated:
        user_id = current_user.id
        user_name = getattr(current_user, "name", "") or current_user.user

    action_label = "Approval allowed" if action_policy != "block" else "Approval rejected"
    comment_str = f"Budget exceeded\n\nMode:\n{action_policy}\n\nAction:\n{action_label}"

    log_entry = AuditTrail(
        document_type=document_type,
        document_id=document_id,
        document_no=doc_no,
        company=company,
        action="budget_exceeded",
        actor_user_id=user_id,
        actor_name=user_name,
        comment=comment_str,
        timestamp=datetime.now(),
        changes_json=json.dumps(
            {
                "date": str(posting_date),
                "user": user_name,
                "company": company,
                "document": doc_no or document_id,
                "account_id": acc_id,
                "cost_center_id": cc_id,
                "budget": float(result["budget"]),
                "available": float(result["available"]),
                "requested": float(result["requested"]),
                "excess": float(result["excess"]),
                "action_executed": action_policy,
            },
            ensure_ascii=False,
        ),
    )
    database.session.add(log_entry)
    database.session.commit()


def _execute_budget_policy(action_policy: str, message: str) -> None:
    """Ejecuta la politica de control presupuestario (block/notify/do_nothing)."""
    if action_policy == "block":
        raise ValueError(message)
    if action_policy == "notify":
        flash(message, "warning")


def check_budget_control(
    company: str, posting_date: Any, supplier_id: str | None, document_id: str, document_type: str, items: Any
) -> None:
    """Valida el control presupuestario de las lineas del documento segun la politica de la compania."""
    from cacao_accounting.setup.repository import get_setup_value
    from cacao_accounting.contabilidad.budget_service import BudgetService

    enabled = get_setup_value(f"budget_control_enabled_{company}", "0") == "1"
    if not enabled:
        return

    action_policy = get_setup_value(f"budget_control_action_{company}", "do_nothing")
    groups = _group_items_by_budget_dimensions(items, company, supplier_id)
    budget_service = BudgetService()

    for (acc_id, cc_id, business_unit_id, project_id), total_requested in groups.items():
        if not acc_id:
            continue

        result = budget_service.validate_transaction(
            company=company,
            date_val=posting_date,
            account_id=acc_id,
            cost_center_id=cc_id,
            amount=total_requested,
            document_id=document_id,
            document_type=document_type,
            business_unit_id=business_unit_id,
            project_id=project_id,
        )

        if not result["exceeded"]:
            continue

        doc_no = _resolve_document_no_for_budget(document_type, document_id)
        _log_budget_exceeded(company, document_type, document_id, doc_no, posting_date, acc_id, cc_id, result, action_policy)
        message = _build_budget_exceeded_message(result, action_policy)
        _execute_budget_policy(action_policy, message)
