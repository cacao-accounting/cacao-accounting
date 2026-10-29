# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas focales para el adaptador de documentos transaccionales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Entity,
    Item,
    ItemUOMConversion,
    PurchaseOrder,
    PurchaseOrderItem,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.inventario.service import InventoryServiceError, item_qty_in_base_uom
from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter
from cacao_accounting.imports.adapters.transaction_documents import PurchaseOrderAdapter as TransactionPurchaseOrderAdapter
from cacao_accounting.imports.adapters.transaction_documents import (
    TransactionDocumentAdapter,
    TransactionImportConfig,
)
from cacao_accounting.imports.services.import_service import ImportService


@pytest.fixture()
def app_ctx():
    """Provide an isolated database for import adapter validation tests."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with app.app_context():
        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        yield app
        database.session.remove()


def test_purchase_order_import_rejects_foreign_warehouse(app_ctx) -> None:
    """Purchase order imports cannot reference a warehouse from another company."""
    with app_ctx.app_context():
        database.session.add(Entity(code="cafe", name="Café", company_name="Café", tax_id="T-IMPORT-CAFE", currency="NIO"))
        database.session.add(Warehouse(code="WH-CAFE-IMPORT", name="Café", company="cafe"))
        database.session.commit()

        errors = PurchaseOrderAdapter().validate_document(
            [
                {
                    "document_ref": "PO-IMPORT-FOREIGN-WH",
                    "fecha": date.today().isoformat(),
                    "proveedor": "SUP-1",
                    "producto": "ITEM-1",
                    "cantidad": "1",
                    "precio_unitario": "1",
                    "bodega": "WH-CAFE-IMPORT",
                }
            ],
            {"company_id": "cacao"},
        )

    assert any("no pertenece a la compañía" in error for error in errors)


def test_purchase_order_import_preserves_currency_and_base_amounts(app_ctx, monkeypatch) -> None:
    """Purchase order imports retain their foreign-currency conversion context."""
    from cacao_accounting.imports.adapters import purchase_order

    monkeypatch.setattr(purchase_order, "company_currency", lambda _company: "NIO")
    with app_ctx.app_context():
        database.session.add(UOM(code="UND-IMPORT", name="Unidad"))
        database.session.add(Item(code="ITEM-1", name="Artículo importado", item_type="goods", default_uom="UND-IMPORT"))
        database.session.flush()
        document = PurchaseOrderAdapter().build_document(
            [
                {
                    "document_ref": "PO-IMPORT-USD",
                    "fecha": date.today().isoformat(),
                    "moneda": "USD",
                    "tipo_cambio": "36.5",
                    "proveedor": "SUP-1",
                    "producto": "ITEM-1",
                    "cantidad": "2",
                    "precio_unitario": "10",
                }
            ],
            {"company_id": "cacao"},
        )

    order = document["order"]
    item = document["items"][0]
    assert order.transaction_currency == "USD"
    assert order.base_currency == "NIO"
    assert order.exchange_rate == Decimal("36.5")
    assert order.base_total == Decimal("730.0000")
    assert item.base_amount == Decimal("730.0000")


def test_transaction_document_import_converts_quantity_to_item_base_uom(app_ctx, monkeypatch) -> None:
    """El adaptador guarda la cantidad base aunque el archivo use otra UOM."""
    from cacao_accounting.imports.adapters import transaction_documents

    monkeypatch.setattr(transaction_documents, "company_currency", lambda _company: "NIO")
    with app_ctx.app_context():
        database.session.add_all(
            [
                UOM(code="UND-BASE", name="Unidad"),
                UOM(code="BOX-IMPORT", name="Caja"),
                Item(
                    code="ITEM-UOM-IMPORT",
                    name="Artículo con conversión",
                    item_type="goods",
                    default_uom="UND-BASE",
                ),
                ItemUOMConversion(
                    item_code="ITEM-UOM-IMPORT",
                    from_uom="BOX-IMPORT",
                    to_uom="UND-BASE",
                    conversion_factor=10,
                ),
            ]
        )
        database.session.flush()
        adapter = TransactionDocumentAdapter(
            TransactionImportConfig(
                entity_type="purchase_order",
                header_model=PurchaseOrder,
                item_model=PurchaseOrderItem,
                parent_field="purchase_order_id",
            )
        )
        document = adapter.build_document(
            [
                {
                    "document_ref": "PO-UOM-IMPORT",
                    "fecha": date.today().isoformat(),
                    "moneda": "NIO",
                    "producto": "ITEM-UOM-IMPORT",
                    "uom": "BOX-IMPORT",
                    "cantidad": "2",
                    "precio_unitario": "5",
                }
            ],
            {"company_id": "cacao"},
        )
        assert item_qty_in_base_uom("ITEM-UOM-IMPORT", Decimal("0"), None) == Decimal("0")

    assert document["items"][0].qty == Decimal("2")
    assert document["items"][0].qty_in_base_uom == Decimal("20")


def test_item_base_quantity_rejects_non_finite_values(app_ctx) -> None:
    """La conversión rechaza valores numéricos no finitos."""
    with app_ctx.app_context(), pytest.raises(InventoryServiceError, match="debe ser finita"):
        item_qty_in_base_uom("ITEM-MISSING", Decimal("NaN"), None)


def test_item_base_quantity_requires_existing_item(app_ctx) -> None:
    """La conversión exige un artículo existente para consultar su UOM base."""
    with app_ctx.app_context():
        with pytest.raises(InventoryServiceError, match="requiere un artículo"):
            item_qty_in_base_uom(None, Decimal("1"), None)
        with pytest.raises(InventoryServiceError, match="no existe o no tiene UOM base"):
            item_qty_in_base_uom("ITEM-MISSING", Decimal("1"), None)


def test_item_base_quantity_requires_configured_conversion(app_ctx) -> None:
    """La conversión entre UOM solo procede con un factor explícito."""
    with app_ctx.app_context():
        database.session.add_all(
            [
                UOM(code="UND-CONVERT", name="Unidad"),
                UOM(code="BOX-CONVERT", name="Caja"),
                Item(code="ITEM-NO-CONVERSION", name="Artículo", item_type="goods", default_uom="UND-CONVERT"),
            ]
        )
        database.session.flush()

        with pytest.raises(InventoryServiceError, match="No se pudo convertir"):
            item_qty_in_base_uom("ITEM-NO-CONVERSION", Decimal("2"), "BOX-CONVERT")


@pytest.mark.parametrize(
    "record_type",
    [
        "purchase_request",
        "purchase_quotation",
        "supplier_quotation",
        "purchase_order",
        "purchase_receipt",
        "purchase_invoice",
        "sales_request",
        "sales_quotation",
        "sales_order",
        "delivery_note",
        "sales_invoice",
    ],
)
@pytest.mark.parametrize(("quantity", "is_valid"), [("0", False), ("-1", False), ("0.001", True)])
def test_transaction_import_requires_positive_quantity(record_type: str, quantity: str, is_valid: bool) -> None:
    """Todos los adaptadores transaccionales bloquean cantidades no positivas."""
    adapter = ImportService()._get_adapter(record_type)
    row = {
        "document_ref": "TX-QTY-001",
        "fecha": date.today().isoformat(),
        "producto": "ITEM-1",
        "cantidad": quantity,
        "precio_unitario": "1",
    }

    errors = adapter.validate_row(row)

    if is_valid:
        assert not errors
    else:
        assert any("cantidad" in error.lower() and "mayor que cero" in error.lower() for error in errors)


class _DummyItem:
    """Objeto mínimo para validar asignaciones opcionales del adaptador."""

    def __init__(self) -> None:
        self.item_code = "ITEM-BATCH-IMP"
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


def test_optional_item_fields_are_applied_consistently(app_ctx) -> None:
    """El adaptador llena los campos opcionales sin mezclar la lógica."""

    from cacao_accounting.database import Batch

    with app_ctx.app_context():
        lot = Batch(item_code="ITEM-BATCH-IMP", batch_no="LOT-001", is_active=True)
        database.session.add(lot)
        database.session.commit()

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
        assert item.batch_id == lot.id
        assert item.serial_no == "SER-009"


def test_build_document_keeps_transaction_and_base_amounts(app_ctx, monkeypatch) -> None:
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

    with app_ctx.app_context():
        database.session.add(UOM(code="UND-IMPORT", name="Unidad"))
        database.session.add(Item(code="ITEM-1", name="Artículo importado", item_type="goods", default_uom="UND-IMPORT"))
        database.session.flush()
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


@pytest.mark.parametrize("field", ["cantidad", "precio_unitario"])
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_transaction_import_rejects_non_finite_row_values(monkeypatch, field: str, value: str) -> None:
    """Las cantidades y tarifas no finitas se rechazan antes de persistir."""
    from cacao_accounting.imports.adapters import transaction_documents

    monkeypatch.setattr(transaction_documents, "company_currency", lambda _company: "NIO")
    adapter = TransactionPurchaseOrderAdapter()
    row = {
        "document_ref": "PO-NONFINITE",
        "fecha": date.today().isoformat(),
        "moneda": "NIO",
        "producto": "ITEM-1",
        "cantidad": "1",
        "precio_unitario": "1",
    }
    row[field] = value

    assert any("Valor numérico inválido" in error for error in adapter.validate_row(row))
    with pytest.raises(ValueError):
        adapter.build_document([row], {"company_id": "cacao"})


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_transaction_import_rejects_non_finite_exchange_rate(monkeypatch, value: str) -> None:
    """La tasa explícita no finita genera un error controlado."""
    from cacao_accounting.imports.adapters import transaction_documents

    monkeypatch.setattr(transaction_documents, "company_currency", lambda _company: "NIO")
    with pytest.raises(ValueError, match="finito"):
        TransactionPurchaseOrderAdapter()._currency_and_rate(  # noqa: SLF001
            {"moneda": "USD", "tipo_cambio": value}, None, "cacao", date.today()
        )
