# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2353: dos salidas concurrentes no reclaman el mismo serial."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, SerialNumber, UOM, Warehouse, database
from cacao_accounting.inventario.service import InventoryServiceError, _claim_outgoing_serial

pytestmark = pytest.mark.database


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        pytest.skip("La carrera requiere bloqueo de fila real.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2353",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str) -> tuple[str, str, str]:
    company = f"S{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
                UOM(code=f"U{suffix}", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        item = Item(
            code=f"IT{suffix}",
            name="Artículo serializado",
            item_type="goods",
            is_stock_item=True,
            has_serial_no=True,
            default_uom=f"U{suffix}",
        )
        warehouse = Warehouse(code=f"W{suffix}", name="Bodega", company=company)
        database.session.add_all([item, warehouse])
        database.session.flush()
        serial_no = f"SER-{suffix}"
        database.session.add(
            SerialNumber(
                serial_no=serial_no,
                item_code=item.code,
                warehouse=warehouse.code,
                serial_status="available",
            )
        )
        database.session.commit()
        result = (serial_no, item.code, warehouse.code)
        database.session.remove()
        return result


def test_dos_salidas_concurrentes_reclaman_un_solo_serial(tmp_path):
    """La actualización condicional deja un solo reclamo confirmado."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    serial_no, item_code, warehouse = _seed(app, suffix)
    barrier = Barrier(2, timeout=30)

    def claim() -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                _claim_outgoing_serial(serial_no, item_code, warehouse)
                database.session.commit()
                return "reclamado"
            except InventoryServiceError:
                database.session.rollback()
                return "rechazado"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: claim(), range(2)))
    assert sorted(results) == ["rechazado", "reclamado"], results
    with app.app_context():
        serial = database.session.execute(database.select(SerialNumber).filter_by(serial_no=serial_no)).scalar_one()
        assert serial.serial_status == "posting"
