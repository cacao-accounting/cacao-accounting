# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2172: dos importaciones concurrentes no duplican un movimiento bancario.

El adaptador comprobaba la existencia y después insertaba sin serializar por
cuenta. Bajo PostgreSQL/MySQL, la segunda importación espera el lock de la
cuenta y ve la fila confirmada por la primera.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    Currency,
    Entity,
    database,
)
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

pytestmark = pytest.mark.database


def test_concurrent_import_of_same_movement_is_rejected():
    """Solo una importación persiste el movimiento; la otra recibe conflicto."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if configured_uri.startswith("sqlite"):
        pytest.skip("Este caso requiere locking reads de PostgreSQL o MySQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    suffix = uuid4().hex[:6].upper()
    company_code = f"B{suffix}"
    currency_code = f"B{suffix}"
    account_no = f"ACC-{suffix}"
    posting_date = date(2026, 5, 15)

    with app.app_context():
        database.create_all()
        currency = Currency(code=currency_code, name="Moneda bancaria", decimals=2, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa bancaria {suffix}",
            company_name=f"Empresa bancaria {suffix} SA",
            tax_id=f"B{suffix}",
            currency=currency_code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        bank = Bank(name=f"Banco {suffix}")
        database.session.add(bank)
        database.session.flush()
        bank_account = BankAccount(
            company=company_code,
            bank_id=bank.id,
            account_name=f"Cuenta {suffix}",
            account_no=account_no,
            currency=currency_code,
            is_active=True,
        )
        database.session.add(bank_account)
        database.session.commit()
        account_id = bank_account.id

    inserted = Event()
    release_first = Event()

    def insert_first():
        with app.app_context():
            try:
                database.session.execute(
                    database.select(BankAccount)
                    .where(BankAccount.id == account_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).scalar_one()
                transaction = BankTransaction(
                    bank_account_id=account_id,
                    posting_date=posting_date,
                    reference_number="",
                    description="Movimiento concurrente",
                    deposit=Decimal("10"),
                    withdrawal=None,
                )
                database.session.add(transaction)
                database.session.flush()
                inserted.set()
                assert release_first.wait(timeout=10)
                database.session.commit()
            finally:
                database.session.remove()

    def import_second() -> str:
        with app.app_context():
            try:
                BankStatementAdapter().persist_document(
                    [
                        {
                            "bank_account_id": account_id,
                            "company_id": company_code,
                            "posting_date": posting_date,
                            "reference_number": "",
                            "description": "Movimiento concurrente",
                            "deposit": Decimal("10"),
                            "withdrawal": None,
                        }
                    ]
                )
                database.session.commit()
                return "imported"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(insert_first)
            assert inserted.wait(timeout=10)
            second = workers.submit(import_second)
            finished_before_commit = False
            try:
                second.result(timeout=0.5)
                finished_before_commit = True
            except TimeoutError:
                pass
            release_first.set()
            first.result(timeout=10)
            second_outcome = second.result(timeout=10)

        assert finished_before_commit is False
        assert second_outcome == "rejected"
        with app.app_context():
            assert (
                database.session.execute(
                    database.select(database.func.count())
                    .select_from(BankTransaction)
                    .where(BankTransaction.bank_account_id == account_id)
                ).scalar_one()
                == 1
            )
    finally:
        release_first.set()
        with app.app_context():
            database.session.rollback()
            for transaction in database.session.execute(
                database.select(BankTransaction).where(BankTransaction.bank_account_id == account_id)
            ).scalars():
                database.session.delete(transaction)
            database.session.flush()
            account = database.session.get(BankAccount, account_id)
            if account is not None:
                database.session.delete(account)
            database.session.flush()
            database.session.delete(company)
            database.session.flush()
            database.session.delete(bank)
            database.session.delete(currency)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
