# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Aislamiento por compañía en cierres, recurrentes y revalorización."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.services import enforce_close_and_recurring_company_access
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    ExchangeRevaluation,
    Modules,
    PeriodCloseCheck,
    PeriodCloseRun,
    RecurringJournalTemplate,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "guard-compania-2026"
FECHA = date(2026, 10, 31)


@pytest.fixture
def guard_contable():
    """Cloud con recursos Beta y un contralor autorizado solo en Alpha."""
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=False, enabled=True),
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
        database.session.flush()
        period = AccountingPeriod(
            entity="beta",
            name="PERIODO-BETA-10",
            start=date(2026, 10, 1),
            end=FECHA,
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.flush()
        run = PeriodCloseRun(company="beta", period_id=period.id, run_status="open")
        template = RecurringJournalTemplate(
            code="RECURRING-BETA",
            company="beta",
            name="Plantilla Beta",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            frequency="monthly",
            status="draft",
        )
        revaluation = ExchangeRevaluation(
            company="beta",
            posting_date=FECHA,
            run_date=FECHA,
            year=2026,
            month=10,
            status="posted",
            docstatus=1,
        )
        database.session.add_all([run, template, revaluation])
        database.session.commit()
        ids = {"close_run": run.id, "template": template.id, "revaluation": revaluation.id}
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("contralor", "accounting_user")
        database.session.commit()
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    """Authenticate the Alpha-only accounting user."""
    response = client.post("/login", data={"usuario": "contralor", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_el_guard_de_compania_vive_en_el_blueprint_registrado(guard_contable):
    """The registered accounting blueprint owns the company guard."""
    application, _ = guard_contable
    registered = application.blueprints["contabilidad"]
    assert enforce_close_and_recurring_company_access in registered.before_request_funcs.get(None, [])


@pytest.mark.parametrize(
    "path_key,path_template",
    [
        ("close_run", "/accounting/period-close/monthly/{identifier}"),
        ("template", "/accounting/journal/recurring/{identifier}"),
        ("revaluation", "/accounting/exchange-revaluation/{identifier}"),
    ],
)
def test_recursos_contables_de_otra_compania_no_se_exponen(guard_contable, path_key, path_template):
    """Cross-company close, recurring, and revaluation details fail closed."""
    application, ids = guard_contable
    client = application.test_client()
    _iniciar(client)

    response = client.get(path_template.format(identifier=ids[path_key]))

    assert response.status_code == 403
    assert "Beta SA" not in response.get_data(as_text=True)


def test_post_de_cierre_de_otra_compania_no_escribe_checks(guard_contable):
    """A cross-company close action is rejected before it mutates the run."""
    application, ids = guard_contable
    client = application.test_client()
    _iniciar(client)

    response = client.post(f"/accounting/period-close/monthly/{ids['close_run']}/apply-recurring")

    assert response.status_code == 403
    with application.app_context():
        run = database.session.get(PeriodCloseRun, ids["close_run"])
        assert run is not None and run.run_status == "open"
        assert (
            database.session.execute(
                database.select(PeriodCloseCheck).filter_by(close_run_id=ids["close_run"])
            ).scalar_one_or_none()
            is None
        )


def test_revalorizacion_de_compania_autorizada_sigue_disponible(guard_contable):
    """A company grant still allows the normal revaluation detail route."""
    application, _ = guard_contable
    with application.app_context():
        revaluation = ExchangeRevaluation(
            company="alpha",
            posting_date=FECHA,
            run_date=FECHA,
            year=2026,
            month=10,
            status="posted",
            docstatus=1,
        )
        database.session.add(revaluation)
        database.session.commit()
        identifier = revaluation.id

    client = application.test_client()
    _iniciar(client)
    response = client.get(f"/accounting/exchange-revaluation/{identifier}")

    assert response.status_code == 200


def test_post_de_ruta_con_accion_propia_no_exige_autorizar():
    """#1797: el guard aísla la compañía y no impone ``autorizar`` a todo POST."""
    from flask import request as flask_request
    from flask_login import login_user

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
                Modules(module="accounting", default=True, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="auxiliar",
                    user="auxiliar",
                    name="Auxiliar Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="auxiliar", company_code="alpha"),
            ]
        )
        database.session.flush()
        period = AccountingPeriod(
            entity="alpha",
            name="PERIODO-ALPHA-10",
            start=date(2026, 10, 1),
            end=FECHA,
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.flush()
        run = PeriodCloseRun(company="alpha", period_id=period.id, run_status="open")
        database.session.add(run)
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("auxiliar", "accounting_auxiliar")
        database.session.commit()
        usuario = database.session.get(User, "auxiliar")

        with application.test_request_context(
            f"/accounting/period-close/monthly/{run.id}/project-capitalization", method="POST"
        ):
            flask_request.view_args = {"identifier": run.id}
            login_user(usuario)
            assert enforce_close_and_recurring_company_access() is None

    with application.app_context():
        database.session.remove()
        database.engine.dispose()
