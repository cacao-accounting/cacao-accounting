# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1960: el portal muestra el número de lote y no el identificador interno."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    CompanyParty,
    Currency,
    Entity,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    UOM,
    User,
    database,
)


@pytest.fixture
def portal_lotes():
    """Escenario aislado con un cliente y dos facturas de clientes distintos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    sufijo = uuid4().hex[:6]
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        articulo = Item(code=f"ART-{sufijo}", name="Artículo lote", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add(articulo)
        database.session.flush()
        lote = Batch(item_code=articulo.code, batch_no=f"LOTE-PUB-{sufijo}", is_active=True)
        database.session.add(lote)
        database.session.flush()
        cliente = Party(code=f"CLI-{sufijo}", name="Cliente lote", is_customer=True, is_active=True)
        otro = Party(code=f"OTR-{sufijo}", name="Otro cliente", is_customer=True, is_active=True)
        database.session.add_all([cliente, otro])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente.id, is_active=True),
                CompanyParty(company="cacao", party_id=otro.id, is_active=True),
                User(
                    id=f"portal-{sufijo}",
                    user=f"portal_{sufijo}",
                    name="Cliente lote",
                    password=b"x",
                    active=True,
                    classification="customer",
                    party_id=cliente.id,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        propio = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"FAC-LOTE-{sufijo}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("10"),
            total=Decimal("10"),
            outstanding_amount=Decimal("10"),
        )
        ajeno = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"FAC-AJENA-{sufijo}",
            customer_id=otro.id,
            customer_name=otro.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("20"),
            total=Decimal("20"),
            outstanding_amount=Decimal("20"),
        )
        database.session.add_all([propio, ajeno])
        database.session.flush()
        database.session.add_all(
            [
                SalesInvoiceItem(
                    sales_invoice_id=propio.id,
                    item_code=articulo.code,
                    item_name=articulo.name,
                    qty=Decimal("1"),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal("10"),
                    batch_id=lote.id,
                    serial_no=f"SER-PUB-{sufijo}",
                ),
                SalesInvoiceItem(
                    sales_invoice_id=ajeno.id,
                    item_code=articulo.code,
                    item_name=articulo.name,
                    qty=Decimal("1"),
                    uom="UND",
                    rate=Decimal("20"),
                    amount=Decimal("20"),
                ),
            ]
        )
        database.session.commit()
        ids = {
            "user": f"portal-{sufijo}",
            "invoice": propio.id,
            "batch_id": lote.id,
            "batch_no": lote.batch_no,
            "serial": f"SER-PUB-{sufijo}",
            "other_invoice": f"FAC-AJENA-{sufijo}",
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_portal_muestra_batch_no_y_oculta_el_identificador(portal_lotes):
    """El detalle autorizado muestra lote, serie y nunca el ULID del lote."""
    application, ids = portal_lotes
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, ids["user"]).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = ids["user"]
        session["_auth_version"] = version
        session["_fresh"] = True

    response = client.get(f"/portal/customer/invoice/{ids['invoice']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert ids["batch_no"] in cuerpo
    assert ids["batch_id"] not in cuerpo
    assert ids["serial"] in cuerpo
    assert ids["other_invoice"] not in cuerpo
