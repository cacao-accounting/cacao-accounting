"""Business regressions for shared AR/AP open-item balances."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event, current_thread
from uuid import uuid4

import pytest
from sqlalchemy import func, select


from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import arap_ledger_service
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.arap_ledger_service import post_payment_application_ar_ap
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    cancel_submitted_journal,
    create_journal_draft,
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
    Modules,
    Party,
    PaymentEntry,
    PurchaseInvoice,
    SalesInvoice,
    User,
    database,
)

pytestmark = pytest.mark.database


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
        database.session.add_all([fiscal_year, period, receivable, payable, sales, returns, cost_center, user])
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


def _seed_opening_journal(application, seed) -> str:
    """Post a real customer invoice balance through the manual journal flow."""
    payload = {
        "company": seed["company"],
        "posting_date": seed["today"].isoformat(),
        "books": [seed["book"]],
        "transaction_currency": seed["currency"],
        "base_currency": seed["currency"],
        "exchange_rate": "1",
        "reference": "Saldo inicial de factura de cliente",
        "lines": [
            {
                "account": seed["receivable"],
                "debit": "100",
                "credit": "0",
                "currency": seed["currency"],
                "party_type": "customer",
                "party": seed["customer_id"],
            },
            {"account": seed["sales"], "debit": "0", "credit": "100", "currency": seed["currency"]},
        ],
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
            lock_headers(payment, document)

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


def test_payment_cancellation_waits_for_application_and_reverses_both_ledgers(arap_application, monkeypatch):
    """Cancelling a payment after waiting on allocation sees and reverses that allocation."""
    application, seed = arap_application
    seed = _seed_payment_application_business_data(application, seed, "customer")
    invoice_id = seed["invoices"][0]
    payment_id = seed["payment_id"]
    application_locked = Event()
    release_application = Event()
    cancellation_lock_attempted = Event()
    original_header_lock = arap_ledger_service._lock_payment_application_headers
    original_writer_reservation = arap_ledger_service._reserve_sqlite_open_item_writer
    original_document_lock = posting_service._lock_document_for_transition
    cancellation_thread_name = None

    def pause_after_payment_header_lock(payment, document):
        original_header_lock(payment, document)
        if payment.id == payment_id:
            application_locked.set()
            if not release_application.wait(timeout=10):
                raise TimeoutError("No se liberó la aplicación para completar la carrera de anulación.")

    def signal_payment_cancellation_lock(document):
        if document.id == payment_id:
            cancellation_lock_attempted.set()
        return original_document_lock(document)

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
                arap_ledger_service._reserve_sqlite_open_item_writer()
                payment = posting_service._lock_document_for_transition(payment)
                arap_ledger_service.cancel_document_ar_ap(payment, cancellation_date=seed["today"])
                payment.docstatus = 2
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
