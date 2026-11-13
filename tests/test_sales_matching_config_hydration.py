# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El formulario de matching de ventas hidrata la configuración persistida.

Escenario de negocio (issue #2012): la pantalla mostraba siempre «Nueva
configuración» con defaults; guardar esa vista sobrescribía la política de
ventas existente.
"""

from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    SalesMatchingConfig,
    User,
    database,
)


def _crear_app():
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
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="CACAO",
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
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                SalesMatchingConfig(
                    company="CACAO",
                    matching_type="2-way",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("5"),
                    require_sales_order=False,
                    allow_price_difference=True,
                ),
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_hidrata_la_configuracion_de_ventas():
    """La compañía seleccionada muestra matching, tolerancia y casillas guardadas."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/settings/sales-matching?company=CACAO").get_data(as_text=True)

        assert "Editar configuración" in html
        assert 'name="company" value="CACAO"' in html
        assert re.search(r'name="matching_type".*?value="2-way" selected', html, re.S)
        assert re.search(r'name="price_tolerance_type".*?value="absolute" selected', html, re.S)
        assert Decimal(re.search(r'name="price_tolerance_value"[^>]*value="([^"]+)"', html).group(1)) == Decimal("5")
        assert not re.search(r'id="req_so"[^>]*checked', html)
        assert re.search(r'id="allow_price"[^>]*checked', html)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_sin_compania_mantiene_los_defaults_de_alta():
    """El GET inicial mantiene 3-way, porcentaje y cero."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/settings/sales-matching").get_data(as_text=True)

        assert "Nueva configuración" in html
        assert re.search(r'id="req_so"[^>]*checked', html)
        assert not re.search(r'id="allow_price"[^>]*checked', html)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
