# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Pruebas de revalorizacion cambiaria NIIF multiledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Crea una aplicacion Flask aislada para pruebas de revalorizacion."""
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
        from cacao_accounting.database import (
            AccountingPeriod,
            Book,
            CompanyDefaultAccount,
            Currency,
            Entity,
            ExchangeRate,
            Modules,
            User,
            database,
        )

        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J0001", currency="NIO"),
                Currency(code="USD", name="Dollar", decimals=2, active=True),
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Currency(code="EUR", name="Euro", decimals=2, active=True),
                AccountingPeriod(
                    entity="cacao",
                    name="2026-05",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                ),
                Book(code="USD", name="USD Ledger", entity="cacao", currency="USD", status="activo", is_primary=True),
                Book(code="NIO", name="NIO Ledger", entity="cacao", currency="NIO", status="activo"),
                Book(code="EUR", name="EUR Ledger", entity="cacao", currency="EUR", status="activo"),
            ]
        )
        accounts = _seed_accounts()
        database.session.add(
            CompanyDefaultAccount(
                company="cacao",
                default_receivable=accounts["ar"].id,
                default_payable=accounts["ap"].id,
                default_bank=accounts["bank"].id,
                exchange_gain_account_id=accounts["gain"].id,
                exchange_loss_account_id=accounts["loss"].id,
            )
        )
        database.session.add_all(
            [
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("37.00"), date=date(2026, 5, 31)),
                ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.93"), date=date(2026, 5, 31)),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _seed_accounts() -> dict[str, object]:
    from cacao_accounting.database import Accounts, database

    accounts = {
        "ar": Accounts(
            entity="cacao",
            code="1105",
            name="Clientes",
            active=True,
            enabled=True,
            classification="asset",
            account_type="receivable",
        ),
        "ap": Accounts(
            entity="cacao",
            code="2105",
            name="Proveedores",
            active=True,
            enabled=True,
            classification="liability",
            account_type="payable",
        ),
        "bank": Accounts(
            entity="cacao",
            code="1005",
            name="Banco USD",
            active=True,
            enabled=True,
            classification="asset",
            account_type="bank",
        ),
        "gain": Accounts(
            entity="cacao",
            code="4205",
            name="Ganancia cambiaria",
            active=True,
            enabled=True,
            classification="income",
            account_type="exchange_gain",
        ),
        "loss": Accounts(
            entity="cacao",
            code="5205",
            name="Perdida cambiaria",
            active=True,
            enabled=True,
            classification="expense",
            account_type="exchange_loss",
        ),
        "income": Accounts(
            entity="cacao",
            code="4000",
            name="Ingresos",
            active=True,
            enabled=True,
            classification="income",
            account_type="income",
        ),
    }
    database.session.add_all(accounts.values())
    database.session.flush()
    return accounts


def _book(code: str):
    from cacao_accounting.database import Book, database

    return database.session.execute(database.select(Book).filter_by(code=code, entity="cacao")).scalar_one()


def _create_sales_invoice(open_amount: Decimal = Decimal("100.00")):
    from cacao_accounting.database import Accounts, GLEntry, PaymentEntry, PaymentReference, SalesInvoice, database

    ar = database.session.execute(database.select(Accounts.id).filter_by(entity="cacao", code="1105")).scalar_one()
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_no="SI-USD-001",
        customer_id="CUST-1",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36.00"),
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
        outstanding_amount=open_amount,
        base_outstanding_amount=open_amount * Decimal("36.00"),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 5, 1),
                company="cacao",
                ledger_id=_book("NIO").id,
                account_id=ar,
                account_code="1105",
                debit=Decimal("3600.00"),
                credit=Decimal("0"),
                debit_in_account_currency=open_amount,
                account_currency="USD",
                company_currency="NIO",
                exchange_rate=Decimal("36.00"),
                party_type="customer",
                party_id="CUST-1",
                voucher_type="sales_invoice",
                voucher_id=invoice.id,
            ),
            GLEntry(
                posting_date=date(2026, 5, 1),
                company="cacao",
                ledger_id=_book("EUR").id,
                account_id=ar,
                account_code="1105",
                debit=Decimal("90.00"),
                credit=Decimal("0"),
                debit_in_account_currency=open_amount,
                account_currency="USD",
                company_currency="EUR",
                exchange_rate=Decimal("0.90"),
                party_type="customer",
                party_id="CUST-1",
                voucher_type="sales_invoice",
                voucher_id=invoice.id,
            ),
        ]
    )
    if open_amount < Decimal("100.00"):
        payment = PaymentEntry(
            company="cacao",
            posting_date=date(2026, 5, 15),
            payment_type="receive",
            party_type="customer",
            party_id="CUST-1",
            paid_amount=Decimal("100.00") - open_amount,
        )
        database.session.add(payment)
        database.session.flush()
        database.session.add(
            PaymentReference(
                payment_id=payment.id,
                reference_type="sales_invoice",
                reference_id=invoice.id,
                total_amount=Decimal("100.00"),
                outstanding_amount=Decimal("100.00"),
                allocated_amount=Decimal("100.00") - open_amount,
                allocation_date=payment.posting_date,
            )
        )
    database.session.commit()
    return invoice


def test_service_revalues_open_sales_invoice_per_destination_ledger(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import ExchangeRevaluationItem, GLEntry, database

    _create_sales_invoice()

    run = ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    assert run.status == "posted"
    assert run.generated_journal is True
    assert run.processed_documents_count == 1
    assert run.affected_documents_count == 2
    lines = database.session.execute(database.select(ExchangeRevaluationItem)).scalars().all()
    assert {line.ledger_currency_id for line in lines} == {"NIO", "EUR"}
    assert {line.exchange_difference for line in lines} == {Decimal("100.0000"), Decimal("3.0000")}
    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=run.id)).scalars().all()
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)


def test_service_uses_only_open_partial_balance(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import ExchangeRevaluationItem, database

    _create_sales_invoice(open_amount=Decimal("40.00"))

    ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    nio_line = database.session.execute(
        database.select(ExchangeRevaluationItem).filter_by(ledger_currency_id="NIO")
    ).scalar_one()
    assert nio_line.open_amount_original == Decimal("40.0000")
    assert nio_line.exchange_difference == Decimal("40.0000")


def test_service_does_not_duplicate_previous_revaluation(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService

    _create_sales_invoice()
    service = ExchangeRevaluationService()
    first = service.run(company="cacao", year=2026, month=5, user_id="admin")
    second = service.run(company="cacao", year=2026, month=5, user_id="admin")

    assert first.status == "posted"
    assert second.status == "completed_no_changes"
    assert second.generated_journal is False
    assert second.affected_documents_count == 0


def test_service_raises_controlled_error_when_closing_rate_is_missing(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import (
        ExchangeRevaluationError,
        ExchangeRevaluationService,
    )
    from cacao_accounting.database import ExchangeRate, database

    _create_sales_invoice()
    database.session.execute(database.delete(ExchangeRate).where(ExchangeRate.destination == "NIO"))
    database.session.commit()

    with pytest.raises(ExchangeRevaluationError, match="Falta tasa de cierre"):
        ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")


def test_service_revalues_foreign_currency_bank_balance(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import Accounts, Bank, BankAccount, ExchangeRevaluationItem, GLEntry, database

    bank_account_id = database.session.execute(
        database.select(Accounts.id).filter_by(entity="cacao", code="1005")
    ).scalar_one()
    bank = Bank(name="Banco USD")
    database.session.add(bank)
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta USD",
        account_no="USD-1",
        currency="USD",
        gl_account_id=bank_account_id,
    )
    database.session.add(bank_account)
    database.session.flush()
    database.session.add(
        GLEntry(
            posting_date=date(2026, 5, 1),
            company="cacao",
            ledger_id=_book("NIO").id,
            account_id=bank_account_id,
            account_code="1005",
            debit=Decimal("360.00"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("10.00"),
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36.00"),
            bank_account_id=bank_account.id,
            voucher_type="payment_entry",
            voucher_id="PAY-1",
        )
    )
    database.session.commit()

    ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    bank_line = database.session.execute(
        database.select(ExchangeRevaluationItem).filter_by(source_document_type="bank_account", ledger_currency_id="NIO")
    ).scalar_one()
    assert bank_line.open_amount_original == Decimal("10.0000")
    assert bank_line.exchange_difference == Decimal("10.0000")


def test_service_voids_posted_revaluation_with_reversal_entries(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import GLEntry, database

    _create_sales_invoice()
    service = ExchangeRevaluationService()
    run = service.run(company="cacao", year=2026, month=5, user_id="admin")
    voided = service.void(run_id=run.id, user_id="admin", reason="test")

    assert voided.status == "voided"
    reversals = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_id=run.id, is_reversal=True)).scalars().all()
    )
    assert reversals
    assert sum(entry.debit for entry in reversals) == sum(entry.credit for entry in reversals)


def test_exchange_revaluation_routes_render_and_execute(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    assert client.get("/accounting/exchange-revaluation").status_code == 200
    assert client.get("/accounting/exchange-revaluation/new").status_code == 200

    _create_sales_invoice()
    response = client.post(
        "/accounting/exchange-revaluation/new",
        data={"company": "cacao", "year": "2026", "month": "5"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "SI-USD-001".encode() in response.data
