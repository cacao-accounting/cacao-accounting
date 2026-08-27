# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del contrato común de rangos de períodos contables completos.

Cubre los criterios de aceptación de la primitiva compartida:

- Período mensual válido (solo y en rango).
- Período inexistente.
- Período perteneciente a otra compañía.
- Períodos abiertos y cerrados para consultas.
- Período de ajuste con fechas no equivalentes a un mes calendario.
- Límites inclusivos en primer y último día.
- Rechazo de rangos invertidos y de rangos parciales enviados manualmente.
- Selección predeterminada del período actual.
"""

from __future__ import annotations

from datetime import date

import pytest
from werkzeug.exceptions import BadRequest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def periods_app():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "testing",
        }
    )
    with app.app_context():
        from cacao_accounting.database import AccountingPeriod, Entity, Modules, User, database

        database.create_all()
        user = User(user="periods-user", name="Periods User", classification="admin", active=True)
        user.password = b"x"
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="otra",
                    name="Otra Compañía",
                    company_name="Otra SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                user,
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
                AccountingPeriod(
                    entity="cacao", name="02-2026", enabled=True, is_closed=True, start=date(2026, 2, 1), end=date(2026, 2, 28)
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="AJUSTE-Q1",
                    enabled=True,
                    is_closed=True,
                    start=date(2026, 3, 15),
                    end=date(2026, 3, 31),
                ),
                AccountingPeriod(
                    entity="otra", name="01-2026", enabled=True, is_closed=False, start=date(2026, 1, 1), end=date(2026, 1, 31)
                ),
            ]
        )
        database.session.commit()
        yield app


def _period_ids(company: str = "cacao") -> dict[str, str]:
    """Devuelve name→id de los períodos de la compañía indicada."""
    from cacao_accounting.database import AccountingPeriod, database

    rows = database.session.execute(database.select(AccountingPeriod)).scalars().all()
    return {period.name: str(period.id) for period in rows if period.entity == company}


def test_single_period_resolves_inclusive_boundaries(periods_app) -> None:
    """Un período mensual resuelve del primer al último día, ambos inclusivos."""
    from cacao_accounting.reportes.periods import resolve_period_range

    period_range = resolve_period_range("cacao", _period_ids()["01-2026"], None)
    assert period_range is not None
    assert period_range.single_period
    assert period_range.period_start == date(2026, 1, 1)
    assert period_range.period_end == date(2026, 1, 31)
    assert period_range.label == "01-2026"


def test_range_resolves_from_start_of_first_to_end_of_last(periods_app) -> None:
    """Un rango 01-2026 a 02-2026 abarca desde el primer día del inicial hasta el último del final."""
    from cacao_accounting.reportes.periods import resolve_period_range

    period_range = resolve_period_range("cacao", _period_ids()["01-2026"], _period_ids()["02-2026"])
    assert period_range is not None
    assert not period_range.single_period
    assert period_range.period_start == date(2026, 1, 1)
    assert period_range.period_end == date(2026, 2, 28)
    assert period_range.label == "01-2026 – 02-2026"


def test_nonexistent_period_is_rejected(periods_app) -> None:
    """Un período inexistente dispara error 400 (BadRequest)."""
    from cacao_accounting.reportes.periods import resolve_period_range

    with pytest.raises(BadRequest):
        resolve_period_range("cacao", "no-existe", "no-existe")


def test_period_from_another_company_is_rejected(periods_app) -> None:
    """Un período de otra compañía no es válido para la compañía consultada."""
    from cacao_accounting.reportes.periods import resolve_period_range

    other_company_period = _period_ids("otra")["01-2026"]
    with pytest.raises(BadRequest):
        resolve_period_range("cacao", other_company_period, None)
    cacao_period = _period_ids()["01-2026"]
    with pytest.raises(BadRequest):
        resolve_period_range("otra", cacao_period, None)


def test_period_objects_belong_to_the_company(periods_app) -> None:
    """Los extremos del rango conservan el período de la compañía solicitada."""
    from cacao_accounting.reportes.periods import resolve_period_range

    ids = _period_ids()
    period_range = resolve_period_range("cacao", ids["01-2026"], ids["AJUSTE-Q1"])
    assert period_range is not None
    assert period_range.from_period.entity == "cacao"
    assert period_range.to_period.entity == "cacao"


def test_adjustment_period_uses_its_own_dates(periods_app) -> None:
    """Un período de ajuste no equivalente a un mes calendario conserva sus fechas."""
    from cacao_accounting.reportes.periods import resolve_period_range

    period_range = resolve_period_range("cacao", _period_ids()["AJUSTE-Q1"], None)
    assert period_range is not None
    assert period_range.period_start == date(2026, 3, 15)
    assert period_range.period_end == date(2026, 3, 31)


def test_closed_period_is_queryable(periods_app) -> None:
    """Los períodos cerrados siguen siendo consultables para reportes."""
    from cacao_accounting.reportes.periods import resolve_period_range

    period_range = resolve_period_range("cacao", _period_ids()["02-2026"], None)
    assert period_range is not None
    assert period_range.to_period.is_closed is True
    assert period_range.period_end == date(2026, 2, 28)


def test_inverted_range_is_rejected(periods_app) -> None:
    """Un rango donde el extremo inicial es posterior al final se rechaza."""
    from cacao_accounting.reportes.periods import resolve_period_range

    ids = _period_ids()
    with pytest.raises(BadRequest):
        resolve_period_range("cacao", ids["02-2026"], ids["01-2026"])


def test_defaults_to_current_period_when_no_ids(periods_app) -> None:
    """Sin identificadores el rango por defecto es el período actual de la compañía."""
    from cacao_accounting.reportes.periods import resolve_period_range

    period_range = resolve_period_range("cacao", None, None, target_date=date(2026, 2, 15))
    assert period_range is not None
    assert period_range.single_period
    assert period_range.from_name == "02-2026"
    assert period_range.period_start == date(2026, 2, 1)


def test_manual_partial_range_is_rejected(periods_app) -> None:
    """Un rango manual que no coincide con el período seleccionado se rechaza."""
    from cacao_accounting.reportes.periods import reject_manual_date_overrides, resolve_period_range

    period_range = resolve_period_range("cacao", _period_ids()["01-2026"], None)
    assert period_range is not None
    with pytest.raises(BadRequest):
        reject_manual_date_overrides({"date_from": "2026-01-05", "date_to": "2026-01-31"}, period_range)
    with pytest.raises(BadRequest):
        reject_manual_date_overrides({"date_to": "2026-01-30"}, period_range)
    with pytest.raises(BadRequest):
        reject_manual_date_overrides({"as_of_date": "2026-01-15"}, period_range)


def test_manual_dates_matching_the_period_are_allowed(periods_app) -> None:
    """Las fechas manuales que coinciden exactamente con el período no se rechazan."""
    from cacao_accounting.reportes.periods import reject_manual_date_overrides, resolve_period_range

    period_range = resolve_period_range("cacao", _period_ids()["01-2026"], None)
    assert period_range is not None
    reject_manual_date_overrides(
        {"date_from": "2026-01-01", "date_to": "2026-01-31", "as_of_date": "2026-01-31"}, period_range
    )


def test_list_periods_is_chronological(periods_app) -> None:
    """La lista de períodos de la compañía se ordena por fecha de inicio."""
    from cacao_accounting.reportes.periods import list_periods_for_company

    names = [period.name for period in list_periods_for_company("cacao")]
    assert names == ["01-2026", "02-2026", "AJUSTE-Q1"]
