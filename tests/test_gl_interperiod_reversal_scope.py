# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1970 y #2265: los reportes conservan el corte original y su reversa vigente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.cancellation_scope import cancelled_originals_scope, effective_gl_scope, ordinary_gl_scope
from cacao_accounting.database import AccountingPeriod, Accounts, Book, DocumentTransition, GLEntry, User, database
from cacao_accounting.reportes.analytics import _gl_totals
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    OperationalReportFilters,
    _build_actual_query,
    _reconciliation_gl_amount,
    get_account_movement_detail,
    get_gross_margin,
    get_income_statement_report,
    get_trial_balance_report,
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
    """El corte efectivo conserva el original y la contrapartida del período nuevo."""
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
        # #2265: la reversa de noviembre no reescribe el corte de mayo.
        assert original_oct.id in seleccionados
        assert anulada.id not in seleccionados
        assert mismo_periodo.id not in seleccionados

        # El alcance anterior (solo originales vivos) perdía la contrapartida
        # interperíodo: queda fijado como regresión del defecto.
        anteriores = set(database.session.execute(database.select(GLEntry.id).where(*ordinary_gl_scope())).scalars().all())
        assert contra_nov.id not in anteriores


def test_excluye_reversa_adelantada_en_ambos_lados(entorno_contable_aislado):
    """#2265: una contrapartida anterior al origen no revive el corte ni adelanta el gasto."""
    app = entorno_contable_aislado.app
    with app.app_context():
        database.session.add(_periodo("P2026-04", date(2026, 4, 1), date(2026, 4, 30)))
        database.session.flush()
        original = _entrada("P2026-05", date(2026, 5, 10), is_cancelled=True)
        database.session.add(original)
        database.session.flush()
        adelantada = _entrada(
            "P2026-04",
            date(2026, 4, 1),
            debit=Decimal("0"),
            credit=Decimal("10"),
            is_reversal=True,
            reversal_of=original.id,
        )
        database.session.add(adelantada)
        database.session.commit()

        seleccionados = set(database.session.execute(database.select(GLEntry.id).where(*effective_gl_scope())).scalars().all())
        assert original.id not in seleccionados
        assert adelantada.id not in seleccionados

        abril = get_account_movement_detail(
            FinancialReportFilters(
                company="cacao",
                ledger="DEFAULT_BOOK",
                accounting_period="P2026-04",
                account_code="5201",
                page_size=100,
                export_all=True,
            )
        )
        assert sum((row.values.get("credit", Decimal("0")) for row in abril.rows), Decimal("0")) == Decimal("0")


def test_corte_historico_aplica_fecha_efectiva_de_anulacion(entorno_contable_aislado):
    """Los reportes conservan los datos heredados hasta la transición efectiva."""
    app = entorno_contable_aislado.app
    with app.app_context():
        account = Accounts(
            entity="cacao",
            code="5398",
            name="Costo de prueba de anulacion historica",
            classification="cost",
            account_type="expense",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(account)
        database.session.flush()
        ledger_id = _libro()
        original = _entrada(
            "P2026-05",
            date(2026, 5, 10),
            account_id=account.id,
            account_code=account.code,
            voucher_id="COSTO-ANULADO-TARDIO",
            is_cancelled=True,
        )
        database.session.add(original)
        database.session.flush()
        reversal = _entrada(
            "P2026-05",
            date(2026, 5, 20),
            account_id=account.id,
            account_code=account.code,
            voucher_id="COSTO-ANULADO-TARDIO",
            debit=Decimal("0"),
            credit=Decimal("10"),
            is_reversal=True,
            reversal_of=original.id,
        )
        database.session.add(reversal)
        actor_id = database.session.execute(
            database.select(User.id).where(User.classification == "admin").limit(1)
        ).scalar_one()
        database.session.add(
            DocumentTransition(
                source_type=original.voucher_type,
                source_id=original.voucher_id,
                transition_type="cancellation",
                company="cacao",
                posting_date=date(2026, 5, 20),
                accounting_period_id="P2026-05",
                actor_user_id=actor_id,
                reason="Registro heredado para corte histórico",
            )
        )
        database.session.flush()

        before_cancel = set(
            database.session.execute(
                database.select(GLEntry.id).where(
                    GLEntry.posting_date <= date(2026, 5, 15),
                    *effective_gl_scope(date(2026, 5, 15)),
                )
            )
            .scalars()
            .all()
        )
        after_cancel = set(
            database.session.execute(
                database.select(GLEntry.id).where(
                    GLEntry.posting_date <= date(2026, 5, 20),
                    *effective_gl_scope(date(2026, 5, 20)),
                )
            )
            .scalars()
            .all()
        )

        assert original.id in before_cancel
        assert reversal.id not in before_cancel
        assert original.id not in after_cancel
        assert reversal.id not in after_cancel
        assert original.id not in set(
            database.session.execute(database.select(GLEntry.id).where(*cancelled_originals_scope(date(2026, 5, 15))))
            .scalars()
            .all()
        )
        assert original.id in set(
            database.session.execute(database.select(GLEntry.id).where(*cancelled_originals_scope(date(2026, 5, 20))))
            .scalars()
            .all()
        )

        before_gross_margin = get_gross_margin(
            OperationalReportFilters(
                company="cacao",
                date_from=date(2026, 5, 1),
                date_to=date(2026, 5, 15),
            )
        )
        after_gross_margin = get_gross_margin(
            OperationalReportFilters(
                company="cacao",
                date_from=date(2026, 5, 1),
                date_to=date(2026, 5, 20),
            )
        )
        assert before_gross_margin.totals["cogs"] == Decimal("10")
        assert after_gross_margin.totals["cogs"] == Decimal("0")

        assert _gl_totals("cacao", date(2026, 5, 1), date(2026, 5, 15), ledger_id)["cost"] == Decimal("10")
        assert _gl_totals("cacao", date(2026, 5, 1), date(2026, 5, 20), ledger_id)["cost"] == Decimal("0")

        filters = FinancialReportFilters(company="cacao")
        before_budget = _build_actual_query(
            filters,
            database.session.get(Book, ledger_id),
            SimpleNamespace(account_id=account.id),
            None,
            date(2026, 5, 1),
            date(2026, 5, 15),
        )
        after_budget = _build_actual_query(
            filters,
            database.session.get(Book, ledger_id),
            SimpleNamespace(account_id=account.id),
            None,
            date(2026, 5, 1),
            date(2026, 5, 20),
        )
        assert database.session.execute(before_budget).scalar_one() == Decimal("10")
        assert database.session.execute(after_budget).scalar_one() == Decimal("0")

        assert _reconciliation_gl_amount(
            "cacao", ledger_id, [account.id], date_from=date(2026, 5, 1), date_to=date(2026, 5, 15)
        ) == Decimal("10")
        assert _reconciliation_gl_amount(
            "cacao", ledger_id, [account.id], date_from=date(2026, 5, 1), date_to=date(2026, 5, 20)
        ) == Decimal("0")


def test_reporte_gl_incluye_reversion_interperiodo_en_su_periodo(entorno_contable_aislado):
    """El detalle GL, la balanza y el resultado conservan ambos cortes (#2265)."""
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
        estado_mayo = get_income_statement_report(
            FinancialReportFilters(
                company="cacao",
                ledger="DEFAULT_BOOK",
                accounting_period="P2026-05",
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
        balanza_mayo = get_trial_balance_report(
            FinancialReportFilters(
                company="cacao",
                ledger="DEFAULT_BOOK",
                accounting_period="P2026-05",
                page_size=100,
                export_all=True,
            )
        )
        balanza_junio = get_trial_balance_report(
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
        assert debito_mayo == Decimal("15")
        assert credito_mayo == Decimal("0")

        debito_junio = sum((row.values.get("debit", Decimal("0")) for row in junio.rows), Decimal("0"))
        credito_junio = sum((row.values.get("credit", Decimal("0")) for row in junio.rows), Decimal("0"))
        assert debito_junio == Decimal("0")
        assert credito_junio == Decimal("10")
        # La reversa posterior no modifica el gasto ya reconocido en mayo.
        assert estado_mayo.totals["expense"] == Decimal("15")
        assert estado_junio.totals["expense"] == Decimal("-10")

        fila_mayo = next(row for row in balanza_mayo.rows if row.values["account_code"] == "5299")
        fila_junio = next(row for row in balanza_junio.rows if row.values["account_code"] == "5299")
        assert fila_mayo.values["debit"] == Decimal("15")
        assert fila_mayo.values["credit"] == Decimal("0")
        assert fila_junio.values["opening_balance"] == Decimal("15")
        assert fila_junio.values["credit"] == Decimal("10")
        assert balanza_mayo.totals["difference"] == Decimal("15")
        assert balanza_junio.totals["difference"] == Decimal("-10")
