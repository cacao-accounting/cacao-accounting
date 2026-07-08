# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de validacion de precios SO -> Factura (O2C-02)."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    DocumentRelation,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesMatchingConfig,
    SalesOrder,
    SalesOrderItem,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()
        database.session.commit()
        yield app


def login(client, username, password):
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def _create_so_with_item(company="cacao"):
    """Crea una SalesOrder con un ítem a $100."""
    so = SalesOrder(
        id="SO-PRICE-01",
        company=company,
        posting_date=date(2026, 5, 1),
        docstatus=1,
        grand_total=Decimal("1000"),
    )
    so_item = SalesOrderItem(
        sales_order_id="SO-PRICE-01",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("100"),
        amount=Decimal("1000"),
    )
    database.session.add_all([so, so_item])
    database.session.flush()
    return so, so_item


def _create_invoice_from_so(so, so_item, rate, company="cacao"):
    """Crea una SalesInvoice vinculada a la SO con el rate indicado."""
    customer = database.session.execute(
        database.select(Party).filter(Party.is_customer.is_(True))
    ).scalars().first()

    invoice = SalesInvoice(
        id="SI-PRICE-01",
        customer_id=customer.id,
        customer_name=customer.name,
        company=company,
        posting_date=date(2026, 5, 2),
        document_type="sales_invoice",
        docstatus=0,
        grand_total=rate * Decimal("10"),
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id="SI-PRICE-01",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=rate,
        amount=rate * Decimal("10"),
    )
    database.session.add_all([invoice, invoice_item])
    database.session.flush()

    relation = DocumentRelation(
        source_type="sales_order",
        source_id=so.id,
        source_item_id=so_item.id,
        target_type="sales_invoice",
        target_id=invoice.id,
        target_item_id=invoice_item.id,
        company=company,
        qty=Decimal("10"),
        uom="UND",
        rate=rate,
        amount=rate * Decimal("10"),
        relation_type="billing",
        status="active",
    )
    database.session.add(relation)
    database.session.commit()
    return invoice


def test_price_matching_passes_when_equal(app_ctx):
    """Factura con precio igual a SO pasa validacion."""
    from cacao_accounting.ventas import _validate_invoice_prices_against_source

    so, so_item = _create_so_with_item()
    invoice = _create_invoice_from_so(so, so_item, rate=Decimal("100"))

    _validate_invoice_prices_against_source(invoice)


def test_price_matching_rejects_when_out_of_tolerance(app_ctx):
    """Factura con precio fuera de tolerancia es rechazada."""
    from cacao_accounting.ventas import _validate_invoice_prices_against_source

    config = SalesMatchingConfig(
        company="cacao",
        matching_type="3-way",
        price_tolerance_type="percentage",
        price_tolerance_value=Decimal("5"),
        allow_price_difference=False,
    )
    database.session.add(config)
    database.session.commit()

    so, so_item = _create_so_with_item()
    invoice = _create_invoice_from_so(so, so_item, rate=Decimal("120"))

    with pytest.raises(ValueError, match="difiere del precio"):
        _validate_invoice_prices_against_source(invoice)


def test_price_matching_warns_when_allowed(app_ctx):
    """Factura con precio fuera de tolerancia pero allow_price_difference=True solo advierte."""
    from cacao_accounting.ventas import _validate_invoice_prices_against_source

    config = SalesMatchingConfig(
        company="cacao",
        matching_type="3-way",
        price_tolerance_type="percentage",
        price_tolerance_value=Decimal("5"),
        allow_price_difference=True,
    )
    database.session.add(config)
    database.session.commit()

    so, so_item = _create_so_with_item()
    invoice = _create_invoice_from_so(so, so_item, rate=Decimal("120"))

    _validate_invoice_prices_against_source(invoice)


def test_price_matching_passes_within_tolerance(app_ctx):
    """Factura con precio dentro de tolerancia pasa sin error."""
    from cacao_accounting.ventas import _validate_invoice_prices_against_source

    config = SalesMatchingConfig(
        company="cacao",
        matching_type="3-way",
        price_tolerance_type="percentage",
        price_tolerance_value=Decimal("10"),
        allow_price_difference=False,
    )
    database.session.add(config)
    database.session.commit()

    so, so_item = _create_so_with_item()
    invoice = _create_invoice_from_so(so, so_item, rate=Decimal("105"))

    _validate_invoice_prices_against_source(invoice)


def test_price_matching_default_rejects_any_difference(app_ctx):
    """Sin configuracion, cualquier diferencia de precio es rechazada (tolerancia 0)."""
    from cacao_accounting.ventas import _validate_invoice_prices_against_source

    so, so_item = _create_so_with_item()
    invoice = _create_invoice_from_so(so, so_item, rate=Decimal("101"))

    with pytest.raises(ValueError, match="difiere del precio"):
        _validate_invoice_prices_against_source(invoice)
