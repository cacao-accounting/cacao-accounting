# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""P7: `matched_qty` debe coincidir con las asignaciones persistidas.

El encabezado y el evento económico publicaban la cantidad facturada completa,
aunque la factura excediera el pendiente de la OC o recepción y solo se
hubieran asignado las cantidades realmente disponibles. Un replay derivaba la
cantidad desde los detalles y devolvía un valor distinto.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import reconcile_purchase_invoice
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseEconomicEvent,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReconciliationItem,
    UOM,
    database,
)


@pytest.fixture
def matching_scenario():
    """Cree una OC y una recepción de 5 unidades con facturas de 6 unidades."""
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
        database.session.add(
            Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        )
        database.session.flush()
        supplier = Party(code=f"SUP-{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        order = PurchaseOrder(
            company="alpha",
            document_no=f"PO-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                item_code=f"ITEM-{suffix}",
                item_name="Artículo",
                qty=Decimal("5"),
                qty_in_base_uom=Decimal("5"),
                uom="EA",
                rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        receipt = PurchaseReceipt(
            company="alpha",
            document_no=f"PR-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=order.id,
            posting_date=date(2026, 5, 11),
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add(receipt)
        database.session.flush()
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code=f"ITEM-{suffix}",
                item_name="Artículo",
                qty=Decimal("5"),
                qty_in_base_uom=Decimal("5"),
                uom="EA",
                rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        invoice_two_way = _invoice(suffix, supplier, order.id, None, "A")
        invoice_three_way = _invoice(suffix, supplier, order.id, receipt.id, "B")
        database.session.add_all([invoice_two_way, invoice_three_way])
        database.session.flush()
        database.session.add_all(
            [
                PurchaseInvoiceItem(
                    purchase_invoice_id=invoice.id,
                    item_code=f"ITEM-{suffix}",
                    item_name="Artículo",
                    qty=Decimal("6"),
                    qty_in_base_uom=Decimal("6"),
                    uom="EA",
                    rate=Decimal("10"),
                    amount=Decimal("60"),
                )
                for invoice in (invoice_two_way, invoice_three_way)
            ]
        )
        config = PurchaseMatchingConfig(
            company="alpha",
            matching_type="2-way",
            require_purchase_order=True,
            bridge_account_required=False,
            auto_reconcile=False,
            price_tolerance_type="percentage",
            price_tolerance_value=Decimal("0"),
            qty_tolerance_type="percentage",
            qty_tolerance_value=Decimal("50"),
            allow_price_difference=True,
        )
        database.session.add(config)
        database.session.commit()
        ids = {
            "two_way": invoice_two_way.id,
            "three_way": invoice_three_way.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _invoice(suffix, supplier, order_id, receipt_id, marker):
    """Build a submitted invoice that over-invoices the referenced documents."""
    return PurchaseInvoice(
        company="alpha",
        document_type="purchase_invoice",
        document_no=f"PI-{marker}-{suffix}",
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        supplier_invoice_no=f"FAC-{marker}-{suffix}",
        posting_date=date(2026, 5, 12),
        docstatus=1,
        purchase_order_id=order_id,
        purchase_receipt_id=receipt_id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )


def _persisted_qty(reconciliation_id):
    """Return the quantity assigned to source lines for a reconciliation."""
    items = (
        database.session.execute(
            database.select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation_id)
        )
        .scalars()
        .all()
    )
    return sum((Decimal(str(item.matched_qty)) for item in items), Decimal("0"))


def test_two_way_partial_reports_only_persisted_qty(matching_scenario):
    """An over-invoiced order reports the five units actually allocated."""
    app, ids = matching_scenario

    with app.app_context():
        result = reconcile_purchase_invoice(ids["two_way"])

        assert result.matching_result == "MATCH_PARTIAL"
        assert result.status == "partial"
        assert result.matched_qty == Decimal("5")
        assert result.matched_qty == _persisted_qty(result.reconciliation_id)
        event = database.session.execute(
            database.select(PurchaseEconomicEvent).filter_by(document_id=result.reconciliation_id)
        ).scalar_one()
        assert Decimal(json.loads(event.payload)["matched_qty"]) == result.matched_qty


def test_three_way_partial_reports_only_persisted_qty(matching_scenario):
    """An over-invoiced receipt reports the five units actually allocated."""
    app, ids = matching_scenario

    with app.app_context():
        config = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="alpha")).scalar_one()
        config.matching_type = "3-way"
        database.session.commit()

        result = reconcile_purchase_invoice(ids["three_way"])

        assert result.matching_result == "MATCH_PARTIAL"
        assert result.matched_qty == Decimal("5")
        assert result.matched_qty == _persisted_qty(result.reconciliation_id)


def test_failed_match_reports_zero_qty_because_nothing_is_assigned(matching_scenario):
    """A rejected match persists no source lines, so it reports zero quantity."""
    app, ids = matching_scenario

    with app.app_context():
        config = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="alpha")).scalar_one()
        config.allow_price_difference = False
        invoice_item = database.session.execute(
            database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=ids["two_way"])
        ).scalar_one()
        invoice_item.rate = Decimal("12")
        invoice_item.amount = Decimal("72")
        database.session.commit()

        result = reconcile_purchase_invoice(ids["two_way"])

        assert result.matching_result == "MATCH_FAILED"
        assert result.matched_qty == Decimal("0")
        assert _persisted_qty(result.reconciliation_id) == Decimal("0")


@pytest.mark.parametrize(
    ("source_table", "source_id_key"),
    [
        ("purchase_order_item", "purchase_order_item_id"),
        ("purchase_receipt_item", "purchase_receipt_item_id"),
        ("purchase_invoice_item", "purchase_invoice_item_id"),
    ],
)
def test_deleting_reconciled_source_lines_preserves_reconciliation_evidence(matching_scenario, source_table, source_id_key):
    """Deleting any matched source line cannot cascade away reconciliation evidence."""
    app, ids = matching_scenario

    with app.app_context():
        two_way_result = reconcile_purchase_invoice(ids["two_way"])
        config = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="alpha")).scalar_one()
        config.matching_type = "3-way"
        database.session.commit()
        result = reconcile_purchase_invoice(ids["three_way"])
        reconciliation_id = (
            two_way_result.reconciliation_id if source_id_key == "purchase_order_item_id" else result.reconciliation_id
        )
        reconciliation_item = database.session.execute(
            database.select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation_id)
        ).scalar_one()
        reconciliation_item_id = reconciliation_item.id
        source_id = getattr(reconciliation_item, source_id_key)
        assert source_id is not None
        database.session.commit()

        source_models = {
            "purchase_order_item": PurchaseOrderItem,
            "purchase_receipt_item": PurchaseReceiptItem,
            "purchase_invoice_item": PurchaseInvoiceItem,
        }
        source_model = source_models[source_table]
        source_item = database.session.get(source_model, source_id)
        assert source_item is not None
        database.session.delete(source_item)
        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()

        assert database.session.get(PurchaseReconciliationItem, reconciliation_item_id) is not None
        assert database.session.get(source_model, source_id) is not None
