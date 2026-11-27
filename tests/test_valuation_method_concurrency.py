# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Moreno Reyes

"""#1881: el cambio de valuación se serializa con el primer posting (PostgreSQL)."""

from __future__ import annotations

import os
import threading
import time
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import _valuation_method_for_company
from cacao_accounting.database import (
    Entity,
    Item,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)
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
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname = '{nombre}' AND pid <> pg_backend_pid()"
                )
            )
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
            database.session.add(UOM(code="UND1881", name="Unidad 1881"))
            database.session.add(
                Item(code="ART-1881", name="Artículo 1881", item_type="goods", is_stock_item=True, default_uom="UND1881")
            )
            database.session.add(Warehouse(code="BOD-1881", name="Bodega 1881", company="cacao"))
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
    """El guard administrativo no cambia el método si el posting gana la carrera (#1881)."""
    with pg_app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        original = entity.valuation_method or "moving_average"
        nuevo = _metodo_distinto(original)

    bloqueado = threading.Event()
    liberar = threading.Event()
    resultado: dict[str, object] = {}

    def posting():
        with pg_app.app_context():
            try:
                _valuation_method_for_company("cacao")  # SELECT ... FOR UPDATE sobre Entity
                bloqueado.set()
                liberar.wait(timeout=10)
                database.session.add(
                    StockLedgerEntry(
                        posting_date=date(2026, 5, 20),
                        item_code="ART-1881",
                        warehouse="BOD-1881",
                        company="cacao",
                        qty_change=Decimal("5"),
                        voucher_type="stock_entry",
                        voucher_id="SE-1881",
                    )
                )
                database.session.commit()
            except Exception as exc:  # pragma: no cover - diagnóstico de la prueba
                resultado["posting_error"] = repr(exc)
                database.session.rollback()

    def guard():
        with pg_app.app_context():
            try:
                update_company_valuation_method("cacao", nuevo)
                resultado["guard"] = "aplicado"
            except ValueError as exc:
                resultado["guard"] = "rechazado"
                resultado["guard_error"] = str(exc)
            finally:
                database.session.remove()

    hilo_posting = threading.Thread(target=posting)
    hilo_posting.start()
    assert bloqueado.wait(timeout=10), "el posting no tomó el lock de la compañía"

    hilo_guard = threading.Thread(target=guard)
    hilo_guard.start()
    time.sleep(0.5)  # da tiempo a que el guard llegue al SELECT ... FOR UPDATE
    liberar.set()
    hilo_posting.join(timeout=15)
    hilo_guard.join(timeout=15)

    assert not hilo_posting.is_alive() and not hilo_guard.is_alive()
    assert "posting_error" not in resultado, resultado.get("posting_error")
    assert resultado.get("guard") == "rechazado", resultado
    with pg_app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        assert (entity.valuation_method or "moving_average") == original
        assert database.session.execute(database.select(StockLedgerEntry).filter_by(company="cacao")).scalars().all() != []
