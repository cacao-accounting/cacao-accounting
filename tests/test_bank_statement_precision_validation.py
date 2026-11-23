# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1663: los importes bancarios no se redondean al guardarse."""

from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, BankTransaction, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.imports.readers.base import NumericCellValue


@pytest.fixture(name="bank_statement_scenario")
def make_bank_statement_scenario():
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
        assert not errors
        document = adapter.build_document([row], {"company_id": identifiers["company"]})
        assert document[0]["deposit"] == Decimal("123.4567")
        adapter.persist_document(document)
        database.session.commit()
        persisted = database.session.execute(database.select(BankTransaction)).scalar_one()

    assert persisted.deposit == Decimal("123.4567")


def test_equivalent_reimport_uses_the_persisted_scale_for_identity(bank_statement_scenario):
    """Trailing zeros normalize before identity generation and prevent reimport duplicates."""
    app, identifiers = bank_statement_scenario
    adapter = BankStatementAdapter()
    context = {"company_id": identifiers["company"], "import_fingerprint": "same-source"}
    first_row = _row(identifiers["account"], "123.456700")
    first_row["reference_number"] = ""
    repeated_row = _row(identifiers["account"], "123.4567")
    repeated_row["reference_number"] = ""

    with app.app_context():
        first_document = adapter.build_document([first_row], context)
        repeated_document = adapter.build_document([repeated_row], context)
        assert first_document[0]["deposit"] == repeated_document[0]["deposit"] == Decimal("123.4567")

        adapter.persist_document(first_document)
        database.session.commit()
        adapter.persist_document(repeated_document)
        database.session.commit()

        persisted = (
            database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=identifiers["account"]))
            .scalars()
            .all()
        )
        assert len(persisted) == 1
        assert persisted[0].deposit == Decimal("123.4567")


@pytest.mark.parametrize(
    "source_amount",
    ["99999999999.9999", NumericCellValue.from_number("99999999999.9999")],
)
def test_import_accepts_maximum_cross_database_exact_amount(bank_statement_scenario, source_amount):
    """The largest cross-database exact value remains exact after persistence."""
    app, identifiers = bank_statement_scenario
    adapter = BankStatementAdapter()
    row = _row(identifiers["account"], source_amount)

    with app.app_context():
        assert not adapter.validate_row(row)
        document = adapter.build_document([row], {"company_id": identifiers["company"]})
        assert document[0]["deposit"] == Decimal("99999999999.9999")
        adapter.persist_document(document)
        database.session.commit()
        persisted = database.session.execute(database.select(BankTransaction)).scalar_one()

    assert persisted.deposit == Decimal("99999999999.9999")


@pytest.mark.parametrize(
    "source_amount",
    ["100000000000.0000", NumericCellValue.from_number("100000000000.0000")],
)
def test_import_rejects_amount_above_cross_database_exact_range(bank_statement_scenario, source_amount):
    """Values SQLite cannot preserve at scale four fail before persistence."""
    app, identifiers = bank_statement_scenario
    adapter = BankStatementAdapter()
    row = _row(identifiers["account"], source_amount)

    with app.app_context():
        errors = adapter.validate_row(row)
        with pytest.raises(InvalidOperation, match="11 dígitos enteros"):
            adapter.build_document([row], {"company_id": identifiers["company"]})
        assert any("11 dígitos enteros" in error for error in errors)
        assert database.session.execute(database.select(BankTransaction)).scalars().all() == []


@pytest.mark.database
def test_configured_database_persists_normalized_bank_amount(tmp_path):
    """The configured Tier 1 database persists the exact scale used by the adapter."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if configured_uri.startswith("sqlite"):
        configured_uri = f"sqlite:///{tmp_path / 'bank-precision.sqlite'}"
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    suffix = uuid4().hex[:6].upper()
    currency_code = f"P{suffix}"
    company_code = f"P{suffix}"

    with application.app_context():
        database.create_all()
        currency = Currency(code=currency_code, name="Moneda precisión", decimals=4, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa precisión {suffix}",
            company_name=f"Empresa precisión {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency_code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        bank = Bank(name=f"Banco precisión {suffix}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company=company_code,
            bank_id=bank.id,
            account_name=f"Cuenta precisión {suffix}",
            account_no=f"PREC-{suffix}",
            currency=currency_code,
            is_active=True,
        )
        database.session.add(account)
        database.session.commit()

        adapter = BankStatementAdapter()
        row = _row(account.id, "123.4567")
        try:
            assert not adapter.validate_row(row)
            document = adapter.build_document([row], {"company_id": company_code})
            adapter.persist_document(document)
            database.session.commit()
            database.session.expire_all()
            persisted = database.session.execute(
                database.select(BankTransaction).filter_by(bank_account_id=account.id)
            ).scalar_one()
            assert persisted.deposit == Decimal("123.4567")

            row["deposit"] = "123.45678"
            errors = adapter.validate_row(row)
            assert any("máximo 4 decimales" in error for error in errors)
            with pytest.raises(ValueError, match="máximo 4 decimales"):
                adapter.build_document([row], {"company_id": company_code})
        finally:
            database.session.rollback()
            database.session.execute(database.delete(BankTransaction).filter_by(bank_account_id=account.id))
            database.session.delete(account)
            database.session.flush()
            database.session.delete(bank)
            database.session.delete(company)
            database.session.flush()
            database.session.delete(currency)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
