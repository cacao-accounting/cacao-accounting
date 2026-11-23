# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1874: precargar una entrada desde un origen hidrata compañía y moneda."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import DeliveryNote, PurchaseReceipt, StockEntry, database

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


def test_origen_sin_moneda_deja_los_campos_editables(app, authenticated_client):
    """Un origen heredado sin moneda transaccional no bloquea la cabecera vacía."""
    with app.app_context():
        origen = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 15),
            transaction_currency=None,
            base_currency="NIO",
            document_no=f"SE-{uuid4().hex[:8]}",
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id

    response = authenticated_client("admin").get(f"{URL}?source_type=stock_entry&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": ""' in body
    assert '"initialHeader"' not in body


@pytest.mark.parametrize(
    ("modelo", "source_type", "prefijo"),
    [
        (PurchaseReceipt, "purchase_receipt", "PR"),
        (DeliveryNote, "delivery_note", "DN"),
    ],
)
def test_origenes_de_compra_y_venta_hidratan_cabecera(app, authenticated_client, modelo, source_type, prefijo):
    """Recepción de compra y nota de entrega aportan compañía y moneda del origen."""
    with app.app_context():
        origen = modelo(
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            document_no=f"{prefijo}-{uuid4().hex[:8]}",
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id

    response = authenticated_client("admin").get(f"{URL}?source_type={source_type}&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'"initialSourceType": "{source_type}"' in body
    assert '"company": "cacao"' in body
    assert '"currency": "NIO"' in body
