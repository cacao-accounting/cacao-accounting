# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Moreno Reyes

"""#1881: el cambio de valuación se serializa con el primer posting (PostgreSQL)."""

from __future__ import annotations

import os
import threading
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.engine import make_url

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.posting_service import post_stock_entry
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    Currency,
    Entity,
    FiscalYear,
    Item,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from flask_login import login_user
from cacao_accounting.inventario.valuation_settings import update_company_valuation_method

pytestmark = pytest.mark.database


def _pg_isolated_url() -> Any:
    """Crea una base PostgreSQL aislada preservando las credenciales."""
    raw = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("Este escenario requiere PostgreSQL Tier 1.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    nombre = f"vm_{uuid4().hex[:10]}"
    admin_engine = create_engine(url.set(database="postgres"))
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    finally:
        admin_engine.dispose()
    return url.set(database=nombre)


def _drop_pg_isolated_url(url_aislada: Any) -> None:
    """Elimina la base PostgreSQL aislada de la prueba."""
    nombre = url_aislada.database
    admin_engine = create_engine(url_aislada.set(database="postgres"))
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            try:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        f"WHERE datname = '{nombre}' AND pid <> pg_backend_pid()"
                    )
                )
            except ProgrammingError:
                # Un rol sin pg_signal_autovacuum_worker no puede terminar todos los
                # backends; el engine ya hizo dispose y DROP DATABASE no los espera.
                pass
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture
def pg_app():
    """App PostgreSQL aislada para la carrera de valuación."""
    url_aislada = _pg_isolated_url()
    aplicacion = None
    try:
        aplicacion = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url_aislada.render_as_string(hide_password=False),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": True,
            }
        )
        with aplicacion.app_context():
            database.create_all()
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            database.session.flush()
            database.session.add(
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1881",
                    currency="NIO",
                    enabled=True,
                )
            )
            database.session.flush()
            database.session.add(UOM(code="UND1881", name="Unidad 1881"))
            database.session.flush()
            database.session.add(
                Item(code="ART-1881", name="Artículo 1881", item_type="goods", is_stock_item=True, default_uom="UND1881")
            )
            database.session.add_all(
                [
                    Warehouse(code="BOD-1881-A", name="Bodega origen 1881", company="cacao"),
                    Warehouse(code="BOD-1881-B", name="Bodega destino 1881", company="cacao"),
                ]
            )
            database.session.flush()
            inventory = Accounts(
                code="1109-1881",
                name="Inventario 1881",
                entity="cacao",
                group=False,
                active=True,
                enabled=True,
                account_type="stock",
            )
            book = Book(
                entity="cacao",
                code="LIB-1881",
                name="Libro 1881",
                currency="NIO",
                status="activo",
                is_primary=True,
            )
            fiscal_year = FiscalYear(
                entity="cacao",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
            database.session.add_all([inventory, book, fiscal_year])
            database.session.flush()
            database.session.add(
                AccountingPeriod(
                    entity="cacao",
                    fiscal_year_id=fiscal_year.id,
                    name="2026",
                    start=date(2026, 1, 1),
                    end=date(2026, 12, 31),
                    enabled=True,
                    is_closed=False,
                )
            )
            database.session.add_all(
                [
                    WarehouseCompanyAccount(
                        warehouse_code="BOD-1881-A",
                        company="cacao",
                        inventory_account_id=inventory.id,
                        is_active=True,
                    ),
                    WarehouseCompanyAccount(
                        warehouse_code="BOD-1881-B",
                        company="cacao",
                        inventory_account_id=inventory.id,
                        is_active=True,
                    ),
                    User(
                        user="admin-1881",
                        name="Admin 1881",
                        password=b"unused",
                        classification="admin",
                        active=True,
                        company="cacao",
                    ),
                ]
            )
            database.session.commit()
        yield aplicacion
    finally:
        if aplicacion is not None:
            with aplicacion.app_context():
                database.session.remove()
                database.engine.dispose()
        _drop_pg_isolated_url(url_aislada)


def _metodo_distinto(actual: str | None) -> str:
    return "fifo" if str(actual or "").lower() != "fifo" else "moving_average"


def test_cambio_de_metodo_espera_al_primer_posting(pg_app):
    """El guard administrativo no cambia el m?todo si el posting gana la carrera (#1881)."""
    import time

    with pg_app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        original = entity.valuation_method or "moving_average"
        nuevo = _metodo_distinto(original)
        entry = StockEntry(
            company="cacao",
            purpose="material_transfer",
            posting_date=date(2026, 5, 20),
            document_no="SE-1881",
            from_warehouse="BOD-1881-A",
            to_warehouse="BOD-1881-B",
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
                item_code="ART-1881",
                source_warehouse="BOD-1881-A",
                target_warehouse="BOD-1881-B",
                qty=Decimal("5"),
                qty_in_base_uom=Decimal("5"),
                uom="UND1881",
                basic_rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        database.session.commit()
        entry_id = str(entry.id)

    posting_locked = threading.Event()
    guard_at_lock = threading.Event()
    liberar = threading.Event()
    resultado: dict[str, object] = {}

    def _lock_listener(signal: threading.Event | None = None):
        """Marca cu?ndo la sesi?n emite el SELECT ... FOR UPDATE sobre Entity."""

        def listener(conn, cursor, statement, parameters, context, executemany):
            del conn, cursor, parameters, context, executemany
            if "FOR UPDATE" in statement.upper() and "ENTITY" in statement.upper():
                if signal is not None:
                    signal.set()
                else:
                    resultado["posting_lock"] = True

        return listener

    def posting():
        with pg_app.app_context():
            conexion = database.session.connection()
            resultado["posting_pid"] = conexion.execute(text("SELECT pg_backend_pid()")).scalar_one()
            listener = _lock_listener()
            event.listen(conexion, "before_cursor_execute", listener)
            create_original = posting_service._create_stock_ledger

            def pausar_antes_de_crear_actividad(documento):
                posting_locked.set()
                assert liberar.wait(timeout=10), "no se liberó el posting"
                return create_original(documento)

            posting_service._create_stock_ledger = pausar_antes_de_crear_actividad
            try:
                entry = database.session.get(StockEntry, entry_id)
                assert entry is not None
                with pg_app.test_request_context(f"/inventory/stock-entry/{entry_id}"):
                    user = database.session.execute(database.select(User).filter_by(user="admin-1881")).scalar_one()
                    login_user(user)
                    post_stock_entry(entry)
                database.session.commit()
            except Exception as exc:  # pragma: no cover - diagnóstico de la prueba
                resultado["posting_error"] = repr(exc)
                database.session.rollback()
            finally:
                posting_service._create_stock_ledger = create_original
                event.remove(conexion, "before_cursor_execute", listener)

    def guard():
        with pg_app.app_context():
            conexion = database.session.connection()
            resultado["guard_pid"] = conexion.execute(text("SELECT pg_backend_pid()")).scalar_one()
            listener = _lock_listener(guard_at_lock)
            event.listen(conexion, "before_cursor_execute", listener)
            try:
                update_company_valuation_method("cacao", nuevo)
                resultado["guard"] = "aplicado"
            except ValueError as exc:
                resultado["guard"] = "rechazado"
                resultado["guard_error"] = str(exc)
            except Exception as exc:  # pragma: no cover - diagn?stico de la prueba
                resultado["guard"] = "error"
                resultado["guard_error"] = repr(exc)
            finally:
                event.remove(conexion, "before_cursor_execute", listener)
                database.session.remove()

    def _guard_esperando_lock(monitor, guard_pid: int, posting_pid: int) -> bool:
        """Confirma en PostgreSQL que el guard est? bloqueado por el posting."""
        row = (
            monitor.execute(
                text(
                    "SELECT wait_event_type, state, pg_blocking_pids(pid) AS blockers "
                    "FROM pg_stat_activity WHERE pid = :pid"
                ),
                {"pid": guard_pid},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return False
        blockers = [int(b) for b in (row["blockers"] or [])]
        return row["wait_event_type"] == "Lock" and row["state"] == "active" and posting_pid in blockers

    monitor_engine = create_engine(pg_app.config["SQLALCHEMY_DATABASE_URI"])
    try:
        hilo_posting = threading.Thread(target=posting)
        hilo_posting.start()
        assert posting_locked.wait(timeout=10), "el posting no tom? el lock de la compa??a"
        assert resultado.get("posting_lock") is True, "el posting no emiti? SELECT ... FOR UPDATE"

        hilo_guard = threading.Thread(target=guard)
        hilo_guard.start()
        assert guard_at_lock.wait(timeout=10), "el guard no emiti? el SELECT ... FOR UPDATE"

        contendiendo = False
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            guard_pid = resultado.get("guard_pid")
            posting_pid = resultado.get("posting_pid")
            if guard_pid and posting_pid:
                with monitor_engine.connect() as monitor:
                    if _guard_esperando_lock(monitor, int(guard_pid), int(posting_pid)):
                        contendiendo = True
                        break
            time.sleep(0.05)

        # Evidencia determinista: el guard debe estar esperando el lock del posting.
        # Si se retira FOR UPDATE del guard, nunca queda bloqueado; si se retira del
        # posting, no hay bloqueo real que demostrar. En ambos casos la prueba falla.
        assert contendiendo, "el guard no qued? bloqueado esperando el lock del posting"
        liberar.set()
        hilo_posting.join(timeout=15)
        hilo_guard.join(timeout=15)
    finally:
        liberar.set()
        monitor_engine.dispose()

    assert not hilo_posting.is_alive() and not hilo_guard.is_alive()
    assert "posting_error" not in resultado, resultado.get("posting_error")
    assert resultado.get("guard") == "rechazado", resultado
    with pg_app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        assert (entity.valuation_method or "moving_average") == original
        assert database.session.execute(database.select(StockLedgerEntry).filter_by(company="cacao")).scalars().all() != []
