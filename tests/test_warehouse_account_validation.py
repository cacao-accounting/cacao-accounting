# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La configuración contable de bodegas exige cuentas de inventario propias, activas y hoja (#2174).

``_validate_warehouse_company_rows`` (inventario/services.py) y la ruta
``inventario_bodega_nuevo`` (inventario/routes.py) rechazan con flash controlado una
cuenta de inventario inactiva, de grupo o de otra compañía, sin persistir la bodega;
una cuenta válida de cacao sí se persiste junto a su ``WarehouseCompanyAccount``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Warehouse, WarehouseCompanyAccount, database

MENSAJE_CUENTA_NO_HOJA = "activa, habilitada y ser una cuenta hoja"
MENSAJE_CUENTA_AJENA = "debe pertenecer a la compañía"


@pytest.fixture
def cuentas_bodega(app):
    """Crea cuentas de inventario válidas e inválidas y programa su limpieza."""
    sufijo = uuid4().hex[:6].upper()
    codigos = {
        "valida": f"IVA{sufijo}",
        "inactiva": f"IVI{sufijo}",
        "grupo": f"IVG{sufijo}",
        "ajena": f"IVX{sufijo}",
    }
    definiciones = {
        "valida": {"entity": "cacao", "active": True, "enabled": True, "group": False},
        "inactiva": {"entity": "cacao", "active": False, "enabled": False, "group": False},
        "grupo": {"entity": "cacao", "active": True, "enabled": True, "group": True},
        "ajena": {"entity": "alpha", "active": True, "enabled": True, "group": False},
    }
    bodegas_creadas: list[str] = []
    with app.app_context():
        ids = {}
        for clave, codigo in codigos.items():
            cuenta = Accounts(
                entity=definiciones[clave]["entity"],
                code=codigo,
                name=f"Cuenta inventario {clave} QA",
                classification="asset",
                account_type="inventory",
                active=definiciones[clave]["active"],
                enabled=definiciones[clave]["enabled"],
                group=definiciones[clave]["group"],
            )
            database.session.add(cuenta)
            database.session.flush()
            ids[clave] = str(cuenta.id)
        database.session.commit()

    yield {"ids": ids, "bodegas": bodegas_creadas}

    with app.app_context():
        configuraciones = (
            database.session.execute(
                database.select(WarehouseCompanyAccount).where(
                    (WarehouseCompanyAccount.inventory_account_id.in_(list(ids.values())))
                    | (WarehouseCompanyAccount.warehouse_code.in_(bodegas_creadas))
                )
            )
            .scalars()
            .all()
        )
        for configuracion in configuraciones:
            database.session.delete(configuracion)
        for codigo in bodegas_creadas:
            bodega = database.session.execute(database.select(Warehouse).filter_by(code=codigo)).scalar_one_or_none()
            if bodega is not None:
                database.session.delete(bodega)
        for codigo in codigos.values():
            cuenta = database.session.execute(database.select(Accounts).filter_by(code=codigo)).scalar_one_or_none()
            if cuenta is not None:
                database.session.delete(cuenta)
        database.session.commit()


def _datos_bodega(codigo_bodega: str, cuenta_id: str) -> dict[str, list[str] | str]:
    """POST del formulario de nueva bodega con una sola fila de configuración por compañía."""
    return {
        "code": codigo_bodega,
        "name": "Bodega QA validación",
        "warehouse_company": ["cacao"],
        "warehouse_inventory_account_id": [cuenta_id],
    }


@pytest.mark.parametrize(
    ("clave_cuenta", "fragmento_mensaje"),
    [
        ("inactiva", MENSAJE_CUENTA_NO_HOJA),
        ("grupo", MENSAJE_CUENTA_NO_HOJA),
        ("ajena", MENSAJE_CUENTA_AJENA),
    ],
)
def test_configuracion_invalida_rechaza_sin_persistir(
    app, authenticated_client, cuentas_bodega, clave_cuenta, fragmento_mensaje
):
    """Bodegas con cuenta inválida vuelven al formulario con flash y no crean registros."""
    codigo_bodega = f"BOD{uuid4().hex[:8].upper()}"
    datos = _datos_bodega(codigo_bodega, cuentas_bodega["ids"][clave_cuenta])

    response = authenticated_client().post("/inventory/warehouse/new", data=datos)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert b"Internal Server Error" not in response.data
    assert fragmento_mensaje in html
    with app.app_context():
        assert database.session.execute(database.select(Warehouse).filter_by(code=codigo_bodega)).scalar_one_or_none() is None
        assert (
            database.session.execute(
                database.select(WarehouseCompanyAccount).filter_by(warehouse_code=codigo_bodega)
            ).scalar_one_or_none()
            is None
        )


def test_configuracion_valida_persiste_bodega_y_cuenta(app, authenticated_client, cuentas_bodega):
    """Una cuenta de inventario activa, habilitada y hoja de cacao permite crear la bodega."""
    codigo_bodega = f"BOD{uuid4().hex[:8].upper()}"
    cuentas_bodega["bodegas"].append(codigo_bodega)
    datos = _datos_bodega(codigo_bodega, cuentas_bodega["ids"]["valida"])

    response = authenticated_client().post("/inventory/warehouse/new", data=datos)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/inventory/warehouse/list")
    with app.app_context():
        bodega = database.session.execute(database.select(Warehouse).filter_by(code=codigo_bodega)).scalar_one()
        assert bodega.company == "cacao"
        configuracion = database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code=codigo_bodega)
        ).scalar_one()
        assert configuracion.company == "cacao"
        assert configuracion.inventory_account_id == cuentas_bodega["ids"]["valida"]
        assert configuracion.is_active is True
