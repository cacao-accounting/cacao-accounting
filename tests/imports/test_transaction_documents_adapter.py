# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas focales para el adaptador de documentos transaccionales."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.imports.adapters.transaction_documents import (
    TransactionDocumentAdapter,
    TransactionImportConfig,
)


class _DummyItem:
    """Objeto mínimo para validar asignaciones opcionales del adaptador."""

    def __init__(self) -> None:
        self.rate = Decimal("12.50")
        self.base_amount = Decimal("0")
        self.base_rate = Decimal("0")
        self.valuation_rate = Decimal("0")
        self.received_qty = Decimal("9")
        self.billed_qty = Decimal("8")
        self.batch_id = "old-batch"
        self.serial_no = "old-serial"


class _DummyHeader:
    """Encabezado mínimo para verificar conversión de moneda importada."""

    def __init__(self, **values):
        self.__dict__.update(values)
        self.total = None
        self.base_total = None
        self.grand_total = None
        self.base_grand_total = None


class _ImportItem:
    """Línea mínima con campos transaccionales y funcionales."""

    def __init__(self, **values):
        self.__dict__.update(values)
        self.base_amount = Decimal("0")
        self.base_rate = Decimal("0")
        self.valuation_rate = Decimal("0")


def test_optional_item_fields_are_applied_consistently() -> None:
    """El adaptador llena los campos opcionales sin mezclar la lógica."""

    adapter = TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_order",
            header_model=object,
            item_model=object,
            parent_field="purchase_order_id",
            receipt_fields=("received_qty",),
            invoice_fields=("billed_qty",),
            include_batch_serial=True,
        )
    )
    item = _DummyItem()

    adapter._apply_optional_item_fields(  # noqa: SLF001
        item,
        Decimal("31.25"),
        {"lote": "LOT-001", "serie": "SER-009"},
    )

    assert item.base_amount == Decimal("31.25")
    assert item.base_rate == Decimal("12.50")
    assert item.valuation_rate == Decimal("12.50")
    assert item.received_qty == Decimal("0")
    assert item.billed_qty == Decimal("0")
    assert item.batch_id == "LOT-001"
    assert item.serial_no == "SER-009"


def test_build_document_keeps_transaction_and_base_amounts(monkeypatch) -> None:
    """El importador calcula importes base con la tasa declarada por el lote."""
    from importlib import import_module

    module = import_module("cacao_accounting.imports.adapters.transaction_documents")

    monkeypatch.setattr(module, "company_currency", lambda _company: "NIO")
    adapter = TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_order",
            header_model=_DummyHeader,
            item_model=_ImportItem,
            parent_field="purchase_order_id",
        )
    )

    document = adapter.build_document(
        [
            {
                "document_ref": "PO-USD-001",
                "fecha": "2026-08-19",
                "moneda": "USD",
                "tipo_cambio": "36.5",
                "producto": "ITEM-1",
                "cantidad": "2",
                "precio_unitario": "100",
            }
        ],
        {"company_id": "cacao"},
    )

    assert document["header"].transaction_currency == "USD"
    assert document["header"].base_currency == "NIO"
    assert document["header"].exchange_rate == Decimal("36.5")
    assert document["header"].total == Decimal("200")
    assert document["header"].base_total == Decimal("7300.0000")
    assert document["items"][0].base_amount == Decimal("7300.0000")
    assert document["items"][0].base_rate == Decimal("3650.0000")
