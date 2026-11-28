# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2151: el cierre fiscal incluye clasificaciones de los catálogos.

Los catálogos usan `Income`, `Expense` y `Cost` con mayúscula inicial. El
filtro de saldos de cierre debe ser insensible a mayúsculas para no omitir
esas cuentas del asiento de cierre.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.contabilidad.fiscal_year_closing import calculate_closing_balances
from cacao_accounting.database import Accounts, Book, FiscalYear, GLEntry, database


def _account(code: str, classification: str) -> Accounts:
    """Create an income/expense account with the catalog capitalization."""
    return Accounts(
        entity="cacao",
        code=code,
        name=f"Cuenta {code}",
        classification=classification,
        account_type="expense",
        active=True,
        enabled=True,
    )


def test_closing_balances_include_catalog_classifications(app, entorno_contable):
    """Income/Expense/Cost con mayúscula entran al cierre igual que minúsculas."""
    suffix = uuid4().hex[:4].upper()
    with app.app_context():
        book = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        accounts = [
            _account(f"CI{suffix}", "Income"),
            _account(f"CE{suffix}", "Expense"),
            _account(f"CC{suffix}", "Cost"),
            _account(f"CL{suffix}", "income"),
        ]
        database.session.add_all(accounts)
        database.session.flush()
        for index, account in enumerate(accounts, start=1):
            database.session.add(
                GLEntry(
                    company="cacao",
                    account_id=account.id,
                    ledger_id=book.id,
                    account_code=account.code,
                    voucher_type="journal_entry",
                    voucher_id=f"JE-CLOSE-{suffix}-{index}",
                    posting_date=date(2026, 5, 15),
                    debit=Decimal("0"),
                    credit=Decimal("10"),
                    is_cancelled=False,
                    is_reversal=False,
                    is_fiscal_year_closing=False,
                )
            )
        database.session.commit()
        fiscal_year = database.session.get(FiscalYear, "FY2026")
        expected_codes = {account.code for account in accounts}
        codes = {row["account_code"] for row in calculate_closing_balances("cacao", fiscal_year)}

    assert expected_codes <= codes
