# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2141: comparativo de órdenes alineado por identidad y ronda vigente."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.compras import routes
from cacao_accounting.compras.purchase_order_comparison_service import purchase_order_comparison_rows


def _item(code: str, qty: str, warehouse: str = "WH-1") -> SimpleNamespace:
    """Construye una línea de orden con la identidad comercial del comparativo."""
    return SimpleNamespace(
        item_code=code,
        uom="UND",
        qty_in_base_uom=qty,
        warehouse=warehouse,
        description="Artículo",
        item_name=code,
    )


def test_rows_match_same_item_with_different_quantities():
    """Dos órdenes del mismo artículo se comparan aunque cambie la cantidad."""
    orders = [SimpleNamespace(id="A"), SimpleNamespace(id="B")]
    items = {
        "A": [_item("ART-1", "5")],
        "B": [_item("ART-1", "8")],
    }

    rows = purchase_order_comparison_rows(orders, items)

    assert len(rows) == 1
    assert rows[0]["offers"]["A"] is items["A"][0]
    assert rows[0]["offers"]["B"] is items["B"][0]


def test_rows_keep_different_warehouses_separate():
    """La bodega sigue formando parte de la identidad comercial."""
    orders = [SimpleNamespace(id="A"), SimpleNamespace(id="B")]
    items = {
        "A": [_item("ART-1", "5", warehouse="WH-1")],
        "B": [_item("ART-1", "5", warehouse="WH-2")],
    }

    assert len(purchase_order_comparison_rows(orders, items)) == 2


def test_nuevo_participante_parte_de_la_ronda_vigente(monkeypatch):
    """El formulario usa la ronda vigente, no la histórica consultada."""
    comparison = SimpleNamespace(id="COMP-1")
    latest = SimpleNamespace(id="ROUND-2")
    monkeypatch.setattr(routes, "current_purchase_order_comparison_round", lambda _id: latest)
    monkeypatch.setattr(
        routes,
        "purchase_order_comparison_round_orders",
        lambda round_id: [
            SimpleNamespace(purchase_order_id="ORDER-A"),
            SimpleNamespace(purchase_order_id="ORDER-C"),
        ],
    )

    assert routes._current_round_participant_ids(comparison) == {"ORDER-A", "ORDER-C"}


def test_listado_no_ofrece_filtro_de_estado_inoperante():
    """El listado ya limita a solicitudes aprobadas; no muestra estado docstatus."""
    source = routes.__file__.replace("routes.py", "templates/compras/comparativo_ofertas_lista.html")
    with open(source, encoding="utf-8") as template:
        html = template.read()

    assert "list_filters(show_status=False)" in html
    assert "list_filters(show_status=True)" not in html
