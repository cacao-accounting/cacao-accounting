# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las casillas de vigencia reflejan el estado enviado por el formulario.

Escenario de negocio (issue #1962): varios endpoints usaban un default
``"1"`` o ``!= "0"`` para ``is_active``; como el navegador omite una casilla
desmarcada, era imposible crear el registro inactivo desde la interfaz.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    BankMatchingRule,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    Tax,
    TaxTemplate,
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
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
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
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Accounts(
                    entity="cacao",
                    code="110501",
                    name="Caja chica",
                    account_type="petty_cash",
                    active=True,
                    enabled=True,
                    group=False,
                    currency="NIO",
                ),
            ]
        )
        database.session.commit()
        account_id = database.session.execute(database.select(Accounts).filter_by(code="110501")).scalar_one().id
    return application, account_id


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _con_estado(datos: dict[str, str], enviar: bool) -> dict[str, str]:
    if enviar:
        datos["is_active"] = "on"
    return datos


@pytest.mark.parametrize("enviar", [False, True])
def test_impuesto_respeta_la_casilla(enviar):
    """#1962: /settings/taxes persiste Tax activo solo si la casilla llega."""
    application, _account_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/taxes",
            data=_con_estado({"name": "IVA", "rate": "15", "tax_type": "percentage"}, enviar),
        )

        assert respuesta.status_code == 302
        with application.app_context():
            impuesto = database.session.execute(database.select(Tax)).scalar_one()
            assert impuesto.is_active is enviar
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("enviar", [False, True])
def test_plantilla_respeta_la_casilla(enviar):
    """#1962: /settings/tax-templates persiste TaxTemplate según la casilla."""
    application, _account_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/tax-templates",
            data=_con_estado({"name": "Ventas", "company": "cacao", "template_type": "selling"}, enviar),
        )

        assert respuesta.status_code == 302
        with application.app_context():
            plantilla = database.session.execute(database.select(TaxTemplate)).scalar_one()
            assert plantilla.is_active is enviar
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("enviar", [False, True])
def test_regla_bancaria_respeta_la_casilla(enviar):
    """#1962: la regla de matching bancario no se activa por defecto."""
    application, _account_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/bank-matching-rules",
            data=_con_estado(
                {
                    "company": "cacao",
                    "name": "Regla",
                    "days_tolerance": "7",
                    "amount_tolerance": "0",
                    "priority": "100",
                },
                enviar,
            ),
        )

        assert respuesta.status_code == 302
        with application.app_context():
            regla = database.session.execute(database.select(BankMatchingRule)).scalar_one()
            assert regla.is_active is enviar
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("enviar", [False, True])
def test_caja_chica_respeta_la_casilla(enviar):
    """#1962: la caja chica desmarcada queda inactiva, no activa."""
    application, account_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/petty-cash/new",
            data=_con_estado(
                {
                    "company": "cacao",
                    "name": "Caja principal",
                    "account_id": account_id,
                    "float_amount": "0",
                },
                enviar,
            ),
        )

        assert respuesta.status_code == 302
        with application.app_context():
            caja = database.session.execute(database.select(PettyCashAccount)).scalar_one()
            assert caja.is_active is enviar
            assert caja.float_amount == Decimal("0")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
