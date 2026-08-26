# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Módulo de Portal para Clientes y Proveedores (Cloud Mode únicamente)."""

from flask import Blueprint, abort, render_template, flash
from flask_login import current_user, login_required
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting.database import (
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
    """Verifica que el usuario tenga el rol del portal correspondiente o sea administrador."""
    if is_desktop_mode():
        abort(403)
    if _is_user_admin():
        return

    if role_name == "customer" and current_user.classification == "customer":
        if current_user.party_id and current_user.company:
            return
        flash("Usuario de portal sin cliente asignado.", "danger")
        abort(403)

    if role_name == "supplier" and current_user.classification == "supplier":
        if current_user.party_id and current_user.company:
            return
        flash("Usuario de portal sin proveedor asignado.", "danger")
        abort(403)

    abort(403)


# ─── PORTAL DE CLIENTES ───────────────────────────────────────────────────────


@portal.route("/customer")
@login_required
def customer_dashboard():
    """Dashboard principal del portal de clientes."""
    check_portal_access("customer")
    pid = current_user.party_id
    is_admin = _is_user_admin()

    q_invoices = database.select(SalesInvoice).filter_by(
        document_type="sales_invoice", company=current_user.company, docstatus=1
    )
    q_orders = database.select(SalesOrder).filter_by(company=current_user.company, docstatus=1)
    q_quotations = database.select(SalesQuotation).filter_by(company=current_user.company, docstatus=1)
    q_deliveries = database.select(DeliveryNote).filter_by(company=current_user.company, docstatus=1)

    if not is_admin and pid:
        q_invoices = q_invoices.filter_by(customer_id=pid)
        q_orders = q_orders.filter_by(customer_id=pid)
        q_quotations = q_quotations.filter_by(customer_id=pid)
        q_deliveries = q_deliveries.filter_by(customer_id=pid)

    invoices = (
        database.session.execute(q_invoices.order_by(SalesInvoice.posting_date.desc()).limit(PORTAL_PAGE_SIZE)).scalars().all()
    )
    orders = (
        database.session.execute(q_orders.order_by(SalesOrder.posting_date.desc()).limit(PORTAL_PAGE_SIZE)).scalars().all()
    )
    quotations = (
        database.session.execute(q_quotations.order_by(SalesQuotation.posting_date.desc()).limit(PORTAL_PAGE_SIZE))
        .scalars()
        .all()
    )
    deliveries = (
        database.session.execute(q_deliveries.order_by(DeliveryNote.posting_date.desc()).limit(PORTAL_PAGE_SIZE))
        .scalars()
        .all()
    )

    return render_template(
        "portal/customer_dashboard.html",
        invoices=invoices,
        orders=orders,
        quotations=quotations,
        deliveries=deliveries,
        titulo="Portal de Clientes",
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

    is_admin = _is_user_admin()
    if not is_admin and invoice.customer_id != current_user.party_id:
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

    is_admin = _is_user_admin()
    if not is_admin and order.customer_id != current_user.party_id:
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

    is_admin = _is_user_admin()
    if not is_admin and quotation.customer_id != current_user.party_id:
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

    is_admin = _is_user_admin()
    if not is_admin and delivery.customer_id != current_user.party_id:
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
    is_admin = _is_user_admin()

    q_invoices = database.select(PurchaseInvoice).filter_by(
        document_type="purchase_invoice", company=current_user.company, docstatus=1
    )
    q_notes = database.select(PurchaseInvoice).filter(
        PurchaseInvoice.company == current_user.company,
        PurchaseInvoice.docstatus == 1,
        PurchaseInvoice.document_type.in_(["purchase_credit_note", "purchase_debit_note", "purchase_return"]),
    )
    q_orders = database.select(PurchaseOrder).filter_by(company=current_user.company, docstatus=1)
    q_quotations = database.select(PurchaseQuotation).filter_by(company=current_user.company, docstatus=1)
    q_receipts = database.select(PurchaseReceipt).filter_by(company=current_user.company, docstatus=1)

    if not is_admin and pid:
        q_invoices = q_invoices.filter_by(supplier_id=pid)
        q_notes = q_notes.filter_by(supplier_id=pid)
        q_orders = q_orders.filter_by(supplier_id=pid)
        q_quotations = q_quotations.filter_by(supplier_id=pid)
        q_receipts = q_receipts.filter_by(supplier_id=pid)

    invoices = (
        database.session.execute(q_invoices.order_by(PurchaseInvoice.posting_date.desc()).limit(PORTAL_PAGE_SIZE))
        .scalars()
        .all()
    )
    notes = (
        database.session.execute(q_notes.order_by(PurchaseInvoice.posting_date.desc()).limit(PORTAL_PAGE_SIZE)).scalars().all()
    )
    orders = (
        database.session.execute(q_orders.order_by(PurchaseOrder.posting_date.desc()).limit(PORTAL_PAGE_SIZE)).scalars().all()
    )
    quotations = (
        database.session.execute(q_quotations.order_by(PurchaseQuotation.posting_date.desc()).limit(PORTAL_PAGE_SIZE))
        .scalars()
        .all()
    )
    receipts = (
        database.session.execute(q_receipts.order_by(PurchaseReceipt.posting_date.desc()).limit(PORTAL_PAGE_SIZE))
        .scalars()
        .all()
    )

    return render_template(
        "portal/supplier_dashboard.html",
        invoices=invoices,
        notes=notes,
        orders=orders,
        quotations=quotations,
        receipts=receipts,
        titulo="Portal de Proveedores",
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

    is_admin = _is_user_admin()
    if not is_admin and invoice.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id)).all()
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

    is_admin = _is_user_admin()
    if not is_admin and order.supplier_id != current_user.party_id:
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

    is_admin = _is_user_admin()
    if not is_admin and quotation.supplier_id != current_user.party_id:
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

    is_admin = _is_user_admin()
    if not is_admin and receipt.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id)).all()
    return render_template("portal/receipt_detail.html", registro=receipt, items=items, role="supplier")
