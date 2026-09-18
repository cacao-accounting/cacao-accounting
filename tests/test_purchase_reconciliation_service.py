# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Unit tests for purchase-reconciliation allocation helpers."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.compras import purchase_reconciliation_service as service
from cacao_accounting.document_flow import payment as payment_service


@pytest.mark.parametrize("order_mode", [False, True])
def test_available_line_slices_distributes_invoice_across_source_lines(monkeypatch, order_mode):
    """An invoice group consumes each compatible line instead of only the first."""
    lines = [SimpleNamespace(id="first", qty=Decimal("5")), SimpleNamespace(id="second", qty=Decimal("5"))]
    monkeypatch.setattr(service, "_line_qty", lambda line: line.qty)
    monkeypatch.setattr(service, "_matched_qty_for_receipt_item", lambda _line_id: Decimal("0"))
    monkeypatch.setattr(service, "_matched_qty_for_order_item", lambda _line_id: Decimal("0"))

    slices = service._available_line_slices(lines, Decimal("8"), order_mode=order_mode)

    assert [(line.id, qty) for line, qty in slices] == [("first", Decimal("5")), ("second", Decimal("3"))]


def test_payment_candidates_use_invoice_transaction_currency(monkeypatch):
    """Modern invoices must not bypass payment-candidate currency filtering."""
    invoice = SimpleNamespace(
        id="INV-EUR",
        posting_date=None,
        document_no=None,
        transaction_currency="EUR",
        base_currency="NIO",
        grand_total=Decimal("1000"),
    )

    monkeypatch.setattr(payment_service, "_payment_candidate_outstanding", lambda _document, _type: Decimal("1000"))
    candidate = payment_service._build_candidate_row(invoice, "purchase_invoice", "supplier", "SUP-1", "cacao")

    assert candidate["currency"] == "EUR"
    assert payment_service._filter_candidates_by_currency([candidate], "USD") == []
    assert payment_service._filter_candidates_by_currency([candidate], "EUR") == [candidate]


def test_reconcile_two_way_incompatible_item_raises_purchase_reconciliation_error(monkeypatch):
    """When a 2-way invoice has an item without a matching PO group, raise PurchaseReconciliationError."""
    invoice = SimpleNamespace(
        id="INV-1",
        company="cacao",
        posting_date=None,
    )
    po_obj = SimpleNamespace(id="PO-1")
    config = service.MatchingConfig(
        matching_type="2-way",
        price_tolerance_type="percentage",
        price_tolerance_value=Decimal("0"),
        qty_tolerance_type="percentage",
        qty_tolerance_value=Decimal("0"),
        require_purchase_order=True,
        bridge_account_required=True,
        auto_reconcile=True,
        allow_price_difference=False,
    )

    po_line = SimpleNamespace(id="PO-L1", item_code="ITEM-A", uom="UN", warehouse="WH1", qty=Decimal("10"), rate=Decimal("50"))
    inv_line = SimpleNamespace(
        id="INV-L1", item_code="ITEM-B", uom="UN", warehouse="WH1", qty=Decimal("10"), rate=Decimal("50")
    )

    monkeypatch.setattr(service, "_load_purchase_order_for_invoice", lambda _inv: ("PO-1", po_obj))
    monkeypatch.setattr(service, "_lock_purchase_order_items", lambda _po_id: [po_line])
    monkeypatch.setattr(service, "_invoice_items", lambda _inv_id: [inv_line])
    monkeypatch.setattr(service, "_normalized_line_uom", lambda line: line.uom)
    monkeypatch.setattr(service, "database", SimpleNamespace(session=SimpleNamespace(add=lambda x: None, flush=lambda: None)))

    msg = "No existe l[i\u00ed]nea de OC compatible para el [i\u00ed]tem ITEM-B"
    with pytest.raises(service.PurchaseReconciliationError, match=msg):
        service._reconcile_two_way(invoice, config)


def test_allocatable_invoices_returns_empty_without_invoice_or_order():
    """A receipt without explicit invoice or purchase order cannot allocate."""
    receipt = SimpleNamespace(purchase_order_id=None)
    assert service._allocatable_invoices(receipt, None) == []


def test_assert_same_transaction_currency_rejects_mismatch():
    """An invoice and receipt in different currencies must not be allocated."""
    invoice = SimpleNamespace(transaction_currency="USD")
    receipt = SimpleNamespace(transaction_currency="NIO")
    with pytest.raises(service.PurchaseReconciliationError):
        service._assert_same_transaction_currency(invoice, receipt)


def test_assert_same_transaction_currency_allows_missing_or_equal():
    """Missing or matching currencies are accepted."""
    service._assert_same_transaction_currency(
        SimpleNamespace(transaction_currency="USD"), SimpleNamespace(transaction_currency="USD")
    )
    service._assert_same_transaction_currency(
        SimpleNamespace(transaction_currency=None), SimpleNamespace(transaction_currency="NIO")
    )


def test_receipt_item_allocatable_qty_respects_remaining(monkeypatch):
    """The allocatable qty is bounded by the invoice demand and receipt remainder."""
    item = SimpleNamespace(id="R1")
    monkeypatch.setattr(service, "_item_qty_in_base_uom", lambda _line: Decimal("10"))
    monkeypatch.setattr(service, "_allocated_receipt_qty", lambda _item_id: Decimal("4"))
    assert service._receipt_item_allocatable_qty(item, Decimal("20")) == Decimal("6")

    monkeypatch.setattr(service, "_allocated_receipt_qty", lambda _item_id: Decimal("10"))
    assert service._receipt_item_allocatable_qty(item, Decimal("20")) is None


def test_build_invoice_receipt_allocation_computes_variance(monkeypatch):
    """Price and exchange variances follow the documented base-currency formulas."""
    receipt = SimpleNamespace(company="cacao", transaction_currency="USD", base_currency="NIO", exchange_rate=Decimal("36"))
    invoice = SimpleNamespace(transaction_currency="USD", base_currency="NIO", exchange_rate=Decimal("37"))
    receipt_item = SimpleNamespace(id="R1")
    invoice_item = SimpleNamespace(id="I1")
    monkeypatch.setattr(service, "_item_qty_in_base_uom", lambda _line: Decimal("10"))
    monkeypatch.setattr(service, "_line_amount", lambda line: Decimal("100") if line is receipt_item else Decimal("110"))

    row = service._build_invoice_receipt_allocation(receipt, invoice, receipt_item, invoice_item, Decimal("5"))

    assert row.qty_in_base_uom == Decimal("5")
    assert row.receipt_amount == Decimal("50")
    assert row.invoice_amount == Decimal("55")
    assert row.receipt_base_amount == Decimal("1800")
    assert row.invoice_base_amount == Decimal("2035")
    assert row.price_variance_base == Decimal("185")
    assert row.exchange_variance_base == Decimal("50")
    assert row.transaction_currency == "USD"
    assert row.status == "active"


def test_allocate_invoice_lines_consumes_multiple_receipt_lines(monkeypatch):
    """A single invoice line is satisfied across consecutive receipt lines."""
    receipt = SimpleNamespace(company="cacao", transaction_currency="USD", base_currency="NIO", exchange_rate=Decimal("1"))
    invoice = SimpleNamespace(id="INV", transaction_currency="USD", base_currency="NIO", exchange_rate=Decimal("1"))
    invoice_item = SimpleNamespace(id="II", item_code="IT", qty=Decimal("8"))
    first_receipt_item = SimpleNamespace(id="R1", item_code="IT", qty=Decimal("5"))
    second_receipt_item = SimpleNamespace(id="R2", item_code="IT", qty=Decimal("5"))
    added = []
    monkeypatch.setattr(service, "_invoice_items", lambda _invoice_id: [invoice_item])
    monkeypatch.setattr(service, "_item_qty_in_base_uom", lambda line: line.qty)
    monkeypatch.setattr(service, "_allocated_invoice_qty", lambda _item_id: Decimal("0"))
    monkeypatch.setattr(service, "_allocated_receipt_qty", lambda _item_id: Decimal("0"))
    monkeypatch.setattr(service, "_line_amount", lambda line: line.qty * Decimal("10"))
    monkeypatch.setattr(service, "database", SimpleNamespace(session=SimpleNamespace(add=added.append, flush=lambda: None)))

    allocations = service._allocate_invoice_lines(receipt, invoice, [first_receipt_item, second_receipt_item])

    assert [(row.receipt_item_id, row.qty_in_base_uom) for row in allocations] == [
        ("R1", Decimal("5")),
        ("R2", Decimal("3")),
    ]
    assert len(added) == 2
