# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1483: un importe de línea igual a cero es un valor válido."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import (
    _line_amount,
    get_purchase_reconciliation_pending,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseMatchingConfig,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    database,
)


def _line(amount: Decimal | None, qty: Decimal = Decimal("2"), rate: Decimal = Decimal("10")) -> PurchaseReceiptItem:
    """Construye una línea de recepción con el importe persistido indicado."""
    return PurchaseReceiptItem(qty_in_base_uom=qty, amount=amount, rate=rate)


def test_importe_cero_se_conserva_en_lugar_de_recalcularlo(app):
    """Una línea bonificada conserva su importe cero."""
    del app
    assert _line_amount(_line(Decimal("0"))) == Decimal("0")


def test_importe_ausente_se_calcula_con_cantidad_y_tarifa(app):
    """Solo la ausencia del importe activa el cálculo derivado."""
    del app
    assert _line_amount(_line(None)) == Decimal("20")


@pytest.fixture
def zero_amount_pending_scenario():
    """Recepción con una línea bonificada (importe cero) y otra sin importe persistido."""
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
    item_zero = f"ITMZ-{suffix}"
    item_none = f"ITMN-{suffix}"

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
        database.session.add_all(
            [
                Item(code=item_zero, name="Bonificado", item_type="goods", is_stock_item=True, default_uom="EA"),
                Item(code=item_none, name="Calculado", item_type="goods", is_stock_item=True, default_uom="EA"),
            ]
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
        database.session.add_all(
            [
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    item_code=item_zero,
                    item_name="Bonificado",
                    qty=Decimal("2"),
                    qty_in_base_uom=Decimal("2"),
                    uom="EA",
                    rate=Decimal("10"),
                    amount=Decimal("0"),
                ),
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    item_code=item_none,
                    item_name="Calculado",
                    qty=Decimal("2"),
                    qty_in_base_uom=Decimal("2"),
                    uom="EA",
                    rate=Decimal("10"),
                    amount=Decimal("20"),
                ),
            ]
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
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(receipt)
        database.session.flush()
        database.session.add_all(
            [
                PurchaseReceiptItem(
                    purchase_receipt_id=receipt.id,
                    item_code=item_zero,
                    item_name="Bonificado",
                    qty=Decimal("2"),
                    qty_in_base_uom=Decimal("2"),
                    uom="EA",
                    rate=Decimal("10"),
                    amount=Decimal("0"),
                ),
                PurchaseReceiptItem(
                    purchase_receipt_id=receipt.id,
                    item_code=item_none,
                    item_name="Calculado",
                    qty=Decimal("2"),
                    qty_in_base_uom=Decimal("2"),
                    uom="EA",
                    rate=Decimal("10"),
                    amount=None,
                ),
            ]
        )
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
        yield app, {"item_zero": item_zero, "item_none": item_none}

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_pendiente_conciliacion_conserva_importe_cero_y_calcula_ausente(zero_amount_pending_scenario):
    """Conciliación pendiente usa el importe cero persistido y solo deriva el ausente."""
    app, ids = zero_amount_pending_scenario
    with app.app_context():
        rows = get_purchase_reconciliation_pending("alpha")
        by_item = {row.item_code: row for row in rows}

        assert ids["item_zero"] in by_item
        assert by_item[ids["item_zero"]].pending_qty == Decimal("2")
        assert by_item[ids["item_zero"]].pending_amount == Decimal("0")

        assert ids["item_none"] in by_item
        assert by_item[ids["item_none"]].pending_qty == Decimal("2")
        assert by_item[ids["item_none"]].pending_amount == Decimal("20")
