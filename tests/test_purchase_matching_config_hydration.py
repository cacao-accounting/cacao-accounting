# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El formulario de matching hidrata la configuración persistida.

Escenario de negocio (issue #2012): la pantalla mostraba siempre el formulario
«Nueva configuración» con defaults; guardar esa vista sobrescribía la política
existente de la compañía (matching, tolerancias, controles y anticipos).
"""

from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyDefaultAccount,
    Currency,
    Entity,
    Modules,
    PurchaseMatchingConfig,
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
        database.session.add(
            Entity(
                code="CACAO",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                PurchaseMatchingConfig(
                    company="CACAO",
                    matching_type="2-way",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("5"),
                    qty_tolerance_type="absolute",
                    qty_tolerance_value=Decimal("3"),
                    require_purchase_order=False,
                    bridge_account_required=False,
                    auto_reconcile=False,
                    allow_price_difference=True,
                ),
                CompanyDefaultAccount(company="CACAO", apply_advances_automatically=True),
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


def test_el_formulario_muestra_los_valores_persistidos():
    """La compañía seleccionada hidrata todos los controles guardados."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/settings/purchase-reconciliation?company=CACAO").get_data(as_text=True)

        assert "Editar configuración" in html
        assert 'name="company" value="CACAO"' in html
        assert re.search(r'name="matching_type".*?value="2-way" selected', html, re.S)
        assert re.search(r'name="price_tolerance_type".*?value="absolute" selected', html, re.S)
        assert Decimal(re.search(r'name="price_tolerance_value"[^>]*value="([^"]+)"', html).group(1)) == Decimal("5")
        assert Decimal(re.search(r'name="qty_tolerance_value"[^>]*value="([^"]+)"', html).group(1)) == Decimal("3")
        assert not re.search(r'id="req_po"[^>]*checked', html)
        assert not re.search(r'id="req_bridge"[^>]*checked', html)
        assert not re.search(r'id="auto_rec"[^>]*checked', html)
        assert re.search(r'id="allow_price"[^>]*checked', html)
        assert re.search(r'id="apply_advances_automatically"[^>]*checked', html)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_sin_compania_mantiene_el_formulario_de_alta():
    """El GET inicial conserva los defaults de una configuración nueva."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/settings/purchase-reconciliation").get_data(as_text=True)

        assert "Nueva configuración" in html
        assert not re.search(r'id="apply_advances_automatically"[^>]*checked', html)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
