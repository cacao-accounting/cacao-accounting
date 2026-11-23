# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1177 / #1306: el serial anulado no queda como entregado y su salida se serializa."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, local
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, SerialNumber, UOM, Warehouse, database
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


@pytest.fixture
def serial_concurrente():
    """Base SQLite aislada para intercalar validaciones en conexiones separadas."""
    suffix = uuid4().hex[:6].upper()
    db_path = Path(__file__).parent / f".serial-concurrent-{suffix}.sqlite"
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    uom = f"U{suffix}"
    warehouse = f"W{suffix}"
    item_code = f"I{suffix}"
    serial_no = f"SN{suffix}"
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name=f"Cacao {suffix}",
                tax_id=f"TAX-{suffix}",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.add(UOM(code=uom, name="Unidad", is_active=True))
        database.session.flush()
        database.session.add(Warehouse(code=warehouse, name="Bodega", company="cacao", is_active=True))
        database.session.add(
            Item(
                code=item_code,
                name="Artículo serializado",
                item_type="stock",
                is_stock_item=True,
                has_serial_no=True,
                is_purchase_item=True,
                is_sale_item=True,
                default_uom=uom,
            )
        )
        database.session.flush()
        database.session.add(
            SerialNumber(item_code=item_code, serial_no=serial_no, serial_status="available", warehouse=warehouse)
        )
        database.session.commit()

    yield application, item_code, serial_no, warehouse

    with application.app_context():
        database.session.remove()
        database.engine.dispose()
    db_path.unlink(missing_ok=True)


def test_dos_salidas_concurrentes_no_reclaman_el_mismo_serial(serial_concurrente):
    """Dos transacciones que llegan juntas obtienen como máximo una reserva."""
    application, item_code, serial_no, warehouse = serial_concurrente
    at_reservation = Barrier(2)
    thread_state = local()

    def synchronize_first_serial_statement(connection, cursor, statement, parameters, context, executemany):
        del connection, cursor, parameters, context, executemany
        normalized = statement.lstrip().lower()
        if getattr(thread_state, "synchronized", False) or "serial_number" not in normalized:
            return
        if not (normalized.startswith("select") or normalized.startswith("update")):
            return
        thread_state.synchronized = True
        at_reservation.wait(timeout=10)

    with application.app_context():
        engine = database.engine
    event.listen(engine, "before_cursor_execute", synchronize_first_serial_statement)

    def post_outgoing():
        line = SimpleNamespace(serial_no=serial_no, qty=1, item_code=item_code)
        item = SimpleNamespace(code=item_code)
        with application.app_context():
            try:
                _validate_serial(line, item, outgoing=True, warehouse=warehouse)
                update_serial_state(line, outgoing=True, warehouse=warehouse)
                database.session.commit()
                return "accepted"
            except InventoryServiceError:
                database.session.rollback()
                return "rejected"
            except Exception as exc:  # pragma: no cover - failure diagnostic
                database.session.rollback()
                return f"unexpected:{type(exc).__name__}"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: post_outgoing(), range(2)))
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_first_serial_statement)

    assert sorted(results) == ["accepted", "rejected"]
    with application.app_context():
        serial = database.session.execute(database.select(SerialNumber).filter_by(serial_no=serial_no)).scalar_one()
        assert serial.serial_status == "delivered"
        assert serial.warehouse is None
