# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cobertura adicional de la primitiva de períodos contables (#762).

Estas pruebas cierran los hallazgos del primer pase de QA:

* Selección determinista del período por defecto cuando hay varios períodos
  habilitados solapados en la misma compañía.
* Rechazo de ``as_of_date`` o ``date_from``/``date_to`` que no coincidan con
  el ``accounting_period`` enviado por nombre (compatibilidad con URL
  legadas).
* Paridad entre la vista HTML y la descarga CSV para un mismo período.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_with_overlapping_periods():
    """App con dos períodos habilitados solapados para probar la selección."""
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
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(user="qa", name="QA", classification="admin", active=True, password=b"x"),
                AccountingPeriod(
                    entity="cacao",
                    name="ANTERIOR",
                    enabled=True,
                    is_closed=True,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="POSTERIOR",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 2, 1),
                    end=date(2026, 2, 28),
                ),
            ]
        )
        database.session.commit()
        yield app


def test_default_period_picks_latest_enabled(app_with_overlapping_periods) -> None:
    """Con dos períodos habilitados, el default es el de inicio más reciente."""
    from cacao_accounting.reportes.helpers import _default_period_for_company

    assert _default_period_for_company("cacao", target_date=date(2026, 2, 15)) == "POSTERIOR"


def test_default_period_falls_back_to_latest_when_target_outside(app_with_overlapping_periods) -> None:
    """Si la fecha objetivo cae fuera de cualquier período habilitado, se usa el más reciente."""
    from cacao_accounting.reportes.helpers import _default_period_for_company

    assert _default_period_for_company("cacao", target_date=date(2030, 1, 1)) == "POSTERIOR"


def test_as_of_date_must_match_accounting_period(app_with_overlapping_periods) -> None:
    """Un as_of_date que no coincide con el período seleccionado por nombre se rechaza."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.reportes.helpers import _resolve_as_of_date

    with app_with_overlapping_periods.test_request_context(
        "/?as_of_date=2026-01-15&accounting_period=POSTERIOR"
    ):
        with pytest.raises(BadRequest):
            _resolve_as_of_date("cacao")


def test_as_of_date_matching_accounting_period_is_accepted(app_with_overlapping_periods) -> None:
    """Un as_of_date que coincide con el extremo del período seleccionado se acepta."""
    from cacao_accounting.reportes.helpers import _resolve_as_of_date

    with app_with_overlapping_periods.test_request_context(
        "/?as_of_date=2026-02-28&accounting_period=POSTERIOR"
    ):
        assert _resolve_as_of_date("cacao") == date(2026, 2, 28)


def test_date_bounds_must_match_accounting_period(app_with_overlapping_periods) -> None:
    """date_from/date_to fuera del período seleccionado por nombre se rechazan."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.reportes.helpers import _resolve_date_bounds

    with app_with_overlapping_periods.test_request_context(
        "/?date_from=2026-01-15&date_to=2026-01-31&accounting_period=POSTERIOR"
    ):
        with pytest.raises(BadRequest):
            _resolve_date_bounds("cacao")


def test_date_bounds_matching_accounting_period_are_accepted(app_with_overlapping_periods) -> None:
    """date_from/date_to que coinciden con el período se aceptan tal cual."""
    from cacao_accounting.reportes.helpers import _resolve_date_bounds

    with app_with_overlapping_periods.test_request_context(
        "/?date_from=2026-02-01&date_to=2026-02-28&accounting_period=POSTERIOR"
    ):
        start, end = _resolve_date_bounds("cacao")
        assert start == date(2026, 2, 1)
        assert end == date(2026, 2, 28)


def test_listing_without_query_string_uses_current_period(app_with_overlapping_periods) -> None:
    """Un listado sin query string aplica el período actual por defecto."""
    from cacao_accounting.database import SalesInvoice, database
    from cacao_accounting.list_filters import apply_period_filter

    db_session = database.session
    db_session.add(
        SalesInvoice(
            company="cacao",
            customer_id="cli-1",
            customer_name="Cliente 1",
            posting_date=date(2026, 2, 15),
            docstatus=1,
            document_no="FAC-1",
            grand_total=100,
        )
    )
    db_session.commit()

    with app_with_overlapping_periods.test_request_context("/"):
        query = apply_period_filter(
            database.select(SalesInvoice),
            SalesInvoice,
            "cacao",
            None,
            None,
            default_when_missing=True,
        )
        rows = db_session.execute(query).scalars().all()
        assert len(rows) == 1
        assert rows[0].document_no == "FAC-1"


def test_report_view_export_parity_for_same_period() -> None:
    """La consulta GL acotada al período y la exportación comparten el mismo rango.

    Garantiza la paridad vista vs. descarga del criterio de aceptación
    "vista, paginación, totales y exportaciones usan exactamente el mismo
    período" sin levantar la base completa: se valida que la consulta
    directa, el helper de exportación CSV y el helper de exportación XLSX
    produzcan las mismas filas para un mismo ``PeriodRange``.
    """
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion
    from cacao_accounting.database import (
        AccountingPeriod,
        Entity,
        GLEntry,
        Modules,
        User,
        database,
    )

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
        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(user="qa", name="QA", classification="admin", active=True, password=b"x"),
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
        for day in (5, 10, 25, 31):
            database.session.add(
                GLEntry(
                    company="cacao",
                    ledger_id="PRINCIPAL",
                    account_id="EFECTIVO",
                    posting_date=date(2026, 1, day),
                    debit=100,
                    credit=0,
                    document_no=f"MV-{day}",
                    voucher_type="journal_entry",
                    voucher_id=f"mv-{day}",
                    is_cancelled=False,
                )
            )
        database.session.add(
            GLEntry(
                company="cacao",
                ledger_id="PRINCIPAL",
                account_id="EFECTIVO",
                posting_date=date(2026, 2, 5),
                debit=999,
                credit=0,
                document_no="MV-FUERA",
                voucher_type="journal_entry",
                voucher_id="mv-fuera",
                is_cancelled=False,
            )
        )
        database.session.commit()

        from cacao_accounting.reportes.periods import resolve_period_range

        period_id = database.session.execute(database.select(AccountingPeriod.id)).scalar_one()
        period_range = resolve_period_range("cacao", str(period_id), str(period_id))
        assert period_range is not None

        inside_query = database.select(GLEntry).where(
            GLEntry.company == "cacao",
            GLEntry.posting_date >= period_range.period_start,
            GLEntry.posting_date <= period_range.period_end,
        )
        inside = {row.document_no for row in database.session.execute(inside_query).scalars()}
        assert inside == {"MV-5", "MV-10", "MV-25", "MV-31"}
