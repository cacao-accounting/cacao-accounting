# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Tests para la configuracion global de valuacion de inventarios."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="cafe",
                    name="Cafe Accounting",
                    company_name="Cafe Accounting SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="active",
                    valuation_method="fifo",
                ),
                Modules(module="admin", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_inventory_valuation_settings_view_renders_menu_and_current_values(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    settings_response = client.get("/settings")
    valuation_response = client.get("/settings/inventory-valuation?company=cafe")

    assert settings_response.status_code == 200
    assert "Valuación de inventarios" in settings_response.get_data(as_text=True)
    assert valuation_response.status_code == 200
    html = valuation_response.get_data(as_text=True)
    assert "Método de valuación" in html
    assert "Costo promedio" in html
    assert "FIFO" in html
    assert "cafe - Cafe Accounting" in html


def test_inventory_valuation_settings_post_updates_company_method(app_ctx):
    from cacao_accounting.database import Entity, User, database

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.post(
        "/settings/inventory-valuation",
        data={"company": "cacao", "valuation_method": "fifo"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Metodo de valuacion guardado correctamente." in response.get_data(as_text=True)
    entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
    assert entity.valuation_method == "fifo"


def test_inventory_valuation_settings_blocks_changes_with_inventory_activity(app_ctx):
    from cacao_accounting.database import Entity, StockValuationLayer, User, database

    database.session.add(
        StockValuationLayer(
            item_code="ITEM-LOCK",
            warehouse="WH-LOCK",
            company="cacao",
            qty=Decimal("10"),
            rate=Decimal("5"),
            remaining_qty=Decimal("10"),
            remaining_stock_value=Decimal("50"),
            voucher_type="stock_entry",
            voucher_id="STE-LOCK",
            posting_date=date(2026, 7, 3),
        )
    )
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    get_response = client.get("/settings/inventory-valuation?company=cacao")
    post_response = client.post(
        "/settings/inventory-valuation",
        data={"company": "cacao", "valuation_method": "fifo"},
        follow_redirects=True,
    )

    assert get_response.status_code == 200
    assert "compañía ya tiene operación de inventario contabilizada" in get_response.get_data(as_text=True)
    assert post_response.status_code == 200
    assert "No se puede cambiar la valuacion porque la compania ya tiene operacion de inventario." in post_response.get_data(
        as_text=True
    )
    entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
    assert entity.valuation_method == "moving_average"


def test_inventory_valuation_settings_helper_defaults_to_moving_average(app_ctx):
    from cacao_accounting.inventario.valuation_settings import get_company_valuation_method

    assert get_company_valuation_method("cacao") == "moving_average"
