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
    get_account_movement_detail,
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


@pytest.mark.parametrize("report_factory", [get_trial_balance_report, get_account_summary_report])
@pytest.mark.parametrize("include_closing", [False, True])
def test_apertura_incluye_cierre_anterior_sin_alterar_filtro_del_periodo(
    opening_balance_scenario, app, report_factory, include_closing
):
    """El cierre anterior afecta la apertura, independientemente del filtro de movimiento."""
    with app.app_context():
        book = database.session.execute(select(Book).where(Book.code == "TB2190")).scalar_one()
        accounts = {
            code: database.session.execute(
                select(Accounts).where(Accounts.entity == "cacao", Accounts.code == code)
            ).scalar_one()
            for code in ("4101", "5101")
        }
        savepoint = database.session.begin_nested()
        try:
            for period_id, posting_date, amount in (
                ("P2026-04-TB", date(2026, 4, 30), Decimal("100")),
                ("P2026-05", date(2026, 5, 31), Decimal("20")),
            ):
                for code, debit, credit in (("4101", amount, Decimal("0")), ("5101", Decimal("0"), amount)):
                    database.session.add(
                        GLEntry(
                            company="cacao",
                            ledger_id=book.id,
                            account_id=accounts[code].id,
                            account_code=code,
                            account_currency="NIO",
                            company_currency="NIO",
                            exchange_rate=Decimal("1"),
                            posting_date=posting_date,
                            debit=debit,
                            credit=credit,
                            voucher_type="journal_entry",
                            voucher_id=f"{VOUCHER_PREFIX}-closing-{period_id}-{code}",
                            fiscal_year_id="FY2026",
                            accounting_period_id=period_id,
                            is_fiscal_year_closing=True,
                        )
                    )
            database.session.flush()
            filters = FinancialReportFilters(
                company="cacao", ledger="TB2190", accounting_period="P2026-05", include_closing=include_closing
            )
            report = report_factory(filters)
            rows = {row.values["account_code"]: row.values for row in report.rows}
            assert rows["4101"]["opening_balance"] == Decimal("0")
            assert rows["5101"]["opening_balance"] == Decimal("-100")
            assert rows["4101"]["debit"] == (Decimal("20") if include_closing else Decimal("0"))
            assert rows["5101"]["credit"] == (Decimal("20") if include_closing else Decimal("0"))
        finally:
            savepoint.rollback()


def test_detalle_agrupado_pagina_sin_fraccionar_el_subtotal(opening_balance_scenario, authenticated_client):
    """La continuación muestra el subtotal del grupo completo en su última página."""
    client = authenticated_client("admin")
    params = {
        "apply_filters": "1",
        "company": "cacao",
        "ledger": "TB2190",
        "accounting_period_from": "P2026-04-TB",
        "accounting_period_to": "P2026-05",
        "group_by": "account_code",
        "page_size": "1",
    }
    pages = [client.get("/reports/account-movement", query_string={**params, "page": page}) for page in range(1, 5)]
    assert all(response.status_code == 200 for response in pages)
    html = [response.get_data(as_text=True) for response in pages]
    assert f"{VOUCHER_PREFIX}-abril-caja" in html[0]
    assert f"{VOUCHER_PREFIX}-mayo-caja" in html[1]
    assert f"{VOUCHER_PREFIX}-abril-ventas" in html[2]
    assert f"{VOUCHER_PREFIX}-mayo-ventas" in html[3]
    assert "Continuación" not in html[0] and "Continuación" in html[1]
    assert "150.00" not in html[0] and "150.00" in html[1]
    assert "150.00" not in html[2] and "150.00" in html[3]
    assert "page=2" in html[0] and "page=1" in html[1]
    exported = client.get("/reports/account-movement", query_string={**params, "page": 2, "export": "csv"})
    assert exported.status_code == 200
    assert all(
        f"{VOUCHER_PREFIX}-{suffix}" in exported.get_data(as_text=True)
        for suffix in ("abril-caja", "mayo-caja", "abril-ventas", "mayo-ventas")
    )


def test_rechaza_agrupacion_por_saldo_acumulado(opening_balance_scenario, authenticated_client):
    """Las dimensiones calculadas no deben activar agrupación parcial en memoria."""
    client = authenticated_client("admin")
    response = client.get(
        "/reports/account-movement",
        query_string={
            "apply_filters": "1",
            "company": "cacao",
            "ledger": "TB2190",
            "accounting_period": "P2026-05",
            "group_by": "running_balance",
        },
    )

    assert response.status_code == 400


def test_grupo_grande_limita_las_filas_y_conserva_saldo_acumulado(opening_balance_scenario, app):
    """Cinco mil movimientos se consultan en páginas de cien sin perder el acumulado."""
    with app.app_context():
        book = database.session.execute(select(Book).where(Book.code == "TB2190")).scalar_one()
        account = database.session.execute(
            select(Accounts).where(Accounts.entity == "cacao", Accounts.code == "1101")
        ).scalar_one()
        savepoint = database.session.begin_nested()
        try:
            database.session.add_all(
                [
                    GLEntry(
                        company="cacao",
                        ledger_id=book.id,
                        account_id=account.id,
                        account_code=account.code,
                        account_currency="NIO",
                        company_currency="NIO",
                        exchange_rate=Decimal("1"),
                        posting_date=date(2026, 5, 11),
                        debit=Decimal("1"),
                        credit=Decimal("0"),
                        voucher_type="journal_entry",
                        voucher_id=f"TB-LARGE-{index}",
                        fiscal_year_id="FY2026",
                        accounting_period_id="P2026-05",
                    )
                    for index in range(5000)
                ]
            )
            database.session.flush()
            filters = FinancialReportFilters(
                company="cacao",
                ledger="TB2190",
                accounting_period="P2026-05",
                account_code="1101",
                page=2,
                page_size=100,
                include_running_balance=True,
            )
            report = get_account_movement_detail(filters, group_by="account_code")
            assert report.total_rows == 5001
            assert len(report.rows) == 100
            assert report.rows[0].values["__group_position"] == 101
            assert report.rows[-1].values["__group_position"] == 200
            assert report.rows[0].values["running_balance"] == Decimal("150")
            assert report.rows[0].values["__group_debit"] == Decimal("5050")
        finally:
            savepoint.rollback()
