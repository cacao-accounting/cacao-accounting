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
