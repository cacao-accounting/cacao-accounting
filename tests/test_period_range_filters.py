# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de paridad y compatibilidad de los filtros de período en reportes.

Verifica que los helpers de ruta resuelvan el corte "as of" y los límites
temporales desde el rango de períodos contables completos (Fase 1 de #762) y
que conserven el comportamiento histórico cuando la URL usa ``date_from``,
``date_to`` o ``as_of_date`` directamente.
"""

from __future__ import annotations

from datetime import date

import pytest

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
                    entity="cacao",
                    name="02-2026",
                    enabled=True,
                    is_closed=True,
                    start=date(2026, 2, 1),
                    end=date(2026, 2, 28),
                ),
            ]
        )
        database.session.commit()
        yield app


def _period_id(company: str, name: str) -> str:
    from cacao_accounting.database import AccountingPeriod, database

    period = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.entity == company, AccountingPeriod.name == name)
    ).scalar_one()
    return str(period.id)


def _make_filters(company: str, period_name: str | None, period_from: str | None, period_to: str | None) -> object:
    """Proxies mínimos con el contrato que ``_report_period_bounds`` espera."""

    class _Filters:
        def __init__(self) -> None:
            self.company = company
            self.accounting_period = period_name
            self.period_from = period_from
            self.period_to = period_to

    return _Filters()


@pytest.mark.parametrize(
    ("period_from_name", "period_to_name", "expected_start", "expected_end"),
    [
        ("01-2026", None, date(2026, 1, 1), date(2026, 1, 31)),
        ("01-2026", "02-2026", date(2026, 1, 1), date(2026, 2, 28)),
        ("02-2026", "02-2026", date(2026, 2, 1), date(2026, 2, 28)),
    ],
)
def test_report_period_bounds_uses_range(periods_app, period_from_name, period_to_name, expected_start, expected_end) -> None:
    """``_report_period_bounds`` prioriza el rango por ids sobre el nombre."""
    from cacao_accounting.reportes.services import _report_period_bounds

    filters = _make_filters(
        "cacao",
        "01-2026",
        _period_id("cacao", period_from_name),
        _period_id("cacao", period_to_name) if period_to_name else None,
    )
    start, end, to_period = _report_period_bounds(filters)
    assert start == expected_start
    assert end == expected_end
    assert to_period is not None
    assert to_period.name == (period_to_name or period_from_name)


def test_report_period_bounds_falls_back_to_name(periods_app) -> None:
    """Sin ids el resolver conserva la resolución clásica por nombre de período."""
    from cacao_accounting.reportes.services import _report_period_bounds

    filters = _make_filters("cacao", "02-2026", None, None)
    start, end, to_period = _report_period_bounds(filters)
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)
    assert to_period is not None
    assert to_period.name == "02-2026"


def test_report_period_bounds_empty_without_criterion(periods_app) -> None:
    """Sin período ni nombre no hay límites (resolución clásica devuelve nulos)."""
    from cacao_accounting.reportes.services import _report_period_bounds

    start, end, to_period = _report_period_bounds(_make_filters("cacao", None, None, None))
    assert start is None
    assert end is None
    assert to_period is None


def test_resolve_as_of_date_uses_range_end(periods_app) -> None:
    """El corte "as of" es el último día del período final del rango."""
    from cacao_accounting.reportes.helpers import _resolve_as_of_date

    pid_from = _period_id("cacao", "01-2026")
    pid_to = _period_id("cacao", "02-2026")
    url = f"/reports/aging?company=cacao&accounting_period_from={pid_from}&accounting_period_to={pid_to}"
    with periods_app.test_request_context(url):
        assert _resolve_as_of_date("cacao") == date(2026, 2, 28)


def test_resolve_as_of_date_single_period(periods_app) -> None:
    """Un solo período corta al final de ese período."""
    from cacao_accounting.reportes.helpers import _resolve_as_of_date

    url = f"/reports/aging?company=cacao&accounting_period_from={_period_id('cacao', '01-2026')}"
    with periods_app.test_request_context(url):
        assert _resolve_as_of_date("cacao") == date(2026, 1, 31)


def test_resolve_as_of_date_manual_must_match_period(periods_app) -> None:
    """Un ``as_of_date`` manual solo se acepta si coincide con el período resuelto."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.reportes.helpers import _resolve_as_of_date

    pid = _period_id("cacao", "01-2026")
    with periods_app.test_request_context(f"/reports/aging?company=cacao&accounting_period_from={pid}&as_of_date=2026-01-31"):
        assert _resolve_as_of_date("cacao") == date(2026, 1, 31)
    with periods_app.test_request_context(f"/reports/aging?company=cacao&accounting_period_from={pid}&as_of_date=2026-03-10"):
        with pytest.raises(BadRequest):
            _resolve_as_of_date("cacao")


def test_resolve_date_bounds_from_range(periods_app) -> None:
    """El rango de períodos resuelve desde el inicio del primero al final del último."""
    from cacao_accounting.reportes.helpers import _resolve_date_bounds

    pid_from = _period_id("cacao", "01-2026")
    pid_to = _period_id("cacao", "02-2026")
    url = f"/reports/kardex?company=cacao&accounting_period_from={pid_from}&accounting_period_to={pid_to}"
    with periods_app.test_request_context(url):
        date_from, date_to = _resolve_date_bounds("cacao")
        assert date_from == date(2026, 1, 1)
        assert date_to == date(2026, 2, 28)


def test_resolve_date_bounds_manual_override_rejected(periods_app) -> None:
    """Un ``as_of_date`` que no coincide con el período seleccionado se rechaza."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.reportes.helpers import _resolve_date_bounds

    url = f"/reports/kardex?company=cacao&accounting_period_from={_period_id('cacao', '01-2026')}&as_of_date=2026-02-10"
    with periods_app.test_request_context(url):
        with pytest.raises(BadRequest):
            _resolve_date_bounds("cacao")


def test_resolve_date_bounds_rejects_manual_window(periods_app) -> None:
    """``date_from``/``date_to`` manuales ya no abren un flujo alternativo."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.reportes.helpers import _resolve_date_bounds

    pid = _period_id("cacao", "01-2026")
    with periods_app.test_request_context(
        f"/reports/kardex?company=cacao&accounting_period_from={pid}&date_from=2026-01-01&date_to=2026-01-31"
    ):
        assert _resolve_date_bounds("cacao") == (date(2026, 1, 1), date(2026, 1, 31))
    with periods_app.test_request_context(
        f"/reports/kardex?company=cacao&accounting_period_from={pid}&date_from=2026-01-05&date_to=2026-02-15"
    ):
        with pytest.raises(BadRequest):
            _resolve_date_bounds("cacao")
