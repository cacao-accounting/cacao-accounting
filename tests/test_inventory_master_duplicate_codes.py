# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de campos requeridos y códigos duplicados en maestros de inventario."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import UOM, Warehouse, WarehouseCompanyAccount, database


@pytest.fixture
def duplicate_inventory_codes(app):
    """Crea UOM y bodega existentes para probar rechazos de códigos repetidos."""
    suffix = uuid4().hex[:8].upper()
    codes = {"uom": f"U{suffix}", "warehouse": f"W{suffix}"}
    with app.app_context():
        database.session.add_all(
            [
                UOM(code=codes["uom"], name="Unidad existente"),
                Warehouse(code=codes["warehouse"], name="Bodega existente", company="cacao"),
            ]
        )
        database.session.commit()

    yield codes

    with app.app_context():
        database.session.execute(
            database.delete(WarehouseCompanyAccount).where(WarehouseCompanyAccount.warehouse_code == codes["warehouse"])
        )
        warehouse = database.session.execute(
            database.select(Warehouse).filter_by(code=codes["warehouse"])
        ).scalar_one_or_none()
        uom = database.session.execute(database.select(UOM).filter_by(code=codes["uom"])).scalar_one_or_none()
        if warehouse is not None:
            database.session.delete(warehouse)
        if uom is not None:
            database.session.delete(uom)
        database.session.commit()


def test_uom_rejects_missing_required_fields(app, authenticated_client):
    """An invalid UOM POST does not persist empty code or name values."""
    response = authenticated_client().post("/inventory/uom/new", data={"code": "", "name": ""})

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(UOM).filter_by(code="")).scalar_one_or_none() is None


def test_warehouse_rejects_missing_required_fields(app, authenticated_client):
    """An invalid warehouse POST does not persist empty code or name values."""
    response = authenticated_client().post(
        "/inventory/warehouse/new",
        data={"code": "", "name": "", "warehouse_company": "cacao"},
    )

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(Warehouse).filter_by(code="")).scalar_one_or_none() is None


def test_uom_duplicate_code_returns_controlled_error(app, authenticated_client, duplicate_inventory_codes):
    """A database uniqueness conflict returns to the form without duplicating the UOM."""
    code = duplicate_inventory_codes["uom"]

    response = authenticated_client().post("/inventory/uom/new", data={"code": code, "name": "Duplicada"})

    assert response.status_code == 200
    assert "El código ya está en uso." in response.get_data(as_text=True)
    with app.app_context():
        rows = database.session.execute(database.select(UOM).filter_by(code=code)).scalars().all()
        assert len(rows) == 1
        assert rows[0].name == "Unidad existente"


def test_warehouse_duplicate_code_returns_controlled_error(app, authenticated_client, duplicate_inventory_codes):
    """A warehouse uniqueness conflict rolls back and preserves the original row."""
    code = duplicate_inventory_codes["warehouse"]

    response = authenticated_client().post(
        "/inventory/warehouse/new",
        data={"code": code, "name": "Duplicada", "warehouse_company": "cacao"},
    )

    assert response.status_code == 200
    assert "El código ya está en uso." in response.get_data(as_text=True)
    with app.app_context():
        rows = database.session.execute(database.select(Warehouse).filter_by(code=code)).scalars().all()
        assert len(rows) == 1
        assert rows[0].name == "Bodega existente"
        configurations = (
            database.session.execute(database.select(WarehouseCompanyAccount).filter_by(warehouse_code=code)).scalars().all()
        )
        assert configurations == []
