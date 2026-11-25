# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1854: duplicar un movimiento de inventario deja evidencia en el nuevo documento.

La duplicación crea un borrador independiente con sus propias líneas, sin
vínculos documentales ni movimientos de GL/stock. El AuditTrail del duplicado
debe registrar quién lo creó y referenciar el documento de origen.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.audit_trail_service import format_document_timeline
from cacao_accounting.database import (
    AuditTrail,
    DocumentRelation,
    GLEntry,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    database,
)


def _seed_entry(app) -> dict[str, str]:
    """Crea un movimiento borrador con una línea para duplicar."""
    sufijo = uuid4().hex[:10]
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 15),
            document_no=f"SE-ORIGEN-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            remarks=f"Movimiento origen {sufijo}",
        )
        database.session.add(entry)
        database.session.flush()
        line = StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ART01",
            qty=Decimal("2"),
            uom="UND",
            qty_in_base_uom=Decimal("2"),
            basic_rate=Decimal("10"),
            amount=Decimal("20"),
        )
        database.session.add(line)
        database.session.flush()
        relation = DocumentRelation(
            source_type="purchase_receipt",
            source_id=f"receipt-{sufijo}",
            target_type="stock_entry",
            target_id=entry.id,
            company="cacao",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
            relation_type="purchase_receipt_to_stock_entry",
            status="active",
        )
        database.session.add(relation)
        database.session.commit()
        return {"entry": entry.id, "document_no": entry.document_no, "remarks": entry.remarks, "line": line.id}


def test_duplicar_stock_entry_registra_creacion_con_origen(app, entorno_contable, authenticated_client):
    """El duplicado queda como borrador con un evento created y la referencia al origen."""
    origen = _seed_entry(app)

    respuesta = authenticated_client("admin").post(f"/inventory/stock-entry/{origen['entry']}/duplicate")

    assert respuesta.status_code == 302
    with app.app_context():
        duplicados = (
            database.session.execute(
                database.select(StockEntry).where(
                    StockEntry.company == "cacao",
                    StockEntry.remarks == origen["remarks"],
                    StockEntry.id != origen["entry"],
                )
            )
            .scalars()
            .all()
        )
        assert len(duplicados) == 1, "Debe existir exactamente un duplicado del movimiento."
        duplicado = duplicados[0]
        assert duplicado.docstatus == 0

        evento = database.session.execute(
            database.select(AuditTrail).filter_by(document_type="stock_entry", document_id=duplicado.id, action="created")
        ).scalar_one_or_none()
        assert evento is not None, "La duplicación no registró evento de auditoría."
        assert evento.actor_user_id is not None
        assert origen["document_no"] in (evento.comment or "")

        lineas = (
            database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=duplicado.id)).scalars().all()
        )
        assert len(lineas) == 1
        assert lineas[0].item_code == "ART01" and lineas[0].amount == Decimal("20.0000")

        vínculos = (
            database.session.execute(
                database.select(DocumentRelation.id).where(
                    DocumentRelation.target_type == "stock_entry",
                    DocumentRelation.target_id == duplicado.id,
                )
            )
            .scalars()
            .all()
        )
        assert vínculos == [], "El duplicado no debe heredar vínculos documentales."

        movimientos_stock = (
            database.session.execute(
                database.select(StockLedgerEntry.id).where(
                    StockLedgerEntry.voucher_type == "stock_entry",
                    StockLedgerEntry.voucher_id == duplicado.id,
                )
            )
            .scalars()
            .all()
        )
        assert movimientos_stock == []
        movimientos_gl = (
            database.session.execute(
                database.select(GLEntry.id).where(
                    GLEntry.voucher_type == "stock_entry",
                    GLEntry.voucher_id == duplicado.id,
                )
            )
            .scalars()
            .all()
        )
        assert movimientos_gl == []


@pytest.mark.parametrize("modo_escritorio", [True, False])
def test_timeline_del_duplicado_es_visible_en_desktop_y_cloud(app, authenticated_client, monkeypatch, modo_escritorio):
    """La vista de detalle muestra el evento created y su origen en ambos modos."""
    origen = _seed_entry(app)
    respuesta = authenticated_client("admin").post(f"/inventory/stock-entry/{origen['entry']}/duplicate")
    assert respuesta.status_code == 302

    with app.app_context():
        duplicado = (
            database.session.execute(
                database.select(StockEntry).where(
                    StockEntry.company == "cacao",
                    StockEntry.remarks == origen["remarks"],
                    StockEntry.id != origen["entry"],
                )
            )
            .scalars()
            .one()
        )
        duplicado_id = duplicado.id
        monkeypatch.setitem(app.config, "MODO_ESCRITORIO", modo_escritorio)
        timeline = format_document_timeline("stock_entry", duplicado_id)

    creados = [fila["event"] for fila in timeline if fila["event"].action == "created"]
    assert len(creados) == 1
    assert origen["document_no"] in (creados[0].comment or "")
    assert creados[0].actor_name or creados[0].actor_user_id

    detalle = authenticated_client("admin").get(f"/inventory/stock-entry/{duplicado_id}")
    assert detalle.status_code == 200
    cuerpo = detalle.get_data(as_text=True)
    assert "Historial del documento" in cuerpo
    assert origen["document_no"] in cuerpo
