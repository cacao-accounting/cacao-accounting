"""Regression coverage for party dimensions on purchase-receipt inventory entries."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.posting_service import LedgerContext


def test_purchase_receipt_inventory_entries_do_not_receive_supplier_dimension(monkeypatch) -> None:
    """Keep party dimensions for AP, not inventory or the GR/IR bridge."""
    app = create_app({**configuracion, "TESTING": True})
    with app.app_context():
        calls: list[dict] = []
        line = SimpleNamespace(item_code="ITEM-1", qty=Decimal("2"), rate=Decimal("5"), amount=Decimal("10"))
        receipt = SimpleNamespace(supplier_id="SUP-1", is_return=False, company="cacao")
        ledger_context = LedgerContext(
            company="cacao",
            posting_date=None,
            ledger_id="LEDGER",
            voucher_type="purchase_receipt",
            voucher_id="PR-1",
            document_no="PR-2026-0001",
            naming_series_id=None,
            accounting_period_id=None,
            fiscal_year_id=None,
            transaction_currency=None,
            company_currency=None,
            document_base_currency=None,
            exchange_rate=Decimal("1"),
            document_remarks=None,
        )

        monkeypatch.setattr(posting_service, "_document_contexts", lambda _document, ledger_code=None: [ledger_context])
        monkeypatch.setattr(posting_service, "_document_items", lambda _document: [line])
        monkeypatch.setattr(posting_service, "_should_skip_non_stock_line", lambda _line: False)
        monkeypatch.setattr(posting_service, "_line_qty_generic", lambda _line: Decimal("2"))
        monkeypatch.setattr(posting_service, "_line_rate_generic", lambda _line: Decimal("5"))
        monkeypatch.setattr(posting_service, "_warehouse_inventory_account_id", lambda *_args: "INVENTORY")
        monkeypatch.setattr(posting_service, "_require_account", lambda account_id, _message: account_id)
        monkeypatch.setattr(posting_service, "_add_entries", lambda entries: entries)

        def record_entries(**kwargs):
            calls.append(kwargs)
            return ["entry"]

        monkeypatch.setattr(posting_service, "_normal_entries_for_amount", record_entries)

        posting_service._build_purchase_receipt_ledger_entries(receipt, "cacao", "BRIDGE", None)

    assert calls == [
        {
            "context": ledger_context,
            "debit_account_id": "INVENTORY",
            "credit_account_id": "BRIDGE",
            "amount": Decimal("10"),
            "debit_remarks": "Recepción de compra",
            "credit_remarks": "Cuenta puente compras",
        }
    ]
