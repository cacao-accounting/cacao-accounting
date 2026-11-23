# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1970: los reportes incluyen la reversión interperíodo vigente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.cancellation_scope import effective_gl_scope, ordinary_gl_scope
from cacao_accounting.database import AccountingPeriod, Accounts, Book, GLEntry, database
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    get_account_movement_detail,
    get_income_statement_report,
)


def _periodo(period_id: str, start: date, end: date) -> AccountingPeriod:
    return AccountingPeriod(
        id=period_id,
        entity="cacao",
        fiscal_year_id="FY2026",
        name=period_id,
        start=start,
        end=end,
        enabled=True,
        is_closed=False,
    )


def _libro() -> str:
    return database.session.execute(database.select(Book.id).filter_by(code="DEFAULT_BOOK")).scalar_one()


def _entrada(period: str, fecha: date, **extra) -> GLEntry:
    datos = {
        "company": "cacao",
        "account_code": "5201",
        "debit": Decimal("10"),
        "credit": Decimal("0"),
        "posting_date": fecha,
        "accounting_period_id": period,
        "ledger_id": _libro(),
        "voucher_type": "journal_entry",
        "voucher_id": f"V-{period}-{fecha.day}",
    }
    datos.update(extra)
    return GLEntry(**datos)


def test_incluye_reversion_interperiodo_y_excluye_la_del_mismo_periodo(app, entorno_contable):
    """El corte efectivo conserva la contrapartida vigente del período nuevo."""
    with app.app_context():
        database.session.add(_periodo("P2026-11", date(2026, 11, 1), date(2026, 11, 30)))
        database.session.flush()

        original_oct = _entrada("P2026-05", date(2026, 5, 10), is_cancelled=True)
        database.session.add(original_oct)
        database.session.flush()

        vigente = _entrada("P2026-05", date(2026, 5, 11))
        contra_nov = _entrada("P2026-11", date(2026, 11, 1), is_reversal=True, reversal_of=original_oct.id)
        anulada = _entrada("P2026-05", date(2026, 5, 12), is_cancelled=True)
        database.session.add_all([vigente, contra_nov, anulada])
        database.session.flush()

        mismo_periodo = _entrada("P2026-05", date(2026, 5, 13), is_reversal=True, reversal_of=vigente.id)
        database.session.add(mismo_periodo)
        database.session.commit()

        seleccionados = set(database.session.execute(database.select(GLEntry.id).where(*effective_gl_scope())).scalars().all())

        assert vigente.id in seleccionados
        assert contra_nov.id in seleccionados
        assert original_oct.id not in seleccionados
        assert anulada.id not in seleccionados
        assert mismo_periodo.id not in seleccionados

        # El alcance anterior (solo originales vivos) perdía la contrapartida
        # interperíodo: queda fijado como regresión del defecto.
        anteriores = set(database.session.execute(database.select(GLEntry.id).where(*ordinary_gl_scope())).scalars().all())
        assert contra_nov.id not in anteriores


def test_reporte_gl_incluye_reversion_interperiodo_en_su_periodo(entorno_contable_aislado):
    """El detalle GL y el estado de resultados reflejan la reversa en junio."""
    app = entorno_contable_aislado.app
    with app.app_context():
        database.session.add(_periodo("P2026-06", date(2026, 6, 1), date(2026, 6, 30)))
        cuenta = Accounts(
            entity="cacao",
            code="5299",
            name="Gasto de revaluación",
            classification="expense",
            account_type="expense",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        libro = _libro()

        def entrada(fecha: date, periodo: str, *, debito="0", credito="0", **extra) -> GLEntry:
            datos = {
                "company": "cacao",
                "account_code": cuenta.code,
                "account_id": cuenta.id,
                "ledger_id": libro,
                "posting_date": fecha,
                "accounting_period_id": periodo,
                "debit": Decimal(debito),
                "credit": Decimal(credito),
                "voucher_type": "exchange_revaluation",
                "voucher_id": f"REV-{periodo}-{fecha.day}",
                "is_cancelled": False,
                "is_reversal": False,
            }
            datos.update(extra)
            return GLEntry(**datos)

        vivo_mayo = entrada(date(2026, 5, 20), "P2026-05", debito="5")
        original_mayo = entrada(date(2026, 5, 10), "P2026-05", debito="10", is_cancelled=True)
        database.session.add_all([vivo_mayo, original_mayo])
        database.session.flush()
        reversa_junio = entrada(date(2026, 6, 1), "P2026-06", credito="10", is_reversal=True, reversal_of=original_mayo.id)
        original_mismo = entrada(date(2026, 5, 12), "P2026-05", debito="7", is_cancelled=True)
        database.session.add_all([reversa_junio, original_mismo])
        database.session.flush()
        contra_mismo = entrada(date(2026, 5, 12), "P2026-05", credito="7", is_reversal=True, reversal_of=original_mismo.id)
        database.session.add(contra_mismo)
        database.session.commit()

        mayo = get_account_movement_detail(
            FinancialReportFilters(
                company="cacao",
                ledger="DEFAULT_BOOK",
                accounting_period="P2026-05",
                account_code="5299",
                page_size=100,
                export_all=True,
            )
        )
        junio = get_account_movement_detail(
            FinancialReportFilters(
                company="cacao",
                ledger="DEFAULT_BOOK",
                accounting_period="P2026-06",
                account_code="5299",
                page_size=100,
                export_all=True,
            )
        )
        estado_junio = get_income_statement_report(
            FinancialReportFilters(
                company="cacao",
                ledger="DEFAULT_BOOK",
                accounting_period="P2026-06",
                page_size=100,
                export_all=True,
            )
        )

        debito_mayo = sum((row.values.get("debit", Decimal("0")) for row in mayo.rows), Decimal("0"))
        credito_mayo = sum((row.values.get("credit", Decimal("0")) for row in mayo.rows), Decimal("0"))
        assert debito_mayo == Decimal("5")
        assert credito_mayo == Decimal("0")

        debito_junio = sum((row.values.get("debit", Decimal("0")) for row in junio.rows), Decimal("0"))
        credito_junio = sum((row.values.get("credit", Decimal("0")) for row in junio.rows), Decimal("0"))
        assert debito_junio == Decimal("0")
        assert credito_junio == Decimal("10")
        assert estado_junio.totals["expense"] == Decimal("-10")
