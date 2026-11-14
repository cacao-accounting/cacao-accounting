"""Business regressions for shared AR/AP open-item balances."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event, current_thread
from uuid import uuid4

import pytest
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session


from cacao_accounting import create_app
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import arap_ledger_service
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.arap_allocation import list_cached_open_items, list_open_items
from cacao_accounting.contabilidad.arap_ledger_service import post_payment_application_ar_ap
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    cancel_submitted_journal,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    submit_journal,
)
from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    ARAPOpenItem,
    AccountingPeriod,
    Accounts,
    Book,
    CompanyParty,
    ComprobanteContable,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    Modules,
    Party,
    PaymentEntry,
    PurchaseInvoice,
    SalesInvoice,
    User,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.database


def _snapshot_arap_movements(movements, book_entries_by_movement=None):
    """Capture immutable subledger evidence and per-book valuations by row ID."""
    return {
        str(movement.id): (
            movement.company,
            movement.ledger_type,
            movement.party_type,
            movement.party_id,
            movement.document_type,
            movement.document_id,
            movement.posting_date,
            movement.event_type,
            movement.currency,
            movement.document_amount,
            movement.economic_line_id,
            movement.reference_type,
            movement.reference_id,
            movement.voucher_type,
            movement.voucher_id,
            movement.is_reversal,
            movement.reversal_of,
            tuple(
                sorted(
                    (
                        str(book_entry.id),
                        str(book_entry.ledger_entry_id),
                        str(book_entry.ledger_id),
                        book_entry.document_amount,
                        book_entry.book_amount,
                        book_entry.exchange_rate,
                        book_entry.debit,
                        book_entry.credit,
                        book_entry.account_id,
                        book_entry.gl_entry_id,
                        book_entry.is_reversal,
                        book_entry.reversal_of,
                    )
                    for book_entry in (
                        book_entries_by_movement[str(movement.id)]
                        if book_entries_by_movement is not None
                        else movement.book_entries
                    )
                )
            ),
        )
        for movement in movements
    }


def _assert_append_only_arap_reversals(originals, reversals, book_entries_by_movement=None):
    """Require one linked, amount-inverting reversal for each original ledger row."""
    originals_by_id = {str(movement.id): movement for movement in originals}
    assert len(reversals) == len(originals_by_id)
    assert {str(reversal.reversal_of) for reversal in reversals} == set(originals_by_id)

    for reversal in reversals:
        original = originals_by_id[str(reversal.reversal_of)]
        assert reversal.is_reversal is True
        assert reversal.event_type == "cancellation"
        assert reversal.document_amount == -original.document_amount
        original_book_entries = (
            book_entries_by_movement[str(original.id)] if book_entries_by_movement is not None else original.book_entries
        )
        reversal_book_entries = (
            book_entries_by_movement[str(reversal.id)] if book_entries_by_movement is not None else reversal.book_entries
        )
        original_books = {str(entry.id): entry for entry in original_book_entries}
        reversal_books = {str(entry.reversal_of): entry for entry in reversal_book_entries}
        assert set(reversal_books) == set(original_books)
        for original_book_id, original_book in original_books.items():
            reversal_book = reversal_books[original_book_id]
            assert reversal_book.is_reversal is True
            assert reversal_book.book_amount == -original_book.book_amount
            assert (reversal_book.debit, reversal_book.credit) == (original_book.credit, original_book.debit)


@pytest.fixture
def arap_application(tmp_path):
    """Create an isolated business database or use an opt-in external engine."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'arap-application.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        suffix = uuid4().hex[:7].upper()
        company_code = f"A{suffix}"
        currency_code = f"C{suffix}"
        book_code = f"B{suffix}"
        today = date.today()
        currency = Currency(code=currency_code, name="Moneda AR/AP", decimals=2, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa de cartera {suffix}",
            company_name=f"Empresa de cartera {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency_code,
            enabled=True,
            status="default",
        )
        customer = Party(code=f"CLI{suffix}", name="Cliente de prueba", is_customer=True, is_active=True)
        supplier = Party(code=f"PRO{suffix}", name="Proveedor de prueba", is_supplier=True, is_active=True)
        book = Book(
            code=book_code,
            name="Libro financiero de cartera",
            entity=company_code,
            currency=currency_code,
            status="activo",
            is_primary=True,
            default=True,
        )
        database.session.add_all([currency, company, customer, supplier])
        database.session.flush()
        database.session.add(book)
        accounting_module = database.session.execute(
            select(Modules).where(Modules.module == "accounting")
        ).scalar_one_or_none()
        if accounting_module is None:
            database.session.add(Modules(module="accounting", enabled=True, default=True))
        database.session.flush()

        fiscal_year = FiscalYear(
            entity=company_code,
            name=f"FY-{suffix}",
            year_start_date=date(today.year, 1, 1),
            year_end_date=date(today.year, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        period = AccountingPeriod(
            entity=company_code,
            fiscal_year_id=fiscal_year.id,
            name=f"Período {suffix}",
            status="open",
            enabled=True,
            is_closed=False,
            start=date(today.year, 1, 1),
            end=date(today.year, 12, 31),
        )
        receivable = Accounts(
            entity=company_code,
            code=f"AR{suffix}",
            name="Cuentas por cobrar",
            classification="asset",
            account_type="receivable",
            active=True,
            enabled=True,
            currency=currency_code,
        )
        payable = Accounts(
            entity=company_code,
            code=f"AP{suffix}",
            name="Cuentas por pagar",
            classification="liability",
            account_type="payable",
            active=True,
            enabled=True,
            currency=currency_code,
        )
        sales = Accounts(
            entity=company_code,
            code=f"REV{suffix}",
            name="Ventas",
            classification="revenue",
            account_type="income",
            active=True,
            enabled=True,
            currency=currency_code,
        )
        returns = Accounts(
            entity=company_code,
            code=f"RET{suffix}",
            name="Devoluciones sobre ventas",
            classification="expense",
            account_type="expense",
            active=True,
            enabled=True,
            currency=currency_code,
        )
        bank = Accounts(
            entity=company_code,
            code=f"BNK{suffix}",
            name="Banco de pruebas",
            classification="asset",
            account_type="bank",
            active=True,
            enabled=True,
            currency=currency_code,
        )
        cost_center = CostCenter(
            entity=company_code,
            code=f"CC{suffix}",
            name="Devoluciones a clientes",
            active=True,
            enabled=True,
        )
        user = User(
            user=f"admin-{suffix.lower()}",
            name="Administrador de pruebas",
            password=b"unused-test-password",
            classification="admin",
            active=True,
            company=company_code,
        )
        database.session.add_all([fiscal_year, period, receivable, payable, sales, returns, bank, cost_center, user])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company=company_code, party_id=customer.id, is_active=True),
                CompanyParty(company=company_code, party_id=supplier.id, is_active=True),
            ]
        )

        database.session.commit()

        seed = {
            "company": company_code,
            "currency": currency_code,
            "book": book_code,
            "book_id": book.id,
            "customer_id": customer.id,
            "supplier_id": supplier.id,
            "receivable": receivable.code,
            "receivable_id": receivable.id,
            "payable": payable.code,
            "payable_id": payable.id,
            "sales": sales.code,
            "sales_id": sales.id,
            "bank_id": bank.id,
            "bank": bank.code,
            "returns": returns.code,
            "cost_center": cost_center.code,
            "user_id": user.id,
            "today": today,
        }
        database.session.remove()

    yield application, seed

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _seed_payment_application_business_data(application, seed, party_type):
    """Create two open invoices and one received or paid balance for allocation."""
    with application.app_context():
        suffix = seed["company"][1:]
        is_customer = party_type == "customer"
        document_type = "sales_invoice" if is_customer else "purchase_invoice"
        ledger_type = "AR" if is_customer else "AP"
        account_id = seed["receivable_id"] if is_customer else seed["payable_id"]
        account_code = seed["receivable"] if is_customer else seed["payable"]
        invoice_party = (
            {"customer_id": seed["customer_id"], "customer_name": "Cliente de prueba"}
            if is_customer
            else {"supplier_id": seed["supplier_id"], "supplier_name": "Proveedor de prueba"}
        )
        invoice_model = SalesInvoice if is_customer else PurchaseInvoice
        invoices = [
            invoice_model(
                company=seed["company"],
                posting_date=seed["today"],
                docstatus=1,
                document_no=f"INV-{suffix}-{index}",
                transaction_currency=seed["currency"],
                base_currency=seed["currency"],
                exchange_rate=Decimal("1"),
                total=Decimal("60"),
                grand_total=Decimal("60"),
                base_grand_total=Decimal("60"),
                outstanding_amount=Decimal("60"),
                base_outstanding_amount=Decimal("60"),
                **invoice_party,
            )
            for index in (1, 2)
        ]
        payment = PaymentEntry(
            company=seed["company"],
            posting_date=seed["today"],
            docstatus=1,
            document_no=f"PAY-{suffix}",
            payment_type="receive" if is_customer else "pay",
            party_type=party_type,
            party_id=seed["customer_id"] if is_customer else seed["supplier_id"],
            party_name="Cliente de prueba" if is_customer else "Proveedor de prueba",
            currency=seed["currency"],
            exchange_rate=Decimal("1"),
            received_amount=Decimal("100") if is_customer else Decimal("0"),
            base_received_amount=Decimal("100") if is_customer else Decimal("0"),
            paid_amount=Decimal("0") if is_customer else Decimal("100"),
            base_paid_amount=Decimal("0") if is_customer else Decimal("100"),
            unallocated_amount=Decimal("100"),
        )
        database.session.add_all([*invoices, payment])
        database.session.commit()

        for open_document_type, document, amount, direction in [
            (document_type, invoices[0], Decimal("60"), "debit"),
            (document_type, invoices[1], Decimal("60"), "debit"),
            ("payment_entry", payment, Decimal("-100"), "credit"),
        ]:
            movement = ARAPLedgerEntry(
                company=seed["company"],
                ledger_type=ledger_type,
                party_type=party_type,
                party_id=seed["customer_id"] if is_customer else seed["supplier_id"],
                document_type=open_document_type,
                document_id=document.id,
                document_no=document.document_no,
                posting_date=seed["today"],
                event_type="opening",
                currency=seed["currency"],
                document_amount=amount,
                economic_line_id=document.id,
                voucher_type=open_document_type,
                voucher_id=document.id,
            )
            database.session.add(movement)
            database.session.flush()
            database.session.add(
                ARAPOpenItem(
                    company=seed["company"],
                    ledger_type=ledger_type,
                    party_type=party_type,
                    party_id=seed["customer_id"] if is_customer else seed["supplier_id"],
                    account_id=account_id,
                    document_type=open_document_type,
                    document_id=document.id,
                    document_no=document.document_no,
                    economic_line_id=document.id,
                    posting_date=seed["today"],
                    currency=seed["currency"],
                    original_amount=abs(amount),
                    unallocated_amount=abs(amount),
                    direction=direction,
                    status="open",
                    source_voucher_type=open_document_type,
                    source_voucher_id=document.id,
                )
            )
            database.session.add(
                ARAPLedgerBookEntry(
                    ledger_entry_id=movement.id,
                    ledger_id=seed["book_id"],
                    posting_date=seed["today"],
                    document_currency=seed["currency"],
                    book_currency=seed["currency"],
                    document_amount=amount,
                    book_amount=amount,
                    exchange_rate=Decimal("1"),
                    debit=amount if amount > 0 else Decimal("0"),
                    credit=-amount if amount < 0 else Decimal("0"),
                    account_id=account_id,
                    account_code=account_code,
                )
            )
        database.session.commit()
        return {
            **seed,
            "invoices": [invoice.id for invoice in invoices],
            "payment_id": payment.id,
            "document_type": document_type,
        }


def _seed_payment_gl_evidence(application, seed):
    """Persist balanced invoice/payment GL rows matching the seeded AR/AP books."""
    with application.app_context():
        entries = []
        for invoice_id in seed["invoices"]:
            invoice = database.session.get(SalesInvoice, invoice_id)
            assert invoice is not None
            entries.extend(
                [
                    GLEntry(
                        company=seed["company"],
                        ledger_id=seed["book_id"],
                        account_id=seed["receivable_id"],
                        account_code=seed["receivable"],
                        debit=Decimal("60"),
                        credit=Decimal("0"),
                        debit_in_account_currency=Decimal("60"),
                        credit_in_account_currency=Decimal("0"),
                        account_currency=seed["currency"],
                        company_currency=seed["currency"],
                        exchange_rate=Decimal("1"),
                        party_type="customer",
                        party_id=seed["customer_id"],
                        posting_date=seed["today"],
                        voucher_type="sales_invoice",
                        voucher_id=invoice_id,
                        document_no=invoice.document_no,
                    ),
                    GLEntry(
                        company=seed["company"],
                        ledger_id=seed["book_id"],
                        account_id=seed["sales_id"],
                        account_code=seed["sales"],
                        debit=Decimal("0"),
                        credit=Decimal("60"),
                        debit_in_account_currency=Decimal("0"),
                        credit_in_account_currency=Decimal("60"),
                        account_currency=seed["currency"],
                        company_currency=seed["currency"],
                        exchange_rate=Decimal("1"),
                        posting_date=seed["today"],
                        voucher_type="sales_invoice",
                        voucher_id=invoice_id,
                        document_no=invoice.document_no,
                    ),
                ]
            )

        payment = database.session.get(PaymentEntry, seed["payment_id"])
        assert payment is not None
        entries.extend(
            [
                GLEntry(
                    company=seed["company"],
                    ledger_id=seed["book_id"],
                    account_id=seed["bank_id"],
                    account_code=seed["bank"],
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    debit_in_account_currency=Decimal("100"),
                    credit_in_account_currency=Decimal("0"),
                    account_currency=seed["currency"],
                    company_currency=seed["currency"],
                    exchange_rate=Decimal("1"),
                    posting_date=seed["today"],
                    voucher_type="payment_entry",
                    voucher_id=str(payment.id),
                    document_no=payment.document_no,
                ),
                GLEntry(
                    company=seed["company"],
                    ledger_id=seed["book_id"],
                    account_id=seed["receivable_id"],
                    account_code=seed["receivable"],
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    debit_in_account_currency=Decimal("0"),
                    credit_in_account_currency=Decimal("100"),
                    account_currency=seed["currency"],
                    company_currency=seed["currency"],
                    exchange_rate=Decimal("1"),
                    party_type="customer",
                    party_id=seed["customer_id"],
                    posting_date=seed["today"],
                    voucher_type="payment_entry",
                    voucher_id=str(payment.id),
                    document_no=payment.document_no,
                ),
            ]
        )
        database.session.add_all(entries)
        database.session.commit()
        return [entry.id for entry in entries if entry.voucher_type == "payment_entry"]


def _seed_opening_journal(application, seed, books: list[str] | None = None, party_type: str = "customer") -> str:
    """Post a customer receivable or supplier payable through the manual journal flow."""
    receivable = party_type == "customer"
    account = seed["receivable"] if receivable else seed["payable"]
    party_id = seed["customer_id"] if receivable else seed["supplier_id"]
    party_account_line = {
        "account": account,
        "debit": "100" if receivable else "0",
        "credit": "0" if receivable else "100",
        "currency": seed["currency"],
        "party_type": party_type,
        "party": party_id,
    }
    offset_line = {
        "account": seed["sales"] if receivable else seed["bank"],
        "debit": "0" if receivable else "100",
        "credit": "100" if receivable else "0",
        "currency": seed["currency"],
    }
    payload = {
        "company": seed["company"],
        "posting_date": seed["today"].isoformat(),
        "books": books or [seed["book"]],
        "transaction_currency": seed["currency"],
        "base_currency": seed["currency"],
        "exchange_rate": "1",
        "reference": "Saldo inicial de factura de cliente",
        "lines": [party_account_line, offset_line],
    }
    with application.app_context():
        journal = create_journal_draft(payload, user_id=seed["user_id"])
        submit_journal(journal.id, user_id=seed["user_id"])
        return journal.id


def _credit_adjustment_payload(seed, target_open_item_id: str, amount: str, reference: str) -> dict:
    """Build a customer credit adjustment linked to an open receivable."""
    return {
        "company": seed["company"],
        "posting_date": seed["today"].isoformat(),
        "books": [seed["book"]],
        "transaction_currency": seed["currency"],
        "base_currency": seed["currency"],
        "exchange_rate": "1",
        "reference": reference,
        "lines": [
            {
                "account": seed["returns"],
                "debit": amount,
                "credit": "0",
                "cost_center": seed["cost_center"],
                "currency": seed["currency"],
            },
            {
                "account": seed["receivable"],
                "debit": "0",
                "credit": amount,
                "currency": seed["currency"],
                "party_type": "customer",
                "party": seed["customer_id"],
                "reference_type": "journal_entry",
                "reference_open_item_id": target_open_item_id,
            },
        ],
    }


def _multi_credit_adjustment_payload(seed, target_open_item_ids: list[str], reference: str) -> dict:
    """Build one real credit journal that applies to two receivable documents."""
    lines = [
        {
            "account": seed["receivable"],
            "debit": "0",
            "credit": "70",
            "currency": seed["currency"],
            "party_type": "customer",
            "party": seed["customer_id"],
            "reference_type": "journal_entry",
            "reference_open_item_id": target_id,
        }
        for target_id in target_open_item_ids
    ]
    return {
        "company": seed["company"],
        "posting_date": seed["today"].isoformat(),
        "books": [seed["book"]],
        "transaction_currency": seed["currency"],
        "base_currency": seed["currency"],
        "exchange_rate": "1",
        "reference": reference,
        "lines": [
            {
                "account": seed["returns"],
                "debit": "140",
                "credit": "0",
                "cost_center": seed["cost_center"],
                "currency": seed["currency"],
            },
            *lines,
        ],
    }


def test_posted_customer_balance_reconciles_and_appears_in_journal_selector(arap_application):
    """A posted customer balance is visible and consistent in both accounting APIs."""
    application, seed = arap_application
    journal_id = _seed_opening_journal(application, seed)
    with application.app_context():
        journal = database.session.get(ComprobanteContable, journal_id)
        assert journal is not None and journal.document_no
        document_number = journal.document_no

    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = seed["user_id"]
        session["_fresh"] = True

    policy_response = client.post(
        "/api/accounting/arap-reconciliation",
        json={"company": seed["company"], "mode": "strict", "tolerance": "0.01", "enabled": True},
    )
    assert policy_response.status_code == 200, policy_response.get_data(as_text=True)
    saved_policy = policy_response.get_json()
    assert saved_policy["company"] == seed["company"]
    assert saved_policy["mode"] == "strict"
    assert Decimal(saved_policy["tolerance"]) == Decimal("0.01")
    assert saved_policy["enabled"] is True

    reconciliation = client.get(
        "/api/accounting/arap-reconciliation",
        query_string={"company": seed["company"], "as_of_date": seed["today"].isoformat()},
    )
    assert reconciliation.status_code == 200, reconciliation.get_data(as_text=True)
    reconciliation_body = reconciliation.get_json()
    assert reconciliation_body["balanced"] is True
    customer_line = next(
        line
        for line in reconciliation_body["lines"]
        if line["party_type"] == "customer" and line["party_id"] == seed["customer_id"]
    )
    assert customer_line["subledger_amount"] == "100.0000"
    assert customer_line["gl_amount"] == "100.0000"
    assert customer_line["difference"] == "0.0000"

    open_items = client.get(
        "/api/line-import/open-items",
        query_string={
            "company": seed["company"],
            "party_type": "customer",
            "party": seed["customer_id"],
            "reference_type": "journal_entry",
            "q": document_number,
        },
    )
    assert open_items.status_code == 200, open_items.get_data(as_text=True)
    results = open_items.get_json()["results"]
    assert len(results) == 1
    assert results[0]["document_id"] == journal_id
    assert results[0]["label"] == document_number
    assert results[0]["outstanding"] == "100.0000"


@pytest.mark.parametrize("party_type", ["customer", "supplier"])
def test_payment_applications_cannot_consume_shared_balance_twice(arap_application, monkeypatch, party_type):
    """Two invoices cannot concurrently consume more than one customer's or supplier's payment."""
    application, seed = arap_application
    seed = _seed_payment_application_business_data(application, seed, party_type)
    with application.app_context():
        engine = database.engine
    if engine.dialect.name != "sqlite":
        header_barrier = Barrier(2)
        lock_headers = arap_ledger_service._lock_payment_application_headers

        def synchronize_before_header_locks(payment, document):
            header_barrier.wait(timeout=10)
            return lock_headers(payment, document)

        monkeypatch.setattr(arap_ledger_service, "_lock_payment_application_headers", synchronize_before_header_locks)

    def apply_to_invoice(invoice_id: str):
        with application.app_context():
            payment = database.session.get(PaymentEntry, seed["payment_id"])
            invoice_model = SalesInvoice if party_type == "customer" else PurchaseInvoice
            invoice = database.session.get(invoice_model, invoice_id)
            assert payment is not None and invoice is not None
            try:
                post_payment_application_ar_ap(
                    payment,
                    invoice,
                    document_amount=Decimal("60"),
                    payment_amount=Decimal("60"),
                    allocation_date=seed["today"],
                )
                database.session.commit()
                return "applied"
            except ValueError:
                database.session.rollback()
                return "rejected"
            except Exception as exc:
                database.session.rollback()
                return f"error:{type(exc).__name__}:{exc}"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(apply_to_invoice, seed["invoices"]))

    assert sorted(results) == ["applied", "rejected"]

    with application.app_context():
        payment_cache = database.session.execute(
            database.select(ARAPOpenItem).where(
                ARAPOpenItem.document_type == "payment_entry",
                ARAPOpenItem.document_id == seed["payment_id"],
            )
        ).scalar_one()
        assert payment_cache.unallocated_amount == Decimal("40.0000")
        payment_balance = ARAPLedgerEntry.document_balance("payment_entry", seed["payment_id"])
        assert payment_balance == Decimal("-40.0000")
        invoice_balances = [
            ARAPLedgerEntry.document_balance(seed["document_type"], invoice_id) for invoice_id in seed["invoices"]
        ]
        assert sorted(invoice_balances) == [Decimal("0.0000"), Decimal("60.0000")]


def test_concurrent_manual_credits_never_overapply_one_receivable(arap_application, monkeypatch):
    """Concurrent journals lock two referenced receivables in a stable order."""
    application, seed = arap_application
    opening_journal_ids = [_seed_opening_journal(application, seed) for _ in range(2)]

    with application.app_context():
        targets = [
            database.session.execute(
                select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=opening_id)
            ).scalar_one()
            for opening_id in opening_journal_ids
        ]
        target_open_item_ids = [target.id for target in targets]
        journals = [
            create_journal_draft(
                _multi_credit_adjustment_payload(
                    seed,
                    target_open_item_ids if index == 1 else list(reversed(target_open_item_ids)),
                    f"Crédito cliente {index}",
                ),
                user_id=seed["user_id"],
            )
            for index in (1, 2)
        ]
        journal_ids = [journal.id for journal in journals]
        database.session.remove()

    submit_barrier = Barrier(2)
    lock_references = arap_ledger_service.lock_journal_open_item_references

    def synchronize_before_reference_locks(journal):
        submit_barrier.wait(timeout=10)
        lock_references(journal)

    monkeypatch.setattr(
        arap_ledger_service,
        "lock_journal_open_item_references",
        synchronize_before_reference_locks,
    )

    def submit(journal_id: str):
        with application.app_context():
            try:
                submit_journal(journal_id, user_id=seed["user_id"])
                return "submitted"
            except (JournalValidationError, ValueError):
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, journal_ids))
    assert results == ["submitted", "submitted"]

    with application.app_context():
        target_balances = [ARAPLedgerEntry.document_balance("journal_entry", opening_id) for opening_id in opening_journal_ids]
        assert target_balances == [Decimal("0.0000"), Decimal("0.0000")]
        target_caches = [database.session.get(ARAPOpenItem, target_id) for target_id in target_open_item_ids]
        statuses = [database.session.get(ComprobanteContable, journal_id).status for journal_id in journal_ids]
        assert statuses == ["submitted", "submitted"]
        assert all(target is not None and target.unallocated_amount == Decimal("0.0000") for target in target_caches)
        residual_credits = (
            database.session.execute(
                select(ARAPOpenItem).where(
                    ARAPOpenItem.document_type == "journal_entry",
                    ARAPOpenItem.document_id.in_(journal_ids),
                    ARAPOpenItem.direction == "credit",
                    ARAPOpenItem.unallocated_amount > 0,
                )
            )
            .scalars()
            .all()
        )
        assert len(residual_credits) == 2
        assert all(item.unallocated_amount == Decimal("40.0000") for item in residual_credits)

        ar_balance = database.session.execute(
            select(func.coalesce(func.sum(ARAPLedgerEntry.document_amount), 0)).where(
                ARAPLedgerEntry.company == seed["company"],
                ARAPLedgerEntry.party_id == seed["customer_id"],
                ARAPLedgerEntry.ledger_type == "AR",
            )
        ).scalar_one()
        assert Decimal(str(ar_balance)) == Decimal("-80.0000")


@pytest.mark.parametrize(
    ("party_type", "allocation_amount"), [("customer", "60"), ("customer", "100"), ("supplier", "60"), ("supplier", "100")]
)
def test_manual_reversal_restores_closed_or_partial_arap_reference(arap_application, party_type, allocation_amount):
    """A later-period reversal restores partial and closed customer or supplier balances."""
    application, seed = arap_application

    with application.app_context():
        second_book = Book(
            code=f"B2{uuid4().hex[:7].upper()}",
            name="Libro adicional de cartera",
            entity=seed["company"],
            currency=seed["currency"],
            status="activo",
            is_primary=False,
            default=False,
        )
        database.session.add(second_book)
        database.session.commit()
        book_codes = [seed["book"], second_book.code]

    opening_journal_id = _seed_opening_journal(application, seed, books=book_codes, party_type=party_type)

    with application.app_context():
        target = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=opening_journal_id)
        ).scalar_one()
        if party_type == "customer":
            allocation_payload = _credit_adjustment_payload(
                seed, str(target.id), allocation_amount, "Ajuste AP/AR para reversar"
            )
        else:
            allocation_payload = {
                "company": seed["company"],
                "posting_date": seed["today"].isoformat(),
                "books": book_codes,
                "transaction_currency": seed["currency"],
                "base_currency": seed["currency"],
                "exchange_rate": "1",
                "reference": "Ajuste AP/AR para reversar",
                "lines": [
                    {"account": seed["bank"], "debit": "0", "credit": allocation_amount, "currency": seed["currency"]},
                    {
                        "account": seed["payable"],
                        "debit": allocation_amount,
                        "credit": "0",
                        "currency": seed["currency"],
                        "party_type": "supplier",
                        "party": seed["supplier_id"],
                        "reference_type": "journal_entry",
                        "reference_open_item_id": str(target.id),
                    },
                ],
            }
        allocation_payload["books"] = book_codes
        allocation = create_journal_draft(
            allocation_payload,
            user_id=seed["user_id"],
        )
        submit_journal(allocation.id, user_id=seed["user_id"])
        source_id = str(allocation.id)
        source_movements = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_type == "journal_entry",
                    ARAPLedgerEntry.voucher_id == source_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        related_movements = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.reference_type == "journal_entry",
                    ARAPLedgerEntry.reference_id == source_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        source_movements_by_id = {str(row.id): row for row in [*source_movements, *related_movements]}
        source_snapshot = _snapshot_arap_movements(list(source_movements_by_id.values()))

        next_year = seed["today"].year + 1
        fiscal_year = FiscalYear(
            entity=seed["company"],
            name=f"FY-REV-{uuid4().hex[:8]}",
            year_start_date=date(next_year, 1, 1),
            year_end_date=date(next_year, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(fiscal_year)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity=seed["company"],
                fiscal_year_id=fiscal_year.id,
                name=f"Período de reversión {uuid4().hex[:8]}",
                status="open",
                enabled=True,
                is_closed=False,
                start=date(next_year, 1, 1),
                end=date(next_year, 12, 31),
            )
        )
        database.session.commit()

        reversal = duplicate_journal_as_reversal_draft(
            source_id,
            user_id=seed["user_id"],
            reversal_date_raw=date(next_year, 1, 15),
            reason="Revertir aplicación contra saldo AP/AR",
        )
        reversal_id = str(reversal.id)
        submit_journal(reversal_id, user_id=seed["user_id"])

        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_type == "journal_entry",
                    ARAPLedgerEntry.voucher_id == source_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        target_movements = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.reference_type == "journal_entry",
                    ARAPLedgerEntry.reference_id == source_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        originals_by_id = {str(row.id): row for row in [*originals, *target_movements]}
        reversals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_id == reversal_id,
                )
            )
            .scalars()
            .all()
        )
        originals = list(originals_by_id.values())
        reversed_by_id = {str(row.reversal_of): row for row in reversals}
        original_book_entries = (
            database.session.execute(
                select(ARAPLedgerBookEntry).where(ARAPLedgerBookEntry.ledger_entry_id.in_(originals_by_id))
            )
            .scalars()
            .all()
        )
        reversal_book_entries = (
            database.session.execute(
                select(ARAPLedgerBookEntry).where(ARAPLedgerBookEntry.ledger_entry_id.in_([row.id for row in reversals]))
            )
            .scalars()
            .all()
        )
        original_books_by_id = {(str(row.id), str(row.ledger_id)): row for row in original_book_entries}
        reversal_books_by_original = {(str(row.reversal_of), str(row.ledger_id)): row for row in reversal_book_entries}
        restored_target = database.session.get(ARAPOpenItem, target.id)
        source_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=source_id)
        ).scalar_one()

        assert len(reversals) == len(originals)
        assert set(reversed_by_id) == {str(row.id) for row in originals}
        assert all(reversed_by_id[str(row.id)].document_amount == -row.document_amount for row in originals)
        assert set(reversal_books_by_original) == set(original_books_by_id)
        assert {ledger_id for _entry_id, ledger_id in original_books_by_id} == {
            str(book_id) for book_id in database.session.execute(select(Book.id).where(Book.code.in_(book_codes))).scalars()
        }
        for original_key, original_book in original_books_by_id.items():
            reversal_book = reversal_books_by_original[original_key]
            assert reversal_book.book_amount == -original_book.book_amount
            assert reversal_book.exchange_rate == original_book.exchange_rate
            assert (reversal_book.debit, reversal_book.credit) == (original_book.credit, original_book.debit)
        assert restored_target is not None and restored_target.unallocated_amount == Decimal("100.0000")
        assert source_cache.unallocated_amount == Decimal("0.0000")
        assert ARAPLedgerEntry.document_balance("journal_entry", opening_journal_id) == Decimal("100.0000")
        assert ARAPLedgerEntry.document_balance("journal_entry", source_id) == Decimal("0.0000")
        reloaded_originals = (
            database.session.execute(select(ARAPLedgerEntry).where(ARAPLedgerEntry.id.in_(source_movements_by_id)))
            .scalars()
            .all()
        )
        assert _snapshot_arap_movements(reloaded_originals) == source_snapshot


def test_cancellation_waits_for_manual_allocation_and_reverses_its_movement(arap_application, monkeypatch):
    """Cancellation sees a concurrent allocation after waiting on its source journal."""
    application, seed = arap_application
    opening_journal_id = _seed_opening_journal(application, seed)

    with application.app_context():
        target = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=opening_journal_id)
        ).scalar_one()
        allocation = create_journal_draft(
            _credit_adjustment_payload(seed, target.id, "70", "Crédito contra saldo inicial"),
            user_id=seed["user_id"],
        )
        allocation_id = allocation.id
        database.session.commit()

    reference_locked = Event()
    release_submit = Event()
    cancellation_lock_attempted = Event()
    original_reference_lock = arap_ledger_service.lock_journal_open_item_references
    original_sqlite_writer_reservation = arap_ledger_service._reserve_sqlite_open_item_writer
    original_document_lock = posting_service._lock_document_for_transition
    cancellation_thread_name = None

    def pause_after_reference_lock(journal):
        original_reference_lock(journal)
        if journal.id == allocation_id:
            reference_locked.set()
            if not release_submit.wait(timeout=10):
                raise TimeoutError("No se liberó el submit para completar la carrera de anulación.")

    def signal_cancellation_lock(document):
        if document.id == opening_journal_id:
            cancellation_lock_attempted.set()
        return original_document_lock(document)

    def signal_sqlite_writer_reservation():
        if current_thread().name == cancellation_thread_name and database.engine.dialect.name == "sqlite":
            cancellation_lock_attempted.set()
        original_sqlite_writer_reservation()

    monkeypatch.setattr(arap_ledger_service, "lock_journal_open_item_references", pause_after_reference_lock)
    monkeypatch.setattr(
        arap_ledger_service,
        "_reserve_sqlite_open_item_writer",
        signal_sqlite_writer_reservation,
    )
    monkeypatch.setattr(posting_service, "_lock_document_for_transition", signal_cancellation_lock)

    def submit_allocation():
        with application.app_context():
            try:
                submit_journal(allocation_id, user_id=seed["user_id"])
                return "submitted"
            finally:
                database.session.remove()

    def cancel_opening():
        nonlocal cancellation_thread_name
        cancellation_thread_name = current_thread().name
        with application.app_context():
            try:
                cancel_submitted_journal(
                    opening_journal_id,
                    user_id=seed["user_id"],
                    reason="Corrección de saldo inicial",
                    cancellation_date=seed["today"],
                )
                return "cancelled"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        submit_future = executor.submit(submit_allocation)
        assert reference_locked.wait(timeout=10)
        cancel_future = executor.submit(cancel_opening)
        try:
            assert cancellation_lock_attempted.wait(timeout=10)
        finally:
            release_submit.set()
        assert submit_future.result(timeout=20) == "submitted"
        assert cancel_future.result(timeout=20) == "cancelled"

    with application.app_context():
        journal = database.session.get(ComprobanteContable, opening_journal_id)
        cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=opening_journal_id)
        ).scalar_one()
        original_entries = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.document_type == "journal_entry",
                    ARAPLedgerEntry.document_id == opening_journal_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        reversals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(ARAPLedgerEntry.reversal_of.in_([row.id for row in original_entries]))
            )
            .scalars()
            .all()
        )
        cancellation_movements = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_id == opening_journal_id,
                    ARAPLedgerEntry.is_reversal.is_(True),
                )
            )
            .scalars()
            .all()
        )
        allocation_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=allocation_id)
        ).scalar_one()
        assert journal is not None and journal.status == "cancelled"
        assert len(original_entries) == 2
        assert len(reversals) == 2
        assert len(cancellation_movements) == 3
        assert ARAPLedgerEntry.document_balance("journal_entry", opening_journal_id) == Decimal("0.0000")
        assert cache.unallocated_amount == Decimal("0.0000")
        assert cache.status == "closed"
        assert ARAPLedgerEntry.document_balance("journal_entry", allocation_id) == Decimal("-70.0000")
        assert allocation_cache.unallocated_amount == Decimal("70.0000")


def test_cancel_manual_allocation_closes_its_own_open_item(arap_application):
    """Cancelling an allocating journal closes its own cache and reopens the target."""
    application, seed = arap_application
    opening_journal_id = _seed_opening_journal(application, seed)

    with application.app_context():
        target = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=opening_journal_id)
        ).scalar_one()
        adjustment = create_journal_draft(
            _credit_adjustment_payload(seed, target.id, "70", "Crédito a saldo inicial"),
            user_id=seed["user_id"],
        )
        submit_journal(adjustment.id, user_id=seed["user_id"])
        adjustment_id = str(adjustment.id)
        own_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=adjustment_id)
        ).scalar_one()
        assert own_cache.unallocated_amount == Decimal("0.0000")
        assert own_cache.status == "closed"
        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_type == "journal_entry",
                    ARAPLedgerEntry.voucher_id == adjustment_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert originals
        original_snapshot = _snapshot_arap_movements(originals)
        database.session.commit()

    with application.app_context():
        adjustment = database.session.get(ComprobanteContable, adjustment_id)
        assert adjustment is not None
        cancel_submitted_journal(
            adjustment_id,
            user_id=seed["user_id"],
            reason="Corrección del crédito",
            cancellation_date=seed["today"],
        )

    with application.app_context():
        adjustment = database.session.get(ComprobanteContable, adjustment_id)
        own_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=adjustment_id)
        ).scalar_one()
        target_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=opening_journal_id)
        ).scalar_one()
        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_type == "journal_entry",
                    ARAPLedgerEntry.voucher_id == adjustment_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        reversals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(ARAPLedgerEntry.reversal_of.in_([row.id for row in originals]))
            )
            .scalars()
            .all()
        )
        cached_items = list_cached_open_items(
            company=seed["company"],
            party_type="customer",
            party_id=seed["customer_id"],
        )
        assert adjustment is not None and adjustment.status == "cancelled"
        assert own_cache.unallocated_amount == Decimal("0.0000")
        assert own_cache.status == "closed"
        assert target_cache.unallocated_amount == Decimal("100.0000")
        assert target_cache.status == "open"
        assert ARAPLedgerEntry.document_balance("journal_entry", adjustment_id) == Decimal("0.0000")
        assert ARAPLedgerEntry.document_balance("journal_entry", opening_journal_id) == Decimal("100.0000")
        assert _snapshot_arap_movements(originals) == original_snapshot
        _assert_append_only_arap_reversals(originals, reversals)
        assert all(item.document_id != adjustment_id for item in cached_items)


def test_payment_cancellation_waits_for_application_and_reverses_both_ledgers(arap_application, monkeypatch):
    """Cancelling a payment after waiting on allocation sees and reverses that allocation."""
    application, seed = arap_application
    seed = _seed_payment_application_business_data(application, seed, "customer")
    payment_gl_ids = _seed_payment_gl_evidence(application, seed)
    invoice_id = seed["invoices"][0]
    payment_id = seed["payment_id"]
    application_locked = Event()
    release_application = Event()
    cancellation_lock_attempted = Event()
    cancellation_document_locked = Event()
    original_header_lock = arap_ledger_service._lock_payment_application_headers
    original_writer_reservation = arap_ledger_service._reserve_sqlite_open_item_writer
    original_document_lock = posting_service._lock_document_for_transition
    cancellation_thread_name = None
    cancellation_snapshot = {}

    def pause_after_payment_header_lock(payment, document):
        locked_payment = original_header_lock(payment, document)
        if payment.id == payment_id:
            application_locked.set()
            if not release_application.wait(timeout=10):
                raise TimeoutError("No se liberó la aplicación para completar la carrera de anulación.")
        return locked_payment

    def signal_payment_cancellation_lock(document):
        if document.id == payment_id:
            cancellation_lock_attempted.set()
        locked_document = original_document_lock(document)
        if locked_document.id == payment_id:
            # MySQL REPEATABLE READ can retain the snapshot from the earlier
            # document lookup while waiting for the application transaction.
            # Use locking reads to capture the committed allocation after the
            # cancellation acquired the payment lock.
            originals = (
                database.session.execute(
                    select(ARAPLedgerEntry)
                    .where(
                        ARAPLedgerEntry.is_reversal.is_(False),
                        or_(
                            (ARAPLedgerEntry.document_type == "payment_entry") & (ARAPLedgerEntry.document_id == payment_id),
                            (ARAPLedgerEntry.reference_type == "payment_entry") & (ARAPLedgerEntry.reference_id == payment_id),
                        ),
                    )
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            gl_originals = (
                database.session.execute(select(GLEntry).where(GLEntry.id.in_(payment_gl_ids)).with_for_update())
                .scalars()
                .all()
            )
            cancellation_snapshot["arap_original_ids"] = [str(movement.id) for movement in originals]
            arap_book_entries = (
                database.session.execute(
                    select(ARAPLedgerBookEntry)
                    .where(ARAPLedgerBookEntry.ledger_entry_id.in_(cancellation_snapshot["arap_original_ids"]))
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            book_entries_by_movement = {movement_id: [] for movement_id in cancellation_snapshot["arap_original_ids"]}
            for book_entry in arap_book_entries:
                book_entries_by_movement[str(book_entry.ledger_entry_id)].append(book_entry)
            cancellation_snapshot["arap"] = _snapshot_arap_movements(originals, book_entries_by_movement)
            cancellation_snapshot["gl_originals"] = {
                str(entry.id): (
                    entry.company,
                    entry.ledger_id,
                    entry.account_id,
                    entry.account_code,
                    entry.debit,
                    entry.credit,
                    entry.debit_in_account_currency,
                    entry.credit_in_account_currency,
                    entry.account_currency,
                    entry.company_currency,
                    entry.exchange_rate,
                    entry.party_type,
                    entry.party_id,
                    entry.posting_date,
                    entry.voucher_type,
                    entry.voucher_id,
                    entry.document_no,
                )
                for entry in gl_originals
            }
            assert len(gl_originals) == 2
            cancellation_document_locked.set()
        return locked_document

    def signal_sqlite_writer_reservation():
        if current_thread().name == cancellation_thread_name and database.engine.dialect.name == "sqlite":
            cancellation_lock_attempted.set()
        original_writer_reservation()

    monkeypatch.setattr(arap_ledger_service, "_lock_payment_application_headers", pause_after_payment_header_lock)
    monkeypatch.setattr(arap_ledger_service, "_reserve_sqlite_open_item_writer", signal_sqlite_writer_reservation)
    monkeypatch.setattr(posting_service, "_lock_document_for_transition", signal_payment_cancellation_lock)

    def apply_payment():
        with application.app_context():
            payment = database.session.get(PaymentEntry, payment_id)
            invoice = database.session.get(SalesInvoice, invoice_id)
            try:
                post_payment_application_ar_ap(
                    payment,
                    invoice,
                    document_amount=Decimal("60"),
                    payment_amount=Decimal("60"),
                    allocation_date=seed["today"],
                )
                database.session.commit()
                return "applied"
            finally:
                database.session.remove()

    def cancel_payment():
        nonlocal cancellation_thread_name
        cancellation_thread_name = current_thread().name
        with application.app_context():
            try:
                payment = database.session.get(PaymentEntry, payment_id)
                try:
                    with audit_actor(seed["user_id"], "Usuario de prueba"), approved_execution(payment, seed["user_id"]):
                        posting_service.cancel_document(
                            payment,
                            reason="Pago de prueba cancelado después de aplicar",
                            actor_user_id=seed["user_id"],
                            cancellation_date=seed["today"],
                        )
                except Exception:
                    cancellation_lock_attempted.set()
                    raise
                database.session.commit()
                return "cancelled"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        apply_future = executor.submit(apply_payment)
        assert application_locked.wait(timeout=10)
        cancel_future = executor.submit(cancel_payment)
        try:
            assert cancellation_lock_attempted.wait(timeout=10)
        finally:
            release_application.set()
        assert apply_future.result(timeout=20) == "applied"
        assert cancel_future.result(timeout=20) == "cancelled"

    assert cancellation_document_locked.is_set()

    with application.app_context():
        payment_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="payment_entry", document_id=payment_id)
        ).scalar_one()
        invoice_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="sales_invoice", document_id=invoice_id)
        ).scalar_one()
        payment = database.session.get(PaymentEntry, payment_id)
        assert payment is not None and payment.docstatus == 2
        assert payment_cache.unallocated_amount == Decimal("0.0000")
        assert payment_cache.status == "closed"
        assert invoice_cache.unallocated_amount == Decimal("60.0000")
        assert ARAPLedgerEntry.document_balance("payment_entry", payment_id) == Decimal("0.0000")
        assert ARAPLedgerEntry.document_balance("sales_invoice", invoice_id) == Decimal("60.0000")
        payment_arap_originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(ARAPLedgerEntry.id.in_(cancellation_snapshot["arap_original_ids"]))
            )
            .scalars()
            .all()
        )
        payment_arap_reversals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.voucher_type == "payment_entry",
                    ARAPLedgerEntry.voucher_id == payment_id,
                    ARAPLedgerEntry.is_reversal.is_(True),
                )
            )
            .scalars()
            .all()
        )
        original_book_entries = (
            database.session.execute(
                select(ARAPLedgerBookEntry)
                .where(ARAPLedgerBookEntry.ledger_entry_id.in_(cancellation_snapshot["arap_original_ids"]))
                .with_for_update()
            )
            .scalars()
            .all()
        )
        book_entries_by_movement = {movement_id: [] for movement_id in cancellation_snapshot["arap_original_ids"]}
        for book_entry in original_book_entries:
            book_entries_by_movement[str(book_entry.ledger_entry_id)].append(book_entry)
        arap_snapshot_after = _snapshot_arap_movements(payment_arap_originals, book_entries_by_movement)
        assert arap_snapshot_after == cancellation_snapshot["arap"]
        arap_book_rows = (
            database.session.execute(
                select(ARAPLedgerBookEntry)
                .where(
                    ARAPLedgerBookEntry.ledger_entry_id.in_(
                        [str(movement.id) for movement in payment_arap_originals + payment_arap_reversals]
                    )
                )
                .with_for_update()
            )
            .scalars()
            .all()
        )
        book_entries_by_movement = {str(movement.id): [] for movement in payment_arap_originals + payment_arap_reversals}
        for book_entry in arap_book_rows:
            book_entries_by_movement[str(book_entry.ledger_entry_id)].append(book_entry)
        _assert_append_only_arap_reversals(
            payment_arap_originals,
            payment_arap_reversals,
            book_entries_by_movement,
        )

        payment_gl_originals = database.session.execute(select(GLEntry).where(GLEntry.id.in_(payment_gl_ids))).scalars().all()
        assert {
            str(entry.id): (
                entry.company,
                entry.ledger_id,
                entry.account_id,
                entry.account_code,
                entry.debit,
                entry.credit,
                entry.debit_in_account_currency,
                entry.credit_in_account_currency,
                entry.account_currency,
                entry.company_currency,
                entry.exchange_rate,
                entry.party_type,
                entry.party_id,
                entry.posting_date,
                entry.voucher_type,
                entry.voucher_id,
                entry.document_no,
            )
            for entry in payment_gl_originals
        } == cancellation_snapshot["gl_originals"]
        assert all(entry.is_cancelled for entry in payment_gl_originals)
        payment_gl_reversals = (
            database.session.execute(
                select(GLEntry).where(
                    GLEntry.voucher_type == "payment_entry",
                    GLEntry.voucher_id == payment_id,
                    GLEntry.is_reversal.is_(True),
                )
            )
            .scalars()
            .all()
        )
        originals_by_id = {str(entry.id): entry for entry in payment_gl_originals}
        assert {str(entry.reversal_of) for entry in payment_gl_reversals} == set(originals_by_id)
        for reversal in payment_gl_reversals:
            original = originals_by_id[str(reversal.reversal_of)]
            assert reversal.debit == original.credit
            assert reversal.credit == original.debit
            assert reversal.is_reversal is True
        cached_items = list_cached_open_items(
            company=seed["company"],
            party_type="customer",
            party_id=seed["customer_id"],
        )
        ledger_items = list_open_items(
            company=seed["company"],
            party_type="customer",
            party_id=seed["customer_id"],
        )
        assert all(item.document_type != "payment_entry" or item.document_id != payment_id for item in cached_items)
        assert all(item.document_type != "payment_entry" or item.document_id != payment_id for item in ledger_items)


def test_cancelled_payment_without_open_item_cannot_be_applied(arap_application):
    """A stale payment instance cannot recreate an allocatable balance after cancellation."""
    application, seed = arap_application
    seed = _seed_payment_application_business_data(application, seed, "customer")
    invoice_id = seed["invoices"][0]

    with application.app_context():
        invoice = database.session.get(SalesInvoice, invoice_id)
        assert invoice is not None
        cancelled_payment = PaymentEntry(
            company=seed["company"],
            posting_date=seed["today"],
            docstatus=1,
            document_no=f"CANCELLED-{uuid4().hex[:8]}",
            payment_type="receive",
            party_type="customer",
            party_id=seed["customer_id"],
            party_name="Cliente de prueba",
            currency=seed["currency"],
            exchange_rate=Decimal("1"),
            received_amount=Decimal("60"),
            base_received_amount=Decimal("60"),
            unallocated_amount=Decimal("0"),
        )
        database.session.add(cancelled_payment)
        database.session.commit()
        payment_id = str(cancelled_payment.id)
        database.session.expunge(cancelled_payment)

        with Session(database.engine) as cancellation_session:
            cancellation_session.execute(update(PaymentEntry).where(PaymentEntry.id == payment_id).values(docstatus=2))
            cancellation_session.commit()

        assert cancelled_payment.docstatus == 1

        with pytest.raises(ValueError, match="El pago/anticipo debe estar aprobado"):
            post_payment_application_ar_ap(
                cancelled_payment,
                invoice,
                document_amount=Decimal("40"),
                payment_amount=Decimal("40"),
                allocation_date=seed["today"],
            )

        assert ARAPLedgerEntry.document_balance("payment_entry", payment_id) == Decimal("0")
        assert cancelled_payment.docstatus == 1
        assert (
            database.session.execute(
                select(ARAPOpenItem).filter_by(document_type="payment_entry", document_id=payment_id)
            ).scalar_one_or_none()
            is None
        )
        invoice_cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="sales_invoice", document_id=invoice_id)
        ).scalar_one()
        assert invoice_cache.unallocated_amount == Decimal("60.0000")


def test_cancel_partially_paid_invoice_closes_its_open_item_cache(arap_application):
    """Cancelling an invoice closes its cache even after reversing its allocation."""
    application, seed = arap_application
    seed = _seed_payment_application_business_data(application, seed, "customer")
    invoice_id = seed["invoices"][0]

    with application.app_context():
        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, seed["payment_id"])
        assert invoice is not None and payment is not None
        post_payment_application_ar_ap(
            payment,
            invoice,
            document_amount=Decimal("40"),
            payment_amount=Decimal("40"),
            allocation_date=seed["today"],
        )
        database.session.commit()
        cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="sales_invoice", document_id=invoice_id)
        ).scalar_one()
        assert cache.unallocated_amount == Decimal("20.0000")
        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.document_type == "sales_invoice",
                    ARAPLedgerEntry.document_id == invoice_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert len(originals) == 2
        original_snapshot = _snapshot_arap_movements(originals)

    with application.app_context():
        invoice = database.session.get(SalesInvoice, invoice_id)
        assert invoice is not None
        # This scenario seeds the AR/AP ledger directly to isolate the cancellation cache transition.
        arap_ledger_service.cancel_document_ar_ap(invoice, cancellation_date=seed["today"])
        invoice.docstatus = 2
        database.session.commit()

    with application.app_context():
        invoice = database.session.get(SalesInvoice, invoice_id)
        cache = database.session.execute(
            select(ARAPOpenItem).filter_by(document_type="sales_invoice", document_id=invoice_id)
        ).scalar_one()
        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.document_type == "sales_invoice",
                    ARAPLedgerEntry.document_id == invoice_id,
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
        reversals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(ARAPLedgerEntry.reversal_of.in_([row.id for row in originals]))
            )
            .scalars()
            .all()
        )
        cached_items = list_cached_open_items(
            company=seed["company"],
            party_type="customer",
            party_id=seed["customer_id"],
        )
        assert invoice is not None and invoice.docstatus == 2
        assert cache.unallocated_amount == Decimal("0.0000")
        assert cache.status == "closed"
        assert ARAPLedgerEntry.document_balance("sales_invoice", invoice_id) == Decimal("0.0000")
        assert _snapshot_arap_movements(originals) == original_snapshot
        _assert_append_only_arap_reversals(originals, reversals)
        assert all(item.document_type != "sales_invoice" or item.document_id != invoice_id for item in cached_items)
