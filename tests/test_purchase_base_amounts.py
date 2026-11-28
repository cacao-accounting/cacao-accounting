# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2133: las líneas de compra guardan el importe en moneda del libro."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras.services import (
    _group_items_by_budget_dimensions,
    _save_purchase_invoice_items,
    _save_purchase_order_items,
    _save_purchase_receipt_items,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    ExchangeRate,
    Item,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    database,
)

FECHA = date(2026, 5, 1)


@pytest.fixture
def compras_usd():
    """App aislada con una tasa USD→NIO y un artículo no inventariable."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code="ART-USD",
                    name="Artículo en dólares",
                    item_type="goods",
                    is_stock_item=False,
                    is_purchase_item=True,
                    default_uom="UND",
                ),
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.50"), date=FECHA),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _formulario() -> dict[str, str]:
    return {
        "item_code_0": "",
        "item_code_1": "ART-USD",
        "item_name_1": "Artículo en dólares",
        "qty_1": "1",
        "rate_1": "100",
        "uom_1": "UND",
    }


def test_orden_guarda_base_amount_y_el_presupuesto_usa_esa_moneda(compras_usd):
    """Una orden de USD 100 se presupuesta como NIO 3.650 con la tasa del día."""
    application = compras_usd
    with application.app_context():
        order = PurchaseOrder(
            company="cacao",
            posting_date=FECHA,
            transaction_currency="USD",
            docstatus=0,
        )
        database.session.add(order)
        database.session.commit()
        order_id = order.id

        with application.test_request_context("/", method="POST", data=_formulario()):
            _save_purchase_order_items(order_id)
            database.session.commit()

        linea = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=order_id)).scalar_one()
        assert linea.amount == Decimal("100.0000")
        assert linea.base_amount == Decimal("3650.0000")
        assert linea.base_rate == Decimal("36.5000")
        assert sum(_group_items_by_budget_dimensions([linea], "cacao", None).values()) == Decimal("3650.0000")


def test_recepcion_guarda_base_amount(compras_usd):
    """La recepción convierte sus líneas con la tasa del documento."""
    application = compras_usd
    with application.app_context():
        receipt = PurchaseReceipt(
            company="cacao",
            posting_date=FECHA,
            transaction_currency="USD",
            docstatus=0,
        )
        database.session.add(receipt)
        database.session.commit()
        receipt_id = receipt.id

        with application.test_request_context("/", method="POST", data=_formulario()):
            _save_purchase_receipt_items(receipt_id)
            database.session.commit()

        linea = database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id)
        ).scalar_one()
        assert linea.base_amount == Decimal("3650.0000")


def test_factura_guarda_base_amount_y_base_rate(compras_usd):
    """La factura de compra conserva importe transaccional y de libro."""
    application = compras_usd
    with application.app_context():
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            transaction_currency="USD",
            docstatus=0,
            document_type="purchase_invoice",
        )
        database.session.add(invoice)
        database.session.commit()
        invoice_id = invoice.id

        with application.test_request_context("/", method="POST", data=_formulario()):
            _save_purchase_invoice_items(invoice_id)
            database.session.commit()

        linea = database.session.execute(
            database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id)
        ).scalar_one()
        assert linea.amount == Decimal("100.0000")
        assert linea.base_amount == Decimal("3650.0000")
        assert linea.base_rate == Decimal("36.5000")


def test_factura_guarda_lineas_despues_de_fila_vacia(compras_usd):  # pylint: disable=redefined-outer-name
    """Una fila vacía no debe hacer que se pierdan líneas válidas posteriores."""
    application = compras_usd
    with application.app_context():
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            transaction_currency="USD",
            docstatus=0,
            document_type="purchase_invoice",
        )
        database.session.add(invoice)
        database.session.commit()
        invoice_id = invoice.id

        form = {
            "item_code_0": "",
            "item_code_1": "ART-USD",
            "item_code_01": "IGNORED-NONCANONICAL-ALIAS",
            "item_name_1": "Artículo en dólares",
            "qty_1": "2",
            "rate_1": "100",
            "uom_1": "UND",
            "item_code_2": "ART-USD",
            "item_name_2": "Artículo en dólares",
            "qty_2": "1",
            "rate_2": "50",
            "uom_2": "UND",
        }
        with application.test_request_context("/", method="POST", data=form):
            total_qty, total = _save_purchase_invoice_items(invoice_id)
            database.session.commit()

        lineas = (
            database.session.execute(
                database.select(PurchaseInvoiceItem)
                .filter_by(purchase_invoice_id=invoice_id)
                .order_by(PurchaseInvoiceItem.item_code)
            )
            .scalars()
            .all()
        )
        assert total_qty == Decimal("3.0000")
        assert total == Decimal("250.0000")
        assert len(lineas) == 2
        assert sum((linea.qty for linea in lineas), Decimal("0")) == total_qty
        assert sum((linea.amount for linea in lineas), Decimal("0")) == total
