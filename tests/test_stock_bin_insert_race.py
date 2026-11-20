# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#332: carreras en INSERT de StockBin y validación de bodega en el posting."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _insert_stock_bin_race_safe,
    post_stock_entry,
)
from cacao_accounting.database import (
    Entity,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    UOM,
    User,
    Warehouse,
    database,
)


def _sembrar_item_bodega(artefacto: str, bodega: str, uom: str) -> None:
    """Crea el item y la bodega referenciados por el bin (#332)."""
    database.session.add(UOM(code=uom, name="Unidad 332"))
    database.session.flush()
    database.session.add(Item(code=artefacto, name="Articulo 332", item_type="goods", is_stock_item=True, default_uom=uom))
    database.session.flush()
    database.session.add(Warehouse(code=bodega, name="Bodega 332", company="cacao"))
    database.session.flush()


def test_insert_stock_bin_race_safe_retoma_bin_existente(app):
    """Si otra transacción insertó el bin antes, se devuelve el registro existente (#332)."""
    with app.app_context():
        _sembrar_item_bodega("ART-332", "BOD-332", "UND332A")
        existing = StockBin(company="cacao", item_code="ART-332", warehouse="BOD-332", actual_qty=Decimal("7"))
        database.session.add(existing)
        database.session.commit()
        row = _insert_stock_bin_race_safe(company="cacao", item_code="ART-332", warehouse="BOD-332")
        assert row.id == existing.id


def test_insert_stock_bin_race_safe_crea_bin_nuevo(app):
    """Sin bin existente, el insert se confirma y devuelve el nuevo registro (#332)."""
    with app.app_context():
        _sembrar_item_bodega("ART-332B", "BOD-332B", "UND332B")
        row = _insert_stock_bin_race_safe(company="cacao", item_code="ART-332B", warehouse="BOD-332B")
        assert row.actual_qty == Decimal("0")


def test_post_stock_entry_rechaza_bodega_ajena_al_company(app, entorno_contable):
    """El posting rechaza bodegas que no pertenecen a la compañía del documento (#332)."""
    with app.app_context():
        artefacto = f"332A-{uuid4().hex[:6].upper()}"
        bodega = f"332W-{uuid4().hex[:6].upper()}"
        database.session.add_all(
            [
                Entity(code="cafe", name="Cafe", company_name="Cafe SA", tax_id="J0002", currency="NIO", enabled=True),
                Item(code=artefacto, name="Articulo 332", item_type="goods", is_stock_item=True, default_uom="UND"),
                Warehouse(code=bodega, name="Bodega ajena 332", company="cafe"),
            ]
        )
        database.session.commit()
        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date(2026, 5, 20),
            to_warehouse=bodega,
            from_warehouse=bodega,
            document_no=f"332P-{uuid4().hex[:8]}",
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=1,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=artefacto,
                source_warehouse=bodega,
                target_warehouse=bodega,
                qty=Decimal("5"),
                uom="UND",
                qty_in_base_uom=Decimal("5"),
                basic_rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        database.session.commit()
        with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
            login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
            with pytest.raises(PostingError, match="no pertenece a la compañía"):
                post_stock_entry(entry)
