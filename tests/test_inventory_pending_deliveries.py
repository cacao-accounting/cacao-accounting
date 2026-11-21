# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1332: proyección logística de entregas pendientes para Inventario.

La consulta de pendientes de despacho no expone precios, importes ni datos
comerciales y se limita a la compañía solicitada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    CompanyParty,
    Currency,
    Entity,
    FiscalYear,
    Item,
    Modules,
    Party,
    SalesOrder,
    SalesOrderItem,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)


@pytest.fixture
def inventory_delivery_scenario():
    """Create two companies and a warehouse user authorized only for alpha."""
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
    with app.app_context():
        database.create_all()
        customer = Party(code="CLI-1332", name="Cliente Confidencial", is_customer=True, tax_id="J-CLI-1332")
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                UOM(code="UND", name="Unidad", is_active=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J-ALPHA-1332",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J-BETA-1332",
                    currency="NIO",
                    enabled=True,
                ),
                customer,
                User(
                    id="delivery_user",
                    user="delivery_user",
                    name="Bodeguero Alpha",
                    password=proteger_passwd("delivery-user-password"),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(code="DEL-ITEM", name="Artículo despachado", item_type="goods", is_stock_item=True, default_uom="UND"),
                Item(code="BETA-ITEM", name="Artículo confidencial", item_type="goods", is_stock_item=True, default_uom="UND"),
                Warehouse(code="ALPHA-WH", name="Bodega Alpha", company="alpha"),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="delivery_user", company_code="alpha"))
        database.session.add(
            FiscalYear(
                id="FY2026-1332",
                entity="alpha",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                id="P2026-05-1332",
                entity="alpha",
                fiscal_year_id="FY2026-1332",
                name="Mayo 2026",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                enabled=True,
                is_closed=False,
            )
        )
        customer_id = customer.id
        alpha_order = SalesOrder(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no="SO-ALPHA-1332",
            customer_id=customer_id,
            customer_name="Cliente Confidencial",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        beta_order = SalesOrder(
            company="beta",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no="SO-BETA-1332",
            customer_name="Cliente Beta",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([alpha_order, beta_order])
        database.session.flush()
        database.session.add(CompanyParty(company="alpha", party_id=customer_id, is_active=True))
        alpha_line = SalesOrderItem(
            sales_order_id=alpha_order.id,
            item_code="DEL-ITEM",
            item_name="Artículo despachado",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="UND",
            rate=Decimal("12.50"),
            amount=Decimal("62.50"),
            warehouse="ALPHA-WH",
        )
        beta_line = SalesOrderItem(
            sales_order_id=beta_order.id,
            item_code="BETA-ITEM",
            item_name="Artículo confidencial",
            qty=Decimal("9"),
            qty_in_base_uom=Decimal("9"),
            uom="UND",
            rate=Decimal("99.99"),
            amount=Decimal("899.91"),
        )
        database.session.add_all([alpha_line, beta_line])
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("delivery_user", "inventory_auxiliar")
        database.session.commit()
        ids = {
            "alpha_order": alpha_order.id,
            "alpha_line": alpha_line.id,
            "beta_order": beta_order.id,
            "beta_line": beta_line.id,
            "customer": customer_id,
        }
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app):
    """Return an authenticated client for the alpha-only warehouse user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "delivery_user"
        session["_fresh"] = True
    return client


def test_pending_deliveries_projection_is_company_scoped(inventory_delivery_scenario):
    """The logistics endpoint only exposes alpha pending lines to alpha users."""
    app, ids = inventory_delivery_scenario
    client = _authenticated_client(app)

    response = client.get("/api/document-flow/pending-deliveries?company=alpha")

    assert response.status_code == 200
    items = response.get_json()["items"]
    assert [item["source_id"] for item in items] == [ids["alpha_order"]]
    assert items[0]["source_document_no"] == "SO-ALPHA-1332"
    assert "rate" not in items[0]
    assert "amount" not in items[0]
    assert items[0]["item_code"] == "DEL-ITEM"

    denied = client.get("/api/document-flow/pending-deliveries?company=beta")
    assert denied.status_code == 403


def test_pending_deliveries_page_renders_logistics_list(inventory_delivery_scenario):
    """Inventory has a page listing pending dispatches with a delivery link."""
    app, ids = inventory_delivery_scenario
    client = _authenticated_client(app)

    response = client.get("/inventory/pending-deliveries?company=alpha")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "SO-ALPHA-1332" in html
    assert "DEL-ITEM" in html
    assert f"/sales/delivery-note/new?from_order={ids['alpha_order']}" in html
    assert "SO-BETA-1332" not in html
