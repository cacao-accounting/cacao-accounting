# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1871: una fila vacía en StockEntry no descarta las líneas posteriores."""

# pylint: disable=protected-access,unused-argument

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.inventario import services as inventario


def test_fila_vacia_no_trunca_las_lineas_siguientes(app, monkeypatch):
    """Se visitan todos los índices enviados, no solo hasta el primer hueco."""
    visitados: list[tuple[int, str]] = []

    def registrar(entry, index, item_code):
        visitados.append((index, item_code))
        return Decimal("0")

    monkeypatch.setattr(inventario, "_save_stock_entry_item", registrar)
    monkeypatch.setattr(
        inventario,
        "request",
        SimpleNamespace(
            form=OrderedDict([("item_code_0", ""), ("item_code_1", "A"), ("item_code_01", "alias"), ("item_code_2", "B")])
        ),
    )

    with app.app_context():
        inventario._save_stock_entry_items(SimpleNamespace())

    assert visitados == [(1, "A"), (2, "B")]


def test_fila_vacia_no_trunca_lineas_de_conciliacion(app, monkeypatch):
    """Las conciliaciones también procesan cada línea enviada después de un hueco."""
    validadas: list[tuple[str, str | None]] = []
    guardadas: list[tuple[int, str, str | None]] = []

    def validar(company, lines):
        validadas.extend(lines)

    def guardar(entry, index, item_code, warehouse):
        guardadas.append((index, item_code, warehouse))
        return Decimal("10")

    monkeypatch.setattr(inventario, "validate_stock_reconciliation_line_keys", validar)
    monkeypatch.setattr(inventario, "_save_stock_reconciliation_item", guardar)
    monkeypatch.setattr(
        inventario,
        "request",
        SimpleNamespace(
            form=OrderedDict(
                [
                    ("item_code_0", ""),
                    ("item_code_1", "A"),
                    ("item_code_01", "alias"),
                    ("warehouse_1", "WH-A"),
                    ("item_code_2", "B"),
                    ("warehouse_2", "WH-A"),
                ]
            )
        ),
    )
    entry = SimpleNamespace(company="cacao", to_warehouse="WH-A", from_warehouse=None)

    with app.app_context():
        total = inventario._save_stock_reconciliation_items(entry)

    assert total == Decimal("20")
    assert validadas == [("A", "WH-A"), ("B", "WH-A")]
    assert guardadas == [(1, "A", "WH-A"), (2, "B", "WH-A")]
