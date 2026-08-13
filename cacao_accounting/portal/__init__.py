# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Módulo de Portal para Clientes y Proveedores (Cloud Mode únicamente)."""

from functools import wraps
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


def _is_user_admin() -> bool:
    """Retorna verdadero si el usuario actual es administrador."""
    if getattr(current_user, "classification", None) == "admin":
        return True
    from cacao_accounting.auth.roles import tiene_rol

    return tiene_rol(current_user.id, "admin")


def requires_portal_role(role_name):
    """Verifica que el usuario tenga el rol del portal correspondiente o sea administrador."""

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if is_desktop_mode():
                abort(403)
            if _is_user_admin():
                return f(*args, **kwargs)

            if role_name == "customer" and current_user.is_portal_customer:
                if current_user.party_id:
                    return f(*args, **kwargs)
                flash("Usuario de portal sin cliente asignado.", "danger")
                abort(403)

            if role_name == "supplier" and current_user.is_portal_supplier:
                if current_user.party_id:
                    return f(*args, **kwargs)
                flash("Usuario de portal sin proveedor asignado.", "danger")
                abort(403)

            abort(403)

        return decorated_function

    return decorator


# ─── PORTAL DE CLIENTES ───────────────────────────────────────────────────────


@portal.route("/customer")
@requires_portal_role("customer")
def customer_dashboard():
    """Dashboard principal del portal de clientes."""
    pid = current_user.party_id
    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )

    q_invoices = database.select(SalesInvoice).filter_by(document_type="sales_invoice")
    q_orders = database.select(SalesOrder)
    q_quotations = database.select(SalesQuotation)
    q_deliveries = database.select(DeliveryNote)

    if not is_admin and pid:
        q_invoices = q_invoices.filter_by(customer_id=pid)
        q_orders = q_orders.filter_by(customer_id=pid)
        q_quotations = q_quotations.filter_by(customer_id=pid)
        q_deliveries = q_deliveries.filter_by(customer_id=pid)

    invoices = database.session.execute(q_invoices.order_by(SalesInvoice.posting_date.desc())).scalars().all()
    orders = database.session.execute(q_orders.order_by(SalesOrder.posting_date.desc())).scalars().all()
    quotations = database.session.execute(q_quotations.order_by(SalesQuotation.posting_date.desc())).scalars().all()
    deliveries = database.session.execute(q_deliveries.order_by(DeliveryNote.posting_date.desc())).scalars().all()

    return render_template(
        "portal/customer_dashboard.html",
        invoices=invoices,
        orders=orders,
        quotations=quotations,
        deliveries=deliveries,
        titulo="Portal de Clientes",
    )


@portal.route("/customer/invoice/<invoice_id>")
@requires_portal_role("customer")
def customer_invoice(invoice_id):
    """Detalle de factura de venta para el cliente."""
    invoice = database.session.get(SalesInvoice, invoice_id)
    if not invoice:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and invoice.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice_id)).all()
    return render_template("portal/invoice_detail.html", registro=invoice, items=items, role="customer")


@portal.route("/customer/order/<order_id>")
@requires_portal_role("customer")
def customer_order(order_id):
    """Detalle de orden de venta para el cliente."""
    order = database.session.get(SalesOrder, order_id)
    if not order:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and order.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=order_id)).all()
    return render_template("portal/order_detail.html", registro=order, items=items, role="customer")


@portal.route("/customer/quotation/<quotation_id>")
@requires_portal_role("customer")
def customer_quotation(quotation_id):
    """Detalle de cotización de venta para el cliente."""
    quotation = database.session.get(SalesQuotation, quotation_id)
    if not quotation:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and quotation.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=quotation_id)).all()
    return render_template("portal/quotation_detail.html", registro=quotation, items=items, role="customer")


@portal.route("/customer/delivery/<delivery_id>")
@requires_portal_role("customer")
def customer_delivery(delivery_id):
    """Detalle de nota de entrega para el cliente."""
    delivery = database.session.get(DeliveryNote, delivery_id)
    if not delivery:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and delivery.customer_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=delivery_id)).all()
    return render_template("portal/delivery_detail.html", registro=delivery, items=items, role="customer")


# ─── PORTAL DE PROVEEDORES ────────────────────────────────────────────────────


@portal.route("/supplier")
@requires_portal_role("supplier")
def supplier_dashboard():
    """Dashboard principal del portal de proveedores."""
    pid = current_user.party_id
    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )

    q_invoices = database.select(PurchaseInvoice).filter_by(document_type="purchase_invoice")
    q_orders = database.select(PurchaseOrder)
    q_quotations = database.select(PurchaseQuotation)
    q_receipts = database.select(PurchaseReceipt)

    if not is_admin and pid:
        q_invoices = q_invoices.filter_by(supplier_id=pid)
        q_orders = q_orders.filter_by(supplier_id=pid)
        q_quotations = q_quotations.filter_by(supplier_id=pid)
        q_receipts = q_receipts.filter_by(supplier_id=pid)

    invoices = database.session.execute(q_invoices.order_by(PurchaseInvoice.posting_date.desc())).scalars().all()
    orders = database.session.execute(q_orders.order_by(PurchaseOrder.posting_date.desc())).scalars().all()
    quotations = database.session.execute(q_quotations.order_by(PurchaseQuotation.posting_date.desc())).scalars().all()
    receipts = database.session.execute(q_receipts.order_by(PurchaseReceipt.posting_date.desc())).scalars().all()

    return render_template(
        "portal/supplier_dashboard.html",
        invoices=invoices,
        orders=orders,
        quotations=quotations,
        receipts=receipts,
        titulo="Portal de Proveedores",
    )


@portal.route("/supplier/invoice/<invoice_id>")
@requires_portal_role("supplier")
def supplier_invoice(invoice_id):
    """Detalle de factura de compra para el proveedor."""
    invoice = database.session.get(PurchaseInvoice, invoice_id)
    if not invoice:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and invoice.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id)).all()
    return render_template("portal/invoice_detail.html", registro=invoice, items=items, role="supplier")


@portal.route("/supplier/order/<order_id>")
@requires_portal_role("supplier")
def supplier_order(order_id):
    """Detalle de orden de compra para el proveedor."""
    order = database.session.get(PurchaseOrder, order_id)
    if not order:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and order.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=order_id)).all()
    return render_template("portal/order_detail.html", registro=order, items=items, role="supplier")


@portal.route("/supplier/quotation/<quotation_id>")
@requires_portal_role("supplier")
def supplier_quotation(quotation_id):
    """Detalle de solicitud de cotización para el proveedor."""
    quotation = database.session.get(PurchaseQuotation, quotation_id)
    if not quotation:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and quotation.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(
        database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=quotation_id)
    ).all()
    return render_template("portal/quotation_detail.html", registro=quotation, items=items, role="supplier")


@portal.route("/supplier/receipt/<receipt_id>")
@requires_portal_role("supplier")
def supplier_receipt(receipt_id):
    """Detalle de recepción de compra para el proveedor."""
    receipt = database.session.get(PurchaseReceipt, receipt_id)
    if not receipt:
        abort(404)

    is_admin = getattr(current_user, "classification", None) == "admin" or (
        not current_user.is_portal_customer and not current_user.is_portal_supplier
    )
    if not is_admin and receipt.supplier_id != current_user.party_id:
        abort(403)

    items = database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id)).all()
    return render_template("portal/receipt_detail.html", registro=receipt, items=items, role="supplier")
