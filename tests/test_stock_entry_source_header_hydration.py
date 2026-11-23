# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1874: precargar una entrada desde un origen hidrata compañía y moneda."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import StockEntry, database

URL = "/inventory/stock-entry/new"


def _origen() -> StockEntry:
    """Crea un movimiento de inventario que sirve como documento origen."""
    sufijo = uuid4().hex[:8]
    entry = StockEntry(
        company="cacao",
        purpose="material_receipt",
        posting_date=date(2026, 5, 15),
        transaction_currency="NIO",
        base_currency="NIO",
        document_no=f"SE-{sufijo}",
    )
    database.session.add(entry)
    database.session.commit()
    return entry


def test_origen_valido_hidrata_cabecera_bloqueada(app, authenticated_client):
    """La compañía y la moneda del origen llegan al formulario."""
    with app.app_context():
        origen_id = _origen().id
    client = authenticated_client("admin")

    response = client.get(f"{URL}?source_type=stock_entry&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": "stock_entry"' in body
    assert '"initialHeader"' in body
    assert '"company": "cacao"' in body
    assert '"currency": "NIO"' in body


def test_origen_inexistente_deja_los_campos_editables(app, authenticated_client):
    """Un origen inexistente no bloquea compañía ni moneda."""
    client = authenticated_client("admin")

    response = client.get(f"{URL}?source_type=stock_entry&source_id=NO-EXISTE")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": ""' in body
    assert '"initialHeader"' not in body
