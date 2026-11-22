# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1891: el ajuste de inventario histórico no se duplica.

El propósito genérico `stock_adjustment` no tiene semántica canónica definida.
Duplicarlo crearía movimientos nuevos sin contrato; el registro histórico debe
seguir siendo consultable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import StockEntry, StockEntryItem, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

FECHA = date(2026, 5, 15)


def _entrada(purpose: str) -> StockEntry:
    """Crea un movimiento histórico con una línea válida."""
    suffix = uuid4().hex[:6]
    entrada = StockEntry(
        company="cacao",
        posting_date=FECHA,
        purpose=purpose,
        docstatus=1,
        document_no=f"SE-{suffix}",
        remarks=f"Movimiento {suffix}",
    )
    database.session.add(entrada)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entrada.id,
            item_code="ART01",
            source_warehouse="BOD01",
            qty=Decimal("1"),
            uom="UND",
            basic_rate=Decimal("5"),
            amount=Decimal("5"),
            qty_in_base_uom=Decimal("1"),
        )
    )
    database.session.commit()
    return entrada


def test_ajuste_historico_no_se_duplica_y_sigue_consultable(app, entorno_contable, authenticated_client):
    """Duplicar un `stock_adjustment` no crea filas y conserva el original."""
    with app.app_context():
        origen = _entrada("stock_adjustment")
        origen_id = origen.id
        antes = database.session.execute(database.select(StockEntry.id)).scalars().all()
    client = authenticated_client("admin")

    response = client.post(f"/inventory/stock-entry/{origen_id}/duplicate", follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        despues = database.session.execute(database.select(StockEntry.id)).scalars().all()
        original = database.session.get(StockEntry, origen_id)
        assert despues == antes
        assert original is not None
        assert original.docstatus == 1
        assert original.purpose == "stock_adjustment"
    detalle = client.get(f"/inventory/stock-entry/{origen_id}")
    assert detalle.status_code == 200


def test_ajuste_canonico_si_se_duplica(app, entorno_contable, authenticated_client):
    """El control positivo: un ajuste positivo canónico crea un borrador."""
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        origen = _entrada("adjustment_positive")
        origen_id = origen.id
        antes = len(database.session.execute(database.select(StockEntry.id)).scalars().all())
    client = authenticated_client("admin")

    response = client.post(f"/inventory/stock-entry/{origen_id}/duplicate")

    assert response.status_code == 302
    duplicado_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    assert duplicado_id != origen_id
    with app.app_context():
        entradas = database.session.execute(database.select(StockEntry.id)).scalars().all()
        assert len(entradas) == antes + 1
        duplicado = database.session.get(StockEntry, duplicado_id)
        assert duplicado is not None
        assert duplicado.docstatus == 0
        assert duplicado.purpose == "adjustment_positive"
