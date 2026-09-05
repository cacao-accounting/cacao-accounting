# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los documentos de compra deben rechazar items inexistentes, inactivos o no comprables.

Regresión para cotizaciones de proveedor y facturas de compra: los helpers de líneas
deben aplicar la misma validación de items (existe, activo, is_purchase_item) que ya
aplica la ruta de órdenes de compra.
"""

from datetime import date
from decimal import Decimal

import pytest
from flask import current_app

from cacao_accounting import create_app
from cacao_accounting.compras.services import (
    _save_purchase_invoice_items,
    _save_supplier_quotation_items,
)
from cacao_accounting.database import (
    Entity,
    Currency,
    UOM,
    Item,
    SupplierQuotation,
    PurchaseInvoice,
    database,
)
from cacao_accounting.document_flow import DocumentFlowError


@pytest.fixture
def app_ctx():
    """Application context fixture aislado en memoria."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="I803", currency="NIO"),
                UOM(code="UND", name="Unidad", is_active=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def _ensure_item(code, name="Item", is_active=True, is_purchase_item=True):
    """Crea un item de prueba si no existe."""
    item = database.session.execute(database.select(Item).filter_by(code=code)).scalar_one_or_none()
    if not item:
        item = Item(
            code=code,
            name=name,
            item_type="service",
            default_uom="UND",
            is_active=is_active,
            is_purchase_item=is_purchase_item,
        )
        database.session.add(item)
        database.session.flush()
    return item


def _quotation_form_data(item_code):
    """Datos de formulario con una sola línea de cotización de proveedor."""
    return {
        "company": "cacao",
        "supplier_id": "SUPLR-I803",
        "posting_date": date.today().isoformat(),
        "item_code_0": item_code,
        "item_name_0": "Item",
        "qty_0": "1",
        "rate_0": "10",
        "amount_0": "10",
    }


def _invoice_form_data(item_code):
    """Datos de formulario con una sola línea de factura de compra."""
    return {
        "company": "cacao",
        "supplier_id": "SUPLR-I803",
        "posting_date": date.today().isoformat(),
        "item_code_0": item_code,
        "item_name_0": "Item",
        "qty_0": "1",
        "rate_0": "10",
        "amount_0": "10",
    }


@pytest.mark.parametrize(
    ("item_code", "setup", "expected_message"),
    [
        ("ITEM-MISSING", None, "no existe"),
        ("ITEM-INACTIVE", {"is_active": False, "is_purchase_item": True}, "no está habilitado para compra"),
        ("ITEM-NOT-PURCHASE", {"is_active": True, "is_purchase_item": False}, "no está habilitado para compra"),
    ],
)
def test_supplier_quotation_rejects_invalid_items(app_ctx, item_code, setup, expected_message):
    """Una cotización de proveedor rechaza items inexistentes, inactivos o no comprables."""
    if setup is not None:
        _ensure_item(item_code, is_active=setup["is_active"], is_purchase_item=setup["is_purchase_item"])
    quotation = SupplierQuotation(
        supplier_id="SUPLR-I803",
        supplier_name="Proveedor",
        company="cacao",
        transaction_currency="NIO",
        base_currency="NIO",
        posting_date=date.today(),
        docstatus=0,
    )
    database.session.add(quotation)
    database.session.flush()

    with current_app.test_request_context(
        "/buying/supplier-quotation/new", method="POST", data=_quotation_form_data(item_code)
    ):
        with pytest.raises(DocumentFlowError, match=expected_message):
            _save_supplier_quotation_items(quotation.id)


@pytest.mark.parametrize(
    ("item_code", "setup", "expected_message"),
    [
        ("ITEM-MISSING", None, "no existe"),
        ("ITEM-INACTIVE", {"is_active": False, "is_purchase_item": True}, "no está habilitado para compra"),
        ("ITEM-NOT-PURCHASE", {"is_active": True, "is_purchase_item": False}, "no está habilitado para compra"),
    ],
)
def test_purchase_invoice_rejects_invalid_items(app_ctx, item_code, setup, expected_message):
    """Una factura de compra rechaza items inexistentes, inactivos o no comprables."""
    if setup is not None:
        _ensure_item(item_code, is_active=setup["is_active"], is_purchase_item=setup["is_purchase_item"])
    invoice = PurchaseInvoice(
        supplier_id="SUPLR-I803",
        company="cacao",
        document_type="purchase_invoice",
        transaction_currency="NIO",
        base_currency="NIO",
        posting_date=date.today(),
        docstatus=0,
    )
    database.session.add(invoice)
    database.session.flush()

    with current_app.test_request_context("/buying/purchase-invoice/new", method="POST", data=_invoice_form_data(item_code)):
        with pytest.raises(DocumentFlowError, match=expected_message):
            _save_purchase_invoice_items(invoice.id)


def test_supplier_quotation_accepts_valid_item(app_ctx):
    """Una cotización de proveedor acepta un item habilitado para compra."""
    _ensure_item("ITEM-VALID")
    quotation = SupplierQuotation(
        supplier_id="SUPLR-I803",
        supplier_name="Proveedor",
        company="cacao",
        transaction_currency="NIO",
        base_currency="NIO",
        posting_date=date.today(),
        docstatus=0,
    )
    database.session.add(quotation)
    database.session.flush()

    with current_app.test_request_context(
        "/buying/supplier-quotation/new", method="POST", data=_quotation_form_data("ITEM-VALID")
    ):
        qty, total = _save_supplier_quotation_items(quotation.id)

    assert qty == Decimal("1")
    assert total == Decimal("10")


def test_purchase_invoice_accepts_valid_item(app_ctx):
    """Una factura de compra acepta un item habilitado para compra."""
    _ensure_item("ITEM-VALID")
    invoice = PurchaseInvoice(
        supplier_id="SUPLR-I803",
        company="cacao",
        document_type="purchase_invoice",
        transaction_currency="NIO",
        base_currency="NIO",
        posting_date=date.today(),
        docstatus=0,
    )
    database.session.add(invoice)
    database.session.flush()

    with current_app.test_request_context(
        "/buying/purchase-invoice/new", method="POST", data=_invoice_form_data("ITEM-VALID")
    ):
        qty, total = _save_purchase_invoice_items(invoice.id)

    assert qty == Decimal("1")
    assert total == Decimal("10")
