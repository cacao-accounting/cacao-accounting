# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Purchase reconciliation displays transaction currency at each amount."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    Currency,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReconciliation,
    UOM,
    Warehouse,
    database,
)


def test_purchase_reconciliation_labels_order_invoice_receipt_and_panel_amounts(app, entorno_contable, authenticated_client):
    """Equal nominal totals remain distinguishable in the reconciliation UI."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        warehouse = database.session.execute(database.select(Warehouse).filter_by(code="BOD01")).scalar_one()
        database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
        database.session.flush()
        order = PurchaseOrder(
            company="cacao",
            document_no=f"PO-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 15),
            docstatus=1,
            transaction_currency="EUR",
            grand_total=Decimal("100"),
        )
        invoice = PurchaseInvoice(
            company="cacao",
            document_type="purchase_invoice",
            document_no=f"PI-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 15),
            docstatus=1,
            transaction_currency="USD",
            grand_total=Decimal("100"),
        )
        receipt = PurchaseReceipt(
            company="cacao",
            document_no=f"PR-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=order.id,
            posting_date=date(2026, 5, 15),
            docstatus=1,
            transaction_currency="EUR",
            grand_total=Decimal("100"),
        )
        database.session.add_all([order, invoice, receipt])
        database.session.flush()
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom=uom.code,
                rate=Decimal("50"),
                amount=Decimal("100"),
                warehouse=warehouse.code,
            )
        )
        database.session.add(
            PurchaseReconciliation(
                company="cacao",
                purchase_order_id=order.id,
                purchase_receipt_id=receipt.id,
                matched_amount=Decimal("25"),
                status="partial",
            )
        )
        database.session.commit()

    client = authenticated_client("admin")
    report = client.get("/buying/purchase-reconciliation?company=cacao")

    assert report.status_code == 200
    report_html = report.get_data(as_text=True)
    assert "EUR 100.00" in report_html
    assert "USD 100.00" in report_html
    assert "EUR 100.00" in report_html

    panel = client.get("/buying/purchase-reconciliation/panel?company=cacao")

    assert panel.status_code == 200
    assert "EUR 25.00" in panel.get_data(as_text=True)
