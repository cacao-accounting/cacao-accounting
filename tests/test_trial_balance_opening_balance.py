# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Balanza y sábana conservan el saldo inicial de períodos anteriores.

Escenario de negocio (issue #2190): el filtro dimensional del período acotaba
toda la consulta a ``accounting_period_id IN (períodos)``, de modo que el
``CASE`` de apertura nunca encontraba filas anteriores y ``opening_balance``
siempre era cero. El saldo inicial debe provenir de los períodos previos del
mismo libro, mientras el movimiento se limita al período seleccionado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.database import GLEntry, AccountingPeriod, Accounts, Book, FiscalYear, database
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    _grouped_movement_condition,
    _grouped_opening_condition,
    get_account_summary_report,
    get_trial_balance_report,
)

VOUCHER_PREFIX = "TB-OPENING-2190"


@pytest.fixture
def opening_balance_scenario(app, entorno_contable):
    """Publica apertura en abril, movimiento en mayo y actividad futura en junio."""
    with app.app_context():
        fiscal_year_id = database.session.execute(select(FiscalYear.id).where(FiscalYear.id == "FY2026")).scalar_one()
        book = database.session.execute(select(Book).where(Book.code == "TB2190")).scalar_one_or_none()
        if book is None:
            book = Book(
                entity="cacao",
                code="TB2190",
                name="Libro de prueba de apertura",
                status="activo",
                is_primary=False,
                currency="NIO",
            )
            database.session.add(book)
            database.session.flush()
        book_id = book.id
        accounts = {
            code: database.session.execute(
                select(Accounts).where(Accounts.entity == "cacao", Accounts.code == code)
            ).scalar_one()
            for code in ("1101", "4101", "5101")
        }
        previous_period = AccountingPeriod(
            id="P2026-04-TB",
            entity="cacao",
            fiscal_year_id=fiscal_year_id,
            name="Abril 2026 TB",
            start=date(2026, 4, 1),
            end=date(2026, 4, 30),
            status="open",
            enabled=True,
            is_closed=False,
        )
        database.session.add(previous_period)
        database.session.flush()

        def add_entry(suffix: str, posting_date: date, account, debit: str, credit: str, period_id: str | None) -> None:
            database.session.add(
                GLEntry(
                    company="cacao",
                    ledger_id=book_id,
                    account_id=account.id,
                    account_code=account.code,
                    account_currency="NIO",
                    company_currency="NIO",
                    exchange_rate=Decimal("1"),
                    posting_date=posting_date,
                    debit=Decimal(debit),
                    credit=Decimal(credit),
                    voucher_type="journal_entry",
                    voucher_id=f"{VOUCHER_PREFIX}-{suffix}",
                    fiscal_year_id=fiscal_year_id,
                    accounting_period_id=period_id,
                )
            )

        # Apertura: caja 100 / ventas 100 en el período anterior.
        add_entry("abril-caja", date(2026, 4, 15), accounts["1101"], "100", "0", previous_period.id)
        add_entry("abril-ventas", date(2026, 4, 15), accounts["4101"], "0", "100", previous_period.id)
        # Movimiento del período consultado: caja 50 / ventas 50.
        add_entry("mayo-caja", date(2026, 5, 10), accounts["1101"], "50", "0", "P2026-05")
        add_entry("mayo-ventas", date(2026, 5, 10), accounts["4101"], "0", "50", "P2026-05")
        # Actividad posterior al período, sin período asignado: no debe aparecer.
        add_entry("junio-costos", date(2026, 6, 10), accounts["5101"], "30", "0", None)
        add_entry("junio-costos-contra", date(2026, 6, 10), accounts["1101"], "0", "30", None)
        database.session.commit()

    yield

    with app.app_context():
        database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id.like(f"{VOUCHER_PREFIX}%")))
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.id == "P2026-04-TB"))
        database.session.execute(database.delete(Book).where(Book.code == "TB2190"))
        database.session.commit()


def _report_filters() -> FinancialReportFilters:
    return FinancialReportFilters(
        company="cacao",
        ledger="TB2190",
        accounting_period="P2026-05",
    )


def test_balanza_conserva_apertura_de_periodos_previos(opening_balance_scenario, app):
    """Caja arrastra 100 de apertura, suma 50 del período y cierra en 150."""
    with app.app_context():
        report = get_trial_balance_report(_report_filters())
    rows = {row.values["account_code"]: row.values for row in report.rows}

    assert rows["1101"]["opening_balance"] == Decimal("100.0000")
    assert rows["1101"]["debit"] == Decimal("50.0000")
    assert rows["1101"]["credit"] == Decimal("0.0000")
    assert rows["1101"]["ending_balance"] == Decimal("150.0000")
    # Ventas es acreedora: apertura -100 y movimiento -50.
    assert rows["4101"]["opening_balance"] == Decimal("-100.0000")
    assert rows["4101"]["credit"] == Decimal("50.0000")
    assert rows["4101"]["ending_balance"] == Decimal("-150.0000")


def test_balanza_no_incluye_cuentas_sin_apertura_ni_movimiento(opening_balance_scenario, app):
    """La actividad posterior al período no crea filas en cero."""
    with app.app_context():
        report = get_trial_balance_report(_report_filters())
    codes = {row.values["account_code"] for row in report.rows}

    assert "5101" not in codes


def test_balanza_mantiene_el_cuadre_de_apertura_y_movimiento(opening_balance_scenario, app):
    """Apertura y movimiento del libro siguen cuadrando por partida doble."""
    with app.app_context():
        report = get_trial_balance_report(_report_filters())

    assert report.totals["opening_balance"] == Decimal("0.0000")
    assert report.totals["debit"] == Decimal("50.0000")
    assert report.totals["credit"] == Decimal("50.0000")
    assert report.totals["ending_balance"] == Decimal("0.0000")


def test_sabana_conserva_apertura_y_limita_el_conteo_de_movimientos(opening_balance_scenario, app):
    """La sábana analítica muestra apertura y solo cuenta movimientos del período."""
    with app.app_context():
        report = get_account_summary_report(_report_filters())
    rows = {row.values["account_code"]: row.values for row in report.rows}

    assert rows["1101"]["opening_balance"] == Decimal("100.0000")
    assert rows["1101"]["movement_count"] == 1
    assert rows["1101"]["ending_balance"] == Decimal("150.0000")
    assert "5101" not in rows


def test_balanza_sin_periodo_suma_toda_la_actividad(opening_balance_scenario, app):
    """Sin período seleccionado todo el historial es movimiento y no hay apertura."""
    filters = FinancialReportFilters(company="cacao", ledger="TB2190")
    with app.app_context():
        report = get_trial_balance_report(filters)
    rows = {row.values["account_code"]: row.values for row in report.rows}

    assert rows["1101"]["opening_balance"] == Decimal("0.0000")
    assert rows["1101"]["debit"] == Decimal("150.0000")
    assert rows["1101"]["credit"] == Decimal("30.0000")
    assert rows["1101"]["ending_balance"] == Decimal("120.0000")
    assert rows["5101"]["debit"] == Decimal("30.0000")


def test_predicados_por_fecha_sin_periodo_resuelto(opening_balance_scenario, app):
    """Sin dimensión de período, las fechas delimitan movimiento y apertura."""
    with app.app_context():
        movement = (
            database.session.execute(
                select(GLEntry.voucher_id)
                .where(GLEntry.voucher_id.like(f"{VOUCHER_PREFIX}%"))
                .where(_grouped_movement_condition(date(2026, 5, 1), date(2026, 5, 31), []))
            )
            .scalars()
            .all()
        )
        opening = (
            database.session.execute(
                select(GLEntry.voucher_id)
                .where(GLEntry.voucher_id.like(f"{VOUCHER_PREFIX}%"))
                .where(_grouped_opening_condition(date(2026, 5, 1), []))
            )
            .scalars()
            .all()
        )

    assert set(movement) == {f"{VOUCHER_PREFIX}-mayo-caja", f"{VOUCHER_PREFIX}-mayo-ventas"}
    assert set(opening) == {f"{VOUCHER_PREFIX}-abril-caja", f"{VOUCHER_PREFIX}-abril-ventas"}
