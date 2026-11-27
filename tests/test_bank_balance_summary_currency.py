# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El resumen bancario conserva una sola moneda por fila."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.database import Accounts, Bank, BankAccount, Book, GLEntry, database
from cacao_accounting.reportes.services import BankingFilters, get_bank_balance_summary


def test_resumen_muestra_saldo_gl_en_moneda_de_cuenta(entorno_contable_aislado):
    """Los importes GL en moneda funcional no se etiquetan como moneda bancaria."""
    entorno_contable_aislado
    account = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1102")).scalar_one()
    assert account is not None
    primary_book = database.session.execute(select(Book).filter_by(entity="cacao", is_primary=True)).scalar_one()
    account.currency = "USD"
    bank = database.session.execute(select(Bank).where(Bank.is_active.is_(True))).scalars().first()
    if bank is None:
        bank = Bank(name="Banco para resumen", is_active=True)
        database.session.add(bank)
        database.session.flush()

    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta en dólares",
        account_no="USD-001",
        currency="USD",
        gl_account_id=account.id,
    )
    database.session.add(bank_account)
    database.session.flush()
    database.session.add_all(
        [
            GLEntry(
                company="cacao",
                ledger_id=primary_book.id,
                account_id=account.id,
                posting_date=date(2026, 5, 2),
                debit=Decimal("3600"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("100"),
                credit_in_account_currency=Decimal("0"),
                account_currency="USD",
                company_currency="NIO",
                bank_account_id=bank_account.id,
                voucher_type="PaymentEntry",
                voucher_id="deposito-usd",
            ),
            GLEntry(
                company="cacao",
                ledger_id=primary_book.id,
                account_id=account.id,
                posting_date=date(2026, 5, 31),
                debit=Decimal("36"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("0"),
                credit_in_account_currency=Decimal("0"),
                account_currency="USD",
                company_currency="NIO",
                bank_account_id=bank_account.id,
                voucher_type="ExchangeRevaluation",
                voucher_id="revaluacion-usd",
            ),
        ]
    )
    database.session.flush()

    report = get_bank_balance_summary(BankingFilters(company="cacao"))

    row = next(row for row in report.rows if row.values["account_no"] == "USD-001")
    assert row.values["currency"] == "USD"
    assert row.values["ending_balance"] == Decimal("100")
    assert report.totals["ending_balance"] == Decimal("100")
