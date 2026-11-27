# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1248: los reportes GL rechazan un período inexistente o ajeno.

Un ``accounting_period`` que no pertenece a la compañía resolvía límites
nulos y el reporte mostraba todo el historial como si no se hubiera
solicitado filtro temporal.
"""

from datetime import date
from uuid import uuid4

import pytest

# pylint: disable=redefined-outer-name
from cacao_accounting.database import AccountingPeriod, Entity, database

FINANCIAL_REPORT_ROUTES = (
    "/reports/trial-balance",
    "/reports/account-summary",
    "/reports/income-statement",
)


@pytest.fixture
def foreign_period(app):
    """Crea un período de otra compañía y lo elimina al finalizar la prueba."""
    suffix = uuid4().hex[:8]
    code = f"Z{suffix}"
    with app.app_context():
        database.session.add(
            Entity(
                code=code,
                name=f"Compañía {code}",
                company_name=f"Compañía {code} SA",
                tax_id=f"TAX-{code}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        period = AccountingPeriod(
            entity=code,
            name=f"PERIODO-{suffix}",
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.commit()
        ids = {"code": code, "period_id": period.id, "period_name": period.name}

    yield ids
    with app.app_context():
        saved_period = database.session.get(AccountingPeriod, ids["period_id"])
        if saved_period is not None:
            database.session.delete(saved_period)
        saved_entity = database.session.execute(database.select(Entity).filter_by(code=code)).scalar_one_or_none()
        if saved_entity is not None:
            database.session.delete(saved_entity)
        database.session.commit()


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_rechaza_periodo_inexistente(authenticated_client, route):
    """Un identificador o nombre que no existe devuelve 400, no todo el historial."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&accounting_period=PERIODO-INEXISTENTE")

    assert response.status_code == 400


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_rechaza_periodo_de_otra_compania(authenticated_client, foreign_period, route):
    """Un período existente de otra compañía no se acepta como filtro."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&accounting_period={foreign_period['period_id']}")

    assert response.status_code == 400


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_acepta_periodo_valido_por_id_y_nombre(app, authenticated_client, entorno_contable, route):
    """El período de la compañía se resuelve por id y por nombre."""
    del entorno_contable
    with app.app_context():
        period_id, period_name = database.session.execute(
            database.select(AccountingPeriod.id, AccountingPeriod.name)
            .filter_by(entity="cacao")
            .order_by(AccountingPeriod.start)
        ).first()
    client = authenticated_client("admin")

    by_id = client.get(f"{route}?apply_filters=1&company=cacao&accounting_period={period_id}")
    by_name = client.get(f"{route}?apply_filters=1&company=cacao&accounting_period={period_name}")

    assert by_id.status_code == 200
    assert by_name.status_code == 200
