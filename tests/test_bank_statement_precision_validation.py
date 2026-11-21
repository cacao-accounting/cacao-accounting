# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1663: los importes bancarios no se redondean al guardarse."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, BankTransaction, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


@pytest.fixture
def bank_statement_scenario():
    """Crea una cuenta de prueba cuya moneda declara cinco decimales."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:8].upper()
    company_code = f"C{suffix}"
    currency_code = f"C{suffix}"
    with app.app_context():
        database.create_all()
        currency = Currency(code=currency_code, name="Moneda cinco", decimals=5, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Compañía {suffix}",
            company_name=f"Compañía {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency_code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        bank = Bank(name=f"Banco {suffix}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company=company_code,
            bank_id=bank.id,
            account_name=f"Cuenta {suffix}",
            account_no=f"ACC-{suffix}",
            currency=currency_code,
            is_active=True,
        )
        database.session.add(account)
        database.session.commit()
        identifiers = {"company": company_code, "account": account.id, "currency": currency_code}

    yield app, identifiers

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _row(account_id: str, deposit: str) -> dict:
    """Build one bank statement row with a numeric amount."""
    return {
        "bank_account_id": account_id,
        "posting_date": date(2026, 5, 15),
        "reference_number": "REF-PRECISION",
        "description": "Prueba de precisión",
        "deposit": deposit,
        "withdrawal": None,
    }


def test_import_rejects_amount_that_database_would_round(bank_statement_scenario):
    """A five-decimal source value is rejected before Numeric(20, 4) can alter it."""
    app, identifiers = bank_statement_scenario
    adapter = BankStatementAdapter()
    row = _row(identifiers["account"], "123.45678")

    with app.app_context():
        errors = adapter.validate_row(row)
        with pytest.raises(ValueError, match="máximo 4 decimales"):
            adapter.build_document([row], {"company_id": identifiers["company"]})
        assert errors and any("máximo 4 decimales" in error for error in errors)
        assert database.session.execute(database.select(BankTransaction)).scalars().all() == []


@pytest.mark.parametrize("source_amount", ["123.4567", "123.456700"])
def test_import_preserves_amount_representable_by_database_scale(bank_statement_scenario, source_amount):
    """Four-place amounts and equivalent trailing-zero inputs persist exactly."""
    app, identifiers = bank_statement_scenario
    adapter = BankStatementAdapter()
    row = _row(identifiers["account"], source_amount)

    with app.app_context():
        errors = adapter.validate_row(row)
        assert errors == []
        document = adapter.build_document([row], {"company_id": identifiers["company"]})
        adapter.persist_document(document)
        database.session.commit()
        persisted = database.session.execute(database.select(BankTransaction)).scalar_one()

    assert persisted.deposit == Decimal("123.4567")
