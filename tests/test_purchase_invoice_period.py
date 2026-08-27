# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del filtro por período contable en el listado de facturas de compra."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def purchases_app():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "testing",
        }
    )
    with app.app_context():
        from cacao_accounting.database import AccountingPeriod, Entity, Modules, User, database

        database.create_all()
        user = User(user="purchases-user", name="Purchases User", classification="admin", active=True)
        user.password = b"x"
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="purchases", default=True, enabled=True),
                user,
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_purchase_invoice_list_renders_with_period_filter(purchases_app) -> None:
    """Un período válido renderiza el listado de facturas de compra."""
    from cacao_accounting.database import AccountingPeriod, User, database

    user = User.query.filter_by(user="purchases-user").first()
    client = purchases_app.test_client()
    _login(client, user.id)
    period = database.session.execute(database.select(AccountingPeriod).where(AccountingPeriod.name == "01-2026")).scalar_one()
    url = f"/buying/purchase-invoice/list?company=cacao&accounting_period_from={period.id}&accounting_period_to={period.id}"
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Listado de Facturas de Compra." in html


def test_purchase_invoice_list_rejects_other_company_period(purchases_app) -> None:
    """Un período de otra compañía es inválido para la compañía consultada."""
    from cacao_accounting.database import AccountingPeriod, Entity, User, database

    user = User.query.filter_by(user="purchases-user").first()
    database.session.add(
        Entity(
            code="otra", name="Otra SA", company_name="Otra SA", tax_id="J0002", currency="NIO", enabled=True, status="default"
        )
    )
    database.session.add(
        AccountingPeriod(
            entity="otra", name="01-2026", enabled=True, is_closed=False, start=date(2026, 1, 1), end=date(2026, 1, 31)
        )
    )
    database.session.commit()
    other_period = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.entity == "otra")
    ).scalar_one()
    client = purchases_app.test_client()
    _login(client, user.id)
    url = f"/buying/purchase-invoice/list?company=cacao&accounting_period_from={other_period.id}"
    response = client.get(url)
    assert response.status_code == 400
