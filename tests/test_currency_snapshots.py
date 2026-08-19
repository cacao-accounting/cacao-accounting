# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas unitarias para snapshots de moneda e importes funcionales."""

from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace


def test_purchase_receipt_totals_recalculate_functional_snapshot(monkeypatch):
    """La edición de recepción debe recalcular tasa y total funcional."""
    compras = import_module("cacao_accounting.compras.services")
    monkeypatch.setattr(compras, "company_currency", lambda _company: "USD")
    monkeypatch.setattr(compras, "_purchase_exchange_rate", lambda *_args: Decimal("2"))
    receipt = SimpleNamespace(company="cacao", posting_date=None, transaction_currency="EUR")

    compras._set_purchase_receipt_totals(receipt, Decimal("150"))

    assert receipt.exchange_rate == Decimal("2")
    assert receipt.base_currency == "USD"
    assert receipt.total == receipt.grand_total == Decimal("150")
    assert receipt.base_total == Decimal("300.0000")


def test_sales_invoice_totals_preserve_source_currency_and_rate(monkeypatch):
    """Una factura derivada conserva la moneda y tasa histórica de su origen."""
    ventas = import_module("cacao_accounting.ventas.services")
    monkeypatch.setattr(ventas, "company_currency", lambda _company: "USD")
    invoice = SimpleNamespace(
        company="cacao",
        posting_date=None,
        transaction_currency=None,
        base_currency=None,
        exchange_rate=None,
    )
    source = SimpleNamespace(transaction_currency="EUR", exchange_rate=Decimal("1.10"))

    ventas._set_sales_invoice_totals(invoice, Decimal("100"), Decimal("100"), source)

    assert invoice.transaction_currency == "EUR"
    assert invoice.base_currency == "USD"
    assert invoice.exchange_rate == Decimal("1.10")
    assert invoice.base_total == Decimal("110.0000")
    assert invoice.base_grand_total == Decimal("110.0000")
    assert invoice.base_outstanding_amount == Decimal("110.0000")
