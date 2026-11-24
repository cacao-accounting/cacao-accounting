# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1587: reorder_level prevalece y el mínimo aplica solo si falta aquel."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.database import Item, StockBin, Warehouse, database
from cacao_accounting.reportes.services import OperationalReportFilters, get_reorder_alerts


def _crear_articulo(entorno, codigo: str, *, reorder, minimo, cantidad: str) -> None:
    with entorno.app.app_context():
        bodega = database.session.execute(database.select(Warehouse).filter_by(company="cacao")).scalars().first()
        database.session.add(
            Item(
                code=codigo,
                name=f"Artículo {codigo}",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                reorder_level=None if reorder is None else Decimal(reorder),
                min_stock_qty=None if minimo is None else Decimal(minimo),
            )
        )
        database.session.flush()
        database.session.add(
            StockBin(
                company="cacao",
                item_code=codigo,
                warehouse=bodega.code,
                actual_qty=Decimal(cantidad),
                stock_value=Decimal(cantidad) * Decimal("10"),
            )
        )
        database.session.commit()


def _alertas(entorno):
    with entorno.app.app_context():
        return get_reorder_alerts(OperationalReportFilters(company="cacao"))


def test_reorder_level_prevalece_sobre_el_minimo(entorno_contable_aislado):
    """Con ambos umbrales, el stock entre ellos no dispara alerta."""
    _crear_articulo(entorno_contable_aislado, "ART-BOTH-1587", reorder="5", minimo="10", cantidad="8")

    alertas = _alertas(entorno_contable_aislado)

    assert all(fila.values["item_code"] != "ART-BOTH-1587" for fila in alertas.rows)


def test_minimo_aplica_cuando_no_hay_punto_de_reorden(entorno_contable_aislado):
    """Sin reorder_level, el mínimo sí alerta y calcula el faltante."""
    _crear_articulo(entorno_contable_aislado, "ART-MIN-1587", reorder=None, minimo="10", cantidad="8")

    alertas = _alertas(entorno_contable_aislado)
    fila = next(fila for fila in alertas.rows if fila.values["item_code"] == "ART-MIN-1587")

    assert fila.values["reorder_level"] == Decimal("10")
    assert fila.values["shortage_qty"] == Decimal("2")


def test_reorder_level_calcula_el_faltante_contra_su_propio_umbral(entorno_contable_aislado):
    """Bajo el punto de reorden, el faltante nunca es cero por el mínimo."""
    _crear_articulo(entorno_contable_aislado, "ART-LOW-1587", reorder="5", minimo="10", cantidad="4")

    alertas = _alertas(entorno_contable_aislado)
    fila = next(fila for fila in alertas.rows if fila.values["item_code"] == "ART-LOW-1587")

    assert fila.values["reorder_level"] == Decimal("5")
    assert fila.values["shortage_qty"] == Decimal("1")
