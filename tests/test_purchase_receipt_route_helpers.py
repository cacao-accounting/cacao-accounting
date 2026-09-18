# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de caracterizacion de los helpers del formulario de recepcion."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.compras import routes as receipt_routes


def test_receipt_available_source_types_switch():
    """A return offers the original receipt; a regular receipt offers the order."""
    assert receipt_routes._receipt_available_source_types(True) == [
        {"value": "purchase_receipt", "label": "Recepción original"}
    ]
    assert [option["value"] for option in receipt_routes._receipt_available_source_types(False)] == ["purchase_order"]


def test_resolve_receipt_selected_company_prefers_sources():
    """The receipt source company wins over the form default."""
    formulario = SimpleNamespace(company=SimpleNamespace(choices=[]))
    assert receipt_routes._resolve_receipt_selected_company(SimpleNamespace(company="COMP-A"), None, formulario) == "COMP-A"
    assert receipt_routes._resolve_receipt_selected_company(None, SimpleNamespace(company="COMP-B"), formulario) == "COMP-B"


def test_receipt_initial_header_defaults_without_source():
    """Without a source document the header only carries company and today."""
    header = receipt_routes._receipt_initial_header(None, None, "COMP")
    assert header["company"] == "COMP"
    assert header["posting_date"]


def test_receipt_initial_header_uses_source_currency(monkeypatch):
    """A source document contributes its currency, party and label."""
    monkeypatch.setattr(receipt_routes, "effective_currency", lambda _source: "USD")
    source = SimpleNamespace(company="COMP", supplier_id="SUP", supplier_name="Proveedor")

    header = receipt_routes._receipt_initial_header(None, source, "COMP")

    assert header["currency"] == "USD"
    assert header["transaction_currency"] == "USD"
    assert header["party"] == "SUP"
    assert header["party_label"] == "Proveedor"


def test_receipt_initial_header_prefers_order_over_receipt(monkeypatch):
    """When both sources exist the purchase order overrides the receipt, as before."""
    monkeypatch.setattr(receipt_routes, "effective_currency", lambda source: source.cur)
    receipt = SimpleNamespace(company="C1", supplier_id="S1", supplier_name="R", cur="USD")
    order = SimpleNamespace(company="C2", supplier_id="S2", supplier_name="O", cur="NIO")

    header = receipt_routes._receipt_initial_header(receipt, order, "C1")

    assert header["company"] == "C2"
    assert header["currency"] == "NIO"


def test_receipt_transaction_config_marks_return():
    """A return config exposes the original receipt as the only source type."""
    config = receipt_routes._receipt_transaction_config(
        company_id="COMP",
        is_return=True,
        from_order_id=None,
        items=[],
        uoms=[],
        bodegas=[],
        initial_header={"company": "COMP"},
    )

    assert config["initialSourceType"] == "purchase_receipt"
    assert config["availableSourceTypes"][0]["value"] == "purchase_receipt"
    assert config["formKey"] == receipt_routes.FORMKEY_PURCHASE_RECEIPT
