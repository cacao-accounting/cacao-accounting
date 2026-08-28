# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de los helpers compartidos de filtro por período en listados."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def filters_app():
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
        user = User(user="filters-user", name="Filters User", classification="admin", active=True)
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
                Modules(module="sales", default=True, enabled=True),
                user,
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
            ]
        )
        database.session.commit()
        yield app


def _admin_user():
    from cacao_accounting.database import User

    return User.query.filter_by(user="filters-user").first()


def test_period_picker_context_defaults_to_current(filters_app) -> None:
    """Sin extremos el contexto del selector cae al período actual."""
    from cacao_accounting.list_filters import period_picker_context

    context = period_picker_context("cacao", None, None)
    assert context["periods"]
    assert context["period_from"] == context["period_to"]
    assert context["period_from"] != ""


def test_period_picker_context_keeps_selection(filters_app) -> None:
    """Un rango explícito se refleja en el contexto del selector."""
    from cacao_accounting.database import AccountingPeriod, database
    from cacao_accounting.list_filters import period_picker_context

    period = database.session.execute(database.select(AccountingPeriod)).scalar_one()
    context = period_picker_context("cacao", str(period.id), None)
    assert context["period_from"] == str(period.id)
    assert context["period_to"] == str(period.id)


def test_pick_company_period_prefers_selection(filters_app) -> None:
    """La compañía seleccionada se prefiere sobre la única disponible."""
    from cacao_accounting.list_filters import pick_company_period

    assert pick_company_period("otra", ["cacao"]) == "otra"
    assert pick_company_period(None, ["cacao"]) == "cacao"
    assert pick_company_period(None, ["a", "b"]) is None


def test_require_period_company_uses_param(filters_app) -> None:
    """Con el parámetro compaños, la compañía se resuelve desde la petición."""
    from cacao_accounting.list_filters import period_company_from_request

    class _User:
        classification = "admin"

    with filters_app.test_request_context("/list?company=cacao&accounting_period_from=1"):
        assert period_company_from_request(("sales",), current_user=_User()) == "cacao"


def test_apply_period_filter_skips_company_clause_without_column(filters_app) -> None:
    """``apply_period_filter`` no aplica la cláusula de compañía a modelos sin esa columna.

    BankTransaction (importación bancaria) expone ``posting_date`` pero no tiene
    columna ``company``; el filtro por período debe acotar por fecha sin fallar.
    """
    from cacao_accounting.database import AccountingPeriod, BankTransaction, database
    from cacao_accounting.list_filters import apply_period_filter

    period = database.session.execute(database.select(AccountingPeriod)).scalar_one()
    with filters_app.test_request_context("/"):
        query = apply_period_filter(database.select(BankTransaction), BankTransaction, "cacao", str(period.id), None)
        compiled = str(query.compile(database.engine))
        assert "posting_date" in compiled
        # La ejecución no debe fallar por intentar filtrar una columna inexistente.
        rows = database.session.execute(query).scalars().all()
        assert rows == []


def test_require_period_company_aborts_when_ambiguous(filters_app) -> None:
    """Sin compañía explícita y varias opciones se rechaza la petición."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.list_filters import require_period_company

    class _User:
        classification = "admin"

    with filters_app.test_request_context("/list?accounting_period_from=1"):
        with pytest.raises(BadRequest):
            require_period_company(("sales",), current_user=_User())
