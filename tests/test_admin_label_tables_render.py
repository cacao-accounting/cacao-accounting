# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2065 y #2067: las tablas administrativas no exponen valores técnicos.

Las regresiones renderizan las plantillas reales con instancias transitorias del
modelo. No escriben en los catálogos compartidos de la suite —el defecto original
de estas pruebas— porque el comportamiento bajo revisión es la presentación, no
la persistencia.
"""

from __future__ import annotations

from decimal import Decimal

from flask import render_template

from cacao_accounting.database import LedgerMappingRule, PriceList, PurchaseMatchingConfig, SalesMatchingConfig


def _tabla(html: str) -> str:
    """Extrae la primera tabla de resultados del HTML renderizado."""
    return html.split("<table", 1)[1].split("</table>", 1)[0]


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

    tabla = _tabla(html)
    assert "Activo" in tabla
    assert "Inactivo" in tabla
    assert ">True<" not in tabla
    assert ">False<" not in tabla


def test_price_lists_renderiza_booleanos_localizados(app):
    """Las columnas Compra, Venta y Predeterminada usan Sí/No."""
    listas = [
        PriceList(name="Lista compra", company="cacao", currency="NIO", is_buying=True, is_selling=False, is_default=True),
        PriceList(name="Lista venta", company="cacao", currency="NIO", is_buying=False, is_selling=True, is_default=False),
    ]

    with app.test_request_context("/settings/price-lists"):
        html = render_template("admin/price_lists.html", price_lists=listas, titulo="Listas de Precios")

    tabla = _tabla(html)
    assert "Lista compra" in tabla
    assert "Lista venta" in tabla
    assert "Sí" in tabla
    assert "No" in tabla
    assert ">True<" not in tabla
    assert ">False<" not in tabla


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
