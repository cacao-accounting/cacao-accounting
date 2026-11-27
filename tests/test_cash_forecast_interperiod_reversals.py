# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones del pronóstico de caja ante anulaciones y reversiones GL."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from cacao_accounting.bancos.cash_forecast_service import _compute_initial_balance, _compute_real_movements
from cacao_accounting.database import Accounts, AccountingPeriod, Book, Entity, FiscalYear, GLEntry, database


def _entrada_caja(**campos: Any) -> GLEntry:
    """Crea una línea GL para probar los cortes temporales del pronóstico."""
    cuenta = campos.pop("account")
    campos["accounting_period_id"] = campos.pop("period_id")
    campos.update(
        account_id=cuenta.id,
        account_code=cuenta.code,
        account_currency="NIO",
        company_currency="NIO",
        exchange_rate=Decimal("1"),
        voucher_type="journal_entry",
    )
    return GLEntry(**campos)


def test_pronostico_conserva_original_y_reversa_en_sus_periodos(entorno_contable_aislado):
    """La caja original queda en mayo y la reversión afecta junio."""
    app = entorno_contable_aislado.app
    with app.app_context():
        company = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        book = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        fiscal_year = database.session.get(FiscalYear, "FY2026")
        cash_account = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        expense_account = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code="5201")
        ).scalar_one()
        assert company is not None and book is not None and fiscal_year is not None
        assert cash_account is not None and expense_account is not None
        company_code = company.code
        may_period_id = "P2026-05"
        database.session.add(
            AccountingPeriod(
                id="P2026-06",
                entity=company_code,
                fiscal_year_id=fiscal_year.id,
                name="Junio 2026",
                start=date(2026, 6, 1),
                end=date(2026, 6, 30),
                enabled=True,
                is_closed=False,
            )
        )
        database.session.flush()

        original = _entrada_caja(
            company=company_code,
            ledger_id=book.id,
            fiscal_year_id=fiscal_year.id,
            account=cash_account,
            posting_date=date(2026, 5, 29),
            period_id=may_period_id,
            debit=Decimal("100"),
            credit=Decimal("0"),
            voucher_id="CASH-REVERSAL-1086",
            is_cancelled=True,
        )
        database.session.add(original)
        database.session.flush()
        # Contrapartida necesaria para que ambos vouchers representen asientos balanceados.
        database.session.add(
            _entrada_caja(
                company=company_code,
                ledger_id=book.id,
                fiscal_year_id=fiscal_year.id,
                account=expense_account,
                posting_date=date(2026, 5, 29),
                period_id=may_period_id,
                debit=Decimal("0"),
                credit=Decimal("100"),
                voucher_id="CASH-REVERSAL-1086",
            )
        )
        database.session.add_all(
            [
                _entrada_caja(
                    company=company_code,
                    ledger_id=book.id,
                    fiscal_year_id=fiscal_year.id,
                    account=cash_account,
                    posting_date=date(2026, 6, 1),
                    period_id="P2026-06",
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    voucher_id="CASH-REVERSAL-1086",
                    is_reversal=True,
                    reversal_of=original.id,
                ),
                _entrada_caja(
                    company=company_code,
                    ledger_id=book.id,
                    fiscal_year_id=fiscal_year.id,
                    account=expense_account,
                    posting_date=date(2026, 6, 1),
                    period_id="P2026-06",
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    voucher_id="CASH-REVERSAL-1086",
                    is_reversal=True,
                    reversal_of=original.id,
                ),
            ]
        )
        anulacion_mismo_periodo = _entrada_caja(
            company=company_code,
            ledger_id=book.id,
            fiscal_year_id=fiscal_year.id,
            account=cash_account,
            posting_date=date(2026, 5, 12),
            period_id=may_period_id,
            debit=Decimal("40"),
            credit=Decimal("0"),
            voucher_id="CASH-SAME-DATE-CANCEL-1086",
            is_cancelled=True,
        )
        database.session.add(anulacion_mismo_periodo)
        database.session.flush()
        database.session.add_all(
            [
                _entrada_caja(
                    company=company_code,
                    ledger_id=book.id,
                    fiscal_year_id=fiscal_year.id,
                    account=expense_account,
                    posting_date=date(2026, 5, 12),
                    period_id=may_period_id,
                    debit=Decimal("0"),
                    credit=Decimal("40"),
                    voucher_id="CASH-SAME-DATE-CANCEL-1086",
                ),
                _entrada_caja(
                    company=company_code,
                    ledger_id=book.id,
                    fiscal_year_id=fiscal_year.id,
                    account=cash_account,
                    posting_date=date(2026, 5, 12),
                    period_id=may_period_id,
                    debit=Decimal("0"),
                    credit=Decimal("40"),
                    voucher_id="CASH-SAME-DATE-CANCEL-1086",
                    is_reversal=True,
                    reversal_of=anulacion_mismo_periodo.id,
                ),
                _entrada_caja(
                    company=company_code,
                    ledger_id=book.id,
                    fiscal_year_id=fiscal_year.id,
                    account=expense_account,
                    posting_date=date(2026, 5, 12),
                    period_id=may_period_id,
                    debit=Decimal("40"),
                    credit=Decimal("0"),
                    voucher_id="CASH-SAME-DATE-CANCEL-1086",
                    is_reversal=True,
                    reversal_of=anulacion_mismo_periodo.id,
                ),
            ]
        )
        database.session.commit()

        caja_ids = [cash_account.id]
        saldo_inicial_junio = _compute_initial_balance(company_code, caja_ids, date(2026, 6, 1))
        movimiento_mayo = _compute_real_movements(company_code, caja_ids, date(2026, 5, 1), date(2026, 5, 31))
        movimiento_junio = _compute_real_movements(company_code, caja_ids, date(2026, 6, 1), date(2026, 6, 30))

    assert saldo_inicial_junio == Decimal("100.00000000")
    assert movimiento_mayo == (Decimal("0"), Decimal("0"), Decimal("100.00000000"))
    assert movimiento_junio == (Decimal("0"), Decimal("0"), Decimal("-100.00000000"))
