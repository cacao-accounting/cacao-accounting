# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1927: una UOM inactiva no se acepta al guardar ni al postear inventario."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting.contabilidad.posting_service import PostingError, post_stock_entry
from cacao_accounting.database import (
    Item,
    StockEntry,
    StockEntryItem,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.inventario.services import _save_stock_entry_item


def _escenario(app) -> tuple[str, str, str]:
    """Crea item, bodega y UOM inactiva."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        uom = UOM(code=f"UI{sufijo}", name="Unidad inactiva", is_active=False)
        database.session.add(uom)
        database.session.flush()
        item = Item(
            code=f"ART{sufijo}",
            name="Artículo",
            item_type="goods",
            is_stock_item=True,
            default_uom=uom.code,
        )
        warehouse = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        database.session.add_all([item, warehouse])
        database.session.commit()
        return item.code, warehouse.code, uom.code


def test_guardar_linea_rechaza_uom_inactiva(entorno_contable_aislado):
    """El servicio de alta de la línea aplica la misma política que el selector."""
    app = entorno_contable_aislado.app
    item_code, warehouse, uom_code = _escenario(app)
    with app.app_context():
        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date(2026, 5, 15),
            to_warehouse=warehouse,
            from_warehouse=warehouse,
            document_no=f"UOM-{uuid4().hex[:8]}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(entry)
        database.session.commit()
        with app.test_request_context(
            "/",
            method="POST",
            data={"uom_0": uom_code, "qty_0": "1", "rate_0": "10"},
        ):
            with pytest.raises(ValueError, match="inactiva"):
                _save_stock_entry_item(entry, 0, item_code)


def test_posting_rechaza_uom_inactiva(entorno_contable_aislado):
    """Un borrador manipulado no puede llegar al Stock Ledger con UOM inactiva."""
    app = entorno_contable_aislado.app
    item_code, warehouse, uom_code = _escenario(app)
    with app.app_context():
        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date(2026, 5, 15),
            to_warehouse=warehouse,
            from_warehouse=warehouse,
            document_no=f"UOM-POST-{uuid4().hex[:8]}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=1,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item_code,
                target_warehouse=warehouse,
                source_warehouse=warehouse,
                qty=Decimal("1"),
                uom=uom_code,
                qty_in_base_uom=Decimal("1"),
                basic_rate=Decimal("10"),
                amount=Decimal("10"),
            )
        )
        database.session.commit()
        with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
            login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
            with pytest.raises(PostingError, match="inactiva"):
                post_stock_entry(entry)


def test_stock_entry_forms_hide_inactive_uom_and_reject_post(app, authenticated_client, entorno_contable):
    """#1927: alta/edición no ofrecen UOM inactiva; el POST manipulado se rechaza."""
    from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

    del entorno_contable
    suffix = uuid4().hex[:6]
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        active = UOM(code=f"UA{suffix}", name="Unidad activa", is_active=True)
        inactive = UOM(code=f"UI{suffix}", name="Unidad inactiva", is_active=False)
        historical = UOM(code=f"UH{suffix}", name="Unidad historica", is_active=False)
        warehouse = Warehouse(code=f"WH{suffix}", name="Bodega", company="cacao", is_active=True)
        database.session.add_all([active, inactive, historical, warehouse])
        database.session.flush()
        item = Item(
            code=f"IT{suffix}",
            name="Articulo",
            item_type="goods",
            is_stock_item=True,
            default_uom=active.code,
        )
        database.session.add(item)
        database.session.flush()
        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date(2026, 5, 15),
            to_warehouse=warehouse.code,
            document_no=f"SE-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item.code,
                target_warehouse=warehouse.code,
                source_warehouse=warehouse.code,
                qty=Decimal("1"),
                uom=historical.code,
                qty_in_base_uom=Decimal("1"),
                basic_rate=Decimal("1"),
                amount=Decimal("1"),
            )
        )
        database.session.commit()
        from cacao_accounting.database import NamingSeries

        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()
        ids = {
            "active": active.code,
            "inactive": inactive.code,
            "historical": historical.code,
            "item": item.code,
            "warehouse": warehouse.code,
            "entry_id": entry.id,
            "series_id": series_id,
        }

    client = authenticated_client("admin")
    new_response = client.get("/inventory/stock-entry/material-receipt/new")
    assert new_response.status_code == 200
    new_body = new_response.get_data(as_text=True)
    assert ids["active"] in new_body
    assert ids["inactive"] not in new_body

    edit_response = client.get(f"/inventory/stock-entry/{ids['entry_id']}/edit")
    assert edit_response.status_code == 200
    edit_body = edit_response.get_data(as_text=True)
    assert ids["historical"] in edit_body
    assert ids["inactive"] not in edit_body

    post_response = client.post(
        "/inventory/stock-entry/material-receipt/new",
        data={
            "purpose": "material_receipt",
            "company": "cacao",
            "naming_series": ids["series_id"],
            "posting_date": "2026-05-15",
            "transaction_currency": "NIO",
            "to_warehouse": ids["warehouse"],
            "warehouse_0": ids["warehouse"],
            "item_code_0": ids["item"],
            "qty_0": "1",
            "rate_0": "1",
            "amount_0": "1",
            "uom_0": ids["inactive"],
            "remarks": f"UOM-INACTIVE-{suffix}",
        },
    )
    assert post_response.status_code == 200
    with app.app_context():
        created = database.session.execute(
            database.select(StockEntry).filter_by(remarks=f"UOM-INACTIVE-{suffix}")
        ).scalar_one_or_none()
        assert created is None
