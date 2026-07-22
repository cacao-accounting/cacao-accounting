# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 William José Reyes

"""Integration and unit tests for query tool handlers."""

from __future__ import annotations

import sys
import os
import pytest
from datetime import date
from decimal import Decimal

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../tests"))

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
        }
    )
    with _app.app_context():
        init_test_db(_app)
        # Ensure 'cacao' user is admin classification
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
        assert any(c["code"] == "cacao" for c in res["items"])

        # Test filter by company_ids
        ctx_restricted = QueryContext(user_id=user.id, company_ids=["nonexistent"])
        res_restricted = h_companies.list_companies.handler(context=ctx_restricted, page=1, page_size=10)
        assert res_restricted["total_items"] == 0


def test_list_accounting_periods_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["cacao"])

        # Seed an accounting period
        period = AccountingPeriod(
            id="test_period_123",
            name="2026-05",
            entity="cacao",
            is_closed=False,
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
            fiscal_year_id="2026",
            status="open",
        )
        database.session.add(period)
        database.session.commit()

        # List all
        res = h_accounting.list_accounting_periods.handler(context=ctx, company_id="cacao")
        assert res["total_items"] > 0
        assert any(p["id"] == "test_period_123" for p in res["items"])

        # List filtered by status=open
        res_open = h_accounting.list_accounting_periods.handler(context=ctx, company_id="cacao", status="open")
        assert res_open["total_items"] > 0

        # List filtered by status=closed
        res_closed = h_accounting.list_accounting_periods.handler(context=ctx, company_id="cacao", status="closed")
        assert not any(p["id"] == "test_period_123" for p in res_closed["items"])


def test_search_accounts_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["cacao"])

        # Seed an account
        acc = Accounts(
            id="test_acc_123",
            code="110101-T",
            name="Caja Chica Test",
            classification="Activo",
            type_="Asset",
            account_type="cash",
            entity="cacao",
            active=True,
        )
        database.session.add(acc)
        database.session.commit()

        # Search by code query
        res = h_accounting.search_accounts.handler(context=ctx, company_id="cacao", query="110101-T")
        assert res["total_items"] > 0
        assert res["items"][0]["code"] == "110101-T"

        # Search by name query
        res_name = h_accounting.search_accounts.handler(context=ctx, company_id="cacao", query="Chica")
        assert res_name["total_items"] > 0

        # Search by classification
        res_class = h_accounting.search_accounts.handler(context=ctx, company_id="cacao", classification="Activo")
        assert res_class["total_items"] > 0


def test_get_trial_balance_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["cacao"])

        # Seed account and GLEntries
        acc = database.session.execute(database.select(Accounts).filter_by(entity="cacao")).scalars().first()
        if acc:
            gl = GLEntry(
                company="cacao",
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
                company_id="cacao",
                ledger_id="standard",
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
            assert res["total_items"] > 0
            assert any(item["account_id"] == acc.id for item in res["items"])


def test_get_general_ledger_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"accounting.reports.read"}, company_ids=["cacao"])

        acc = database.session.execute(database.select(Accounts).filter_by(entity="cacao")).scalars().first()
        if acc:
            res = h_accounting.get_general_ledger.handler(
                context=ctx,
                company_id="cacao",
                ledger_id="standard",
                account_id=acc.id,
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
            assert "items" in res


def test_get_document_timeline_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"audit.reports.read"}, company_ids=["cacao"])

        res = h_audit_trail.get_document_timeline_handler.handler(
            context=ctx,
            company_id="cacao",
            document_type="purchase_order",
            document_id="some_id",
        )
        assert "items" in res


def test_get_banking_accounts_and_transactions_handlers(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"banking.reports.read"}, company_ids=["cacao"])

        # Seed bank first
        bank = Bank(id="test_bank_id", name="BAC Test", swift_code="BAC", is_active=True)
        database.session.add(bank)
        database.session.flush()

        # Seed bank account
        bank_acc = BankAccount(
            id="test_bank_acc_id",
            bank_id="test_bank_id",
            company="cacao",
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
        res_acc = h_banking.get_banking_accounts.handler(context=ctx, company_id="cacao")
        assert res_acc["total_items"] > 0
        assert any(item["account_number"] == "123456789" for item in res_acc["items"])

        # Test get_banking_transactions
        res_tx = h_banking.get_banking_transactions.handler(
            context=ctx,
            company_id="cacao",
            bank_account_id="test_bank_acc_id",
            date_from="2026-05-01",
            date_to="2026-05-31",
        )
        assert res_tx["total_items"] > 0
        assert any(item["description"] == "Transferencia Test" for item in res_tx["items"])


def test_get_document_flow_handler(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"documents.reports.read"}, company_ids=["cacao"])

        # Seed a DocumentRelation
        relation = DocumentRelation(
            source_type="purchase_order",
            source_id="PO-001",
            target_type="purchase_receipt",
            target_id="PR-001",
            relation_type="reference",
            qty=Decimal("10"),
            company="cacao",
        )
        database.session.add(relation)
        database.session.commit()

        res = h_documents.get_document_flow.handler(
            context=ctx,
            company_id="cacao",
            document_type="purchase_order",
            document_id="PO-001",
        )
        assert res["total_items"] > 0
        assert res["items"][0]["source_id"] == "PO-001"


def test_payables_handlers(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"payables.reports.read"}, company_ids=["cacao"])

        # Seed active purchase invoice with docstatus=1
        invoice = PurchaseInvoice(
            document_no="TEST-PI-PAY",
            company="cacao",
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
            company_id="cacao",
            as_of_date="2026-05-31",
            party_id="SUP-TEST",
        )
        assert res_aging["total_items"] > 0
        assert any(item["document_no"] == "TEST-PI-PAY" for item in res_aging["items"])

        # Test get_payables_open_documents
        res_open = h_payables.get_payables_open_documents.handler(
            context=ctx,
            company_id="cacao",
            party_id="SUP-TEST",
        )
        assert res_open["total_items"] > 0


def test_receivables_handlers(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        ctx = QueryContext(user_id=user.id, permissions={"receivables.reports.read"}, company_ids=["cacao"])

        # Seed active sales invoice with docstatus=1
        invoice = SalesInvoice(
            document_no="TEST-SI-REC",
            company="cacao",
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
            company_id="cacao",
            as_of_date="2026-05-31",
            party_id="CUST-TEST",
        )
        assert res_aging["total_items"] > 0
        assert any(item["document_no"] == "TEST-SI-REC" for item in res_aging["items"])

        # Test get_receivables_open_documents
        res_open = h_receivables.get_receivables_open_documents.handler(
            context=ctx,
            company_id="cacao",
            party_id="CUST-TEST",
        )
        assert res_open["total_items"] > 0
