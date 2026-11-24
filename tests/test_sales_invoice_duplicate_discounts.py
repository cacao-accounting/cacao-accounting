# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1618: duplicar una factura conserva los descuentos de línea."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    Item,
    Modules,
    SalesInvoice,
    SalesInvoiceItem,
    UOM,
    User,
    database,
)
from cacao_accounting.ventas.services import _validate_sales_invoice_line_amounts


@pytest.fixture
def invoice_duplicate_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
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
                Modules(module="sales", default=True, enabled=True),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code="ART01",
                    name="Artículo de prueba",
                    item_type="goods",
                    is_stock_item=False,
                    default_uom="UND",
                ),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1618",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin-1618",
                    user="admin-1618",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity="cacao",
                name="Mayo 2026",
                enabled=True,
                is_closed=False,
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
            )
        )
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            status="open",
            customer_name="Cliente 1618",
            document_no="FV-1618",
            transaction_currency="NIO",
            base_currency="NIO",
            total=Decimal("90"),
            grand_total=Decimal("90"),
            outstanding_amount=Decimal("90"),
            base_total=Decimal("90"),
            base_grand_total=Decimal("90"),
            base_outstanding_amount=Decimal("90"),
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=factura.id,
                item_code="ART01",
                item_name="Artículo con descuento",
                qty=Decimal("1"),
                uom="UND",
                qty_in_base_uom=Decimal("1"),
                rate=Decimal("100"),
                amount=Decimal("90"),
                discount_percentage=Decimal("10"),
                discount_amount=Decimal("10"),
            )
        )
        database.session.commit()
        factura_id = factura.id
    yield application, factura_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_duplicar_factura_conserva_descuento_y_permite_validar(invoice_duplicate_scene):
    """La copia conserva porcentaje/importe y el neto sigue siendo coherente."""
    application, factura_id = invoice_duplicate_scene
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin-1618"
        session["_fresh"] = True

    respuesta = client.post(f"/sales/sales-invoice/{factura_id}/duplicate")

    assert respuesta.status_code == 302
    with application.app_context():
        duplicado = database.session.execute(database.select(SalesInvoice).where(SalesInvoice.id != factura_id)).scalar_one()
        linea = database.session.execute(
            database.select(SalesInvoiceItem).filter_by(sales_invoice_id=duplicado.id)
        ).scalar_one()

        assert linea.discount_percentage == Decimal("10.0000")
        assert linea.discount_amount == Decimal("10.0000")
        assert linea.amount == Decimal("90.0000")
        _validate_sales_invoice_line_amounts(duplicado, [linea])
