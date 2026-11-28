# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1698: los pasos del cierre no reabren una corrida cerrada."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import AccountingPeriod, PeriodCloseCheck, PeriodCloseRun, database

PASOS = (
    "/accounting/period-close/monthly/{}/project-capitalization",
    "/accounting/period-close/monthly/{}/apply-recurring",
    "/accounting/period-close/monthly/{}/exchange-revaluation",
)


@pytest.fixture
def closed_run(app, entorno_contable):
    """Corrida de cierre cerrada con su período marcado como cerrado."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        period = AccountingPeriod(
            entity="cacao",
            name=f"CIERRE-{sufijo}",
            enabled=True,
            is_closed=True,
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
        )
        database.session.add(period)
        database.session.flush()
        run = PeriodCloseRun(company="cacao", period_id=period.id, run_status="closed")
        database.session.add(run)
        database.session.commit()
        run_id, period_id = run.id, period.id
    yield run_id
    with app.app_context():
        database.session.execute(database.delete(PeriodCloseCheck).where(PeriodCloseCheck.close_run_id == run_id))
        database.session.execute(database.delete(PeriodCloseRun).where(PeriodCloseRun.id == run_id))
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.id == period_id))
        database.session.commit()


@pytest.mark.parametrize("path", PASOS)
def test_paso_sobre_corrida_cerrada_no_muta_estado(app, authenticated_client, closed_run, path):
    """El POST se rechaza sin cambiar run_status ni registrar el paso."""
    response = authenticated_client("admin").post(path.format(closed_run))

    assert response.status_code == 302
    with app.app_context():
        run = database.session.get(PeriodCloseRun, closed_run)
        assert run.run_status == "closed"
        period = database.session.get(AccountingPeriod, run.period_id)
        assert period.is_closed is True
        checks = database.session.execute(database.select(PeriodCloseCheck).filter_by(close_run_id=closed_run)).scalars().all()
        assert checks == []
