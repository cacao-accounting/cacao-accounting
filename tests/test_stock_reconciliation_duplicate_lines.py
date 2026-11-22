# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresión #1212: una conciliación cuenta una vez cada saldo item/bodega."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad import posting_service
from cacao_accounting.database import NamingSeries, StockEntry, StockEntryItem, Warehouse, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company
from cacao_accounting.inventario.service import validate_stock_reconciliation_line_keys


def _series_id(app) -> str:
    """Return the configured stock-entry sequence for test requests."""
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        database.session.commit()
        return database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()


def _line(index: int, warehouse: str) -> dict[str, str]:
    """Build one valid physical-count line."""
    return {
        f"item_code_{index}": "ART01",
        f"warehouse_{index}": warehouse,
        f"uom_{index}": "UND",
        f"counted_qty_{index}": str(index + 1),
        f"target_valuation_rate_{index}": "1",
        f"target_stock_value_{index}": str(index + 1),
    }


def _post_reconciliation(client, series_id: str, remarks: str, lines: list[dict[str, str]]):
    """Submit a physical count through the authenticated creation route."""
    data = {
        "purpose": "stock_reconciliation",
        "company": "cacao",
        "naming_series": series_id,
        "posting_date": date(2026, 5, 15).isoformat(),
        "transaction_currency": "NIO",
        "remarks": remarks,
    }
    for line in lines:
        data.update(line)
    return client.post("/inventory/stock-entry/reconciliation/new", data=data)


def test_creacion_rechaza_dos_conteos_del_mismo_articulo_y_bodega(app, entorno_contable, authenticated_client):
    """Dos cifras absolutas para el mismo saldo no llegan a persistirse."""
    marker = f"DUP-COUNT-{uuid4().hex}"
    client = authenticated_client()
    response = _post_reconciliation(client, _series_id(app), marker, [_line(0, "BOD01"), _line(1, "BOD01")])

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(StockEntry).filter_by(remarks=marker)).scalar_one_or_none() is None
        assert database.session.execute(database.select(StockEntryItem)).scalars().all() == []


def test_creacion_permite_el_mismo_articulo_en_bodegas_distintas(app, entorno_contable, authenticated_client):
    """Cada bodega es un saldo independiente aunque comparta artículo."""
    with app.app_context():
        database.session.add(Warehouse(code="BOD02", name="Bodega dos", company="cacao", is_active=True))
        database.session.commit()
    marker = f"SPLIT-COUNT-{uuid4().hex}"
    response = _post_reconciliation(authenticated_client(), _series_id(app), marker, [_line(0, "BOD01"), _line(1, "BOD02")])

    assert response.status_code == 302
    with app.app_context():
        entry = database.session.execute(database.select(StockEntry).filter_by(remarks=marker)).scalar_one()
        lines = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entry.id)).scalars().all()
        assert {line.source_warehouse for line in lines} == {"BOD01", "BOD02"}
        assert len(lines) == 2


@pytest.mark.parametrize(
    ("lines", "raises"),
    [
        ([("ART01", "BOD01"), ("ART01", "BOD01")], True),
        ([("ART01", "BOD01"), ("ART01", "BOD02")], False),
        ([(" ART01 ", " BOD01 "), ("ART01", "BOD01")], True),
    ],
)
def test_duplicate_key_validator_normalizes_item_and_warehouse(lines, raises):
    """The shared domain guard compares normalized company/item/warehouse keys."""
    if raises:
        with pytest.raises(ValueError, match="no puede repetir"):
            validate_stock_reconciliation_line_keys("cacao", lines)
    else:
        validate_stock_reconciliation_line_keys("cacao", lines)


def test_posting_rechaza_lineas_duplicadas_heredadas(app, entorno_contable, monkeypatch):
    """Un borrador antiguo duplicado se detiene antes de calcular movimientos."""
    with app.app_context():
        entry = StockEntry(company="cacao", purpose="stock_reconciliation", posting_date=date(2026, 5, 15), docstatus=0)
        database.session.add(entry)
        database.session.flush()
        database.session.add_all(
            [
                StockEntryItem(
                    stock_entry_id=entry.id,
                    item_code="ART01",
                    qty=1,
                    uom="UND",
                    source_warehouse="BOD01",
                    target_warehouse="BOD01",
                ),
                StockEntryItem(
                    stock_entry_id=entry.id,
                    item_code="ART01",
                    qty=1,
                    uom="UND",
                    source_warehouse="BOD01",
                    target_warehouse="BOD01",
                ),
            ]
        )
        database.session.flush()
        monkeypatch.setattr(
            posting_service,
            "_create_stock_movements_for_items",
            lambda *_args: pytest.fail("No debe crear movimientos para una conciliación duplicada"),
        )

        with pytest.raises(ValueError, match="no puede repetir"):
            posting_service._create_stock_ledger(entry)


def test_creacion_conciliacion_sin_moneda_deriva_la_funcional(app, entorno_contable, authenticated_client):
    """#1811: el formulario de conciliación no envía moneda; se deriva la funcional."""
    marker = f"NOCUR-{uuid4().hex}"
    client = authenticated_client()
    data = {
        "purpose": "stock_reconciliation",
        "company": "cacao",
        "naming_series": _series_id(app),
        "posting_date": date(2026, 5, 15).isoformat(),
        "remarks": marker,
    }
    data.update(_line(0, "BOD01"))
    response = client.post("/inventory/stock-entry/reconciliation/new", data=data)

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        entry = database.session.execute(database.select(StockEntry).filter_by(remarks=marker)).scalar_one()
        assert entry.transaction_currency == "NIO"
        assert entry.base_currency == "NIO"
