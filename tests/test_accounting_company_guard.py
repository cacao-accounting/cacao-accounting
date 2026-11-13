# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Aislamiento por compañía en cierres, recurrentes y revalorización.

Escenario de negocio: un contralor autorizado únicamente en la compañía
``alpha`` no debe leer ni ejecutar pasos de cierre, plantillas recurrentes o
revalorizaciones de ``beta``. El guard de compañía debe vivir en el blueprint
de contabilidad que la aplicación registra realmente; si queda en un blueprint
no registrado, las rutas se comportan como si no tuvieran aislamiento.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    ExchangeRevaluation,
    Modules,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "guard-compania-2026"
FECHA = date(2026, 10, 31)


@pytest.fixture
def guard_contable():
    """Cloud con dos compañías y un contralor autorizado solo en alpha."""
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
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                AccountingPeriod(
                    entity="beta",
                    name="PERIODO-BETA-10",
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    enabled=True,
                    is_closed=False,
                ),
                User(
                    id="contralor",
                    user="contralor",
                    name="Contralor Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="contralor", company_code="alpha"),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("contralor", "accounting_user")
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "contralor", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_el_guard_de_compania_vive_en_el_blueprint_registrado(guard_contable):
    """El before_request debe pertenecer al blueprint que la app registra."""
    from cacao_accounting.contabilidad.services import enforce_close_and_recurring_company_access

    blueprint = guard_contable.blueprints["contabilidad"]
    guardas = blueprint.before_request_funcs.get(None, [])
    assert enforce_close_and_recurring_company_access in guardas


def test_revalorizacion_ajena_no_se_expone(guard_contable):
    """Un contralor de alpha no lee la revalorización de beta."""
    application = guard_contable
    with application.app_context():
        corrida = ExchangeRevaluation(
            company="beta",
            posting_date=FECHA,
            run_date=FECHA,
            year=2026,
            month=10,
            status="posted",
            docstatus=1,
        )
        database.session.add(corrida)
        database.session.commit()
        corrida_id = corrida.id

    client = application.test_client()
    _iniciar(client)
    response = client.get(f"/accounting/exchange-revaluation/{corrida_id}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "PERIODO-BETA-10" not in cuerpo
    assert "Beta SA" not in cuerpo


def test_revalorizacion_propia_es_consultable(guard_contable):
    """Control positivo: la corrida de la compañía autorizada sí se consulta."""
    application = guard_contable
    with application.app_context():
        corrida = ExchangeRevaluation(
            company="alpha",
            posting_date=FECHA,
            run_date=FECHA,
            year=2026,
            month=10,
            status="posted",
            docstatus=1,
        )
        database.session.add(corrida)
        database.session.commit()
        corrida_id = corrida.id

    client = application.test_client()
    _iniciar(client)
    response = client.get(f"/accounting/exchange-revaluation/{corrida_id}")

    assert response.status_code == 200
