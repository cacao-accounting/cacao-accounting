# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1827: la salida usa la cuenta de inventario de la bodega origen."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.contabilidad.posting_service import _get_inventory_account_for_line
from cacao_accounting.database import Accounts, Warehouse, WarehouseCompanyAccount, database


def _cuenta(entorno, code: str) -> str:
    """Devuelve el id de una cuenta del escenario."""
    with entorno.app.app_context():
        return str(database.session.execute(database.select(Accounts.id).filter_by(entity="cacao", code=code)).scalar_one())


def _preparar_bodegas(entorno, origen_id: str, destino_id: str) -> None:
    """Configura cuentas de inventario distintas para las dos bodegas."""
    with entorno.app.app_context():
        database.session.add_all(
            [
                Warehouse(code="WH-ORIGEN-1827", name="Origen 1827", company="cacao", is_active=True),
                Warehouse(code="WH-DESTINO-1827", name="Destino 1827", company="cacao", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                WarehouseCompanyAccount(
                    warehouse_code="WH-ORIGEN-1827",
                    company="cacao",
                    inventory_account_id=origen_id,
                    is_active=True,
                ),
                WarehouseCompanyAccount(
                    warehouse_code="WH-DESTINO-1827",
                    company="cacao",
                    inventory_account_id=destino_id,
                    is_active=True,
                ),
            ]
        )
        database.session.commit()


def test_salida_resuelve_la_cuenta_de_la_bodega_origen(entorno_contable_aislado):
    """Material issue con origen y destino distintos acredita el origen."""
    origen_id = _cuenta(entorno_contable_aislado, "1109")
    destino_id = _cuenta(entorno_contable_aislado, "1102")
    _preparar_bodegas(entorno_contable_aislado, origen_id, destino_id)
    document = SimpleNamespace(from_warehouse="WH-ORIGEN-1827", to_warehouse="WH-DESTINO-1827")
    line = SimpleNamespace(
        warehouse="WH-DESTINO-1827",
        source_warehouse="WH-ORIGEN-1827",
        target_warehouse="WH-DESTINO-1827",
    )

    with entorno_contable_aislado.app.app_context():
        assert _get_inventory_account_for_line(document, line, "cacao", "material_issue") == origen_id


def test_entrada_resuelve_la_cuenta_de_la_bodega_destino(entorno_contable_aislado):
    """Material receipt usa la bodega destino aunque el origen esté informado."""
    origen_id = _cuenta(entorno_contable_aislado, "1109")
    destino_id = _cuenta(entorno_contable_aislado, "1102")
    _preparar_bodegas(entorno_contable_aislado, origen_id, destino_id)
    document = SimpleNamespace(from_warehouse="WH-ORIGEN-1827", to_warehouse="WH-DESTINO-1827")
    line = SimpleNamespace(
        warehouse="WH-ORIGEN-1827",
        source_warehouse="WH-ORIGEN-1827",
        target_warehouse="WH-DESTINO-1827",
    )

    with entorno_contable_aislado.app.app_context():
        assert _get_inventory_account_for_line(document, line, "cacao", "material_receipt") == destino_id
