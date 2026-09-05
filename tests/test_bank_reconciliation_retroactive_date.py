# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para la fecha de cierre retroactivo en conciliación bancaria (issue #768).

Cubre:
1. La fecha de conciliación enviada por el cliente (no ``date.today()``) se
   persiste en ``Reconciliation.recon_date`` y en cada
   ``ReconciliationItem.reconciliation_date``.
2. Una fecha en un período contable ya cerrado se rechaza con HTTP 400.
3. Una fecha en un período habilitado y abierto se acepta (no se rechaza con 400).
4. Una fecha mal formada se rechaza con HTTP 400.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

COMPANY = "rcn8"
OPEN_PERIOD_START = date(2026, 5, 1)
OPEN_PERIOD_END = date(2026, 5, 31)
CLOSED_PERIOD_START = date(2026, 4, 1)
CLOSED_PERIOD_END = date(2026, 4, 30)


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con un período abierto y uno cerrado para la compañía."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import AccountingPeriod, Currency, Entity, Modules, User

        database.create_all()
        database.session.add_all(
            [
                Entity(code=COMPANY, name="Recon8", company_name="Recon8", tax_id="RCN-8", currency="NIO"),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                User(id="admin", user="admin", name="Administrator", password=b"x", classification="admin", active=True),
                Modules(module="cash", default=True, enabled=True),
                AccountingPeriod(
                    entity=COMPANY,
                    name="2026-05",
                    enabled=True,
                    is_closed=False,
                    start=OPEN_PERIOD_START,
                    end=OPEN_PERIOD_END,
                ),
                AccountingPeriod(
                    entity=COMPANY,
                    name="2026-04",
                    enabled=True,
                    is_closed=True,
                    start=CLOSED_PERIOD_START,
                    end=CLOSED_PERIOD_END,
                ),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def chart(app_ctx):
    """Catálogo mínimo: cuenta GL bancaria, libro primario y cuenta bancaria."""
    from cacao_accounting.database import Accounts, Bank, BankAccount, Book, database

    bank_gl = Accounts(entity=COMPANY, code="1001", name="Banco A", classification="asset", account_type="bank")
    book = Book(entity=COMPANY, code="RCNKLOC", name="Libro Fiscal", currency="NIO", status="activo", is_primary=True)
    database.session.add_all([bank_gl, book])
    database.session.flush()

    bank = Bank(name="Banco Nacional 8")
    database.session.add(bank)
    database.session.flush()

    account = BankAccount(
        bank_id=bank.id,
        company=COMPANY,
        account_name="Cuenta A",
        account_no="A-001",
        currency="NIO",
        gl_account_id=bank_gl.id,
    )
    database.session.add(account)
    database.session.commit()
    return {"bank_gl_id": bank_gl.id, "book_id": book.id, "account": account}


def _bank_transaction(chart, *, deposit=None, withdrawal=None, posting_date=OPEN_PERIOD_START):
    """Persiste una línea de extracto bancario dentro del período abierto."""
    from cacao_accounting.database import BankTransaction, database

    transaction = BankTransaction(
        bank_account_id=chart["account"].id,
        posting_date=posting_date,
        deposit=deposit,
        withdrawal=withdrawal,
    )
    database.session.add(transaction)
    database.session.commit()
    return transaction


def _gl_entry_target(chart, voucher_id: str, credit: Decimal) -> str:
    """Crea la entrada GL bancaria destino de la conciliación."""
    from cacao_accounting.database import GLEntry, database

    entry = GLEntry(
        posting_date=OPEN_PERIOD_START,
        company=COMPANY,
        ledger_id=chart["book_id"],
        account_id=chart["bank_gl_id"],
        account_code="1001",
        debit=Decimal("0"),
        credit=credit,
        account_currency="NIO",
        company_currency="NIO",
        voucher_type="journal_entry",
        voucher_id=voucher_id,
        is_cancelled=False,
        is_reversal=False,
        bank_account_id=chart["account"].id,
    )
    database.session.add(entry)
    database.session.commit()
    return entry.id


def test_retroactive_reconciliation_date_is_persisted(app_ctx, chart):
    """La fecha enviada por el cliente, no date.today(), queda persistida."""
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )
    from cacao_accounting.database import ReconciliationItem

    transaction = _bank_transaction(chart, deposit=Decimal("100.00"))
    target_id = _gl_entry_target(chart, "JRN-RCN-1", Decimal("100.0000"))

    retroactive_date = date(2026, 5, 15)
    reconciliation = reconcile_bank_items(
        BankReconciliationRequest(
            company=COMPANY,
            reconciliation_date=retroactive_date,
            matches=[BankReconciliationMatch(transaction.id, "gl_entry", target_id, Decimal("100.00"))],
        )
    )
    database.session.commit()

    assert reconciliation.recon_date == retroactive_date
    item = database.session.execute(
        database.select(ReconciliationItem).where(ReconciliationItem.reconciliation_id == reconciliation.id)
    ).scalar_one()
    assert item.reconciliation_date == retroactive_date


def test_reconciliation_form_accepts_difference_on_pending_bank_amount(app_ctx, chart):
    """El formulario usa el remanente, no el total, al agregar una diferencia."""
    from cacao_accounting.bancos.routes import _parse_reconciliation_item_from_form
    from cacao_accounting.database import Reconciliation, ReconciliationItem

    transaction = _bank_transaction(chart, deposit=Decimal("100.00"))
    reconciliation = Reconciliation(company=COMPANY, recon_date=OPEN_PERIOD_START, recon_type="bank")
    database.session.add(reconciliation)
    database.session.flush()
    database.session.add(
        ReconciliationItem(
            reconciliation_id=reconciliation.id,
            reference_type="bank_transaction",
            reference_id=transaction.id,
            amount=Decimal("60.00"),
            allocated_amount=Decimal("60.00"),
            status="partial",
            source_type="bank_transaction",
            source_id=transaction.id,
            target_type="payment_entry",
            target_id="PAYMENT-60",
        )
    )
    database.session.commit()

    with app_ctx.test_request_context(
        "/cash_management/bank-reconciliation/apply",
        method="POST",
        data={
            f"target_{transaction.id}": "payment_entry:PAYMENT-40",
            f"amount_{transaction.id}": "35.00",
            f"difference_{transaction.id}": "5.00",
        },
    ):
        match, difference, error = _parse_reconciliation_item_from_form(transaction.id)

    assert error is None
    assert match is not None
    assert match.allocated_amount == Decimal("35.00")
    assert difference == (transaction.id, Decimal("5.00"))


def test_reconciliation_route_rejects_closed_period(app_ctx, chart):
    """Una fecha en un período ya cerrado se rechaza con HTTP 400."""
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True

    response = client.post(
        "/cash_management/bank-reconciliation/apply",
        data={"company": COMPANY, "reconciliation_date": "2026-04-15"},
    )
    assert response.status_code == 400


def test_reconciliation_route_accepts_open_period(app_ctx, chart):
    """Una fecha en un período abierto no se rechaza (fluye al flasheo/redirección)."""
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True

    response = client.post(
        "/cash_management/bank-reconciliation/apply",
        data={"company": COMPANY, "reconciliation_date": "2026-05-15"},
    )
    assert response.status_code != 400


def test_reconciliation_route_rejects_malformed_date(app_ctx, chart):
    """Una fecha mal formada se rechaza con HTTP 400."""
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True

    response = client.post(
        "/cash_management/bank-reconciliation/apply",
        data={"company": COMPANY, "reconciliation_date": "no-es-una-fecha"},
    )
    assert response.status_code == 400
