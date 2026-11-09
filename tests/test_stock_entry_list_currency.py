# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Moneda transaccional en el listado de movimientos de inventario.

Escenario de negocio: la compañía tiene dos StockEntry con el mismo total
nominal en monedas distintas. El listado compartido por las ocho rutas de
inventario debe distinguir ``USD 100.00`` de ``EUR 100.00``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, StockEntry, User, UserCompanyAccess, database

CONTRASENA = "stock-lista-moneda-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def inventario_multimoneda():
    """Dos movimientos de inventario con total 100 en USD y EUR."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True),
                Currency(code="EUR", name="Euro", decimals=2, active=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="admin", company_code="cacao"),
            ]
        )
        database.session.flush()
        for currency in ("USD", "EUR"):
            database.session.add(
                StockEntry(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no=f"SE-{currency}",
                    purpose="material_receipt",
                    transaction_currency=currency,
                    total_amount=Decimal("100"),
                )
            )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_listado_stock_entry_distingue_la_moneda(inventario_multimoneda):
    """Cada total del listado identifica su moneda transaccional."""
    client = inventario_multimoneda.test_client()
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200

    response = client.get("/inventory/stock-entry/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "USD 100.00" in cuerpo
    assert "EUR 100.00" in cuerpo
