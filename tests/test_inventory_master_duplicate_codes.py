# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de campos requeridos y códigos duplicados en maestros de inventario."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import UOM, Warehouse, WarehouseCompanyAccount, database


@pytest.fixture
def inventory_master_cleanup(app):
    """Registra códigos creados por las pruebas y elimina sus filas al finalizar."""
    created = {"uom": [], "warehouse": []}
    yield created
    with app.app_context():
        for code in created["warehouse"]:
            database.session.execute(
                database.delete(WarehouseCompanyAccount).where(WarehouseCompanyAccount.warehouse_code == code)
            )
            warehouse = database.session.execute(database.select(Warehouse).filter_by(code=code)).scalar_one_or_none()
            if warehouse is not None:
                database.session.delete(warehouse)
        for code in created["uom"]:
            uom = database.session.execute(database.select(UOM).filter_by(code=code)).scalar_one_or_none()
            if uom is not None:
                database.session.delete(uom)
        database.session.commit()


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
    assert 'class="alert alert-danger' in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(UOM).filter_by(code="")).scalar_one_or_none() is None


def test_warehouse_rejects_missing_required_fields(app, authenticated_client):
    """An invalid warehouse POST does not persist empty code or name values."""
    response = authenticated_client().post(
        "/inventory/warehouse/new",
        data={"code": "", "name": "", "warehouse_company": "cacao"},
    )

    assert response.status_code == 200
    assert 'class="alert alert-danger' in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(Warehouse).filter_by(code="")).scalar_one_or_none() is None


def test_uom_valid_post_persists_row(app, authenticated_client, inventory_master_cleanup):
    """A valid UOM POST stores the submitted code and name."""
    code = f"U{uuid4().hex[:8].upper()}"
    inventory_master_cleanup["uom"].append(code)

    response = authenticated_client().post("/inventory/uom/new", data={"code": code, "name": "Unidad válida"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/inventory/uom/list")
    with app.app_context():
        uom = database.session.execute(database.select(UOM).filter_by(code=code)).scalar_one()
        assert uom.name == "Unidad válida"


def test_warehouse_valid_post_persists_row(app, authenticated_client, inventory_master_cleanup):
    """A valid warehouse POST stores the warehouse and its company configuration."""
    code = f"W{uuid4().hex[:8].upper()}"
    inventory_master_cleanup["warehouse"].append(code)

    response = authenticated_client().post(
        "/inventory/warehouse/new",
        data={"code": code, "name": "Bodega válida", "warehouse_company": "cacao"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/inventory/warehouse/list")
    with app.app_context():
        warehouse = database.session.execute(database.select(Warehouse).filter_by(code=code)).scalar_one()
        assert warehouse.name == "Bodega válida"
        assert warehouse.company == "cacao"
        configuration = database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code=code)
        ).scalar_one()
        assert configuration.company == "cacao"
        assert configuration.is_active is True


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
