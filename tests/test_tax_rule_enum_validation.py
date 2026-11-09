# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las reglas fiscales validan sus campos enumerados.

Escenario de negocio (issue #2005): un POST alterado podía persistir
applies_to/level/tax_type/calculation_method/base_mode/accounting_treatment/
recognition_event fuera de catálogo; el builder excluía la regla o el motor
calculaba cero en silencio.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    TaxRule,
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
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
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
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
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


def _formulario(**overrides) -> dict[str, str]:
    datos = {
        "name": "Regla fiscal",
        "company": "cacao",
        "concept": "iva",
        "applies_to": "sales",
        "level": "transaction",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "rate": "15",
        "amount": "0",
        "base_mode": "goods",
        "sequence": "10",
        "accounting_treatment": "separate_tax_account",
        "recognition_event": "invoice",
        "currency": "NIO",
        "country": "NI",
        "is_active": "on",
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("applies_to", "garbage"),
        ("level", "unknown"),
        ("tax_type", "mystery"),
        ("calculation_method", "mystery"),
        ("base_mode", "other"),
        ("accounting_treatment", "whatever"),
        ("recognition_event", "whenever"),
    ],
)
def test_rechaza_enums_fuera_de_catalogo(campo, valor):
    """Cada dominio inválido se rechaza sin persistir."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/tax-rules", data=_formulario(**{campo: valor}))

        assert respuesta.status_code == 200
        assert f"El valor de {campo} no es válido" in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(TaxRule)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_acepta_los_valores_del_catalogo():
    """La combinación válida se persiste con sus enums intactos."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/tax-rules",
            data=_formulario(
                applies_to="purchase",
                level="item",
                tax_type="withholding",
                calculation_method="fixed",
                base_mode="accumulated",
                accounting_treatment="capitalizable_inventory_cost",
                recognition_event="purchase_invoice_confirmed",
            ),
        )

        assert respuesta.status_code == 302
        with application.app_context():
            regla = database.session.execute(database.select(TaxRule)).scalar_one()
            assert regla.applies_to == "purchase"
            assert regla.level == "item"
            assert regla.tax_type == "withholding"
            assert regla.calculation_method == "fixed"
            assert regla.base_mode == "accumulated"
            assert regla.accounting_treatment == "capitalizable_inventory_cost"
            assert regla.recognition_event == "purchase_invoice_confirmed"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
