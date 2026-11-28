# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1075: la conciliacion S2P pendiente respeta la fecha de corte.

Las aplicaciones documentadas despues del corte (conciliacion, asignacion
factura/recepcion o devolucion fisica) no deben disminuir el saldo pendiente
historico de una recepcion.  El saldo a una fecha debe reconstruirse con la
evidencia efectiva hasta esa fecha y la consulta posterior debe reflejar la
aplicacion completa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import (
    allocate_purchase_invoice_receipt_lines,
    create_purchase_receipt_return_allocations,
    get_purchase_reconciliation_pending,
    reconcile_purchase_invoice,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    database,
)

RECEIPT_DATE = date(2026, 5, 1)
CUTOFF_DATE = date(2026, 5, 31)
INVOICE_DATE = date(2026, 6, 10)
RETURN_DATE = date(2026, 6, 15)
AFTER_CUTOFF_DATE = date(2026, 6, 30)


@pytest.fixture
def cutoff_scenario():
    """Recepcion de diez unidades aprobada antes de la fecha de corte."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6].upper()
    item_code = f"ITEM-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(Item(code=item_code, name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA"))
        database.session.flush()
        supplier = Party(code=f"SUP-{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        order = PurchaseOrder(
            company="alpha",
            document_no=f"PO-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=RECEIPT_DATE,
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                item_code=item_code,
                item_name="Artículo",
                qty=Decimal("10"),
                qty_in_base_uom=Decimal("10"),
                uom="EA",
                rate=Decimal("10"),
                amount=Decimal("100"),
            )
        )
        receipt = PurchaseReceipt(
            company="alpha",
            document_no=f"PR-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=order.id,
            posting_date=RECEIPT_DATE,
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(receipt)
        database.session.flush()
        receipt_item = PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code=item_code,
            item_name="Artículo",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("100"),
        )
        database.session.add(receipt_item)
        database.session.add(
            PurchaseMatchingConfig(
                company="alpha",
                matching_type="3-way",
                require_purchase_order=True,
                bridge_account_required=False,
                auto_reconcile=False,
                price_tolerance_type="percentage",
                price_tolerance_value=Decimal("0"),
                qty_tolerance_type="percentage",
                qty_tolerance_value=Decimal("0"),
                allow_price_difference=False,
            )
        )
        database.session.commit()
        ids = {
            "suffix": suffix,
            "item_code": item_code,
            "supplier_id": supplier.id,
            "order_id": order.id,
            "receipt_id": receipt.id,
            "receipt_item_id": receipt_item.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _add_invoice(ids: dict, posting_date: date) -> str:
    """Create a submitted invoice matching the receipt quantity and amount."""
    suffix = ids["suffix"]
    invoice = PurchaseInvoice(
        company="alpha",
        document_type="purchase_invoice",
        document_no=f"PI-{suffix}",
        supplier_id=ids["supplier_id"],
        supplier_name="Proveedor",
        supplier_invoice_no=f"FAC-{suffix}",
        posting_date=posting_date,
        docstatus=1,
        purchase_order_id=ids["order_id"],
        purchase_receipt_id=ids["receipt_id"],
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code=ids["item_code"],
            item_name="Artículo",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("100"),
        )
    )
    database.session.commit()
    return invoice.id


def _pending_row(ids: dict, as_of_date: date | None):
    """Return the pending row for the fixture receipt item, if any."""
    rows = get_purchase_reconciliation_pending("alpha", as_of_date)
    return next((row for row in rows if row.purchase_receipt_item_id == ids["receipt_item_id"]), None)


def test_reconciliation_after_cutoff_preserves_historical_balance(cutoff_scenario):
    """A June reconciliation must not reduce the May pending balance."""
    app, ids = cutoff_scenario

    with app.app_context():
        invoice_id = _add_invoice(ids, INVOICE_DATE)
        result = reconcile_purchase_invoice(invoice_id)
        assert result.status == "reconciled"

        historical = _pending_row(ids, CUTOFF_DATE)
        current = _pending_row(ids, AFTER_CUTOFF_DATE)
        uncut = _pending_row(ids, None)

        assert historical is not None
        assert historical.pending_qty == Decimal("10")
        assert historical.pending_amount == Decimal("100")
        assert current is None
        assert uncut is None


def test_invoice_receipt_allocation_after_cutoff_preserves_historical_balance(cutoff_scenario):
    """A June invoice allocation must not reduce the May pending balance."""
    app, ids = cutoff_scenario

    with app.app_context():
        invoice_id = _add_invoice(ids, INVOICE_DATE)
        allocations = allocate_purchase_invoice_receipt_lines(ids["receipt_id"], invoice_id)
        assert len(allocations) == 1
        assert allocations[0].qty_in_base_uom == Decimal("10")

        historical = _pending_row(ids, CUTOFF_DATE)
        current = _pending_row(ids, AFTER_CUTOFF_DATE)
        uncut = _pending_row(ids, None)

        assert historical is not None
        assert historical.pending_qty == Decimal("10")
        assert historical.pending_amount == Decimal("100")
        assert current is None
        assert uncut is None


def test_physical_return_after_cutoff_preserves_historical_balance(cutoff_scenario):
    """A June return only reduces the pending balance from its own date."""
    app, ids = cutoff_scenario

    with app.app_context():
        suffix = ids["suffix"]
        returned_receipt = PurchaseReceipt(
            company="alpha",
            document_no=f"PRT-{suffix}",
            supplier_id=ids["supplier_id"],
            supplier_name="Proveedor",
            purchase_order_id=ids["order_id"],
            posting_date=RETURN_DATE,
            docstatus=1,
            is_return=True,
            reversal_of=ids["receipt_id"],
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(returned_receipt)
        database.session.flush()
        return_item = PurchaseReceiptItem(
            purchase_receipt_id=returned_receipt.id,
            item_code=ids["item_code"],
            item_name="Artículo",
            qty=Decimal("4"),
            qty_in_base_uom=Decimal("4"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("40"),
        )
        database.session.add(return_item)
        database.session.commit()

        allocations = create_purchase_receipt_return_allocations(returned_receipt.id)
        assert len(allocations) == 1
        assert allocations[0].qty_in_base_uom == Decimal("4")

        historical = _pending_row(ids, CUTOFF_DATE)
        current = _pending_row(ids, AFTER_CUTOFF_DATE)
        uncut = _pending_row(ids, None)

        assert historical is not None
        assert historical.pending_qty == Decimal("10")
        assert historical.pending_amount == Decimal("100")
        assert current is not None
        assert current.pending_qty == Decimal("6")
        assert current.pending_amount == Decimal("60")
        assert uncut is not None
        assert uncut.pending_qty == Decimal("6")
        assert uncut.pending_amount == Decimal("60")
