# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2065 y #2067: las tablas administrativas no exponen valores técnicos.

Las regresiones renderizan las plantillas reales con instancias transitorias del
modelo. No escriben en los catálogos compartidos de la suite —el defecto original
de estas pruebas— porque el comportamiento bajo revisión es la presentación, no
la persistencia.
"""

from __future__ import annotations

import re
from decimal import Decimal

from flask import render_template

from cacao_accounting.database import LedgerMappingRule, PriceList, PurchaseMatchingConfig, SalesMatchingConfig


def _tabla(html: str) -> str:
    """Extrae la primera tabla de resultados del HTML renderizado."""
    return html.split("<table", 1)[1].split("</table>", 1)[0]


def _filas(tabla: str) -> list[str]:
    """Devuelve las filas de datos, sin el encabezado."""
    return re.findall(r"<tr[^>]*>(.*?)</tr>", tabla, re.S)[1:]


def _celdas(fila: str) -> list[str]:
    """Extrae el texto plano de las celdas de una fila."""
    return [re.sub(r"<[^>]+>", "", celda).strip() for celda in re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S)]


def _nombre_fila(fila: str) -> str:
    """Devuelve la primera celda de la fila como identificador."""
    return _celdas(fila)[0]


def test_ledger_mapping_renderiza_estado_localizado(app):
    """La columna Estado muestra Activo/Inactivo y nunca True/False."""
    reglas = [
        LedgerMappingRule(
            id="regla-activa", source_book="DEFAULT_BOOK", target_book="NIIF", rule_description="Activa", is_active=True
        ),
        LedgerMappingRule(
            id="regla-inactiva", source_book="DEFAULT_BOOK", target_book="NIIF", rule_description="Inactiva", is_active=False
        ),
    ]

    with app.test_request_context("/settings/ledger-mapping-rules"):
        html = render_template("admin/ledger_mapping_rules.html", rules=reglas, books=[], accounts=[])

    filas = _filas(_tabla(html))
    assert len(filas) == 2
    assert "Activo" in filas[0] and "Inactivo" not in filas[0]
    assert "Desactivar" in filas[0]
    assert "Inactivo" in filas[1] and ">Activo<" not in filas[1]
    assert "Desactivar" not in filas[1]


def test_price_lists_renderiza_booleanos_localizados(app):
    """Las columnas Compra, Venta y Predeterminada usan Sí/No."""
    listas = [
        PriceList(name="Lista compra", company="cacao", currency="NIO", is_buying=True, is_selling=False, is_default=True),
        PriceList(name="Lista venta", company="cacao", currency="NIO", is_buying=False, is_selling=True, is_default=False),
    ]

    with app.test_request_context("/settings/price-lists"):
        html = render_template("admin/price_lists.html", price_lists=listas, titulo="Listas de Precios")

    filas = {_nombre_fila(fila): fila for fila in _filas(_tabla(html))}
    assert _celdas(filas["Lista compra"])[3:] == ["Sí", "No", "Sí"]
    assert _celdas(filas["Lista venta"])[3:] == ["No", "Sí", "No"]
    assert ">True<" not in "".join(filas.values())
    assert ">False<" not in "".join(filas.values())


def test_compra_renderiza_tipos_de_tolerancia_localizados(app):
    """La tabla de compras traduce percentage/absolute a % y Absoluto."""
    configuraciones = [
        PurchaseMatchingConfig(
            company="cacao",
            matching_type="3-way",
            price_tolerance_type="percentage",
            price_tolerance_value=Decimal("5"),
            qty_tolerance_type="absolute",
            qty_tolerance_value=Decimal("2"),
        )
    ]

    with app.test_request_context("/settings/purchase-reconciliation"):
        html = render_template(
            "admin/purchase_reconciliation_config.html",
            companies=[],
            selected_company="",
            selected_config=None,
            selected_advances=False,
            configs=configuraciones,
            advance_settings={},
            titulo="Conciliación de Compras",
        )

    tabla = _tabla(html)
    assert "5 %" in tabla
    assert "2 Absoluto" in tabla
    assert "percentage" not in tabla
    assert "absolute" not in tabla


def test_venta_renderiza_tipos_de_tolerancia_localizados(app):
    """La tabla de ventas traduce percentage/absolute a % y Absoluto."""
    configuraciones = [
        SalesMatchingConfig(
            company="cacao",
            matching_type="3-way",
            price_tolerance_type="absolute",
            price_tolerance_value=Decimal("7"),
            require_sales_order=True,
            allow_price_difference=False,
        )
    ]

    with app.test_request_context("/settings/sales-matching"):
        html = render_template(
            "admin/sales_matching_config.html",
            companies=[],
            selected_company="",
            selected_config=None,
            configs=configuraciones,
            titulo="Conciliación de Ventas",
        )

    tabla = _tabla(html)
    assert "7 Absoluto" in tabla
    assert "percentage" not in tabla
    assert "absolute" not in tabla
