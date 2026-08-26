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
                unrealized_exchange_gain_account_id=accounts["unrealized_gain"].id,
                unrealized_exchange_loss_account_id=accounts["unrealized_loss"].id,
            )
        )
        database.session.add_all(
            [
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.00"), date=date(2026, 5, 1)),
                ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.90"), date=date(2026, 5, 1)),
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

    accounts: dict[str, object] = {
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
        "unrealized_gain": Accounts(
            entity="cacao",
            code="4210",
            name="Ganancia cambiaria no realizada",
            active=True,
            enabled=True,
            classification="income",
            account_type="unrealized_exchange_gain",
        ),
        "unrealized_loss": Accounts(
            entity="cacao",
            code="5210",
            name="Perdida cambiaria no realizada",
            active=True,
            enabled=True,
            classification="expense",
            account_type="unrealized_exchange_loss",
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
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )

    income = database.session.execute(database.select(Accounts.id).filter_by(entity="cacao", code="4000")).scalar_one()
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
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="SERVICE-USD",
            item_name="Foreign service",
            qty=Decimal("1"),
            rate=Decimal("100"),
            amount=Decimal("100"),
            income_account_id=income,
        )
    )
    database.session.flush()
    post_document_to_gl(invoice)
    if open_amount < Decimal("100.00"):
        # El pago parcial se contabiliza en GL antes del cierre, igual que el
        # flujo real (PaymentEntry -> referencia -> post_document_to_gl); el
        # servicio mide el saldo abierto desde el valor en libros del libro
        # funcional, por lo que el pago debe tener soporte contable.
        payment = PaymentEntry(
            company="cacao",
            posting_date=date(2026, 5, 15),
            payment_type="receive",
            party_type="customer",
            party_id="CUST-1",
            transaction_currency="USD",
            base_currency="NIO",
            currency="USD",
            exchange_rate=Decimal("36.00"),
            received_amount=Decimal("100.00") - open_amount,
            base_received_amount=(Decimal("100.00") - open_amount) * Decimal("36.00"),
            docstatus=1,
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
                company="cacao",
            )
        )
        post_document_to_gl(payment)
    database.session.commit()
    return invoice


def test_service_revalues_open_sales_invoice_per_destination_ledger(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import ExchangeRevaluationItem, GLEntry, database
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        get_balance_sheet_report,
        get_income_statement_report,
        get_trial_balance_report,
    )

    _create_sales_invoice()

    run = ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    assert run.status == "posted"
    assert run.generated_journal is True
    assert run.currency == "NIO"
    assert run.total_gain == Decimal("100.0000")
    assert run.total_loss == Decimal("0.0000")
    assert run.processed_documents_count == 1
    assert run.affected_documents_count == 2
    lines = database.session.execute(database.select(ExchangeRevaluationItem)).scalars().all()
    assert {line.ledger_currency_id for line in lines} == {"NIO", "EUR"}
    assert {line.exchange_difference for line in lines} == {Decimal("100.0000"), Decimal("3.0000")}
    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=run.id)).scalars().all()
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    monetary_entries = [entry for entry in entries if entry.account_code == "1105"]
    offset_entries = [entry for entry in entries if entry.account_code != "1105"]
    assert {entry.account_currency for entry in monetary_entries} == {"USD"}
    assert {entry.account_code for entry in offset_entries} == {"4210"}
    assert sum(entry.debit_in_account_currency or 0 for entry in monetary_entries) == 0
    assert sum(entry.credit_in_account_currency or 0 for entry in monetary_entries) == 0

    for ledger_code, currency, closing_balance in (
        ("USD", "USD", Decimal("100")),
        ("NIO", "NIO", Decimal("3700")),
        ("EUR", "EUR", Decimal("93")),
    ):
        filters = FinancialReportFilters(company="cacao", ledger=ledger_code)
        trial_balance = get_trial_balance_report(filters)
        income_statement = get_income_statement_report(filters)
        balance_sheet = get_balance_sheet_report(filters)
        assert trial_balance.ledger_currency == currency
        assert trial_balance.totals["difference"] == 0
        assert income_statement.totals["net_profit"] == closing_balance
        assert balance_sheet.totals["assets"] == closing_balance
        assert balance_sheet.totals["period_profit"] == closing_balance
        assert balance_sheet.totals["difference"] == 0


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


def test_service_recalculates_previous_revaluation(app_ctx):
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService

    _create_sales_invoice()
    service = ExchangeRevaluationService()
    first = service.run(company="cacao", year=2026, month=5, user_id="admin")
    second = service.run(company="cacao", year=2026, month=5, user_id="admin")

    assert first.status == "voided"
    assert second.id != first.id
    assert second.status == "posted"


def test_service_reverses_prior_period_unrealized_fx_at_next_period_open(app_ctx):
    """The next close reverses prior unrealized FX before remeasuring exposure."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import AccountingPeriod, ExchangeRate, GLEntry, database

    _create_sales_invoice()
    service = ExchangeRevaluationService()
    may_run = service.run(company="cacao", year=2026, month=5, user_id="admin")
    database.session.add(
        AccountingPeriod(
            entity="cacao",
            name="2026-06",
            enabled=True,
            is_closed=False,
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
        )
    )
    database.session.add_all(
        [
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("37"), date=date(2026, 6, 1)),
            ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.91"), date=date(2026, 6, 1)),
        ]
    )
    database.session.commit()

    june_run = service.run(company="cacao", year=2026, month=6, user_id="admin")

    assert may_run.status == "voided"
    assert june_run.status == "posted"
    reversals = database.session.execute(
        database.select(GLEntry).where(GLEntry.exchange_revaluation_run_id == may_run.id, GLEntry.is_reversal.is_(True))
    ).scalars()
    assert reversals
    assert {entry.posting_date for entry in reversals} == {date(2026, 6, 1)}


def test_service_recalculates_partial_balance_revaluation(app_ctx):
    """A repeated run voids the prior adjustment before recalculating it."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService

    _create_sales_invoice(open_amount=Decimal("40.00"))
    service = ExchangeRevaluationService()
    first = service.run(company="cacao", year=2026, month=5, user_id="admin")
    second = service.run(company="cacao", year=2026, month=5, user_id="admin")

    assert first.status == "voided"
    assert second.id != first.id
    assert second.status == "posted"


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


def test_service_rejects_non_positive_historical_closing_rate(app_ctx):
    """A stored zero/negative rate must not become a fictitious FX adjustment."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import (
        ExchangeRevaluationError,
        ExchangeRevaluationService,
    )
    from cacao_accounting.database import ExchangeRate, database

    database.session.execute(
        database.update(ExchangeRate)
        .where(ExchangeRate.origin == "USD", ExchangeRate.destination == "NIO")
        .values(rate=Decimal("0"))
    )
    database.session.commit()

    with pytest.raises(ExchangeRevaluationError, match="positivo y finito"):
        ExchangeRevaluationService()._closing_rate("USD", "NIO", date(2026, 5, 31))


def test_failed_revaluation_rerun_preserves_previous_posted_run(app_ctx):
    """Una reejecución fallida no debe anular la corrida publicada anterior."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationError, ExchangeRevaluationService
    from cacao_accounting.database import ExchangeRate, database

    _create_sales_invoice()
    service = ExchangeRevaluationService()
    previous = service.run(company="cacao", year=2026, month=5, user_id="admin")
    database.session.execute(database.delete(ExchangeRate).where(ExchangeRate.destination == "NIO"))
    database.session.commit()

    with pytest.raises(ExchangeRevaluationError, match="Falta tasa de cierre"):
        service.run(company="cacao", year=2026, month=5, user_id="admin")

    database.session.refresh(previous)
    assert previous.status == "posted"


def test_service_excludes_draft_invoices(app_ctx):
    """Draft documents are not accounting records and cannot be revalued."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import SalesInvoice, database

    database.session.add(
        SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 1),
            customer_id="CUST-DRAFT",
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36"),
            grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
            docstatus=0,
        )
    )
    database.session.commit()

    service = ExchangeRevaluationService()
    run = service.run(company="cacao", year=2026, month=5, user_id="admin")
    second = service.run(company="cacao", year=2026, month=5, user_id="admin")

    assert run.processed_documents_count == 0
    assert run.status == "completed_no_changes"
    assert run.generated_journal is False
    assert second.id != run.id
    assert second.status == "completed_no_changes"


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
    database.session.add(
        GLEntry(
            posting_date=date(2026, 5, 1),
            company="cacao",
            ledger_id=_book("EUR").id,
            account_id=bank_account_id,
            account_code="1005",
            debit=Decimal("9.00"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("10.00"),
            account_currency="USD",
            company_currency="EUR",
            exchange_rate=Decimal("0.90"),
            bank_account_id=bank_account.id,
            voucher_type="payment_entry",
            voucher_id="PAY-1-EUR",
        )
    )
    database.session.commit()

    ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    bank_line = database.session.execute(
        database.select(ExchangeRevaluationItem).filter_by(source_document_type="bank_account", ledger_currency_id="NIO")
    ).scalar_one()
    assert bank_line.open_amount_original == Decimal("10.0000")
    assert bank_line.exchange_difference == Decimal("10.0000")


def test_service_uses_each_ledger_bank_exposure_independently(app_ctx):
    """Una cuenta bancaria revaloriza el saldo original propio de cada libro."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import Accounts, Bank, BankAccount, ExchangeRevaluationItem, GLEntry, database

    bank_account_id = database.session.execute(
        database.select(Accounts.id).filter_by(entity="cacao", code="1005")
    ).scalar_one()
    bank = Bank(name="Banco USD multilibro")
    database.session.add(bank)
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta USD multilibro",
        account_no="USD-ML-1",
        currency="USD",
        gl_account_id=bank_account_id,
    )
    database.session.add(bank_account)
    database.session.flush()
    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 5, 1),
                company="cacao",
                ledger_id=_book("NIO").id,
                account_id=bank_account_id,
                account_code="1005",
                debit=Decimal("360"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("10"),
                account_currency="USD",
                company_currency="NIO",
                exchange_rate=Decimal("36"),
                bank_account_id=bank_account.id,
                voucher_type="payment_entry",
                voucher_id="NIO-1",
            ),
            GLEntry(
                posting_date=date(2026, 5, 1),
                company="cacao",
                ledger_id=_book("EUR").id,
                account_id=bank_account_id,
                account_code="1005",
                debit=Decimal("18"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("20"),
                account_currency="USD",
                company_currency="EUR",
                exchange_rate=Decimal("0.9"),
                bank_account_id=bank_account.id,
                voucher_type="payment_entry",
                voucher_id="EUR-1",
            ),
        ]
    )
    database.session.commit()

    ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    items = (
        database.session.execute(
            database.select(ExchangeRevaluationItem)
            .filter_by(source_document_type="bank_account", source_document_id=bank_account.id)
            .order_by(ExchangeRevaluationItem.ledger_currency_id)
        )
        .scalars()
        .all()
    )
    assert [(item.ledger_currency_id, item.open_amount_original, item.exchange_difference) for item in items] == [
        ("EUR", Decimal("20.0000"), Decimal("0.6000")),
        ("NIO", Decimal("10.0000"), Decimal("10.0000")),
    ]


def test_bank_balance_converts_functional_only_gl_amounts(app_ctx):
    """Bank revaluation falls back to functional GL amounts when needed."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import Accounts, Bank, BankAccount, GLEntry, database

    bank_account_id = database.session.execute(
        database.select(Accounts.id).filter_by(entity="cacao", code="1005")
    ).scalar_one()
    bank = Bank(name="Banco funcional")
    database.session.add(bank)
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta funcional",
        account_no="NIO-BASE-1",
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
            debit=Decimal("720.00"),
            credit=Decimal("0"),
            debit_in_account_currency=None,
            credit_in_account_currency=None,
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36.00"),
            bank_account_id=bank_account.id,
            voucher_type="payment_entry",
            voucher_id="PAY-BASE-ONLY",
        )
    )
    database.session.commit()

    balance = ExchangeRevaluationService()._bank_original_balance(bank_account, date(2026, 5, 31), _book("NIO").id)

    assert balance == Decimal("20.0000")


def test_bank_functional_only_balance_divides_inverse_exchange_pair(app_ctx):
    """A functional-only NIO amount must reach the USD account divided by the quoted pair.

    Regresión del issue #749: con la única tasa configurada USD->NIO
    (36.6243), el saldo en moneda de la cuenta debe ser 36,624.30 / 36.6243
    = 1,000.00 USD y no 36,624.30 * 36.6243.
    """
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import Accounts, Bank, BankAccount, ExchangeRevaluationItem, ExchangeRate, GLEntry, database

    database.session.execute(
        database.update(ExchangeRate)
        .where(ExchangeRate.origin == "USD", ExchangeRate.destination == "NIO", ExchangeRate.date == date(2026, 5, 1))
        .values(rate=Decimal("36.6243"))
    )
    bank_account_id = database.session.execute(
        database.select(Accounts.id).filter_by(entity="cacao", code="1005")
    ).scalar_one()
    bank = Bank(name="Banco par inverso")
    database.session.add(bank)
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta par inverso",
        account_no="USD-INVERSE-1",
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
            debit=Decimal("36624.30"),
            credit=Decimal("0"),
            debit_in_account_currency=None,
            credit_in_account_currency=None,
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36.6243"),
            bank_account_id=bank_account.id,
            voucher_type="payment_entry",
            voucher_id="PAY-INVERSE-1",
        )
    )
    database.session.commit()

    balance = ExchangeRevaluationService()._bank_original_balance(bank_account, date(2026, 5, 31), _book("NIO").id)

    assert balance == Decimal("1000.0000")

    run = ExchangeRevaluationService().run(company="cacao", year=2026, month=5, user_id="admin")

    assert run.status == "posted"
    assert run.total_gain == Decimal("375.7000")
    bank_line = database.session.execute(
        database.select(ExchangeRevaluationItem).filter_by(source_document_type="bank_account", ledger_currency_id="NIO")
    ).scalar_one()
    assert bank_line.open_amount_original == Decimal("1000.0000")
    assert bank_line.revalued_balance == Decimal("37000.0000")
    assert bank_line.exchange_difference == Decimal("375.7000")


def test_revaluation_uses_credit_note_nature_for_open_ar_and_ap(app_ctx):
    """Open credit notes must revalue with the opposite subledger nature."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import PurchaseInvoice, SalesInvoice, database

    database.session.add_all(
        [
            SalesInvoice(
                company="cacao",
                posting_date=date(2026, 5, 1),
                customer_id="CUST-CREDIT-NOTE",
                transaction_currency="USD",
                grand_total=Decimal("10"),
                outstanding_amount=Decimal("10"),
                is_return=True,
                docstatus=1,
            ),
            PurchaseInvoice(
                company="cacao",
                posting_date=date(2026, 5, 1),
                supplier_id="SUPP-CREDIT-NOTE",
                transaction_currency="USD",
                grand_total=Decimal("10"),
                outstanding_amount=Decimal("10"),
                is_return=True,
                docstatus=1,
            ),
        ]
    )
    database.session.commit()

    service = ExchangeRevaluationService()
    ar = service._open_sales_invoices("cacao", date(2026, 5, 31))
    ap = service._open_purchase_invoices("cacao", date(2026, 5, 31))

    assert ar[-1].normal_balance == "credit"
    assert ap[-1].normal_balance == "debit"


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
