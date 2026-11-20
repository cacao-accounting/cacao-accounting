# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1130: los KPI solo aceptan un libro de la compañía solicitada.

Un libro ajeno o inexistente no debe etiquetar el snapshot con una moneda
distinta ni devolver métricas aparentemente válidas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.bancos.services import petty_cash_ledger_balance
from cacao_accounting.database import Accounts, Book, Currency, Entity, GLEntry, PettyCashAccount, database
from cacao_accounting.ledger_queries import PrimaryLedgerUnavailableError
from cacao_accounting.reportes.analytics import get_kpi_snapshot


@pytest.fixture
def kpi_ledger_scenario():
    """Create two companies with books in different currencies."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name=f"Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="USD",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        alpha_book = Book(
            entity="alpha", code=f"ALPHA-{suffix}", name="Libro Alfa", status="activo", is_primary=True, currency="NIO"
        )
        beta_book = Book(
            entity="beta", code=f"BETA-{suffix}", name="Libro Beta", status="activo", is_primary=True, currency="USD"
        )
        database.session.add_all([alpha_book, beta_book])
        database.session.flush()
        income_account = Accounts(
            entity="alpha",
            code=f"4101-{suffix}",
            name="Ingresos",
            classification="income",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add(income_account)
        database.session.flush()
        database.session.add(
            GLEntry(
                company="alpha",
                account_id=income_account.id,
                ledger_id=alpha_book.id,
                account_code=income_account.code,
                voucher_type="journal_entry",
                voucher_id=f"JE-{suffix}",
                posting_date=date(2026, 5, 10),
                debit=Decimal("0"),
                credit=Decimal("100"),
                is_cancelled=False,
                is_reversal=False,
                is_fiscal_year_closing=False,
            )
        )
        database.session.commit()
        ids = {
            "alpha_book_code": alpha_book.code,
            "alpha_book_id": alpha_book.id,
            "beta_book_code": beta_book.code,
            "beta_book_id": beta_book.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_kpi_snapshot_rejects_book_from_another_company(kpi_ledger_scenario):
    """A foreign book ID or code cannot set the KPI currency."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["beta_book_id"])
        with pytest.raises(ValueError):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["beta_book_code"])


def test_kpi_snapshot_rejects_unknown_book(kpi_ledger_scenario):
    """An unknown ledger is rejected instead of returning empty GL metrics."""
    app, _ids = kpi_ledger_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger="NO-SUCH-BOOK")


def test_kpi_snapshot_accepts_own_book_by_code_and_id(kpi_ledger_scenario):
    """The company's book works by code or ULID and keeps its currency."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        by_code = get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["alpha_book_code"])
        by_id = get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["alpha_book_id"])

    assert by_code["currency"] == "NIO"
    assert by_id["currency"] == "NIO"
    assert by_code["metrics"]["income"] == Decimal("100")
    assert by_id["metrics"]["income"] == Decimal("100")


def test_kpi_snapshot_fails_when_no_active_ledger_exists(kpi_ledger_scenario):
    """Inactive books must not be silently combined into a valid-looking KPI."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        primary = database.session.get(Book, ids["alpha_book_id"])
        assert primary is not None
        primary.status = "suspendido"
        second_book = Book(
            entity="alpha",
            code="ALPHA-SUSPENDED",
            name="Libro suspendido",
            status="suspendido",
            currency="USD",
        )
        database.session.add(second_book)
        database.session.flush()
        account = database.session.execute(database.select(Accounts).where(Accounts.entity == "alpha")).scalars().one()
        database.session.add(
            GLEntry(
                company="alpha",
                account_id=account.id,
                ledger_id=second_book.id,
                account_code=account.code,
                voucher_type="journal_entry",
                voucher_id="JE-INACTIVE-BOOK",
                posting_date=date(2026, 5, 10),
                debit=Decimal("0"),
                credit=Decimal("50"),
                is_cancelled=False,
                is_reversal=False,
                is_fiscal_year_closing=False,
            )
        )
        database.session.commit()

        with pytest.raises(PrimaryLedgerUnavailableError, match="libro contable activo"):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31))


def test_kpi_snapshot_uses_only_the_primary_of_multiple_active_ledgers(kpi_ledger_scenario):
    """A multi-book posting is read once in the deterministic primary book."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        secondary_book = Book(
            entity="alpha",
            code="ALPHA-SECONDARY",
            name="Libro secundario",
            status="activo",
            currency="USD",
        )
        database.session.add(secondary_book)
        database.session.flush()
        account = database.session.execute(database.select(Accounts).where(Accounts.entity == "alpha")).scalars().one()
        database.session.add(
            GLEntry(
                company="alpha",
                account_id=account.id,
                ledger_id=secondary_book.id,
                account_code=account.code,
                voucher_type="journal_entry",
                voucher_id="JE-SECONDARY-BOOK",
                posting_date=date(2026, 5, 10),
                debit=Decimal("0"),
                credit=Decimal("50"),
                is_cancelled=False,
                is_reversal=False,
                is_fiscal_year_closing=False,
            )
        )
        database.session.commit()

        snapshot = get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31))

    assert snapshot["metrics"]["income"] == Decimal("100")


def test_petty_cash_balance_uses_one_book_when_posting_has_multiple_books(kpi_ledger_scenario):
    """The operational cash balance must not add two book representations."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        primary = database.session.get(Book, ids["alpha_book_id"])
        assert primary is not None
        secondary = Book(
            entity="alpha",
            code="ALPHA-CASH-SECONDARY",
            name="Libro de efectivo secundario",
            status="activo",
            currency="USD",
        )
        account = Accounts(
            entity="alpha",
            code="1000-CASH",
            name="Caja chica",
            classification="asset",
            account_type="petty_cash",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add_all([secondary, account])
        database.session.flush()
        fund = PettyCashAccount(
            company="alpha",
            account_id=account.id,
            name="Fondo de prueba",
            currency="NIO",
            float_amount=Decimal("100"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fund)
        database.session.flush()
        database.session.add_all(
            [
                GLEntry(
                    company="alpha",
                    account_id=account.id,
                    ledger_id=primary.id,
                    account_code=account.code,
                    voucher_type="journal_entry",
                    voucher_id="JE-PETTY-CASH-PRIMARY",
                    posting_date=date(2026, 5, 10),
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    is_cancelled=False,
                    is_reversal=False,
                    is_fiscal_year_closing=False,
                ),
                GLEntry(
                    company="alpha",
                    account_id=account.id,
                    ledger_id=secondary.id,
                    account_code=account.code,
                    voucher_type="journal_entry",
                    voucher_id="JE-PETTY-CASH-SECONDARY",
                    posting_date=date(2026, 5, 10),
                    debit=Decimal("50"),
                    credit=Decimal("0"),
                    is_cancelled=False,
                    is_reversal=False,
                    is_fiscal_year_closing=False,
                ),
            ]
        )
        database.session.commit()

        assert petty_cash_ledger_balance(fund) == Decimal("100")
        primary.status = "suspendido"
        secondary.status = "suspendido"
        database.session.commit()
        with pytest.raises(PrimaryLedgerUnavailableError, match="libro contable activo"):
            petty_cash_ledger_balance(fund)
