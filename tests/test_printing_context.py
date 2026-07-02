# SPDX-License-Identifier: Apache-2.0

"""Tests for printing context module."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.printing.context import (
    COMMON_SCHEMA,
    LINE_SCHEMA,
    INVOICE_SCHEMA,
    JOURNAL_ENTRY_PRINT_SCHEMA,
    SALES_INVOICE_PRINT_SCHEMA,
    PURCHASE_INVOICE_PRINT_SCHEMA,
    PURCHASE_ORDER_PRINT_SCHEMA,
    DELIVERY_NOTE_PRINT_SCHEMA,
    STOCK_ENTRY_PRINT_SCHEMA,
    QUOTATION_PRINT_SCHEMA,
    PAYMENT_ENTRY_PRINT_SCHEMA,
    EXCHANGE_REVALUATION_PRINT_SCHEMA,
    build_journal_entry_sample_context,
    build_sales_invoice_sample_context,
    build_purchase_order_sample_context,
    build_payment_entry_sample_context,
    build_stock_entry_sample_context,
    build_exchange_revaluation_sample_context,
    build_quotation_sample_context,
)


class TestHelperFunctions:
    def test_first_attr_returns_first_non_empty_attribute(self):
        from cacao_accounting.printing.context import _first_attr

        obj = SimpleNamespace(a=None, b="", c="found", d="ignored")
        assert _first_attr(obj, "a", "b", "c", "d") == "found"

    def test_first_attr_returns_none_when_all_empty(self):
        from cacao_accounting.printing.context import _first_attr

        obj = SimpleNamespace(a=None, b="", c=None)
        assert _first_attr(obj, "a", "b", "c") is None

    def test_first_attr_returns_none_for_empty_names(self):
        from cacao_accounting.printing.context import _first_attr

        obj = SimpleNamespace()
        assert _first_attr(obj, "x", "y", "z") is None

    def test_text_returns_string_value(self):
        from cacao_accounting.printing.context import _text

        obj = SimpleNamespace(name="Hello")
        assert _text(obj, "name") == "Hello"

    def test_text_returns_default_when_attr_missing(self):
        from cacao_accounting.printing.context import _text

        obj = SimpleNamespace()
        assert _text(obj, "missing", "default") == "default"

    def test_text_handles_none_object(self):
        from cacao_accounting.printing.context import _text

        assert _text(None, "attr", "fallback") == "fallback"

    def test_text_converts_none_attr_to_default(self):
        from cacao_accounting.printing.context import _text

        obj = SimpleNamespace(name=None)
        assert _text(obj, "name", "default") == "default"

    def test_number_converts_valid_value(self):
        from cacao_accounting.printing.context import _number

        assert _number(100) == 100.0
        assert _number("123.45") == 123.45
        assert _number(Decimal("99.99")) == 99.99

    def test_number_returns_zero_for_none(self):
        from cacao_accounting.printing.context import _number

        assert _number(None) == 0.0

    def test_number_returns_zero_for_invalid(self):
        from cacao_accounting.printing.context import _number

        assert _number("invalid") == 0.0
        assert _number(object()) == 0.0

    def test_date_text_formats_date_object(self):
        from cacao_accounting.printing.context import _date_text

        d = date(2026, 6, 30)
        assert _date_text(d) == "2026-06-30"

    def test_date_text_formats_datetime_object(self):
        from cacao_accounting.printing.context import _date_text

        dt = datetime(2026, 6, 30, 14, 30, 0)
        assert _date_text(dt) == "2026-06-30"

    def test_date_text_returns_string_for_other(self):
        from cacao_accounting.printing.context import _date_text

        assert _date_text("2026-06-30") == "2026-06-30"
        assert _date_text(None) == ""

    def test_document_number_prefers_document_no(self):
        from cacao_accounting.printing.context import _document_number

        obj = SimpleNamespace(document_no="DOC-001", name="ignored", id="also-ignored")
        assert _document_number(obj) == "DOC-001"

    def test_document_number_falls_back_to_name(self):
        from cacao_accounting.printing.context import _document_number

        obj = SimpleNamespace(name="NAME-001", id="ignored")
        assert _document_number(obj) == "NAME-001"

    def test_document_status_returns_status_when_present(self):
        from cacao_accounting.printing.context import _document_status

        obj = SimpleNamespace(status="submitted")
        assert _document_status(obj) == "submitted"

    def test_document_status_returns_posted_for_docstatus_1(self):
        from cacao_accounting.printing.context import _document_status

        obj = SimpleNamespace(docstatus=1)
        assert _document_status(obj) == "posted"

    def test_document_status_returns_cancelled_for_docstatus_2(self):
        from cacao_accounting.printing.context import _document_status

        obj = SimpleNamespace(docstatus=2)
        assert _document_status(obj) == "cancelled"

    def test_document_status_returns_draft_for_docstatus_0(self):
        from cacao_accounting.printing.context import _document_status

        obj = SimpleNamespace(docstatus=0)
        assert _document_status(obj) == "draft"

    def test_user_name_extracts_user_attribute(self):
        from cacao_accounting.printing.context import _user_name

        obj = SimpleNamespace(user="admin")
        assert _user_name(obj) == "admin"

    def test_user_name_extracts_id_when_no_user(self):
        from cacao_accounting.printing.context import _user_name

        obj = SimpleNamespace(id="user-123")
        assert _user_name(obj) == "user-123"

    def test_user_name_returns_string_directly(self):
        from cacao_accounting.printing.context import _user_name

        assert _user_name("string_user") == "string_user"
        assert _user_name(None) == ""


class TestSampleContextFunctions:
    def test_journal_entry_sample_context_structure(self):
        ctx = build_journal_entry_sample_context()
        assert "company" in ctx
        assert "audit" in ctx
        assert "journal_entry" in ctx
        je = ctx["journal_entry"]
        assert je["number"] == "JOU-2026-00001"
        assert je["status"] == "posted"
        assert je["currency"] == "NIO"
        assert len(je["items"]) == 2
        assert je["total_debit"] == 1000.0
        assert je["total_credit"] == 1000.0

    def test_sales_invoice_sample_context_structure(self):
        ctx = build_sales_invoice_sample_context()
        assert "company" in ctx
        assert "invoice" in ctx
        inv = ctx["invoice"]
        assert inv["number"] == "FAC-2026-00001"
        assert "customer" in inv
        assert len(inv["items"]) == 1
        assert inv["grand_total"] == 1150.0
        assert "amount_in_words" in inv

    def test_purchase_order_sample_context_structure(self):
        ctx = build_purchase_order_sample_context()
        assert "company" in ctx
        assert "purchase_order" in ctx
        po = ctx["purchase_order"]
        assert po["number"] == "PO-2026-00001"
        assert "supplier" in po
        assert po["grand_total"] == 1150.0

    def test_payment_entry_sample_context_structure(self):
        ctx = build_payment_entry_sample_context()
        assert "company" in ctx
        assert "payment" in ctx
        pay = ctx["payment"]
        assert pay["number"] == "PAY-2026-00001"
        assert pay["status"] == "posted"
        assert pay["paid_amount"] == 1150.0
        assert len(pay["references"]) == 1

    def test_stock_entry_sample_context_structure(self):
        ctx = build_stock_entry_sample_context()
        assert "company" in ctx
        assert "adjustment" in ctx
        adj = ctx["adjustment"]
        assert adj["number"] == "STE-2026-00001"
        assert adj["purpose"] == "receipt"
        assert len(adj["items"]) == 1

    def test_exchange_revaluation_sample_context_structure(self):
        ctx = build_exchange_revaluation_sample_context()
        assert "company" in ctx
        assert "revaluation" in ctx
        rev = ctx["revaluation"]
        assert rev["number"] == "REV-2026-00001"
        assert rev["currency"] == "USD"
        assert len(rev["items"]) == 1
        assert rev["total_gain"] == 300.0
        assert rev["total_loss"] == 0.0

    def test_quotation_sample_context_structure(self):
        ctx = build_quotation_sample_context()
        assert "company" in ctx
        assert "quote" in ctx
        quo = ctx["quote"]
        assert quo["number"] == "QUO-2026-00001"
        assert "customer" in quo
        assert quo["grand_total"] == 1150.0


class TestPrintSchemas:
    def test_common_schema_has_required_fields(self):
        assert "company" in COMMON_SCHEMA
        assert "audit" in COMMON_SCHEMA
        company_fields = COMMON_SCHEMA["company"]
        assert "code" in company_fields
        assert "name" in company_fields
        assert "tax_id" in company_fields
        assert "default_currency" in company_fields
        audit_fields = COMMON_SCHEMA["audit"]
        assert "printed_by" in audit_fields
        assert "printed_at" in audit_fields

    def test_line_schema_has_required_fields(self):
        assert "line_number" in LINE_SCHEMA
        assert "item_code" in LINE_SCHEMA
        assert "description" in LINE_SCHEMA
        assert "quantity" in LINE_SCHEMA
        assert "unit_price" in LINE_SCHEMA
        assert "line_total" in LINE_SCHEMA

    def test_invoice_schema_extends_common_schema(self):
        assert "company" in INVOICE_SCHEMA
        assert "audit" in INVOICE_SCHEMA
        assert "invoice" in INVOICE_SCHEMA
        assert "items[]" in INVOICE_SCHEMA["invoice"]

    def test_journal_entry_print_schema_extends_common_schema(self):
        assert "company" in JOURNAL_ENTRY_PRINT_SCHEMA
        assert "journal_entry" in JOURNAL_ENTRY_PRINT_SCHEMA
        je_schema = JOURNAL_ENTRY_PRINT_SCHEMA["journal_entry"]
        assert "items[]" in je_schema
        assert "total_debit" in je_schema
        assert "total_credit" in je_schema

    def test_sales_invoice_print_schema_equals_invoice_schema(self):
        assert SALES_INVOICE_PRINT_SCHEMA == INVOICE_SCHEMA

    def test_purchase_invoice_print_schema_equals_invoice_schema(self):
        assert PURCHASE_INVOICE_PRINT_SCHEMA == INVOICE_SCHEMA

    def test_purchase_order_print_schema_has_items(self):
        assert "company" in PURCHASE_ORDER_PRINT_SCHEMA
        assert "purchase_order" in PURCHASE_ORDER_PRINT_SCHEMA
        assert "items[]" in PURCHASE_ORDER_PRINT_SCHEMA["purchase_order"]

    def test_delivery_note_print_schema_has_items(self):
        assert "company" in DELIVERY_NOTE_PRINT_SCHEMA
        assert "receipt" in DELIVERY_NOTE_PRINT_SCHEMA
        assert "items[]" in DELIVERY_NOTE_PRINT_SCHEMA["receipt"]

    def test_stock_entry_print_schema_has_items(self):
        assert "company" in STOCK_ENTRY_PRINT_SCHEMA
        assert "adjustment" in STOCK_ENTRY_PRINT_SCHEMA
        assert "items[]" in STOCK_ENTRY_PRINT_SCHEMA["adjustment"]

    def test_quotation_print_schema_has_items(self):
        assert "company" in QUOTATION_PRINT_SCHEMA
        assert "quote" in QUOTATION_PRINT_SCHEMA
        assert "items[]" in QUOTATION_PRINT_SCHEMA["quote"]

    def test_payment_entry_print_schema_has_references(self):
        assert "company" in PAYMENT_ENTRY_PRINT_SCHEMA
        assert "payment" in PAYMENT_ENTRY_PRINT_SCHEMA
        assert "references[]" in PAYMENT_ENTRY_PRINT_SCHEMA["payment"]

    def test_exchange_revaluation_print_schema_has_gain_loss(self):
        assert "company" in EXCHANGE_REVALUATION_PRINT_SCHEMA
        assert "revaluation" in EXCHANGE_REVALUATION_PRINT_SCHEMA
        rev_schema = EXCHANGE_REVALUATION_PRINT_SCHEMA["revaluation"]
        assert "total_gain" in rev_schema
        assert "total_loss" in rev_schema
        assert "items[]" in rev_schema


class TestSamplePartyAndLineHelpers:
    def test_sample_common_context_has_all_company_fields(self):
        from cacao_accounting.printing.context import _sample_common_context

        ctx = _sample_common_context()
        assert ctx["company"]["code"] == "cacao"
        assert ctx["company"]["name"] == "Example Company S.A."
        assert ctx["company"]["tax_id"] == "J0310000000001"
        assert ctx["company"]["default_currency"] == "NIO"
        assert "printed_by" in ctx["audit"]

    def test_sample_party_has_required_fields(self):
        from cacao_accounting.printing.context import _sample_party

        party = _sample_party()
        assert party["code"] == "CUST-001"
        assert party["legal_name"] == "Example Customer S.A."
        assert party["tax_id"] == "J0310000000002"

    def test_sample_line_has_all_amount_fields(self):
        from cacao_accounting.printing.context import _sample_line

        line = _sample_line()
        assert line["line_number"] == 1
        assert line["quantity"] == 2.0
        assert line["unit_price"] == 500.0
        assert line["subtotal"] == 1000.0
        assert line["taxes"] == 150.0
        assert line["line_total"] == 1150.0
