# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de periodicidad y moneda en caja y pronósticos.

Escenario de negocio (paraguas #1717):
- #1083: cualquier periodicidad no vacía se persistía y se generaba semanal.
- #1088: cambiar la cuenta de caja chica sin enviar moneda omitía la validación.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.bancos.cash_forecast_service import generate_periods
from cacao_accounting.bancos.services import update_petty_cash_account
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CashForecast,
    Currency,
    Entity,
    FiscalYear,
    Modules,
    PettyCashAccount,
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
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
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
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Accounts(
                    entity="cacao",
                    code="110501",
                    name="Caja chica NIO",
                    account_type="petty_cash",
                    currency="NIO",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="110502",
                    name="Caja chica USD",
                    account_type="petty_cash",
                    currency="USD",
                    active=True,
                    enabled=True,
                    group=False,
                ),
            ]
        )
        database.session.flush()
        anio = FiscalYear(
            entity="cacao",
            name="FY-2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        database.session.add(anio)
        database.session.commit()
        ids = {
            "anio": anio.id,
            "cuenta_nio": database.session.execute(database.select(Accounts).filter_by(code="110501")).scalar_one().id,
            "cuenta_usd": database.session.execute(database.select(Accounts).filter_by(code="110502")).scalar_one().id,
        }
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_generate_periods_rechaza_periodicidad_desconocida():
    """#1083: el servicio no asume weekly para valores arbitrarios."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            anio = database.session.get(FiscalYear, ids["anio"])
            with pytest.raises(ValueError, match="semanal o mensual"):
                generate_periods(anio, "annual")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_pronostico_no_persiste_periodicidad_invalida():
    """#1083: el POST con periodicidad anual vuelve al formulario."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/cash-forecast/new?company=cacao",
            data={"version": "v1", "fiscal_year_id": ids["anio"], "periodicity": "annual"},
        )

        assert respuesta.status_code == 200
        assert "La periodicidad debe ser semanal o mensual." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(CashForecast)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_pronostico_valido_se_crea():
    """#1083: las periodicidades soportadas siguen funcionando."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/cash-forecast/new?company=cacao",
            data={"version": "v1", "fiscal_year_id": ids["anio"], "periodicity": "monthly"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            pronostico = database.session.execute(database.select(CashForecast)).scalar_one()
            assert pronostico.periodicity == "monthly"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cambio_de_cuenta_exige_moneda_compatible():
    """#1088: cambiar a una cuenta USD conservando NIO se rechaza."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            caja = PettyCashAccount(
                company="cacao",
                account_id=ids["cuenta_nio"],
                name="Caja principal",
                currency="NIO",
                float_amount=Decimal("0"),
                is_active=True,
            )
            database.session.add(caja)
            database.session.commit()

            with pytest.raises(ValueError, match="moneda de su cuenta contable"):
                update_petty_cash_account(caja, account_id=ids["cuenta_usd"])

            database.session.refresh(caja)
            assert caja.account_id == ids["cuenta_nio"]
            assert caja.currency == "NIO"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cambio_de_cuenta_compatible_se_guarda():
    """#1088: una cuenta de la misma moneda sigue actualizándose."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            caja = PettyCashAccount(
                company="cacao",
                account_id=ids["cuenta_nio"],
                name="Caja principal",
                currency="NIO",
                float_amount=Decimal("0"),
                is_active=True,
            )
            database.session.add(caja)
            database.session.commit()
            otra_nio = Accounts(
                entity="cacao",
                code="110503",
                name="Caja chica NIO 2",
                account_type="petty_cash",
                currency="NIO",
                active=True,
                enabled=True,
                group=False,
            )
            database.session.add(otra_nio)
            database.session.commit()

            update_petty_cash_account(caja, account_id=otra_nio.id)
            assert caja.account_id == otra_nio.id
            assert caja.currency == "NIO"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
