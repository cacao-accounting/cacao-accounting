# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1739: la configuración de bodega exige cuenta de inventario.

El posting valorizado no tiene fallback: si la bodega no define cuenta, todo
movimiento falla con ``PostingError``. La configuración debe rechazarse al
guardar en lugar de permitir una bodega que nunca podrá contabilizar.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Warehouse, WarehouseCompanyAccount, database
from cacao_accounting.inventario.services import _validate_warehouse_company_rows

MENSAJE_CUENTA_OBLIGATORIA = "cuenta de inventario es obligatoria"


def _crear_cuenta_inventario(app) -> str:
    """Crea una cuenta de inventario válida de la compañía y devuelve su id."""
    with app.app_context():
        sufijo = uuid4().hex[:6].upper()
        cuenta = Accounts(
            entity="cacao",
            code=f"INV{sufijo}",
            name=f"Cuenta inventario {sufijo}",
            classification="asset",
            account_type="inventory",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta)
        database.session.commit()
        return str(cuenta.id)


def _bodega(app, code: str) -> Warehouse | None:
    """Devuelve la bodega con el código indicado, si existe."""
    with app.app_context():
        return database.session.execute(database.select(Warehouse).filter_by(code=code)).scalar_one_or_none()


def test_la_validacion_rechaza_la_fila_sin_cuenta(app):
    """Una fila de compañía sin cuenta de inventario no es configuración válida."""
    with app.app_context():
        with pytest.raises(ValueError, match=MENSAJE_CUENTA_OBLIGATORIA):
            _validate_warehouse_company_rows([{"company": "cacao", "inventory_account_id": ""}])


def test_el_alta_de_bodega_sin_cuenta_no_persiste(app, entorno_contable, authenticated_client):
    """La ruta de alta re-renderiza con error y no crea la bodega incompleta."""
    del entorno_contable
    codigo = f"WH1739-{uuid4().hex[:6].upper()}"

    respuesta = authenticated_client("admin").post(
        "/inventory/warehouse/new",
        data={
            "code": codigo,
            "name": "Bodega sin cuenta 1739",
            "warehouse_company": "cacao",
            "warehouse_inventory_account_id": "",
        },
    )

    assert respuesta.status_code == 200
    assert _bodega(app, codigo) is None


def test_el_alta_de_bodega_con_cuenta_persiste_la_configuracion(app, entorno_contable, authenticated_client):
    """Con una cuenta válida la bodega y su configuración se guardan."""
    del entorno_contable
    codigo = f"WH1739V-{uuid4().hex[:6].upper()}"
    cuenta_id = _crear_cuenta_inventario(app)

    respuesta = authenticated_client("admin").post(
        "/inventory/warehouse/new",
        data={
            "code": codigo,
            "name": "Bodega con cuenta 1739",
            "warehouse_company": "cacao",
            "warehouse_inventory_account_id": cuenta_id,
        },
    )

    assert respuesta.status_code == 302
    with app.app_context():
        bodega = database.session.execute(database.select(Warehouse).filter_by(code=codigo)).scalar_one()
        configuracion = database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code=codigo, company="cacao")
        ).scalar_one()
        assert str(configuracion.inventory_account_id) == cuenta_id
        assert bodega.company == "cacao"
