# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1060: imported lines enforce item roles and active UOMs."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.api.line_import import _validate_import_row
from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry
from cacao_accounting.database import Item, ItemUOMConversion, Party, UOM, Warehouse, database
from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter as LegacyPurchaseOrderAdapter
from cacao_accounting.imports.adapters.transaction_documents import (
    PurchaseOrderAdapter,
    SalesOrderAdapter as RegisteredSalesOrderAdapter,
)
from cacao_accounting.imports.utils.validation import (
    item_import_uom,
    validate_import_item,
    validate_import_uom,
    validate_import_warehouse,
)


def _item(*, active: bool = True, purchase: bool = True, sale: bool = True, uom_active: bool = True) -> Item:
    """Create a unique item with configurable import eligibility and base UOM."""
    suffix = uuid4().hex[:10]
    uom = UOM(code=f"U{suffix}", name="Unidad de prueba", is_active=uom_active)
    database.session.add(uom)
    database.session.flush()
    item = Item(
        code=f"I{suffix}",
        name="Artículo de importación",
        item_type="service",
        is_stock_item=False,
        is_purchase_item=purchase,
        is_sale_item=sale,
        is_active=active,
        default_uom=uom.code,
    )
    database.session.add(item)
    database.session.flush()
    return item


def _line_row(item: Item, uom: str | None = None) -> dict[str, str]:
    """Build a line import row valid for a purchase or sales schema."""
    row = {"item_code": item.code, "quantity": "1", "rate": "10"}
    if uom is not None:
        row["uom"] = uom
    return row


def _validate_api_line(item: Item, doctype: str, uom: str | None = None) -> list[dict[str, object]]:
    """Run the real shared line-import row validator."""
    schema = LineImportSchemaRegistry.get_schema(doctype)
    row = _line_row(item, uom)
    errors, _validated = _validate_import_row(
        row=row,
        row_no=2,
        schema=schema,
        doctype=doctype,
        company_id="cacao",
    )
    return errors


@pytest.mark.parametrize(
    ("doctype", "purchase", "sale", "expected"),
    [
        ("purchase_order", False, True, "compra"),
        ("sales_order", True, False, "venta"),
    ],
)
def test_line_import_rejects_item_without_document_role(entorno_contable, doctype, purchase, sale, expected):
    """Shared line validation applies the matching purchase or sales role."""
    assert entorno_contable is not None
    item = _item(purchase=purchase, sale=sale)

    errors = _validate_api_line(item, doctype)

    assert any(expected in str(error["message"]) for error in errors)


@pytest.mark.parametrize("doctype", ["purchase_order", "sales_order", "stock_entry"])
def test_line_import_rejects_inactive_item_for_every_document(entorno_contable, doctype):
    """Inventory and operational line imports cannot use inactive items."""
    assert entorno_contable is not None
    item = _item(active=False)

    errors = _validate_api_line(item, doctype)

    assert any("inactivo" in str(error["message"]) for error in errors)


def test_line_import_rejects_inactive_explicit_and_fallback_uom(entorno_contable):
    """Both a selected UOM and a default fallback must be active."""
    assert entorno_contable is not None
    inactive_default = _item(uom_active=False)
    active_item = _item()
    inactive_default.purchase_uom = active_item.default_uom
    inactive_default.sale_uom = active_item.default_uom
    database.session.flush()
    inactive_uom = UOM(code=f"X{uuid4().hex[:10]}", name="Unidad inactiva", is_active=False)
    database.session.add(inactive_uom)
    database.session.flush()

    fallback_errors = _validate_api_line(inactive_default, "purchase_order", uom=None)
    explicit_errors = _validate_api_line(active_item, "purchase_order", uom=inactive_uom.code)

    assert any("inactiva" in str(error["message"]) for error in fallback_errors)
    assert any("inactiva" in str(error["message"]) for error in explicit_errors)
    assert item_import_uom(active_item) == active_item.default_uom
    assert validate_import_uom("MISSING-UOM") == "La unidad de medida no existe."


@pytest.mark.parametrize("doctype", ["purchase_order", "sales_order", "stock_entry"])
def test_line_import_rejects_active_uom_without_item_conversion(entorno_contable, doctype):
    """An active global UOM is valid only if the item converts to its base UOM."""
    assert entorno_contable is not None
    item = _item()
    alternate_uom = UOM(code=f"C{uuid4().hex[:10]}", name="Unidad alternativa", is_active=True)
    database.session.add(alternate_uom)
    database.session.flush()

    errors = _validate_api_line(item, doctype, alternate_uom.code)

    assert any(error["field"] == "uom" and "convertir" in str(error["message"]).lower() for error in errors)
    database.session.add(
        ItemUOMConversion(
            item_code=item.code,
            from_uom=alternate_uom.code,
            to_uom=item.default_uom,
            conversion_factor=2,
        )
    )
    database.session.flush()

    errors_with_conversion = _validate_api_line(item, doctype, alternate_uom.code)

    assert not any(error["field"] == "uom" for error in errors_with_conversion)


def test_item_validation_handles_missing_and_unknown_references(entorno_contable):
    """Missing and unknown item references return actionable validation errors."""
    assert entorno_contable is not None
    assert validate_import_item(None, "purchase_order") == (None, None)
    item, error = validate_import_item("MISSING-ITEM", "purchase_order")

    assert item is None
    assert error == "El artículo no existe."


def test_import_warehouse_requires_active_company_owned_location(entorno_contable):
    """An optional warehouse must belong to the company and remain active."""
    with entorno_contable.app.app_context():
        warehouse = database.session.execute(database.select(Warehouse).filter_by(company="cacao")).scalars().first()
        assert warehouse is not None
        assert validate_import_warehouse(None, "cacao") is None
        assert validate_import_warehouse(warehouse.code, "cacao") is None
        assert validate_import_warehouse(warehouse.code, "other") is not None
        assert validate_import_warehouse("UNKNOWN-WAREHOUSE", "cacao") is not None
        warehouse.is_active = False
        database.session.flush()
        assert validate_import_warehouse(warehouse.code, "cacao") is not None
        warehouse.is_active = True
        database.session.flush()


@pytest.mark.parametrize(
    ("active", "purchase", "expected"),
    [(False, True, "inactivo"), (True, False, "compra")],
    ids=["inactive-item", "wrong-role"],
)
@pytest.mark.parametrize("registered", [False, True], ids=["legacy", "registered"])
def test_purchase_order_adapters_reject_ineligible_items(entorno_contable, active, purchase, expected, registered):
    """Both purchase-order adapters reject inactive or non-purchasable items."""
    assert entorno_contable is not None
    item = _item(active=active, purchase=purchase)
    supplier = database.session.query(Party).filter_by(code="PRV001").one()
    row = {
        "document_ref": "PO-ITEM-ELIGIBILITY",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tipo_cambio": "1",
        "proveedor": supplier.id,
        "producto": item.code,
        "cantidad": "1",
        "precio_unitario": "10",
    }
    if registered:
        row["tercero"] = row.pop("proveedor")
        row["uom"] = item.default_uom
        adapter = PurchaseOrderAdapter()
    else:
        adapter = LegacyPurchaseOrderAdapter()

    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any(expected in error.lower() for error in errors)
    with pytest.raises(ValueError, match=expected):
        adapter.build_document([row], {"company_id": "cacao"})


@pytest.mark.parametrize(
    ("active", "sale", "expected"),
    [(False, True, "inactivo"), (True, False, "venta")],
    ids=["inactive-item", "wrong-role"],
)
def test_sales_order_import_rejects_ineligible_items(entorno_contable, active, sale, expected):
    """The registered sales adapter applies the same item checks as the UI."""
    assert entorno_contable is not None
    item = _item(active=active, sale=sale)
    customer = database.session.query(Party).filter_by(code="CLI001").one()
    row = {
        "document_ref": "SO-ITEM-ELIGIBILITY",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tipo_cambio": "1",
        "tercero": customer.id,
        "producto": item.code,
        "cantidad": "1",
        "precio_unitario": "10",
        "uom": item.default_uom,
    }
    adapter = RegisteredSalesOrderAdapter()

    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any(expected in error.lower() for error in errors)
    with pytest.raises(ValueError, match=expected):
        adapter.build_document([row], {"company_id": "cacao"})


@pytest.mark.parametrize("registered", [False, True], ids=["legacy", "registered"])
def test_purchase_order_builder_persists_the_uom_used_for_conversion(entorno_contable, registered):
    """An omitted UOM falls back consistently to the active item base UOM."""
    assert entorno_contable is not None
    item = _item()
    preferred_uom = UOM(code=f"P{uuid4().hex[:10]}", name="Unidad preferida", is_active=True)
    database.session.add(preferred_uom)
    database.session.flush()
    item.purchase_uom = preferred_uom.code
    database.session.flush()
    supplier = database.session.query(Party).filter_by(code="PRV001").one()
    row = {
        "document_ref": "PO-UOM-FALLBACK",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tipo_cambio": "1",
        "proveedor": supplier.id,
        "producto": item.code,
        "cantidad": "1",
        "precio_unitario": "10",
    }
    if registered:
        row["tercero"] = row.pop("proveedor")
        adapter = PurchaseOrderAdapter()
    else:
        adapter = LegacyPurchaseOrderAdapter()

    document = adapter.build_document([row], {"company_id": "cacao"})

    assert document["items"][0].uom == item.default_uom
    assert document["items"][0].qty_in_base_uom == 1


def test_sales_order_builder_persists_base_uom_when_line_uom_is_omitted(entorno_contable):
    """Sales import validates and stores the same default UOM used in conversion."""
    assert entorno_contable is not None
    item = _item()
    preferred_uom = UOM(code=f"S{uuid4().hex[:10]}", name="Unidad de venta", is_active=True)
    database.session.add(preferred_uom)
    database.session.flush()
    item.sale_uom = preferred_uom.code
    database.session.flush()
    customer = database.session.query(Party).filter_by(code="CLI001").one()
    row = {
        "document_ref": "SO-UOM-FALLBACK",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tipo_cambio": "1",
        "tercero": customer.id,
        "producto": item.code,
        "cantidad": "1",
        "precio_unitario": "10",
    }

    document = RegisteredSalesOrderAdapter().build_document([row], {"company_id": "cacao"})

    assert document["items"][0].uom == item.default_uom
    assert document["items"][0].qty_in_base_uom == 1
