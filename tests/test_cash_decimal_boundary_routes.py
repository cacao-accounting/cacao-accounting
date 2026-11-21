# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1972/#1984: los formularios CTM convierten decimales inválidos en errores controlados."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Bank, BankAccount, BankTransaction, PettyCashAccount, database


@pytest.mark.parametrize("amount", ["abc", "NaN", "Infinity"])
def test_bank_reconciliation_invalid_decimal_redirects_without_mutating_transaction(
    app, entorno_contable, authenticated_client, amount
):
    """La conciliación rechaza decimales inválidos antes de marcar el movimiento."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        bank = Bank(name=f"Banco decimal {suffix}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company="cacao",
            bank_id=bank.id,
            account_name=f"Cuenta decimal {suffix}",
            account_no=f"DEC-{suffix}",
            currency="NIO",
            is_active=True,
        )
        database.session.add(account)
        database.session.flush()
        transaction = BankTransaction(
            bank_account_id=account.id,
            posting_date=date(2026, 5, 15),
            reference_number=f"DEC-{suffix}",
            description="Entrada decimal inválida",
            deposit=Decimal("100"),
            withdrawal=None,
        )
        database.session.add(transaction)
        database.session.commit()
        transaction_id = transaction.id
        account_id = account.id
        bank_id = bank.id

    response = authenticated_client().post(
        "/cash_management/bank-reconciliation/apply",
        data={
            "company": "cacao",
            "bank_transaction_id": [transaction_id],
            f"target_{transaction_id}": "gl_entry:does-not-matter",
            f"amount_{transaction_id}": amount,
            f"difference_{transaction_id}": "0",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        saved = database.session.get(BankTransaction, transaction_id)
        assert saved is not None
        assert saved.is_reconciled is False
        database.session.delete(saved)
        database.session.flush()
        database.session.delete(database.session.get(BankAccount, account_id))
        database.session.flush()
        database.session.delete(database.session.get(Bank, bank_id))
        database.session.commit()


@pytest.mark.parametrize("amount", ["abc", "NaN", "Infinity"])
def test_petty_cash_invalid_amount_renders_validation_without_creating_account(
    app, entorno_contable, authenticated_client, amount
):
    """El alta de caja chica no deja escapar InvalidOperation ni persiste una cuenta."""
    name = f"Caja decimal {uuid4().hex[:8]}"
    with app.app_context():
        cash_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="1101")
        ).scalar_one()
    response = authenticated_client().post(
        "/cash_management/petty-cash/new",
        data={
            "company": "cacao",
            "account_id": cash_account_id,
            "name": name,
            "currency": "NIO",
            "float_amount": amount,
        },
    )

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(PettyCashAccount).filter_by(name=name)).scalar_one_or_none() is None
