# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1156: cerrar y reabrir no altera la configuración ``enabled``.

Un período deshabilitado no entra al asistente de cierre y la reapertura
conserva su valor; solo una acción explícita de administración lo habilita.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    FiscalYear,
    PeriodCloseCheck,
    PeriodCloseRun,
    User,
    UserCompanyAccess,
    database,
)


def _crear_empresa_y_anio(sufijo: str) -> tuple[str, str]:
    """Crea compañía y año fiscal únicos para aislar los períodos."""
    company = f"D{sufijo}"
    fiscal_year_id = f"FYD{sufijo}"
    database.session.add(
        Entity(
            code=company,
            name=f"Compañía {sufijo}",
            company_name=f"Compañía {sufijo} SA",
            tax_id=f"J-D{sufijo}",
            currency="NIO",
            enabled=True,
            status="activo",
        )
    )
    database.session.flush()
    database.session.add(
        FiscalYear(
            id=fiscal_year_id,
            entity=company,
            name=f"Año {sufijo}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
    )
    database.session.flush()
    return company, fiscal_year_id


@pytest.fixture
def periodos_cierre(app, entorno_contable):
    """Un período habilitado y otro deshabilitado en una compañía propia."""
    sufijo = uuid4().hex[:6].upper()
    with app.app_context():
        company, fiscal_year_id = _crear_empresa_y_anio(sufijo)
        habilitado = f"PA{sufijo}"
        deshabilitado = f"PD{sufijo}"
        habilitado_name = f"Periodo habilitado {sufijo}"
        deshabilitado_name = f"Periodo deshabilitado {sufijo}"
        database.session.add_all(
            [
                AccountingPeriod(
                    id=habilitado,
                    entity=company,
                    fiscal_year_id=fiscal_year_id,
                    name=habilitado_name,
                    start=date(2026, 4, 1),
                    end=date(2026, 4, 30),
                    enabled=True,
                    is_closed=False,
                ),
                AccountingPeriod(
                    id=deshabilitado,
                    entity=company,
                    fiscal_year_id=fiscal_year_id,
                    name=deshabilitado_name,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                    enabled=False,
                    is_closed=False,
                ),
            ]
        )
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        database.session.add(UserCompanyAccess(user_id=admin.id, company_code=company))
        database.session.commit()
    yield {
        "company": company,
        "fiscal_year": fiscal_year_id,
        "habilitado": habilitado,
        "deshabilitado": deshabilitado,
        "habilitado_name": habilitado_name,
        "deshabilitado_name": deshabilitado_name,
    }
    with app.app_context():
        for period_id in (habilitado, deshabilitado):
            for run in database.session.execute(database.select(PeriodCloseRun).filter_by(period_id=period_id)).scalars():
                for check in database.session.execute(
                    database.select(PeriodCloseCheck).filter_by(close_run_id=run.id)
                ).scalars():
                    database.session.delete(check)
                database.session.delete(run)
        database.session.flush()
        for period_id in (habilitado, deshabilitado):
            period = database.session.get(AccountingPeriod, period_id)
            if period is not None:
                database.session.delete(period)
        database.session.flush()
        fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
        if fiscal_year is not None:
            database.session.delete(fiscal_year)
        database.session.flush()
        database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.company_code == company))
        entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalar_one_or_none()
        if entity is not None:
            database.session.delete(entity)
        database.session.commit()


def test_asistente_excluye_periodos_deshabilitados(app, authenticated_client, periodos_cierre):
    """La lista de períodos disponibles no ofrece un período deshabilitado."""
    from flask import template_rendered

    from cacao_accounting.runtime_mode import is_desktop_mode

    if is_desktop_mode():
        pytest.skip("El escenario usa una compañía adicional y Desktop opera una sola compañía.")

    periodo = periodos_cierre
    capturado: dict[str, object] = {}

    def _capturar(sender, template, context, **extra):
        if template.name.endswith("monthly_close_assistant.html"):
            capturado.update(context)

    template_rendered.connect(_capturar, app)
    try:
        respuesta = authenticated_client().get("/accounting/period-close/monthly")
    finally:
        template_rendered.disconnect(_capturar, app)

    assert respuesta.status_code == 200
    periodos = {period.id for period in capturado["periods"]}
    assert periodo["habilitado"] in periodos
    assert periodo["deshabilitado"] not in periodos


def test_cierre_de_periodo_deshabilitado_se_rechaza(app, authenticated_client, periodos_cierre):
    """El POST no crea un cierre para un período deshabilitado."""
    periodo = periodos_cierre

    respuesta = authenticated_client().post(
        "/accounting/period-close/monthly/new",
        data={"period_id": periodo["deshabilitado"]},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert "deshabilitado" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert (
            database.session.execute(database.select(PeriodCloseRun).filter_by(period_id=periodo["deshabilitado"]))
            .scalars()
            .all()
            == []
        )


def test_cierre_de_periodo_habilitado_sigue_creandose(app, authenticated_client, periodos_cierre):
    """Control positivo: un período habilitado conserva el flujo normal."""
    periodo = periodos_cierre

    respuesta = authenticated_client().post(
        "/accounting/period-close/monthly/new",
        data={"period_id": periodo["habilitado"]},
        follow_redirects=False,
    )

    assert respuesta.status_code == 302
    with app.app_context():
        run = database.session.execute(database.select(PeriodCloseRun).filter_by(period_id=periodo["habilitado"])).scalar_one()
        assert run.run_status == "open"


def _aplicacion_desktop() -> object:
    """Aplicación aislada en modo desktop para la reapertura sin aprobaciones."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def _preparar_reapertura(*, enabled: bool):
    """Crea un período cerrado con su corrida de cierre finalizada."""
    application = _aplicacion_desktop()
    sufijo = uuid4().hex[:6].upper()
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        company, fiscal_year_id = _crear_empresa_y_anio(sufijo)
        period = AccountingPeriod(
            id=f"PR{sufijo}",
            entity=company,
            fiscal_year_id=fiscal_year_id,
            name=f"Periodo cerrado {sufijo}",
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
            enabled=enabled,
            is_closed=True,
            status="habilitado_cerrado" if enabled else "deshabilitado_cerrado",
        )
        database.session.add(period)
        database.session.flush()
        database.session.add(
            PeriodCloseRun(
                company=company,
                period_id=period.id,
                run_status="closed",
                closed_at=datetime.now(timezone.utc),
            )
        )
        database.session.commit()
        period_id = period.id
    return application, period_id


@pytest.mark.parametrize(
    ("enabled", "expected_status"),
    [(False, "deshabilitado_abierto"), (True, "habilitado_abierto")],
)
def test_reapertura_preserva_enabled(enabled: bool, expected_status: str):
    """Reabrir cambia el cierre, no la configuración enabled del período."""
    from cacao_accounting.contabilidad.services import reopen_accounting_period

    application, period_id = _preparar_reapertura(enabled=enabled)
    with application.app_context():
        reopen_accounting_period(period_id, user_id="admin", reason="Corrección del cierre")
        period = database.session.get(AccountingPeriod, period_id)
        assert period is not None
        assert period.is_closed is False
        assert bool(period.enabled) is enabled
        assert period.status == expected_status
        database.session.remove()
        database.engine.dispose()
