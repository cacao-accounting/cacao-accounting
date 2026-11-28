# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1670: la descripción importada solo se acepta con destino en la línea.

Los tipos con columna ``description`` la persisten; ``stock_entry`` no tiene
ese destino en ``StockEntryItem``, por lo que su esquema ya no la declara y un
valor pegado se rechaza en lugar de descartarse en silencio.
"""

from __future__ import annotations

from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry

MENSAJE_RECHAZO = "no admite descripción por línea"


def _columnas(doctype: str) -> set[str]:
    """Devuelve las claves declaradas por el esquema de importación."""
    return {column["key"] for column in LineImportSchemaRegistry.get_schema(doctype)["columns"]}


def test_el_esquema_de_stock_entry_ya_no_declara_descripcion():
    """Sin destino en StockEntryItem la columna no se ofrece."""
    assert "description" not in _columnas("stock_entry")


def test_los_tipos_con_destino_conservan_la_descripcion():
    """Los documentos cuya línea sí guarda descripción la siguen declarando."""
    for doctype in ("purchase_order", "purchase_request", "sales_order", "sales_invoice"):
        assert "description" in _columnas(doctype), doctype


def test_la_validacion_rechaza_descripcion_sin_destino(app, entorno_contable, authenticated_client):
    """Un pegado con descripción para stock_entry se rechaza antes de guardar."""
    del entorno_contable
    respuesta = authenticated_client("admin").post(
        "/api/line-import/validate",
        json={
            "doctype": "stock_entry",
            "context": {"company_id": "cacao"},
            "rows": [
                {
                    "item_code": "ART01",
                    "quantity": "2",
                    "uom": "UND",
                    "description": "Especificación del comprador",
                }
            ],
        },
    )

    assert respuesta.status_code == 200
    errores = respuesta.get_json()["errors"]
    assert any(error.get("field") == "description" and MENSAJE_RECHAZO in error.get("message", "") for error in errores)


def test_la_validacion_acepta_stock_entry_sin_descripcion(app, entorno_contable, authenticated_client):
    """La fila válida sin descripción sigue pasando la validación."""
    del entorno_contable
    respuesta = authenticated_client("admin").post(
        "/api/line-import/validate",
        json={
            "doctype": "stock_entry",
            "context": {"company_id": "cacao"},
            "rows": [{"item_code": "ART01", "quantity": "2", "uom": "UND"}],
        },
    )

    assert respuesta.status_code == 200
    errores = respuesta.get_json()["errors"]
    assert not any(error.get("field") == "description" for error in errores)


def test_sales_order_sigue_aceptando_descripcion(app, entorno_contable, authenticated_client):
    """El tipo que sí persiste la descripción no se ve afectado por el guard."""
    del entorno_contable
    respuesta = authenticated_client("admin").post(
        "/api/line-import/validate",
        json={
            "doctype": "sales_order",
            "context": {"company_id": "cacao"},
            "rows": [{"item_code": "ART01", "qty": "2", "uom": "UND", "description": "Nota de venta"}],
        },
    )

    assert respuesta.status_code == 200
    errores = respuesta.get_json()["errors"]
    assert not any(error.get("field") == "description" for error in errores)
