# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1889: el detalle de StockEntry muestra ambas bodegas, origen por línea y lote legible.

Una transferencia conserva la bodega de origen y destino en la cabecera y en la
línea; la relación documental activa se adjunta por línea y el lote se presenta
por su número público, no por el identificador técnico.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    Batch,
    DocumentRelation,
    StockEntry,
    StockEntryItem,
    Warehouse,
    database,
)


@pytest.fixture
def transferencia_con_origen(app, entorno_contable):
    """Transferencia con relación de compra y lote en la línea."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    destino = f"B{sufijo}"
    lote = f"LOTE-{sufijo}"
    with app.app_context():
        database.session.add(Warehouse(code=destino, name="Bodega Destino", company="cacao"))
        batch = Batch(item_code="ART01", batch_no=lote)
        database.session.add(batch)
        database.session.flush()
        entry = StockEntry(
            company="cacao",
            purpose="material_transfer",
            document_no=f"SE-{sufijo}",
            posting_date=date(2026, 5, 15),
            from_warehouse="BOD01",
            to_warehouse=destino,
            docstatus=1,
        )
        database.session.add(entry)
        database.session.flush()
        linea = StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ART01",
            source_warehouse="BOD01",
            target_warehouse=destino,
            qty=Decimal("2"),
            uom="UND",
            amount=Decimal("20"),
            batch_id=batch.id,
        )
        database.session.add(linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_receipt",
                source_id="PR-SOURCE-1889",
                source_item_id="PR-LINE-1889",
                target_type="stock_entry",
                target_id=entry.id,
                target_item_id=linea.id,
                company="cacao",
                qty=Decimal("2"),
                relation_type="transfer",
            )
        )
        database.session.commit()
        ids = {"entry": entry.id, "batch": batch.id, "destino": destino, "lote": lote}
    yield ids
    with app.app_context():
        database.session.execute(database.delete(DocumentRelation).where(DocumentRelation.target_id == ids["entry"]))
        database.session.execute(database.delete(StockEntryItem).where(StockEntryItem.stock_entry_id == ids["entry"]))
        database.session.execute(database.delete(StockEntry).where(StockEntry.id == ids["entry"]))
        database.session.execute(database.delete(Batch).where(Batch.id == ids["batch"]))
        database.session.execute(database.delete(Warehouse).where(Warehouse.code == ids["destino"]))
        database.session.commit()


def test_detalle_de_transferencia_muestra_bodegas_origen_y_destino(app, authenticated_client, transferencia_con_origen):
    """La cabecera y la línea distinguen origen y destino."""
    ids = transferencia_con_origen
    response = authenticated_client("admin").get(f"/inventory/stock-entry/{ids['entry']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "BOD01" in cuerpo
    assert ids["destino"] in cuerpo
    assert 'data-source-warehouse="BOD01"' in cuerpo
    assert f'data-target-warehouse="{ids["destino"]}"' in cuerpo


def test_detalle_de_transferencia_adjunta_origen_por_linea_y_lote_legible(app, authenticated_client, transferencia_con_origen):
    """La relación activa llega a la línea y el lote no expone su ULID."""
    ids = transferencia_con_origen
    response = authenticated_client("admin").get(f"/inventory/stock-entry/{ids['entry']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert 'data-source-type="purchase_receipt"' in cuerpo
    assert 'data-source-id="PR-SOURCE-1889"' in cuerpo
    assert 'data-source-item-id="PR-LINE-1889"' in cuerpo
    assert f'data-batch-no="{ids["lote"]}"' in cuerpo
    assert ids["batch"] not in cuerpo
