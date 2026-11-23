# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1177 / #1306: el serial anulado no queda como entregado y su salida se serializa."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.database import Item, SerialNumber, UOM, Warehouse, database
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    _validate_incoming_serial,
    _validate_serial,
    update_serial_state,
)


@pytest.fixture
def serializado(app):
    """Artículo serializado con una bodega y un serial disponible, aislado por prueba."""
    suffix = uuid4().hex[:6].upper()
    codes = SimpleNamespace(uom=f"U{suffix}", warehouse=f"W{suffix}", item=f"I{suffix}", serial=f"SN{suffix}")
    with app.app_context():
        database.session.add(UOM(code=codes.uom, name="Unidad", is_active=True))
        database.session.add(Warehouse(code=codes.warehouse, name="Bodega uno", company="cacao", is_active=True))
        database.session.flush()
        database.session.add(
            Item(
                code=codes.item,
                name="Artículo serializado",
                item_type="stock",
                is_stock_item=True,
                has_serial_no=True,
                is_purchase_item=True,
                is_sale_item=True,
                default_uom=codes.uom,
            )
        )
        database.session.add(
            SerialNumber(
                item_code=codes.item,
                serial_no=codes.serial,
                serial_status="available",
                warehouse=codes.warehouse,
            )
        )
        database.session.commit()
        yield SimpleNamespace(
            item=SimpleNamespace(code=codes.item),
            line=SimpleNamespace(serial_no=codes.serial, item_code=codes.item),
            serial=codes.serial,
            warehouse=codes.warehouse,
        )


def _serial(serial_no: str) -> SerialNumber:
    return database.session.execute(database.select(SerialNumber).filter_by(serial_no=serial_no)).scalar_one()


def test_recepcion_anulada_no_se_marca_entregada(serializado):
    """La reversa de una entrada deja el serial cancelado y sin bodega, no entregado."""
    update_serial_state(serializado.line, outgoing=True, warehouse=serializado.warehouse, cancel_entry=True)

    serial = _serial(serializado.serial)
    assert serial.serial_status == "cancelled"
    assert serial.warehouse is None


def test_serial_cancelado_puede_recibirse_de_nuevo(serializado):
    """Sin entrada activa el mismo serial vuelve a recibirse por la vía normal."""
    update_serial_state(serializado.line, outgoing=True, warehouse=serializado.warehouse, cancel_entry=True)

    _validate_incoming_serial(_serial(serializado.serial), allow_transfer=False, allow_return=False)
    update_serial_state(serializado.line, outgoing=False, warehouse=serializado.warehouse)

    serial = _serial(serializado.serial)
    assert serial.serial_status == "available"
    assert serial.warehouse == serializado.warehouse


def test_serial_cancelado_no_puede_salir(serializado):
    """Un serial cancelado no está disponible para una salida comercial."""
    update_serial_state(serializado.line, outgoing=True, warehouse=serializado.warehouse, cancel_entry=True)

    with pytest.raises(InventoryServiceError, match="no esta disponible"):
        _validate_serial(serializado.line, serializado.item, outgoing=True, warehouse=serializado.warehouse)


def test_entrega_real_conserva_su_ciclo(serializado):
    """La salida comercial sigue marcando entregado y solo la devolución lo reingresa."""
    update_serial_state(serializado.line, outgoing=True, warehouse=serializado.warehouse)
    assert _serial(serializado.serial).serial_status == "delivered"

    with pytest.raises(InventoryServiceError, match="solo puede cambiar de bodega"):
        _validate_incoming_serial(_serial(serializado.serial), allow_transfer=False, allow_return=False)

    _validate_incoming_serial(_serial(serializado.serial), allow_transfer=False, allow_return=True)
    update_serial_state(serializado.line, outgoing=False, warehouse=serializado.warehouse)
    assert _serial(serializado.serial).serial_status == "available"


def test_orden_de_reversas_fija_el_estado_final():
    """Al cancelar una transferencia se reversa la entrada antes que la salida."""
    from cacao_accounting.contabilidad.posting_service import _reversal_order

    entrada = SimpleNamespace(qty_change=1, id="01")
    salida = SimpleNamespace(qty_change=-1, id="00")
    ajuste = SimpleNamespace(qty_change=0, id="03")

    assert _reversal_order([salida, ajuste, entrada]) == [entrada, ajuste, salida]
