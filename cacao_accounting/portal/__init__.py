# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Módulo de Portal para Clientes y Proveedores (Cloud Mode únicamente)."""

from typing import Any

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required
from cacao_accounting.i18n import _
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting.database import (
    CompanyParty,
    Party,
    database,
    SalesInvoice,
    SalesOrder,
    SalesQuotation,
    DeliveryNote,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseQuotation,
    PurchaseReceipt,
    SalesInvoiceItem,
    SalesOrderItem,
    SalesQuotationItem,
    DeliveryNoteItem,
    PurchaseInvoiceItem,
    PurchaseOrderItem,
    PurchaseQuotationItem,
    PurchaseReceiptItem,
)

portal = Blueprint("portal", __name__, template_folder="templates")
PORTAL_PAGE_SIZE = 100


def _is_user_admin() -> bool:
    """Retorna verdadero si el usuario actual es administrador."""
    if getattr(current_user, "classification", None) == "admin":
        return True
    from cacao_accounting.auth.roles import tiene_rol

    return tiene_rol(current_user.id, "admin")


def check_portal_access(role_name: str) -> None:
    """Verifica que el usuario tenga el rol del portal correspondiente o sea administrador.

    El acceso del tercero exige además que ``Party.is_active`` y su vínculo
    ``CompanyParty.is_active`` para la compañía del usuario sigan vigentes. La
    desactivación revoca nuevas consultas, incluso sobre documentos históricos,
    sin modificar la evidencia almacenada (#1919). Un rol administrativo
    adicional no exime al perfil de portal de esa revocación.
    """
    if is_desktop_mode():
        abort(403)
    if current_user.is_portal_customer or current_user.is_portal_supplier:
        _require_active_party_link()
        if role_name == "customer" and current_user.is_portal_customer:
            return
        if role_name == "supplier" and current_user.is_portal_supplier:
            return
        abort(403)
    if _is_user_admin():
        return
    abort(403)


def active_party_link_exists() -> bool:
    """Indica si el tercero del usuario y su vínculo con la compañía están vigentes."""
    party_id = current_user.party_id
    company = current_user.company
    if not party_id or not company:
        return False
    party = database.session.get(Party, party_id)
    if party is None or not party.is_active:
        return False
    link = database.session.execute(
        database.select(CompanyParty.id).where(
            CompanyParty.company == company,
            CompanyParty.party_id == party_id,
            CompanyParty.is_active.is_(True),
        )
    ).scalar_one_or_none()
    return link is not None


def portal_home_for_user() -> str | None:
    """Devuelve la ruta del portal aplicable con el mismo criterio que el guard.

    Evita redirigir al portal a un usuario cuya clasificación lo habilita pero
    cuyo tercero o vínculo fue revocado, que terminaría en 403 (#1920). Un rol
    administrativo adicional no convierte al perfil de portal en administrador
    para este flujo.
    """
    if is_desktop_mode():
        return None
    if current_user.is_portal_customer or current_user.is_portal_supplier:
        if not active_party_link_exists():
            return None
        if current_user.is_portal_customer:
            return "/portal/customer"
        return "/portal/supplier"
    return None


def _require_active_party_link() -> None:
    """Rechaza el acceso del portal si el tercero o su vínculo están inactivos."""
    if not active_party_link_exists():
        abort(403)


# ─── PORTAL DE CLIENTES ───────────────────────────────────────────────────────


def _portal_page(query, ordering: Any, page: int = 1) -> tuple[list[Any], int]:
    """Devuelve la página solicitada y el total real de resultados (#1564).

    El portal pagina cada listado en bloques de ``PORTAL_PAGE_SIZE``; el total
    se calcula sobre la consulta completa para que la plantilla pueda mostrar
    el conjunto real y la navegación entre páginas.
    """
    total = database.session.execute(database.select(database.func.count()).select_from(query.subquery())).scalar_one()
    offset = (page - 1) * PORTAL_PAGE_SIZE
    rows = database.session.execute(query.order_by(ordering).offset(offset).limit(PORTAL_PAGE_SIZE)).scalars().all()
    return list(rows), int(total)


def _portal_page_number() -> int:
    """Página solicitada por la consulta, acotada a valores positivos."""
    return max(1, request.args.get("page", 1, type=int) or 1)


def _portal_page_count(totals: dict[str, int]) -> int:
    """Cantidad de páginas necesarias para el listado más extenso."""
    mayor = max(totals.values(), default=0)
    return max(1, (mayor + PORTAL_PAGE_SIZE - 1) // PORTAL_PAGE_SIZE)


@portal.route("/customer")
@login_required
def customer_dashboard():
    """Dashboard principal del portal de clientes."""
    check_portal_access("customer")
    pid = current_user.party_id

    q_invoices = database.select(SalesInvoice).filter_by(
        document_type="sales_invoice", company=current_user.company, docstatus=1
    )
    q_orders = database.select(SalesOrder).filter_by(company=current_user.company, docstatus=1)
    q_quotations = database.select(SalesQuotation).filter_by(company=current_user.company, docstatus=1)
    q_deliveries = database.select(DeliveryNote).filter_by(company=current_user.company, docstatus=1)

    portal_pid = pid if current_user.is_portal_customer or current_user.is_portal_supplier else None
    if portal_pid:
        q_invoices = q_invoices.filter_by(customer_id=portal_pid)
        q_orders = q_orders.filter_by(customer_id=portal_pid)
        q_quotations = q_quotations.filter_by(customer_id=portal_pid)
        q_deliveries = q_deliveries.filter_by(customer_id=portal_pid)

    page = _portal_page_number()
    invoices, total_invoices = _portal_page(q_invoices, SalesInvoice.posting_date.desc(), page)
    orders, total_orders = _portal_page(q_orders, SalesOrder.posting_date.desc(), page)
    quotations, total_quotations = _portal_page(q_quotations, SalesQuotation.posting_date.desc(), page)
    deliveries, total_deliveries = _portal_page(q_deliveries, DeliveryNote.posting_date.desc(), page)
    totals = {
        "invoices": total_invoices,
        "orders": total_orders,
        "quotations": total_quotations,
        "deliveries": total_deliveries,
    }
    page_count = _portal_page_count(totals)
    page_label = _("Página %(page)s de %(pages)s") % {"page": page, "pages": page_count}

    return render_template(
        "portal/customer_dashboard.html",
        invoices=invoices,
        orders=orders,
        quotations=quotations,
        deliveries=deliveries,
        totals=totals,
        page_size=PORTAL_PAGE_SIZE,
        page=page,
        page_count=page_count,
        page_label=page_label,
        has_next=page < page_count,
        titulo=_("Portal de Clientes"),
    )


@portal.route("/customer/invoice/<invoice_id>")
@login_required
def customer_invoice(invoice_id):
    """Detalle de factura de venta para el cliente."""
    check_portal_access("customer")
    invoice = database.session.execute(
        database.select(SalesInvoice).filter_by(id=invoice_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not invoice:
        abort(404)

    if current_user.is_portal_customer and invoice.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice_id)).all()
    return render_template("portal/invoice_detail.html", registro=invoice, items=items, role="customer")


@portal.route("/customer/order/<order_id>")
@login_required
def customer_order(order_id):
    """Detalle de orden de venta para el cliente."""
    check_portal_access("customer")
    order = database.session.execute(
        database.select(SalesOrder).filter_by(id=order_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not order:
        abort(404)

    if current_user.is_portal_customer and order.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=order_id)).all()
    return render_template("portal/order_detail.html", registro=order, items=items, role="customer")


@portal.route("/customer/quotation/<quotation_id>")
@login_required
def customer_quotation(quotation_id):
    """Detalle de cotización de venta para el cliente."""
    check_portal_access("customer")
    quotation = database.session.execute(
        database.select(SalesQuotation).filter_by(id=quotation_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not quotation:
        abort(404)

    if current_user.is_portal_customer and quotation.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=quotation_id)).all()
    return render_template("portal/quotation_detail.html", registro=quotation, items=items, role="customer")


@portal.route("/customer/delivery/<delivery_id>")
@login_required
def customer_delivery(delivery_id):
    """Detalle de nota de entrega para el cliente."""
    check_portal_access("customer")
    delivery = database.session.execute(
        database.select(DeliveryNote).filter_by(id=delivery_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not delivery:
        abort(404)

    if current_user.is_portal_customer and delivery.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=delivery_id)).all()
    return render_template("portal/delivery_detail.html", registro=delivery, items=items, role="customer")


# ─── PORTAL DE PROVEEDORES ────────────────────────────────────────────────────


@portal.route("/supplier")
@login_required
def supplier_dashboard():
    """Dashboard principal del portal de proveedores."""
    check_portal_access("supplier")
    pid = current_user.party_id

    q_invoices = database.select(PurchaseInvoice).filter_by(
        document_type="purchase_invoice", company=current_user.company, docstatus=1
    )
    q_notes = database.select(PurchaseInvoice).filter(
        PurchaseInvoice.company == current_user.company,
        PurchaseInvoice.docstatus == 1,
        PurchaseInvoice.document_type.in_(["purchase_credit_note", "purchase_debit_note"]),
    )
    q_orders = database.select(PurchaseOrder).filter_by(company=current_user.company, docstatus=1)
    q_quotations = database.select(PurchaseQuotation).filter_by(company=current_user.company, docstatus=1)
    q_receipts = database.select(PurchaseReceipt).filter_by(company=current_user.company, docstatus=1)

    portal_pid = pid if current_user.is_portal_customer or current_user.is_portal_supplier else None
    if portal_pid:
        q_invoices = q_invoices.filter_by(supplier_id=portal_pid)
        q_notes = q_notes.filter_by(supplier_id=portal_pid)
        q_orders = q_orders.filter_by(supplier_id=portal_pid)
        q_quotations = q_quotations.filter_by(supplier_id=portal_pid)
        q_receipts = q_receipts.filter_by(supplier_id=portal_pid)

    page = _portal_page_number()
    invoices, total_invoices = _portal_page(q_invoices, PurchaseInvoice.posting_date.desc(), page)
    notes, total_notes = _portal_page(q_notes, PurchaseInvoice.posting_date.desc(), page)
    orders, total_orders = _portal_page(q_orders, PurchaseOrder.posting_date.desc(), page)
    quotations, total_quotations = _portal_page(q_quotations, PurchaseQuotation.posting_date.desc(), page)
    receipts, total_receipts = _portal_page(q_receipts, PurchaseReceipt.posting_date.desc(), page)
    totals = {
        "invoices": total_invoices,
        "notes": total_notes,
        "orders": total_orders,
        "quotations": total_quotations,
        "receipts": total_receipts,
    }
    page_count = _portal_page_count(totals)
    page_label = _("Página %(page)s de %(pages)s") % {"page": page, "pages": page_count}

    return render_template(
        "portal/supplier_dashboard.html",
        invoices=invoices,
        notes=notes,
        orders=orders,
        quotations=quotations,
        receipts=receipts,
        totals=totals,
        page_size=PORTAL_PAGE_SIZE,
        page=page,
        page_count=page_count,
        page_label=page_label,
        has_next=page < page_count,
        titulo=_("Portal de Proveedores"),
    )


@portal.route("/supplier/invoice/<invoice_id>")
@portal.route("/supplier/note/<invoice_id>")
@login_required
def supplier_invoice(invoice_id):
    """Detalle de factura de compra para el proveedor."""
    check_portal_access("supplier")
    invoice = database.session.execute(
        database.select(PurchaseInvoice).filter_by(id=invoice_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not invoice:
        abort(404)

    if current_user.is_portal_supplier and invoice.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(
        database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id, is_superseded=False)
    ).all()
    return render_template("portal/invoice_detail.html", registro=invoice, items=items, role="supplier")


@portal.route("/supplier/order/<order_id>")
@login_required
def supplier_order(order_id):
    """Detalle de orden de compra para el proveedor."""
    check_portal_access("supplier")
    order = database.session.execute(
        database.select(PurchaseOrder).filter_by(id=order_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not order:
        abort(404)

    if current_user.is_portal_supplier and order.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=order_id)).all()
    return render_template("portal/order_detail.html", registro=order, items=items, role="supplier")


@portal.route("/supplier/quotation/<quotation_id>")
@login_required
def supplier_quotation(quotation_id):
    """Detalle de solicitud de cotización para el proveedor."""
    check_portal_access("supplier")
    quotation = database.session.execute(
        database.select(PurchaseQuotation).filter_by(id=quotation_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not quotation:
        abort(404)

    if current_user.is_portal_supplier and quotation.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=quotation_id)
    ).all()
    return render_template("portal/quotation_detail.html", registro=quotation, items=items, role="supplier")


@portal.route("/supplier/receipt/<receipt_id>")
@login_required
def supplier_receipt(receipt_id):
    """Detalle de recepción de compra para el proveedor."""
    check_portal_access("supplier")
    receipt = database.session.execute(
        database.select(PurchaseReceipt).filter_by(id=receipt_id, company=current_user.company, docstatus=1)
    ).scalar_one_or_none()
    if not receipt:
        abort(404)

    if current_user.is_portal_supplier and receipt.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(
        database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id, is_superseded=False)
    ).all()
    return render_template("portal/receipt_detail.html", registro=receipt, items=items, role="supplier")
