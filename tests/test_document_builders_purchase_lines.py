# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de caracterizacion de las lineas de factura de compra.

Cubren las ramas de resolucion de cuenta puente, porcion no recibida y
variacion de liquidacion de `_purchase_invoice_account_lines` sin depender
de la base de datos: los helpers de acceso a datos se sustituyen para
ejercitar cada camino de forma aislada.
"""

from __future__ import annotations

import types
from decimal import Decimal

import pytest

from cacao_accounting.accounting_engine import document_builders as builders


class _Defaults:
    """Doble de CompanyDefaultAccount para las cuentas puente y variacion."""

    def __init__(self, bridge: str | None = "BRIDGE", variance: str | None = "VARIANCE") -> None:
        self.bridge_account_id = bridge
        self.purchase_settlement_variance_account_id = variance


def _document(*, has_receipt: bool = False, is_credit_note: bool = False, credit_note_type: str | None = None):
    return types.SimpleNamespace(
        document_type="purchase_credit_note" if is_credit_note else "purchase_invoice",
        is_return=is_credit_note,
        credit_note_type=credit_note_type,
        supplier_id="SUP",
        _has_receipt=has_receipt,
        _is_credit_note=is_credit_note,
    )


def _item(amount: str, receipt: str = "0", invoice: str = "0", name: str = "Item", code: str = "I1"):
    return types.SimpleNamespace(
        id=f"item-{code}",
        item_name=name,
        item_code=code,
        amount=Decimal(amount),
        _alloc=(Decimal(receipt), Decimal(invoice)),
    )


@pytest.fixture
def patched_helpers(monkeypatch):
    """Sustituye los helpers de datos por valores controlados."""

    def fake_company_defaults(company: str) -> _Defaults:
        return _Defaults()

    def fake_require_account_id(account_id: str | None, message: str) -> str:
        if not account_id:
            raise builders.CalculationContextBuilderError(message)
        return str(account_id)

    def fake_item_account_for_line(line, company, account_type):
        return {
            "expense": "EXPENSE",
            "purchase_settlement_variance": "ITEM_VARIANCE",
            "bridge": "ITEM_BRIDGE",
        }.get(account_type)

    def fake_line_amount(line) -> Decimal:
        return builders._decimal_value(getattr(line, "amount", None))

    def fake_allocations(item):
        return getattr(item, "_alloc", (Decimal("0"), Decimal("0")))

    def fake_has_receipt(document, company) -> bool:
        return bool(getattr(document, "_has_receipt", False))

    def fake_is_credit_note(document) -> bool:
        return bool(getattr(document, "_is_credit_note", False))

    monkeypatch.setattr(builders, "_company_defaults", fake_company_defaults)
    monkeypatch.setattr(builders, "_require_account_id", fake_require_account_id)
    monkeypatch.setattr(builders, "_item_account_for_line", fake_item_account_for_line)
    monkeypatch.setattr(builders, "_line_amount", fake_line_amount)
    monkeypatch.setattr(builders, "_invoice_receipt_allocation_amounts", fake_allocations)
    monkeypatch.setattr(builders, "_purchase_invoice_has_receipt", fake_has_receipt)
    monkeypatch.setattr(builders, "_is_purchase_credit_note", fake_is_credit_note)


def test_expense_line_without_receipt(patched_helpers):
    document = _document()
    specs = builders._purchase_invoice_account_lines(document, [_item("100")], "cacao")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [("EXPENSE", Decimal("100"), "debit")]


def test_credit_note_physical_return_uses_bridge(patched_helpers):
    document = _document(has_receipt=True, is_credit_note=True, credit_note_type="physical_return")
    specs = builders._purchase_invoice_account_lines(document, [_item("50", receipt="50", invoice="50")], "cacao")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [("BRIDGE", Decimal("50"), "credit")]


def test_commercial_adjustment_without_bridge_uses_variance_account(patched_helpers):
    document = _document(is_credit_note=True)
    specs = builders._purchase_invoice_account_lines(document, [_item("100")], "cacao")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [("ITEM_VARIANCE", Decimal("100"), "credit")]


def test_bridge_positive_variance_uses_debit(patched_helpers):
    document = _document(has_receipt=True)
    specs = builders._purchase_invoice_account_lines(document, [_item("100", receipt="60", invoice="100")], "cacao")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [
        ("BRIDGE", Decimal("60"), "debit"),
        ("VARIANCE", Decimal("40"), "debit"),
    ]


def test_bridge_negative_variance_and_unreceived_portion(patched_helpers):
    document = _document(has_receipt=True)
    specs = builders._purchase_invoice_account_lines(document, [_item("100", receipt="100", invoice="60")], "cacao")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [
        ("BRIDGE", Decimal("100"), "debit"),
        ("EXPENSE", Decimal("40"), "debit"),
        ("VARIANCE", Decimal("40"), "credit"),
    ]


def test_bridge_variance_requires_configured_account(patched_helpers, monkeypatch):
    document = _document(has_receipt=True)
    monkeypatch.setattr(builders, "_company_defaults", lambda company: _Defaults(variance=None))
    with pytest.raises(builders.CalculationContextBuilderError):
        builders._purchase_invoice_account_lines(document, [_item("100", receipt="60", invoice="100")], "cacao")


def test_non_positive_line_amount_is_skipped(patched_helpers):
    document = _document()
    assert builders._purchase_invoice_account_lines(document, [_item("0")], "cacao") == []


def test_receipt_reclassification_with_allocation_adds_variance(patched_helpers):
    document = _document(has_receipt=True)
    item = _item("100", receipt="60", invoice="100")
    late_amounts = {"I1": Decimal("100")}
    specs, reclassified = builders._receipt_reclassification_specs(
        document, item, "cacao", Decimal("100"), (Decimal("60"), Decimal("100")), late_amounts, "VARIANCE"
    )
    assert reclassified == Decimal("100")
    assert late_amounts["I1"] == Decimal("0")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [
        ("EXPENSE", Decimal("100"), "credit"),
        ("VARIANCE", Decimal("40"), "debit"),
    ]


def test_receipt_reclassification_without_allocation_consumes_late_amount(patched_helpers):
    document = _document()
    item = _item("100")
    late_amounts = {"I1": Decimal("30")}
    specs, reclassified = builders._receipt_reclassification_specs(
        document, item, "cacao", Decimal("100"), (Decimal("0"), Decimal("0")), late_amounts, "VARIANCE"
    )
    assert reclassified == Decimal("30")
    assert late_amounts["I1"] == Decimal("0")
    assert [(spec.account_id, spec.amount, spec.side) for spec in specs] == [("EXPENSE", Decimal("30"), "credit")]


def test_receipt_reclassification_variance_requires_account(patched_helpers):
    document = _document(has_receipt=True)
    item = _item("100", receipt="60", invoice="100")
    with pytest.raises(builders.CalculationContextBuilderError):
        builders._receipt_reclassification_specs(
            document, item, "cacao", Decimal("100"), (Decimal("60"), Decimal("100")), {}, None
        )


def test_receipt_bridge_line_covers_unallocated_remainder(patched_helpers):
    document = _document()
    item = _item("100")
    bridge = builders._receipt_bridge_line(
        document, item, Decimal("100"), (Decimal("0"), Decimal("0")), Decimal("30"), "BRIDGE", "credit"
    )
    assert bridge is not None
    assert (bridge.account_id, bridge.amount, bridge.side) == ("BRIDGE", Decimal("70"), "credit")


def test_receipt_bridge_line_returns_none_without_remainder(patched_helpers):
    document = _document(has_receipt=True)
    item = _item("100", receipt="100", invoice="100")
    bridge = builders._receipt_bridge_line(
        document, item, Decimal("100"), (Decimal("100"), Decimal("100")), Decimal("100"), "BRIDGE", "credit"
    )
    assert bridge is None
