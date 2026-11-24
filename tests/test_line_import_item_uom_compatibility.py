# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1624: la importación rechaza UOM sin conversión para el artículo."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Item, ItemUOMConversion, UOM, database


def _crear_uom_incompatible() -> str:
    codigo = f"BX{uuid4().hex[:5].upper()}"
    database.session.add(UOM(code=codigo, name="Caja de prueba"))
    database.session.commit()
    return codigo


def _limpiar(codigo_uom: str) -> None:
    database.session.execute(database.delete(ItemUOMConversion).where(ItemUOMConversion.from_uom == codigo_uom))
    database.session.execute(database.delete(UOM).where(UOM.code == codigo_uom))
    database.session.commit()


def test_endpoint_rechaza_uom_existente_sin_conversion(app, authenticated_client, entorno_contable):
    """Una UOM global no basta si el artículo no tiene conversión configurada."""
    del entorno_contable
    with app.app_context():
        codigo_uom = _crear_uom_incompatible()

    try:
        respuesta = authenticated_client("admin").post(
            "/api/line-import/validate",
            json={
                "doctype": "sales_order",
                "context": {"company_id": "cacao"},
                "rows": [{"item_code": "ART01", "qty": "2", "uom": codigo_uom}],
            },
        )

        assert respuesta.status_code == 200
        errores = respuesta.get_json()["errors"]
        assert any(error.get("field") == "uom" for error in errores)
        assert any(
            "convertir" in error.get("message", "") or "conversion" in error.get("message", "").lower() for error in errores
        )
    finally:
        with app.app_context():
            _limpiar(codigo_uom)


def test_endpoint_acepta_uom_con_conversion_configurada(app, authenticated_client, entorno_contable):
    """Una UOM con factor explícito sigue siendo válida en la importación."""
    del entorno_contable
    with app.app_context():
        codigo_uom = _crear_uom_incompatible()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        database.session.add(
            ItemUOMConversion(item_code=item.code, from_uom=codigo_uom, to_uom=item.default_uom, conversion_factor=12)
        )
        database.session.commit()

    try:
        respuesta = authenticated_client("admin").post(
            "/api/line-import/validate",
            json={
                "doctype": "sales_order",
                "context": {"company_id": "cacao"},
                "rows": [{"item_code": "ART01", "qty": "2", "uom": codigo_uom}],
            },
        )

        assert respuesta.status_code == 200
        errores_uom = [error for error in respuesta.get_json()["errors"] if error.get("field") == "uom"]
        assert errores_uom == []
    finally:
        with app.app_context():
            _limpiar(codigo_uom)
