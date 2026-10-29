# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Integration and unit tests for query tool handlers."""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__)))

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    AccountingPeriod,
    Accounts,
    GLEntry,
    Bank,
    BankAccount,
    BankTransaction,
    DocumentRelation,
    PurchaseInvoice,
    SalesInvoice,
    User,
)
from cacao_accounting.query_tools import PaginatedResult, QueryContext
from z_func import init_test_db

# Explicitly import all handlers to ensure they are registered and their schemas are loaded
import cacao_accounting.query_tools.handlers.accounting as h_accounting
import cacao_accounting.query_tools.handlers.audit_trail as h_audit_trail
import cacao_accounting.query_tools.handlers.banking as h_banking
import cacao_accounting.query_tools.handlers.companies as h_companies
import cacao_accounting.query_tools.handlers.documents as h_documents
import cacao_accounting.query_tools.handlers.operational as h_operational
import cacao_accounting.query_tools.handlers.payables as h_payables
import cacao_accounting.query_tools.handlers.receivables as h_receivables


@pytest.fixture(scope="module")
def app_instance():
    """Instancia de aplicación Flask con base de datos en memoria para pruebas de query handlers."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "handlers_test_secret_key",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "MODO_ESCRITORIO": False,
        }
    )
    with _app.app_context():
        init_test_db(_app)
        # Ensure 'CACAO' user is admin classification
        cacao_user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one_or_none()
        if cacao_user:
            cacao_user.classification = "admin"
            database.session.commit()
    return _app


@pytest.mark.slow
class TestPaginatedResultIntegration:
    def test_paginated_result_with_items(self):
        items = [{"id": "1", "name": "Test"}]
        result = PaginatedResult(
            page=1,
            page_size=10,
            total_items=1,
            items=items,
        )
        assert result.total_items == 1
        assert len(result.items) == 1
        assert result.has_next_page is False
        assert result.total_pages == 1

    def test_paginated_result_multi_page(self):
        items = [{"id": str(i)} for i in range(10)]
        result = PaginatedResult(
            page=1,
            page_size=10,
            total_items=15,
            items=items,
        )
        assert result.total_pages == 2
        assert result.has_next_page is True

    def test_paginated_result_to_dict_format(self):
        result = PaginatedResult(
            page=2,
            page_size=5,
            total_items=12,
            items=[{"num": i} for i in range(5)],
        )
        d = result.to_dict()
        assert d["page"] == 2
        assert d["page_size"] == 5
        assert d["total_items"] == 12
        assert d["total_pages"] == 3
        assert d["has_next_page"] is True
        assert len(d["items"]) == 5

    def test_paginated_result_empty_items(self):
        result = PaginatedResult(page=1, page_size=10, total_items=0, items=[])
        assert result.total_pages == 1
        assert result.has_next_page is False

    def test_paginated_result_last_page(self):
        items = [{"id": str(i)} for i in range(3)]
        result = PaginatedResult(
            page=2,
            page_size=10,
            total_items=12,
            items=items,
        )
        assert result.total_pages == 2
        assert result.has_next_page is False

    def test_paginated_result_single_page(self):
        items = [{"id": str(i)} for i in range(5)]
        result = PaginatedResult(
            page=1,
            page_size=10,
            total_items=5,
            items=items,
        )
        assert result.total_pages == 1
        assert result.has_next_page is False


def test_list_companies_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, company_ids=[], allow_all_companies=True)

        # Test success list all (call handler function of the QueryTool instance)
        res = h_companies.list_companies.handler(context=ctx, page=1, page_size=10)
        assert "items" in res
        assert res["total_items"] > 0
        assert any(c["code"] == "CACAO" for c in res["items"])

        # Test filter by company_ids
        ctx_restricted = QueryContext(user_id=user.id, company_ids=["nonexistent"])
        res_restricted = h_companies.list_companies.handler(context=ctx_restricted, page=1, page_size=10)
        assert res_restricted["total_items"] == 0


def test_operational_paginated_handlers_include_provenance(app_instance):
    """Los seis handlers operativos devuelven completitud según el contrato paginado."""
    with app_instance.app_context():
        context = QueryContext(
            user_id="query-tool-service",
            company_ids=["CACAO"],
            permissions={
                "banking.reports.read",
                "documents.reports.read",
                "audit.reports.read",
                "accounting.reports.read",
            },
            is_service_principal=True,
        )
        handlers = (
            (h_operational.search_payments, {}),
            (h_operational.get_unapplied_payments, {}),
            (h_operational.get_payment_applications, {"payment_id": "missing-payment"}),
            (h_operational.search_document_relations, {}),
            (h_operational.search_audit_events, {}),
            (h_operational.get_revaluations, {}),
        )

        for query_tool, parameters in handlers:
            result = query_tool.handler(context=context, company_id="CACAO", **parameters)
            completeness = result["provenance"]["completeness"]

            assert completeness["page"] == result["page"]
            assert completeness["page_size"] == result["page_size"]
            assert completeness["truncated"] is result["has_next_page"]
            assert completeness["returned_items"] == len(result["items"])
            assert completeness["total_items"] == result["total_items"]


def test_cash_forecast_list_uses_paginated_contract(app_instance):
    """La lista de pronósticos informa correctamente si queda otra página."""
    from cacao_accounting.database import CashForecast, FiscalYear
    from cacao_accounting.query_tools.handlers import treasury as h_treasury

    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        context = QueryContext(user_id=user.id, permissions={"banking.reports.read"}, company_ids=["CACAO"])
        fiscal_year = database.session.execute(
            database.select(FiscalYear).where(FiscalYear.entity == "CACAO").limit(1)
        ).scalar_one()
        database.session.add_all(
            [
                CashForecast(
                    version="pagination-contract-1",
                    fiscal_year_id=fiscal_year.id,
                    company="CACAO",
                    periodicity="monthly",
                ),
                CashForecast(
                    version="pagination-contract-2",
                    fiscal_year_id=fiscal_year.id,
                    company="CACAO",
                    periodicity="monthly",
                ),
            ]
        )
        database.session.commit()

        first = h_treasury.list_cash_forecasts.handler(context=context, company_id="CACAO", page_size=1)
        last = h_treasury.list_cash_forecasts.handler(context=context, company_id="CACAO", page=2, page_size=1)

        assert first["provenance"]["completeness"]["truncated"] is True
        assert last["provenance"]["completeness"]["truncated"] is False


def test_list_accounting_periods_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["CACAO"])

        # Seed an accounting period
        period = AccountingPeriod(
            id="test_period_123",
            name="2026-05",
            entity="CACAO",
            is_closed=False,
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
            fiscal_year_id="2026",
            status="open",
        )
        database.session.add(period)
        database.session.commit()

        # List all
        res = h_accounting.list_accounting_periods.handler(context=ctx, company_id="CACAO")
        assert res["total_items"] > 0
        assert any(p["id"] == "test_period_123" for p in res["items"])

        # List filtered by status=open
        res_open = h_accounting.list_accounting_periods.handler(context=ctx, company_id="CACAO", status="open")
        assert res_open["total_items"] > 0

        # List filtered by status=closed
        res_closed = h_accounting.list_accounting_periods.handler(context=ctx, company_id="CACAO", status="closed")
        assert not any(p["id"] == "test_period_123" for p in res_closed["items"])


def test_search_accounts_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["CACAO"])

        # Seed an account
        acc = Accounts(
            id="test_acc_123",
            code="110101-T",
            name="Caja Chica Test",
            classification="Activo",
            type_="Asset",
            account_type="cash",
            entity="CACAO",
            active=True,
        )
        database.session.add(acc)
        database.session.commit()

        # Search by code query
        res = h_accounting.search_accounts.handler(context=ctx, company_id="CACAO", query="110101-T")
        assert res["total_items"] > 0
        assert res["items"][0]["code"] == "110101-T"

        # Search by name query
        res_name = h_accounting.search_accounts.handler(context=ctx, company_id="CACAO", query="Chica")
        assert res_name["total_items"] > 0

        # Search by classification
        res_class = h_accounting.search_accounts.handler(context=ctx, company_id="CACAO", classification="Activo")
        assert res_class["total_items"] > 0


def test_get_trial_balance_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["CACAO"])

        # Seed account and GLEntries
        acc = database.session.execute(database.select(Accounts).filter_by(entity="CACAO")).scalars().first()
        if acc:
            gl = GLEntry(
                company="CACAO",
                ledger_id="standard",
                account_id=acc.id,
                debit=Decimal("150.00"),
                credit=Decimal("0.00"),
                posting_date=date(2026, 5, 15),
                voucher_type="journal_entry",
                voucher_id="test_voucher_id",
            )
            database.session.add(gl)
            database.session.commit()

            res = h_accounting.get_trial_balance.handler(
                context=ctx,
                company_id="CACAO",
                ledger_id="standard",
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
            assert res["total_items"] > 0
            assert any(item["account_id"] == acc.id for item in res["items"])


def test_get_general_ledger_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["CACAO"])

        acc = database.session.execute(database.select(Accounts).filter_by(entity="CACAO")).scalars().first()
        if acc:
            res = h_accounting.get_general_ledger.handler(
                context=ctx,
                company_id="CACAO",
                ledger_id="standard",
                account_id=acc.id,
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
            assert "items" in res


def test_get_document_timeline_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"audit.reports.read"}, company_ids=["CACAO"])

        res = h_audit_trail.get_document_timeline_handler.handler(
            context=ctx,
            company_id="CACAO",
            document_type="purchase_order",
            document_id="some_id",
        )
        assert "items" in res


def test_get_banking_accounts_and_transactions_handlers(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"banking.reports.read"}, company_ids=["CACAO"])

        # Seed bank first
        bank = Bank(id="test_bank_id", name="BAC Test", swift_code="BAC", is_active=True)
        database.session.add(bank)
        database.session.flush()

        # Seed bank account
        bank_acc = BankAccount(
            id="test_bank_acc_id",
            bank_id="test_bank_id",
            company="CACAO",
            account_name="Savings Account",
            account_no="123456789",
            currency="NIO",
            is_active=True,
        )
        database.session.add(bank_acc)
        database.session.flush()

        # Seed bank transaction
        bank_tx = BankTransaction(
            bank_account_id="test_bank_acc_id",
            posting_date=date(2026, 5, 15),
            description="Transferencia Test",
            deposit=Decimal("500.00"),
            withdrawal=Decimal("0.00"),
            reference_number="REF-123",
            is_reconciled=False,
        )
        database.session.add(bank_tx)
        database.session.commit()

        # Test get_banking_accounts
        res_acc = h_banking.get_banking_accounts.handler(context=ctx, company_id="CACAO")
        assert res_acc["total_items"] > 0
        account_item = next(item for item in res_acc["items"] if item["account_number"] == "123456789")
        assert account_item["balance"] == "0"

        # Test get_banking_transactions
        res_tx = h_banking.get_banking_transactions.handler(
            context=ctx,
            company_id="CACAO",
            bank_account_id="test_bank_acc_id",
            date_from="2026-05-01",
            date_to="2026-05-31",
        )
        assert res_tx["total_items"] > 0
        assert any(item["description"] == "Transferencia Test" for item in res_tx["items"])


def test_get_document_flow_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"documents.reports.read"}, company_ids=["CACAO"])

        # Seed a DocumentRelation
        relation = DocumentRelation(
            source_type="purchase_order",
            source_id="PO-001",
            target_type="purchase_receipt",
            target_id="PR-001",
            relation_type="reference",
            qty=Decimal("10"),
            company="CACAO",
        )
        database.session.add(relation)
        database.session.commit()

        res = h_documents.get_document_flow.handler(
            context=ctx,
            company_id="CACAO",
            document_type="purchase_order",
            document_id="PO-001",
        )
        assert res["total_items"] > 0
        assert res["items"][0]["source_id"] == "PO-001"


def test_payables_handlers(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"payables.reports.read"}, company_ids=["CACAO"])

        # Seed active purchase invoice with docstatus=1
        invoice = PurchaseInvoice(
            document_no="TEST-PI-PAY",
            company="CACAO",
            supplier_id="SUP-TEST",
            supplier_name="Supplier Test",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            grand_total=Decimal("1500.00"),
            total=Decimal("1500.00"),
            outstanding_amount=Decimal("1500.00"),
            transaction_currency="NIO",
            base_currency="NIO",
            status="open",
        )
        database.session.add(invoice)
        database.session.commit()

        # Test get_payables_aging
        res_aging = h_payables.get_payables_aging.handler(
            context=ctx,
            company_id="CACAO",
            as_of_date="2026-05-31",
            party_id="SUP-TEST",
        )
        assert res_aging["total_items"] > 0
        assert any(item["document_no"] == "TEST-PI-PAY" for item in res_aging["items"])

        # Test get_payables_open_documents
        res_open = h_payables.get_payables_open_documents.handler(
            context=ctx,
            company_id="CACAO",
            party_id="SUP-TEST",
        )
        assert res_open["total_items"] > 0


def test_receivables_handlers(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"receivables.reports.read"}, company_ids=["CACAO"])

        # Seed active sales invoice with docstatus=1
        invoice = SalesInvoice(
            document_no="TEST-SI-REC",
            company="CACAO",
            customer_id="CUST-TEST",
            customer_name="Customer Test",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            grand_total=Decimal("800.00"),
            total=Decimal("800.00"),
            outstanding_amount=Decimal("800.00"),
            transaction_currency="NIO",
            base_currency="NIO",
            status="open",
        )
        database.session.add(invoice)
        database.session.commit()

        # Test get_receivables_aging
        res_aging = h_receivables.get_receivables_aging.handler(
            context=ctx,
            company_id="CACAO",
            as_of_date="2026-05-31",
            party_id="CUST-TEST",
        )
        assert res_aging["total_items"] > 0
        assert any(item["document_no"] == "TEST-SI-REC" for item in res_aging["items"])

        # Test get_receivables_open_documents
        res_open = h_receivables.get_receivables_open_documents.handler(
            context=ctx,
            company_id="CACAO",
            party_id="CUST-TEST",
        )
        assert res_open["total_items"] > 0


@pytest.mark.parametrize(
    "module_name,handler,model,party_field,document_type,payment_type,note_type",
    [
        (
            "receivables",
            h_receivables.get_receivables_aging,
            SalesInvoice,
            "customer_id",
            "sales_invoice",
            "receive",
            "sales_credit_note",
        ),
        (
            "payables",
            h_payables.get_payables_aging,
            PurchaseInvoice,
            "supplier_id",
            "purchase_invoice",
            "pay",
            "purchase_credit_note",
        ),
    ],
)
def test_aging_uses_cutoff_for_posted_payments_and_notes(
    app_instance, module_name, handler, model, party_field, document_type, payment_type, note_type
):
    """AR/AP aging excludes real payments and notes posted after its cutoff."""
    from cacao_accounting.database import (
        ARAPLedgerEntry,
        Party,
        PaymentEntry,
        PaymentReference,
    )

    with app_instance.app_context():
        from cacao_accounting.reportes.services import SubledgerFilters, get_ar_ap_subledger

        company = "CACAO"
        party_id = f"CUT-{module_name}"
        party_name = "Corte de aging"
        party = Party(
            id=party_id,
            code=party_id,
            name=party_name,
            is_customer=module_name == "receivables",
            is_supplier=module_name == "payables",
        )
        database.session.add(party)
        party_fields = (
            {"customer_id": party_id, "customer_name": party_name}
            if module_name == "receivables"
            else {"supplier_id": party_id, "supplier_name": party_name}
        )
        invoice_number = f"AGING-{module_name}"
        invoice = model(
            document_no=invoice_number,
            company="CACAO",
            posting_date=date(2026, 1, 1),
            docstatus=1,
            grand_total=Decimal("100.00"),
            total=Decimal("100.00"),
            outstanding_amount=Decimal("100.00"),
            transaction_currency="NIO",
            base_currency="NIO",
            status="unpaid",
            **party_fields,
        )
        database.session.add(invoice)
        database.session.flush()

        database.session.add(
            ARAPLedgerEntry(
                company=company,
                ledger_type="AR" if module_name == "receivables" else "AP",
                party_type="customer" if module_name == "receivables" else "supplier",
                party_id=party.id,
                document_type=document_type,
                document_id=invoice.id,
                document_no=invoice_number,
                posting_date=date(2026, 1, 1),
                event_type="opening",
                currency="NIO",
                document_amount=Decimal("100.00"),
            )
        )

        for payment_date, allocated_amount in (
            (date(2026, 1, 15), Decimal("30.00")),
            (date(2026, 2, 15), Decimal("25.00")),
        ):
            payment = PaymentEntry(company=company, posting_date=payment_date, payment_type=payment_type, docstatus=1)
            database.session.add(payment)
            database.session.flush()
            reference = PaymentReference(
                payment_id=payment.id,
                reference_type=document_type,
                reference_id=invoice.id,
                company=company,
                total_amount=Decimal("100.00"),
                outstanding_amount=Decimal("100.00"),
                allocated_amount=allocated_amount,
                allocation_date=payment_date,
            )
            database.session.add(reference)
            database.session.flush()
            database.session.add(
                DocumentRelation(
                    source_type=document_type,
                    source_id=invoice.id,
                    target_type="payment_entry",
                    target_id=payment.id,
                    target_item_id=reference.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=allocated_amount,
                    relation_type="payment_reference",
                    status="active",
                )
            )

        for note_index, (note_date, note_amount) in enumerate(
            ((date(2026, 1, 20), Decimal("10.00")), (date(2026, 2, 20), Decimal("5.00"))),
            start=1,
        ):
            note = model(
                document_no=f"{invoice_number}-NOTE-{note_index}",
                company=company,
                posting_date=note_date,
                docstatus=1,
                document_type=note_type,
                is_return=True,
                grand_total=note_amount,
                total=note_amount,
                outstanding_amount=note_amount,
                transaction_currency="NIO",
                base_currency="NIO",
                status="unpaid",
                **party_fields,
            )
            database.session.add(note)
            database.session.flush()
            database.session.add(
                DocumentRelation(
                    source_type=document_type,
                    source_id=invoice.id,
                    target_type="sales_invoice" if module_name == "receivables" else "purchase_invoice",
                    target_id=note.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=note_amount,
                    relation_type="credit_note",
                    status="active",
                )
            )

        database.session.commit()

        context = QueryContext(
            user_id="query-tool-service",
            permissions={f"{module_name}.reports.read"},
            company_ids=[company],
            is_service_principal=True,
        )
        for cutoff, expected_paid, expected_outstanding, expected_bucket in (
            ("2026-01-31", Decimal("30.00"), Decimal("60.00"), "0_30"),
            ("2026-02-28", Decimal("55.00"), Decimal("30.00"), "31_60"),
        ):
            subledger = get_ar_ap_subledger(
                SubledgerFilters(
                    company=company,
                    party_type="customer" if module_name == "receivables" else "supplier",
                    party_id=party_id,
                    as_of_date=date.fromisoformat(cutoff),
                )
            )
            subledger_row = next(row for row in subledger.rows if row.values["document_no"] == invoice_number)
            assert Decimal(subledger_row.values["paid_amount"]) == expected_paid
            assert Decimal(subledger_row.values["outstanding_amount"]) == expected_outstanding
            result = handler.handler(context=context, company_id=company, as_of_date=cutoff, party_id=party_id)
            row = next(item for item in result["items"] if item["document_no"] == invoice_number)
            assert Decimal(row["outstanding"]) == expected_outstanding
            assert row["bucket"] == expected_bucket
            assert Decimal(row["base_outstanding"]) == expected_outstanding
            assert Decimal(result["summary"][expected_bucket]) == expected_outstanding
            assert result["summary_currency"] == "NIO"
            next_page = handler.handler(
                context=context,
                company_id=company,
                as_of_date=cutoff,
                party_id=party_id,
                page=2,
                page_size=1,
            )
            assert next_page["items"] == []
            assert next_page["summary"] == result["summary"]
            assert next_page["total_items"] == result["total_items"]


def test_aging_keeps_legacy_allocations_until_their_later_cancellation(app_instance):
    """Historical aging retains legacy payment and note relations at the cutoff."""
    from datetime import datetime, timezone

    from cacao_accounting.database import ARAPLedgerEntry, DocumentTransition, Party, PaymentEntry, PaymentReference

    with app_instance.app_context():
        company = "CACAO"
        party = Party(id="CUT-HISTORIC", code="CUT-HISTORIC", name="Historical", is_customer=True)
        invoice = SalesInvoice(
            company=company,
            customer_id=party.id,
            document_type="sales_invoice",
            document_no="AGING-HISTORICAL",
            posting_date=date(2026, 1, 1),
            docstatus=1,
            grand_total=Decimal("100"),
            total=Decimal("100"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([party, invoice])
        database.session.flush()
        cancellation_time = datetime(2026, 2, 15, tzinfo=timezone.utc)
        period = database.session.execute(database.select(AccountingPeriod).filter_by(entity=company)).scalars().first()
        actor = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        assert period is not None

        payment = PaymentEntry(
            company=company,
            posting_date=date(2026, 1, 15),
            payment_type="receive",
            docstatus=2,
            cancelled_at=cancellation_time,
        )
        database.session.add(payment)
        database.session.flush()
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            company=company,
            allocated_amount=Decimal("30"),
            allocation_date=date(2026, 1, 15),
        )
        database.session.add(reference)
        database.session.flush()
        payment_effective_before_cutoff = PaymentEntry(
            company=company,
            posting_date=date(2026, 1, 10),
            payment_type="receive",
            docstatus=2,
            cancelled_at=cancellation_time,
        )
        database.session.add(payment_effective_before_cutoff)
        database.session.flush()
        reference_effective_before_cutoff = PaymentReference(
            payment_id=payment_effective_before_cutoff.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            company=company,
            allocated_amount=Decimal("20"),
            allocation_date=date(2026, 1, 10),
        )
        database.session.add(reference_effective_before_cutoff)
        database.session.flush()

        note = SalesInvoice(
            company=company,
            document_type="sales_credit_note",
            document_no="AGING-HISTORICAL-CN",
            customer_id=party.id,
            posting_date=date(2026, 1, 20),
            docstatus=2,
            cancelled_at=cancellation_time,
            is_return=True,
            grand_total=Decimal("10"),
            total=Decimal("10"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(note)
        database.session.flush()
        note_effective_before_cutoff = SalesInvoice(
            company=company,
            document_type="sales_credit_note",
            document_no="AGING-HISTORICAL-CN-EARLY",
            customer_id=party.id,
            posting_date=date(2026, 1, 25),
            docstatus=2,
            cancelled_at=cancellation_time,
            is_return=True,
            grand_total=Decimal("5"),
            total=Decimal("5"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(note_effective_before_cutoff)
        database.session.flush()
        database.session.add_all(
            [
                ARAPLedgerEntry(
                    company=company,
                    ledger_type="AR",
                    party_type="customer",
                    party_id=party.id,
                    document_type="sales_invoice",
                    document_id=invoice.id,
                    document_no=invoice.document_no,
                    posting_date=date(2026, 1, 1),
                    event_type="opening",
                    currency="NIO",
                    document_amount=Decimal("100"),
                ),
                DocumentTransition(
                    source_type="payment_entry",
                    source_id=payment.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 2, 15),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="future effective cancellation",
                ),
                DocumentTransition(
                    source_type="payment_entry",
                    source_id=payment_effective_before_cutoff.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 1, 10),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="cancellation effective before cutoff",
                ),
                DocumentTransition(
                    source_type="sales_credit_note",
                    source_id=note.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 2, 15),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="future effective cancellation",
                ),
                DocumentTransition(
                    source_type="sales_credit_note",
                    source_id=note_effective_before_cutoff.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 1, 25),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="cancellation effective before cutoff",
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="payment_entry",
                    target_id=payment.id,
                    target_item_id=reference.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("30"),
                    relation_type="payment_reference",
                    status="cancelled",
                    cancelled_at=cancellation_time,
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="payment_entry",
                    target_id=payment_effective_before_cutoff.id,
                    target_item_id=reference_effective_before_cutoff.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("20"),
                    relation_type="payment_reference",
                    status="reverted",
                    reversed_at=cancellation_time,
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="sales_credit_note",
                    target_id=note.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("10"),
                    relation_type="credit_note",
                    status="cancelled",
                    cancelled_at=cancellation_time,
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="sales_credit_note",
                    target_id=note_effective_before_cutoff.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("5"),
                    relation_type="credit_note",
                    status="reverted",
                    reversed_at=cancellation_time,
                ),
            ]
        )
        database.session.commit()

        context = QueryContext(
            user_id="query-tool-service",
            permissions={"receivables.reports.read"},
            company_ids=[company],
            is_service_principal=True,
        )
        before_cancel = h_receivables.get_receivables_aging.handler(
            context=context, company_id=company, party_id=party.id, as_of_date="2026-01-31"
        )
        row_before = next(item for item in before_cancel["items"] if item["document_no"] == invoice.document_no)
        assert Decimal(row_before["outstanding"]) == Decimal("60")
        assert Decimal(before_cancel["summary"]["0_30"]) == Decimal("60")

        after_cancel = h_receivables.get_receivables_aging.handler(
            context=context, company_id=company, party_id=party.id, as_of_date="2026-02-28"
        )
        row_after = next(item for item in after_cancel["items"] if item["document_no"] == invoice.document_no)
        assert Decimal(row_after["outstanding"]) == Decimal("100")
        assert Decimal(after_cancel["summary"]["31_60"]) == Decimal("100")


def test_aging_includes_invoice_cancelled_after_cutoff(app_instance):
    """Retain an invoice in historical aging until its effective cancellation date."""
    from datetime import datetime, timezone

    from cacao_accounting.database import ARAPLedgerEntry, AccountingPeriod, DocumentTransition, Party

    with app_instance.app_context():
        company = "CACAO"
        party = Party(id="CUT-CANCELLED-INVOICE", code="CUT-CANCELLED-INVOICE", name="Historical", is_customer=True)
        invoice = SalesInvoice(
            company=company,
            customer_id=party.id,
            document_type="sales_invoice",
            document_no="AGING-CANCELLED-LATER",
            posting_date=date(2026, 1, 1),
            docstatus=2,
            cancelled_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
            grand_total=Decimal("100"),
            total=Decimal("100"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([party, invoice])
        database.session.flush()
        period = database.session.execute(database.select(AccountingPeriod).filter_by(entity=company)).scalars().first()
        actor = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        assert period is not None
        database.session.add_all(
            [
                ARAPLedgerEntry(
                    company=company,
                    ledger_type="AR",
                    party_type="customer",
                    party_id=party.id,
                    document_type="sales_invoice",
                    document_id=invoice.id,
                    document_no=invoice.document_no,
                    posting_date=date(2026, 1, 1),
                    event_type="opening",
                    currency="NIO",
                    document_amount=Decimal("100"),
                ),
                DocumentTransition(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 2, 15),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="future effective cancellation",
                ),
            ]
        )
        database.session.commit()

        context = QueryContext(
            user_id="query-tool-service",
            permissions={"receivables.reports.read"},
            company_ids=[company],
            is_service_principal=True,
        )
        before_cancel = h_receivables.get_receivables_aging.handler(
            context=context, company_id=company, party_id=party.id, as_of_date="2026-01-31"
        )
        assert before_cancel["total_items"] == 1
        row = before_cancel["items"][0]
        assert row["document_no"] == invoice.document_no
        assert Decimal(row["outstanding"]) == Decimal("100")

        after_cancel = h_receivables.get_receivables_aging.handler(
            context=context, company_id=company, party_id=party.id, as_of_date="2026-02-28"
        )
        assert after_cancel["total_items"] == 0


def test_aging_uses_effective_cancellation_date_for_reverted_relations(app_instance):
    """Keep allocations through the effective date when relations revert earlier."""
    from datetime import datetime, timezone

    from cacao_accounting.database import ARAPLedgerEntry, DocumentTransition, Party, PaymentEntry, PaymentReference
    from cacao_accounting.document_flow.payment import compute_outstanding_amount

    with app_instance.app_context():
        company = "CACAO"
        executed_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        party = Party(id="CUT-EFFECTIVE-RELATION", code="CUT-EFFECTIVE-RELATION", name="Effective", is_customer=True)
        invoice = SalesInvoice(
            company=company,
            customer_id=party.id,
            document_type="sales_invoice",
            document_no="AGING-EFFECTIVE-RELATION",
            posting_date=date(2026, 1, 1),
            docstatus=2,
            cancelled_at=executed_at,
            grand_total=Decimal("100"),
            total=Decimal("100"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([party, invoice])
        database.session.flush()

        period = database.session.execute(database.select(AccountingPeriod).filter_by(entity=company)).scalars().first()
        actor = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        assert period is not None
        payment = PaymentEntry(
            company=company,
            posting_date=date(2026, 1, 15),
            payment_type="receive",
            docstatus=2,
            received_amount=Decimal("30"),
            cancelled_at=executed_at,
        )
        database.session.add(payment)
        database.session.flush()
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            company=company,
            allocated_amount=Decimal("30"),
            allocation_date=date(2026, 1, 15),
        )
        note = SalesInvoice(
            company=company,
            document_type="sales_credit_note",
            document_no="AGING-EFFECTIVE-NOTE",
            customer_id=party.id,
            posting_date=date(2026, 1, 20),
            docstatus=2,
            cancelled_at=executed_at,
            is_return=True,
            grand_total=Decimal("10"),
            total=Decimal("10"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([reference, note])
        database.session.flush()
        database.session.add_all(
            [
                ARAPLedgerEntry(
                    company=company,
                    ledger_type="AR",
                    party_type="customer",
                    party_id=party.id,
                    document_type="sales_invoice",
                    document_id=invoice.id,
                    document_no=invoice.document_no,
                    posting_date=date(2026, 1, 1),
                    event_type="opening",
                    currency="NIO",
                    document_amount=Decimal("100"),
                ),
                DocumentTransition(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 2, 20),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="future effective cancellation",
                ),
                DocumentTransition(
                    source_type="payment_entry",
                    source_id=payment.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 2, 20),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="future effective cancellation",
                ),
                DocumentTransition(
                    source_type="sales_credit_note",
                    source_id=note.id,
                    transition_type="cancellation",
                    company=company,
                    posting_date=date(2026, 2, 20),
                    accounting_period_id=period.id,
                    actor_user_id=actor.id,
                    reason="future effective cancellation",
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="payment_entry",
                    target_id=payment.id,
                    target_item_id=reference.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("30"),
                    relation_type="payment_reference",
                    status="reverted",
                    reversed_at=executed_at,
                    reversal_reason="payment_cancelled",
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="sales_credit_note",
                    target_id=note.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("5"),
                    relation_type="credit_note",
                    revision=1,
                    status="reverted",
                    reversed_at=datetime(2026, 1, 25, tzinfo=timezone.utc),
                    reversal_reason="reversal_document_revised",
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id=invoice.id,
                    target_type="sales_credit_note",
                    target_id=note.id,
                    company=company,
                    qty=Decimal("1"),
                    amount=Decimal("10"),
                    relation_type="credit_note",
                    revision=2,
                    status="reverted",
                    reversed_at=executed_at,
                    reversal_reason="target_cancelled",
                ),
            ]
        )
        database.session.commit()

        context = QueryContext(
            user_id="query-tool-service",
            permissions={"receivables.reports.read"},
            company_ids=[company],
            is_service_principal=True,
        )
        before_effective_date = h_receivables.get_receivables_aging.handler(
            context=context, company_id=company, party_id=party.id, as_of_date="2026-02-10"
        )
        row_before = next(row for row in before_effective_date["items"] if row["document_no"] == invoice.document_no)
        assert Decimal(row_before["outstanding"]) == Decimal("60")

        after_effective_date = h_receivables.get_receivables_aging.handler(
            context=context, company_id=company, party_id=party.id, as_of_date="2026-02-28"
        )
        assert after_effective_date["total_items"] == 0
        assert compute_outstanding_amount(invoice, as_of_date=date(2026, 2, 28)) == Decimal("100")


def test_subledger_paid_matches_cutoff_allocations_without_arap_opening(app_instance):
    """Keep paid and outstanding amounts aligned for legacy-only invoices."""
    from datetime import datetime, timezone

    from cacao_accounting.database import Party, PaymentEntry, PaymentReference
    from cacao_accounting.reportes.services import SubledgerFilters, get_ar_ap_subledger

    with app_instance.app_context():
        company = "CACAO"
        party = Party(id="CUT-LEGACY-PAID", code="CUT-LEGACY-PAID", name="Legacy", is_customer=True)
        invoice = SalesInvoice(
            company=company,
            customer_id=party.id,
            document_type="sales_invoice",
            document_no="AGING-LEGACY-ONLY",
            posting_date=date(2026, 1, 1),
            docstatus=1,
            grand_total=Decimal("100"),
            total=Decimal("100"),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([party, invoice])
        database.session.flush()
        cancellation_time = datetime(2026, 2, 15, tzinfo=timezone.utc)
        payment = PaymentEntry(
            company=company,
            posting_date=date(2026, 1, 15),
            payment_type="receive",
            docstatus=2,
            cancelled_at=cancellation_time,
        )
        database.session.add(payment)
        database.session.flush()
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            company=company,
            allocated_amount=Decimal("30"),
            allocation_date=date(2026, 1, 15),
        )
        database.session.add(reference)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice.id,
                target_type="payment_entry",
                target_id=payment.id,
                target_item_id=reference.id,
                company=company,
                qty=Decimal("1"),
                amount=Decimal("30"),
                relation_type="payment_reference",
                status="cancelled",
                cancelled_at=cancellation_time,
            )
        )
        database.session.commit()

        report = get_ar_ap_subledger(
            SubledgerFilters(company=company, party_type="customer", party_id=party.id, as_of_date=date(2026, 1, 31))
        )
        row = next(row.values for row in report.rows if row.values["document_no"] == invoice.document_no)
        assert Decimal(row["paid_amount"]) == Decimal("30")
        assert Decimal(row["outstanding_amount"]) == Decimal("70")


@pytest.mark.parametrize(
    "module_name,handler,model,party_field,party_name_field,party_type",
    [
        (
            "receivables",
            h_receivables.get_receivables_aging,
            SalesInvoice,
            "customer_id",
            "customer_name",
            "customer",
        ),
        (
            "payables",
            h_payables.get_payables_aging,
            PurchaseInvoice,
            "supplier_id",
            "supplier_name",
            "supplier",
        ),
    ],
)
def test_aging_maps_duplicate_document_numbers_by_record_id(
    app_instance, module_name, handler, model, party_field, party_name_field, party_type
):
    """Duplicate human document numbers remain distinct and base totals preserve FX."""
    with app_instance.app_context():
        company = "CACAO"
        party_id = f"DUP-{module_name}"
        party_fields = {party_field: party_id, party_name_field: "Parte de prueba"}
        document_no = f"DUP-AGING-{module_name}"
        database.session.add_all(
            [
                model(
                    document_no=document_no,
                    company=company,
                    posting_date=date(2026, 1, 1),
                    docstatus=1,
                    total=Decimal("100"),
                    grand_total=Decimal("100"),
                    base_total=Decimal("100"),
                    base_grand_total=Decimal("100"),
                    transaction_currency="NIO",
                    base_currency="NIO",
                    exchange_rate=Decimal("1"),
                    status="unpaid",
                    **party_fields,
                ),
                model(
                    document_no=document_no,
                    company=company,
                    posting_date=date(2026, 1, 1),
                    docstatus=1,
                    total=Decimal("50"),
                    grand_total=Decimal("50"),
                    base_total=Decimal("1800"),
                    base_grand_total=Decimal("1800"),
                    transaction_currency="USD",
                    base_currency="NIO",
                    exchange_rate=Decimal("36"),
                    status="unpaid",
                    **party_fields,
                ),
            ]
        )
        database.session.commit()

        context = QueryContext(
            user_id="query-tool-service",
            permissions={f"{module_name}.reports.read"},
            company_ids=[company],
            is_service_principal=True,
        )
        result = handler.handler(
            context=context,
            company_id=company,
            as_of_date="2026-01-31",
            party_id=party_id,
        )

        rows = result["items"]
        assert len(rows) == 2
        assert sorted(
            (row["total"], row["outstanding"], row["base_outstanding"], row["transaction_currency"]) for row in rows
        ) == [("100.0000", "100.0000", "100.0000", "NIO"), ("50.0000", "50.0000", "1800.0000", "USD")]
        assert Decimal(result["summary"]["0_30"]) == Decimal("1900")
        assert result["summary_currency"] == "NIO"


def test_banking_balance_summary_applies_the_published_cutoff(app_instance):
    """El handler transfiere as_of_date al servicio que calcula el saldo."""
    from cacao_accounting.query_tools.handlers import advanced as h_advanced

    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        context = QueryContext(user_id=user.id, permissions={"banking.reports.read"}, company_ids=["CACAO"])

        result = h_advanced.get_banking_balance_summary.handler(
            context=context,
            company_id="CACAO",
            as_of_date="2026-05-01",
            date_from="2026-04-01",
            date_to="2026-04-30",
        )

        filters = result["provenance"]["filters"]
        assert filters["as_of_date"] == "2026-05-01"
        assert "date_from" not in filters
        assert "date_to" not in filters


def test_get_banking_accounts_returns_primary_ledger_balance(app_instance):
    """Calcula desde el libro primario e ignora asientos excluidos del resumen."""
    from cacao_accounting.database import Book
    from cacao_accounting.reportes.services import BankingFilters, get_bank_balance_summary

    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        context = QueryContext(user_id=user.id, permissions={"banking.reports.read"}, company_ids=["CACAO"])
        primary_book = database.session.execute(
            database.select(Book).where(
                Book.entity == "CACAO",
                Book.status == "activo",
                Book.is_primary.is_(True),
            )
        ).scalar_one()
        secondary_book = (
            database.session.execute(
                database.select(Book).where(
                    Book.entity == "CACAO",
                    Book.status == "activo",
                    Book.is_primary.is_(False),
                )
            )
            .scalars()
            .first()
        )
        assert secondary_book is not None

        bank = Bank(id="balance_test_bank", name="A Balance Test Bank", is_active=True)
        gl_account = Accounts(
            entity="CACAO",
            code="TEST-BANK-BALANCE",
            name="Test bank balance",
            active=True,
            enabled=True,
            group=False,
            currency="NIO",
            classification="Activo",
            type_="Cta. Bancaria",
            account_type="bank",
        )
        database.session.add_all([bank, gl_account])
        database.session.flush()
        bank_account = BankAccount(
            id="balance_test_account",
            bank_id=bank.id,
            company="CACAO",
            account_name="Balance test account",
            account_no="BALANCE-001",
            currency="NIO",
            gl_account_id=gl_account.id,
            is_active=True,
        )
        database.session.add(bank_account)
        database.session.flush()

        common_entry = {
            "company": "CACAO",
            "account_id": gl_account.id,
            "bank_account_id": bank_account.id,
            "posting_date": date(2026, 5, 15),
            "voucher_type": "Test",
        }
        database.session.add_all(
            [
                GLEntry(
                    **common_entry,
                    ledger_id=primary_book.id,
                    voucher_id="balance-primary-debit",
                    debit=Decimal("125"),
                    credit=Decimal("0"),
                ),
                GLEntry(
                    **common_entry,
                    ledger_id=primary_book.id,
                    voucher_id="balance-cancelled",
                    debit=Decimal("10"),
                    credit=Decimal("0"),
                    is_cancelled=True,
                ),
                GLEntry(
                    **common_entry,
                    ledger_id=primary_book.id,
                    voucher_id="balance-reversal",
                    debit=Decimal("20"),
                    credit=Decimal("0"),
                    is_reversal=True,
                ),
                GLEntry(
                    **common_entry,
                    ledger_id=secondary_book.id,
                    voucher_id="balance-secondary",
                    debit=Decimal("900"),
                    credit=Decimal("0"),
                ),
            ]
        )
        database.session.commit()

        result = h_banking.get_banking_accounts.handler(
            context=context,
            company_id="CACAO",
            page_size=500,
        )

        item = next(item for item in result["items"] if item["id"] == bank_account.id)
        report = get_bank_balance_summary(BankingFilters(company="CACAO", bank_account_id=bank_account.id))
        report_balance = report.rows[0].values["ending_balance"]

        assert item["balance"] == "125.0000"
        assert item["balance"] == str(report_balance)


def test_get_banking_accounts_returns_empty_page_without_balances(app_instance):
    """Evita consultar el mayor cuando la página solicitada no contiene cuentas."""
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        context = QueryContext(user_id=user.id, permissions={"banking.reports.read"}, company_ids=["CACAO"])

        result = h_banking.get_banking_accounts.handler(
            context=context,
            company_id="CACAO",
            page=9999,
            page_size=1,
        )

        assert result["items"] == []
        assert result["total_items"] > 0
