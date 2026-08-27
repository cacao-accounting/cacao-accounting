# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del filtro por período contable en el listado de facturas de venta."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def sales_app():
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
        user = User(user="sales-user", name="Sales User", classification="admin", active=True)
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
                Entity(
                    code="otra",
                    name="Otra Compañía",
                    company_name="Otra SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="sales", default=True, enabled=True),
                user,
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
                AccountingPeriod(
                    entity="otra",
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


def _period_id(company: str, name: str) -> str:
    from cacao_accounting.database import AccountingPeriod, database

    period = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.entity == company, AccountingPeriod.name == name)
    ).scalar_one()
    return str(period.id)


def test_sales_invoice_list_renders_with_period_filter(sales_app) -> None:
    """Un período válido renderiza el listado (aunque no haya comprobantes)."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="sales-user").first()
    client = sales_app.test_client()
    _login(client, user.id)
    pid = _period_id("cacao", "01-2026")
    url = f"/sales/sales-invoice/list?company=cacao&accounting_period_from={pid}&accounting_period_to={pid}"
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Listado de Facturas de Venta." in html


def test_sales_invoice_list_rejects_other_company_period(sales_app) -> None:
    """Un período de otra compañía es inválido para la compañía consultada."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="sales-user").first()
    client = sales_app.test_client()
    _login(client, user.id)
    url = f"/sales/sales-invoice/list?company=cacao&accounting_period_from={_period_id('otra', '01-2026')}"
    response = client.get(url)
    assert response.status_code == 400


def test_sales_invoice_list_without_period_is_unchanged(sales_app) -> None:
    """Sin filtro de período el listado conserva su comportamiento."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="sales-user").first()
    client = sales_app.test_client()
    _login(client, user.id)
    response = client.get("/sales/sales-invoice/list?company=cacao")
    assert response.status_code == 200
