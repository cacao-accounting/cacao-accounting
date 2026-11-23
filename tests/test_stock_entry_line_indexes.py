# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1871: una fila vacía en StockEntry no descarta las líneas posteriores."""

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
        SimpleNamespace(form=OrderedDict([("item_code_0", ""), ("item_code_1", "A"), ("item_code_2", "B")])),
    )

    with app.app_context():
        inventario._save_stock_entry_items(SimpleNamespace())

    assert visitados == [(1, "A"), (2, "B")]
