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
