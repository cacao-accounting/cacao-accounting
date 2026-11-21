# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1881: el cambio de valuación se serializa con el primer movimiento."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.posting_service import _valuation_method_for_company
from cacao_accounting.database import Entity, Item, StockLedgerEntry, UOM, Warehouse, database
from cacao_accounting.inventario.valuation_settings import update_company_valuation_method

FECHA = date(2026, 5, 20)


def _otro_metodo(current: str | None) -> str:
    """Devuelve un método distinto al actual."""
    return "fifo" if str(current or "").lower() != "fifo" else "moving_average"


def test_cambio_valuacion_aplica_sin_actividad(app):
    """Sin actividad de inventario, el cambio de método aplica (#1881)."""
    with app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        method = _otro_metodo(entity.valuation_method)
        updated = update_company_valuation_method("cacao", method)
        assert updated.valuation_method == method
        assert _valuation_method_for_company("cacao") == method.lower()


def test_cambio_valuacion_rechaza_con_actividad(app):
    """Con actividad de inventario, el cambio de método queda bloqueado (#1881)."""
    with app.app_context():
        sufijo = uuid4().hex[:8].upper()
        uom_code = f"U{sufijo}"
        articulo = f"A{sufijo}"
        bodega = f"B{sufijo}"
        database.session.add(UOM(code=uom_code, name="Unidad 1881"))
        database.session.flush()
        database.session.add(
            Item(code=articulo, name="Articulo 1881", item_type="goods", is_stock_item=True, default_uom=uom_code)
        )
        database.session.add(Warehouse(code=bodega, name="Bodega 1881", company="cacao"))
        database.session.flush()
        database.session.add(
            StockLedgerEntry(
                posting_date=FECHA,
                item_code=articulo,
                warehouse=bodega,
                company="cacao",
                qty_change=Decimal("5"),
                voucher_type="stock_entry",
                voucher_id=f"SE-{sufijo}",
            )
        )
        # Basta el flush: la actividad debe ser visible dentro de la misma
        # transacción y la limpieza automática evita contaminar al worker.
        database.session.flush()
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        method = _otro_metodo(entity.valuation_method)
        with pytest.raises(ValueError, match="operacion de inventario"):
            update_company_valuation_method("cacao", method)
