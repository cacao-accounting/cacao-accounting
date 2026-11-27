# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1223: purchase notes must follow their source invoice's links and currency."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.compras import services
from cacao_accounting.database import (
    Currency,
    Party,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseReceipt,
    database,
)


@pytest.fixture
def purchase_note_sources(entorno_contable_aislado):
    """Create one invoice flow and unrelated same-company purchase sources."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    with app.app_context():
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        for code in ("USD", "EUR"):
            currency = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
            if currency is None:
                database.session.add(Currency(code=code, name=code, decimals=2, active=True, default=False))
        database.session.flush()
        source_order = PurchaseOrder(
            company="cacao",
            posting_date=date(2026, 5, 1),
            docstatus=1,
            document_no=f"PO-NOTE-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_order = PurchaseOrder(
            company="cacao",
            posting_date=date(2026, 5, 1),
            docstatus=1,
            document_no=f"PO-OTHER-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        database.session.add_all([source_order, unrelated_order])
        database.session.flush()
        original_receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 5),
            docstatus=1,
            document_no=f"PR-NOTE-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=source_order.id,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_usd_receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 6),
            docstatus=1,
            document_no=f"PR-USD-OTHER-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_eur_receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 6),
            docstatus=1,
            document_no=f"PR-EUR-OTHER-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="EUR",
            base_currency="NIO",
        )
        database.session.add_all([original_receipt, unrelated_usd_receipt, unrelated_eur_receipt])
        database.session.flush()
        source_invoice = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"PI-NOTE-{suffix}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=source_order.id,
            purchase_receipt_id=original_receipt.id,
            transaction_currency="USD",
            base_currency="NIO",
        )
        database.session.add(source_invoice)
        database.session.commit()
        return {
            "app": app,
            "supplier_id": str(supplier.id),
            "invoice_id": str(source_invoice.id),
            "order_id": str(source_order.id),
            "unrelated_order_id": str(unrelated_order.id),
            "receipt_id": str(original_receipt.id),
            "unrelated_usd_receipt_id": str(unrelated_usd_receipt.id),
            "unrelated_eur_receipt_id": str(unrelated_eur_receipt.id),
        }


def _bypass_unrelated_creation_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep source-link tests focused on the invoice-flow invariant."""
    monkeypatch.setattr(services, "_require_purchase_document_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "exige_acceso_compania", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_purchase_tax_template", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_supplier_company_membership", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_supplier_invoice_flags", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_duplicate_supplier_invoice", lambda *args, **kwargs: None)


def _note_form_data(sources: dict[str, str], **overrides: str) -> dict[str, str]:
    """Build the minimal posted form values needed by the creation context."""
    data = {
        "company": "cacao",
        "supplier_id": sources["supplier_id"],
        "posting_date": "2026-05-20",
        "document_type": "purchase_credit_note",
        "credit_note_type": "commercial_adjustment",
        "from_invoice": sources["invoice_id"],
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("receipt_currency", ["EUR", "USD"], ids=["foreign-currency", "same-currency"])
def test_unrelated_receipt_cannot_be_combined_with_source_invoice(
    purchase_note_sources,
    monkeypatch,
    receipt_currency,
):
    """A receipt is rejected when it is not linked to the reversal invoice, even at same currency."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    receipt_id = sources[f"unrelated_{receipt_currency.lower()}_receipt_id"]
    app = sources["app"]

    with (
        app.app_context(),
        app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data=_note_form_data(sources, from_receipt=receipt_id),
        ),
    ):
        invoice_count_before = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()
        result = services._create_purchase_invoice_from_request()
        invoice_count_after = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()

    assert result is None
    assert invoice_count_after == invoice_count_before


def test_unrelated_order_cannot_be_combined_with_source_invoice(purchase_note_sources, monkeypatch):
    """Matching supplier, company and currency do not make another order part of an invoice."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data=_note_form_data(sources, from_order=sources["unrelated_order_id"]),
        ),
    ):
        invoice_count_before = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()
        result = services._create_purchase_invoice_from_request()
        invoice_count_after = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()

    assert result is None
    assert invoice_count_after == invoice_count_before


def test_valid_note_uses_source_invoice_currency_and_links(purchase_note_sources, monkeypatch):
    """Valid note defaults come from the invoice, not an independently selected source."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data=_note_form_data(sources),
        ),
    ):
        context = services._purchase_invoice_creation_context()

    assert context["source"].id == sources["invoice_id"]
    assert context["transaction_currency"] == "USD"
    assert context["from_order"] == sources["order_id"]
    assert context["from_receipt"] == sources["receipt_id"]
