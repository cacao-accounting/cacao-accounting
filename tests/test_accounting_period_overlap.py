# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1155: los períodos contables no se superponen dentro de una compañía.

Las pruebas usan compañías y años fiscales propios para no depender de los
períodos que otros escenarios dejan en la base compartida de la suite.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import AccountingPeriod, Entity, FiscalYear, User, UserCompanyAccess, database

FECHA_INICIO = date(2026, 1, 1)
FECHA_FIN = date(2026, 12, 31)


@pytest.fixture
def periodos_aislados(app, entorno_contable):
    """Crea dos compañías con su año fiscal y limpia todo lo que crea la prueba."""
    sufijo = uuid4().hex[:6].upper()
    creados = {
        "periods": [],
        "fiscal_years": [f"FYB{sufijo}", f"FYG{sufijo}"],
        "entities": [f"B{sufijo}", f"G{sufijo}"],
    }
    with app.app_context():
        database.session.add_all(
            [
                Entity(
                    code=creados["entities"][0],
                    name=f"Beta {sufijo}",
                    company_name=f"Beta {sufijo} SA",
                    tax_id=f"J-B{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code=creados["entities"][1],
                    name=f"Gamma {sufijo}",
                    company_name=f"Gamma {sufijo} SA",
                    tax_id=f"J-G{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                FiscalYear(
                    id=creados["fiscal_years"][0],
                    entity=creados["entities"][0],
                    name=f"Año Beta {sufijo}",
                    year_start_date=FECHA_INICIO,
                    year_end_date=FECHA_FIN,
                    is_closed=False,
                ),
                FiscalYear(
                    id=creados["fiscal_years"][1],
                    entity=creados["entities"][1],
                    name=f"Año Gamma {sufijo}",
                    year_start_date=FECHA_INICIO,
                    year_end_date=FECHA_FIN,
                    is_closed=False,
                ),
            ]
        )
        # #1828: en Cloud la clasificación admin no concede compañías por sí
        # sola; el formulario publica como admin y debe alcanzar ambas compañías.
        admin_user = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        for entity_code in creados["entities"]:
            if (
                database.session.execute(
                    select(UserCompanyAccess).filter_by(user_id=admin_user.id, company_code=entity_code)
                ).scalar_one_or_none()
                is None
            ):
                database.session.add(UserCompanyAccess(user_id=admin_user.id, company_code=entity_code))
        database.session.commit()
    yield creados
    with app.app_context():
        admin_user = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        for entity_code in creados["entities"]:
            access = database.session.execute(
                select(UserCompanyAccess).filter_by(user_id=admin_user.id, company_code=entity_code)
            ).scalar_one_or_none()
            if access is not None:
                database.session.delete(access)
        database.session.flush()
        for period_id in creados["periods"]:
            period = database.session.get(AccountingPeriod, period_id)
            if period is not None:
                database.session.delete(period)
        database.session.flush()
        for fiscal_year_id in creados["fiscal_years"]:
            fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
            if fiscal_year is not None:
                database.session.delete(fiscal_year)
        database.session.flush()
        for entity_code in creados["entities"]:
            entity = database.session.get(Entity, entity_code)
            if entity is not None:
                database.session.delete(entity)
        database.session.commit()


def _crear_periodo(app, creados, *, entity: str, fiscal_year: str, nombre: str, start: date, end: date) -> str:
    """Inserta un período vigente y registra su identificador para la limpieza."""
    period_id = f"P{uuid4().hex[:24]}"
    with app.app_context():
        database.session.add(
            AccountingPeriod(
                id=period_id,
                entity=entity,
                fiscal_year_id=fiscal_year,
                name=nombre,
                start=start,
                end=end,
                enabled=True,
                is_closed=False,
            )
        )
        database.session.commit()
    creados["periods"].append(period_id)
    return period_id


def _formulario(*, entity: str, fiscal_year: str, nombre: str, start: date, end: date) -> dict[str, str]:
    """Construye el POST del formulario de período con fechas ISO."""
    return {
        "id": f"P{uuid4().hex[:20]}",
        "entidad": entity,
        "fiscal_year": fiscal_year,
        "nombre": nombre,
        "inicio": start.isoformat(),
        "fin": end.isoformat(),
        "habilitado": "on",
    }


def _periodo_por_nombre(app, nombre: str) -> AccountingPeriod | None:
    """Busca un período persistido por su nombre único de prueba."""
    with app.app_context():
        return database.session.execute(database.select(AccountingPeriod).filter_by(name=nombre)).scalar_one_or_none()


def test_nuevo_periodo_rechaza_superposicion(app, authenticated_client, periodos_aislados):
    """Un rango que cruza un período existente no se persiste."""
    beta = periodos_aislados["entities"][0]
    fiscal_year = periodos_aislados["fiscal_years"][0]
    _crear_periodo(
        app,
        periodos_aislados,
        entity=beta,
        fiscal_year=fiscal_year,
        nombre=f"Beta marzo {uuid4().hex[:6]}",
        start=date(2026, 3, 1),
        end=date(2026, 3, 31),
    )
    nombre = f"Beta solapado {uuid4().hex[:8]}"

    respuesta = authenticated_client().post(
        "/accounting/accounting_period/new",
        data=_formulario(
            entity=beta,
            fiscal_year=fiscal_year,
            nombre=nombre,
            start=date(2026, 3, 15),
            end=date(2026, 4, 15),
        ),
    )

    assert respuesta.status_code == 200
    assert "se superpone" in respuesta.get_data(as_text=True)
    assert _periodo_por_nombre(app, nombre) is None


def test_nuevo_periodo_acepta_rango_adyacente(app, authenticated_client, periodos_aislados):
    """Un período que empieza justo después del anterior no se considera solapado."""
    beta = periodos_aislados["entities"][0]
    fiscal_year = periodos_aislados["fiscal_years"][0]
    _crear_periodo(
        app,
        periodos_aislados,
        entity=beta,
        fiscal_year=fiscal_year,
        nombre=f"Beta marzo {uuid4().hex[:6]}",
        start=date(2026, 3, 1),
        end=date(2026, 3, 31),
    )
    nombre = f"Beta abril {uuid4().hex[:8]}"

    respuesta = authenticated_client().post(
        "/accounting/accounting_period/new",
        data=_formulario(
            entity=beta,
            fiscal_year=fiscal_year,
            nombre=nombre,
            start=date(2026, 4, 1),
            end=date(2026, 4, 30),
        ),
    )

    assert respuesta.status_code == 302
    periodo = _periodo_por_nombre(app, nombre)
    assert periodo is not None
    periodos_aislados["periods"].append(periodo.id)


def test_editar_periodo_rechaza_superposicion_y_conserva_fechas(app, authenticated_client, periodos_aislados):
    """La edición no mueve un período sobre otro ni reescribe sus fechas."""
    beta = periodos_aislados["entities"][0]
    fiscal_year = periodos_aislados["fiscal_years"][0]
    _crear_periodo(
        app,
        periodos_aislados,
        entity=beta,
        fiscal_year=fiscal_year,
        nombre=f"Beta marzo {uuid4().hex[:6]}",
        start=date(2026, 3, 1),
        end=date(2026, 3, 31),
    )
    nombre = f"Beta mayo {uuid4().hex[:8]}"
    period_id = _crear_periodo(
        app,
        periodos_aislados,
        entity=beta,
        fiscal_year=fiscal_year,
        nombre=nombre,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
    )

    respuesta = authenticated_client().post(
        f"/accounting/accounting_period/{period_id}/edit",
        data=_formulario(
            entity=beta,
            fiscal_year=fiscal_year,
            nombre=nombre,
            start=date(2026, 3, 15),
            end=date(2026, 4, 15),
        ),
    )

    assert respuesta.status_code == 200
    assert "se superpone" in respuesta.get_data(as_text=True)
    with app.app_context():
        periodo = database.session.get(AccountingPeriod, period_id)
        assert periodo is not None
        assert periodo.start == date(2026, 5, 1)
        assert periodo.end == date(2026, 5, 31)


def test_editar_periodo_acepta_rango_libre(app, authenticated_client, periodos_aislados):
    """La edición válida actualiza ambas fechas del período."""
    beta = periodos_aislados["entities"][0]
    fiscal_year = periodos_aislados["fiscal_years"][0]
    nombre = f"Beta junio {uuid4().hex[:8]}"
    period_id = _crear_periodo(
        app,
        periodos_aislados,
        entity=beta,
        fiscal_year=fiscal_year,
        nombre=nombre,
        start=date(2026, 6, 1),
        end=date(2026, 6, 30),
    )

    respuesta = authenticated_client().post(
        f"/accounting/accounting_period/{period_id}/edit",
        data=_formulario(
            entity=beta,
            fiscal_year=fiscal_year,
            nombre=nombre,
            start=date(2026, 7, 1),
            end=date(2026, 7, 31),
        ),
    )

    assert respuesta.status_code == 302
    with app.app_context():
        periodo = database.session.get(AccountingPeriod, period_id)
        assert periodo is not None
        assert periodo.start == date(2026, 7, 1)
        assert periodo.end == date(2026, 7, 31)


def test_mismo_rango_en_otra_compania_es_valido(app, authenticated_client, periodos_aislados):
    """La superposición se evalúa por compañía: dos compañías comparten fechas."""
    beta = periodos_aislados["entities"][0]
    gamma = periodos_aislados["entities"][1]
    fiscal_year_beta = periodos_aislados["fiscal_years"][0]
    fiscal_year_gamma = periodos_aislados["fiscal_years"][1]
    _crear_periodo(
        app,
        periodos_aislados,
        entity=beta,
        fiscal_year=fiscal_year_beta,
        nombre=f"Beta agosto {uuid4().hex[:6]}",
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
    )
    nombre = f"Gamma agosto {uuid4().hex[:8]}"

    respuesta = authenticated_client().post(
        "/accounting/accounting_period/new",
        data=_formulario(
            entity=gamma,
            fiscal_year=fiscal_year_gamma,
            nombre=nombre,
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        ),
    )

    assert respuesta.status_code == 302
    periodo = _periodo_por_nombre(app, nombre)
    assert periodo is not None
    assert periodo.entity == gamma
    periodos_aislados["periods"].append(periodo.id)
