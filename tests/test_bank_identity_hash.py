"""Tests for bank statement identity hash and duplicate detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BankAccount,
    BankTransaction,
    CacaoConfig,
    Currency,
    Entity,
    User,
    database,
)
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


@pytest.fixture()
def bank_app():
    """Create an isolated schema for bank transaction tests."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "bank-identity-test-secret",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                BankAccount(bank_id="bank-001", company="cacao", account_name="Test Account"),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()


def test_two_identical_same_day_commissions_can_be_imported(bank_app):
    """Two identical commissions on the same day should be importable.

    This is a regression test for issue #737: legitimate same-day duplicate
    transactions (like repeated commissions) should not be rejected.
    """
    account = database.session.execute(database.select(BankAccount).filter_by(account_name="Test Account")).scalar_one()
    adapter = BankStatementAdapter()

    # Two identical commissions on the same day with no reference
    document = [
        {
            "bank_account_id": account.id,
            "posting_date": date(2026, 8, 26),
            "reference_number": "",
            "description": "Commission fee",
            "deposit": None,
            "withdrawal": Decimal("5.00"),
            "company_id": "cacao",
        },
        {
            "bank_account_id": account.id,
            "posting_date": date(2026, 8, 26),
            "reference_number": "",
            "description": "Commission fee",
            "deposit": None,
            "withdrawal": Decimal("5.00"),
            "company_id": "cacao",
        },
    ]

    # Should not raise an error
    built = adapter.build_document(document, {})
    adapter.persist_document(built)

    # Both transactions should be persisted
    transactions = (
        database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account.id)).scalars().all()
    )
    assert len(transactions) == 2


def test_reimport_of_same_file_still_deduplicates(bank_app):
    """Re-importing the same file should detect duplicates from previous import.

    This ensures that deduplication still works across imports.
    """
    account = database.session.execute(database.select(BankAccount).filter_by(account_name="Test Account")).scalar_one()
    adapter = BankStatementAdapter()

    document = [
        {
            "bank_account_id": account.id,
            "posting_date": date(2026, 8, 26),
            "reference_number": "REF-001",
            "description": "Payment",
            "deposit": Decimal("100.00"),
            "withdrawal": None,
            "company_id": "cacao",
        },
    ]

    # First import should succeed
    built1 = adapter.build_document(document, {})
    adapter.persist_document(built1)
    database.session.commit()

    # Second import of same data should fail (duplicate in database)
    with pytest.raises(ValueError, match="ya existe"):
        built2 = adapter.build_document(document, {})
        adapter.persist_document(built2)


def test_identity_hash_includes_bank_account_and_date(bank_app):
    """Identity hash should be unique per bank account and date."""
    from cacao_accounting.database import _bank_transaction_identity

    account = database.session.execute(database.select(BankAccount).filter_by(account_name="Test Account")).scalar_one()

    tx1 = BankTransaction(
        bank_account_id=account.id,
        posting_date=date(2026, 8, 26),
        reference_number="REF-001",
        deposit=Decimal("100.00"),
    )
    tx2 = BankTransaction(
        bank_account_id=account.id,
        posting_date=date(2026, 8, 27),  # Different date
        reference_number="REF-001",
        deposit=Decimal("100.00"),
    )

    assert _bank_transaction_identity(tx1) != _bank_transaction_identity(tx2)
