# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1871: una fila vacía en StockEntry no descarta las líneas posteriores."""

# pylint: disable=protected-access,unused-argument

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.database import NamingSeries, StockEntry, StockEntryItem, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company
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


def test_alta_http_persiste_lineas_posteriores_al_hueco(app, entorno_contable, authenticated_client):
    """Un POST con filas 0 y 2 persiste ambas líneas y suma el total real."""
    marcador = f"GAP-PERSIST-{uuid4().hex[:8]}"
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        database.session.commit()
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()

    form_data = {
        "purpose": "material_receipt",
        "company": "cacao",
        "naming_series": series_id,
        "posting_date": "2026-05-15",
        "transaction_currency": "NIO",
        "to_warehouse": "BOD01",
        "warehouse_0": "BOD01",
        "item_code_0": "ART01",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
        "item_code_1": "",
        "warehouse_2": "BOD01",
        "item_code_2": "ART01",
        "qty_2": "2",
        "rate_2": "5",
        "uom_2": "UND",
        "remarks": marcador,
    }

    response = authenticated_client().post("/inventory/stock-entry/material-receipt/new", data=form_data)

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        entrada = database.session.execute(database.select(StockEntry).filter_by(remarks=marcador)).scalar_one()
        lineas = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entrada.id)).scalars().all()
        try:
            assert len(lineas) == 2
            assert sum(linea.amount for linea in lineas) == Decimal("20")
            assert entrada.total_amount == Decimal("20")
        finally:
            database.session.delete(entrada)
            database.session.commit()
