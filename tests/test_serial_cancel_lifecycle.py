# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1177 / #1306 / #1829: ciclo, colisión global y concurrencia real de seriales."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event, local
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    GLEntry,
    Item,
    SerialNumber,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    _is_serial_number_unique_violation,
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


def _other_serialized_item(app, source_item_code: str) -> SimpleNamespace:
    """Create a second serialized item without assigning the shared serial."""
    other_code = f"OTHER-{uuid4().hex[:6].upper()}"
    with app.app_context():
        default_uom = database.session.execute(database.select(Item.default_uom).filter_by(code=source_item_code)).scalar_one()
        database.session.add(
            Item(
                code=other_code,
                name="Otro artículo serializado",
                item_type="stock",
                is_stock_item=True,
                has_serial_no=True,
                default_uom=default_uom,
            )
        )
        database.session.commit()
    return SimpleNamespace(code=other_code)


@pytest.mark.parametrize("outgoing", [False, True])
def test_serial_of_other_item_is_rejected_by_global_validation(app, serializado, outgoing):
    """Entrada y salida validan el serial globalmente, no solo dentro del artículo (#1829)."""
    with app.app_context():
        other_item = _other_serialized_item(app, serializado.item.code)
        line = SimpleNamespace(serial_no=serializado.serial, qty=1, item_code=other_item.code)
        with pytest.raises(InventoryServiceError, match="registrado para otro artículo"):
            _validate_serial(line, other_item, outgoing=outgoing, warehouse=serializado.warehouse)


def test_serial_of_other_item_cannot_be_reassigned_on_update(app, serializado):
    """La actualización directa tampoco puede mover un serial a otro artículo (#1829)."""
    with app.app_context():
        other_item = _other_serialized_item(app, serializado.item.code)
        line = SimpleNamespace(serial_no=serializado.serial, item_code=other_item.code)

        with pytest.raises(InventoryServiceError, match="registrado para otro artículo"):
            update_serial_state(line, outgoing=False, warehouse=serializado.warehouse)

        serial = _serial(serializado.serial)
        assert serial.item_code == serializado.item.code
        assert serial.serial_status == "available"
        assert serial.warehouse == serializado.warehouse


@pytest.mark.parametrize(
    ("message", "constraint_name", "error_code", "statement", "expected"),
    [
        (
            "duplicate key value violates unique constraint",
            "serial_number_serial_no_key",
            None,
            "INSERT INTO serial_number (serial_no) VALUES (:serial_no)",
            True,
        ),
        (
            "duplicate key value violates unique constraint",
            "serial_number_other_key",
            None,
            "INSERT INTO serial_number (serial_no) VALUES (:serial_no)",
            False,
        ),
        (
            "UNIQUE constraint failed: serial_number.serial_no",
            None,
            None,
            "INSERT INTO serial_number (serial_no) VALUES (:serial_no)",
            True,
        ),
        (
            "Duplicate entry 'SN' for key 'serial_number.serial_no'",
            None,
            1062,
            "INSERT INTO serial_number (serial_no) VALUES (:serial_no)",
            True,
        ),
        (
            "Duplicate entry 'SN' for key 'serial_no'",
            None,
            1062,
            "INSERT INTO serial_number (serial_no) VALUES (:serial_no)",
            True,
        ),
        (
            "Duplicate entry 'SN' for key 'serial_no'",
            None,
            1062,
            "INSERT INTO another_table (serial_no) VALUES (:serial_no)",
            False,
        ),
        (
            "NOT NULL constraint failed: serial_number.item_code",
            None,
            None,
            "INSERT INTO serial_number (serial_no) VALUES (:serial_no)",
            False,
        ),
    ],
)
def test_serial_unique_diagnostic_is_constraint_specific(message, constraint_name, error_code, statement, expected):
    """Los diagnósticos conocidos distinguen serial_no de cualquier otra integridad."""
    original = Exception(error_code, message) if error_code is not None else Exception(message)
    if constraint_name is not None:
        original.diag = SimpleNamespace(constraint_name=constraint_name)
    error = IntegrityError(statement, {}, original)

    assert _is_serial_number_unique_violation(error) is expected


def test_unrelated_integrity_error_is_not_hidden(app):
    """Una violación NOT NULL real se propaga y deja la sesión utilizable (#1829)."""
    serial_no = f"MISSING-{uuid4().hex[:6].upper()}"
    with app.app_context():
        line = SimpleNamespace(serial_no=serial_no, item_code=None)

        with pytest.raises(IntegrityError) as captured:
            update_serial_state(line, outgoing=False, warehouse=None)

        assert "serial_number.item_code" in str(captured.value.orig)
        assert (
            database.session.execute(
                database.select(database.func.count()).select_from(SerialNumber).filter_by(serial_no=serial_no)
            ).scalar_one()
            == 0
        )


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
    at_reservation = Barrier(2, timeout=30)
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


def test_two_receipts_racing_serial_insert_have_one_winner_and_usable_loser(serial_concurrente):
    """La constraint global real decide la carrera y el savepoint conserva la sesión (#1829)."""
    application, item_code, existing_serial_no, warehouse = serial_concurrente
    serial_no = f"RACE-{existing_serial_no}"
    at_savepoint = Barrier(2, timeout=30)
    winner_committed = Event()
    thread_state = local()

    def pause_before_serial_savepoint(connection, cursor, statement, parameters, context, executemany):
        del connection, cursor, parameters, context, executemany
        normalized = statement.lstrip().lower()
        if getattr(thread_state, "synchronized", False) or not normalized.startswith("savepoint"):
            return
        thread_state.synchronized = True
        at_savepoint.wait(timeout=10)
        if not thread_state.winner:
            winner_committed.wait(timeout=10)

    with application.app_context():
        engine = database.engine
    event.listen(engine, "before_cursor_execute", pause_before_serial_savepoint)

    def receive(winner: bool) -> str:
        thread_state.winner = winner
        line = SimpleNamespace(serial_no=serial_no, item_code=item_code)
        with application.app_context():
            try:
                update_serial_state(line, outgoing=False, warehouse=warehouse)
                database.session.commit()
                return "accepted"
            except InventoryServiceError as exc:
                cause = exc.__cause__
                constraint_activated = isinstance(cause, IntegrityError) and "serial_number.serial_no" in str(cause.orig)
                usable_session = (
                    database.session.execute(
                        database.select(database.func.count()).select_from(SerialNumber).filter_by(serial_no=serial_no)
                    ).scalar_one()
                    == 1
                )
                database.session.rollback()
                return "rejected" if constraint_activated and usable_session else "uncontrolled"
            except Exception as exc:  # pragma: no cover - failure diagnostic
                database.session.rollback()
                return f"unexpected:{type(exc).__name__}"
            finally:
                if winner:
                    winner_committed.set()
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            winner_future = executor.submit(receive, True)
            loser_future = executor.submit(receive, False)
            winner_result = winner_future.result(timeout=20)
            loser_result = loser_future.result(timeout=20)
    finally:
        event.remove(engine, "before_cursor_execute", pause_before_serial_savepoint)

    assert winner_result == "accepted"
    assert loser_result == "rejected"
    with application.app_context():
        rows = database.session.execute(database.select(SerialNumber).filter_by(serial_no=serial_no)).scalars().all()
        assert len(rows) == 1
        assert rows[0].item_code == item_code
        assert rows[0].serial_status == "available"
        assert rows[0].warehouse == warehouse


def test_stock_entry_submit_rejects_serial_owned_by_another_item(entorno_contable_aislado):
    """El submit HTTP real revierte docstatus y no deja evidencia de stock o GL (#1829)."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:6].upper()
    item_code = f"HTTP-{suffix}"
    serial_no = f"HTTP-SN-{suffix}"
    entry_no = f"HTTP-ENTRY-{suffix}"
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(admin.id)
        auth_version = admin.auth_version
        owner_item_code = database.session.execute(database.select(Item.code).filter_by(code="ART01")).scalar_one()
        warehouse_code = database.session.execute(database.select(Warehouse.code).filter_by(code="BOD01")).scalar_one()
        database.session.add(
            Item(
                code=item_code,
                name="Artículo HTTP serializado",
                item_type="stock",
                is_stock_item=True,
                has_serial_no=True,
                default_uom="UND",
            )
        )
        database.session.add(
            SerialNumber(
                item_code=owner_item_code,
                serial_no=serial_no,
                serial_status="available",
                warehouse=warehouse_code,
            )
        )
        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date(2026, 5, 20),
            to_warehouse=warehouse_code,
            document_no=entry_no,
            transaction_currency="NIO",
            base_currency="NIO",
            total_amount=Decimal("10"),
            docstatus=0,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item_code,
                target_warehouse=warehouse_code,
                qty=Decimal("1"),
                uom="UND",
                qty_in_base_uom=Decimal("1"),
                basic_rate=Decimal("10"),
                amount=Decimal("10"),
                serial_no=serial_no,
            )
        )
        database.session.commit()
        entry_id = entry.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.post(f"/inventory/stock-entry/{entry_id}/submit")

    assert response.status_code == 302
    with client.session_transaction() as session:
        flashes = session.get("_flashes", [])
    assert any("registrado para otro artículo" in str(message) for _, message in flashes)
    with app.app_context():
        entry = database.session.get(StockEntry, entry_id)
        assert entry is not None
        assert entry.docstatus == 0
        serial = database.session.execute(database.select(SerialNumber).filter_by(serial_no=serial_no)).scalar_one()
        assert serial.item_code == owner_item_code
        assert serial.serial_status == "available"
        assert database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id)).scalars().all() == []
        assert database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars().all() == []
