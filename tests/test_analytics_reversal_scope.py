# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1582: las métricas analíticas incluyen reversas interperíodo activas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import Accounts, AccountingPeriod, Book, GLEntry, database
from cacao_accounting.reportes.analytics import get_kpi_snapshot


def _registrar(entorno, cuenta, fecha, debito, credito, *, reversal=False, reversal_of=None, periodo=None, cancelada=False):
    libro = database.session.execute(database.select(Book).filter_by(entity="cacao", code="DEFAULT_BOOK")).scalars().first()
    entrada = GLEntry(
        company="cacao",
        account_id=cuenta.id,
        ledger_id=libro.id,
        posting_date=fecha,
        debit=Decimal(debito),
        credit=Decimal(credito),
        voucher_type="journal_entry",
        voucher_id=f"KPI-1582-{fecha.isoformat()}-{debito}-{credito}",
        is_reversal=reversal,
        reversal_of=reversal_of,
        accounting_period_id=periodo,
        is_cancelled=cancelada,
    )
    database.session.add(entrada)
    database.session.flush()
    return entrada


def test_kpi_incluye_reversa_interperiodo_en_el_periodo_vigente(entorno_contable_aislado):
    """Una reversa de mayo revierte los ingresos de una venta de abril."""
    entorno = entorno_contable_aislado
    with entorno.app.app_context():
        ingresos = Accounts(
            entity="cacao",
            code="4199-1582",
            name="Ingresos 1582",
            classification="income",
            account_type="income",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add(ingresos)
        database.session.flush()
        periodo = database.session.execute(
            database.select(AccountingPeriod).filter_by(entity="cacao", name="Mayo 2026")
        ).scalar_one()
        abril = AccountingPeriod(
            entity="cacao",
            fiscal_year_id=periodo.fiscal_year_id,
            name="Abril 2026",
            status="open",
            enabled=True,
            is_closed=False,
            start=date(2026, 4, 1),
            end=date(2026, 4, 30),
        )
        database.session.add(abril)
        database.session.flush()
        original = _registrar(entorno, ingresos, date(2026, 4, 15), "0", "100", periodo=abril.id)
        _registrar(
            entorno,
            ingresos,
            date(2026, 5, 10),
            "100",
            "0",
            reversal=True,
            reversal_of=original.id,
            periodo=periodo.id,
        )
        database.session.commit()

        snapshot = get_kpi_snapshot("cacao", date(2026, 5, 1), date(2026, 5, 31))

    assert snapshot["metrics"]["income"] == Decimal("-100")
    assert snapshot["metrics"]["net_income"] == Decimal("-100")


def test_kpi_excluye_anulacion_del_mismo_periodo(entorno_contable_aislado):
    """La contrapartida del mismo periodo no infla ingresos ni gastos."""
    entorno = entorno_contable_aislado
    with entorno.app.app_context():
        ingresos = Accounts(
            entity="cacao",
            code="4198-1582",
            name="Ingresos 1582 B",
            classification="income",
            account_type="income",
            group=False,
            active=True,
            enabled=True,
        )
        gastos = Accounts(
            entity="cacao",
            code="5298-1582",
            name="Gastos 1582 B",
            classification="expense",
            account_type="expense",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add_all([ingresos, gastos])
        database.session.flush()
        periodo = database.session.execute(
            database.select(AccountingPeriod).filter_by(entity="cacao", name="Mayo 2026")
        ).scalar_one()
        original_ingreso = _registrar(entorno, ingresos, date(2026, 5, 5), "0", "50", periodo=periodo.id, cancelada=True)
        _registrar(
            entorno,
            ingresos,
            date(2026, 5, 5),
            "50",
            "0",
            reversal=True,
            reversal_of=original_ingreso.id,
            periodo=periodo.id,
        )
        original_gasto = _registrar(entorno, gastos, date(2026, 5, 6), "30", "0", periodo=periodo.id, cancelada=True)
        _registrar(
            entorno,
            gastos,
            date(2026, 5, 6),
            "0",
            "30",
            reversal=True,
            reversal_of=original_gasto.id,
            periodo=periodo.id,
        )
        database.session.commit()

        snapshot = get_kpi_snapshot("cacao", date(2026, 5, 1), date(2026, 5, 31))

    assert snapshot["metrics"]["income"] == Decimal("0")
    assert snapshot["metrics"]["expenses"] == Decimal("0")
    assert snapshot["metrics"]["net_income"] == Decimal("0")
