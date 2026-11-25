# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1854: duplicar un movimiento de inventario deja un único evento en el nuevo documento.

La duplicación crea un borrador independiente con sus propias líneas, sin
vínculos documentales ni movimientos de GL/stock. El AuditTrail del duplicado
debe registrar quién lo creó y referenciar el documento de origen, tanto en
Desktop como en Cloud, sin duplicar el evento automático de la inserción.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user
from sqlalchemy import inspect, select

from cacao_accounting.audit_trail_service import format_document_timeline
from cacao_accounting.database import (
    AuditTrail,
    DocumentRelation,
    GLEntry,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    User,
    database,
)
from cacao_accounting.inventario.routes import inventario_entrada_duplicar


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


def _configurar_modo(app, monkeypatch, escritorio: bool) -> None:
    """Fija el modo y los controles internos antes de ejecutar la petición."""
    monkeypatch.setitem(app.config, "MODO_ESCRITORIO", escritorio)
    monkeypatch.setitem(app.config, "INTERNAL_CONTROLS_ENFORCE", not escritorio)


@pytest.mark.parametrize("escritorio", [True, False])
def test_duplicar_stock_entry_deja_un_created_visible_en_ambos_modos(
    app, entorno_contable, authenticated_client, monkeypatch, escritorio
):
    """El duplicado conserva un solo evento con origen, actor y documento íntegro."""
    origen = _seed_entry(app)
    _configurar_modo(app, monkeypatch, escritorio)

    respuesta = authenticated_client("admin").post(f"/inventory/stock-entry/{origen['entry']}/duplicate")

    assert respuesta.status_code == 302
    with app.app_context():
        duplicados = (
            database.session.execute(
                select(StockEntry).where(
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

        eventos = (
            database.session.execute(
                select(AuditTrail).filter_by(
                    document_type="stock_entry",
                    document_id=duplicado.id,
                    action="created",
                )
            )
            .scalars()
            .all()
        )
        assert len(eventos) == 1, "La duplicación no debe emitir un created automático y otro explícito."
        evento = eventos[0]
        assert evento.actor_user_id is not None
        assert origen["document_no"] in (evento.comment or "")

        lineas = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=duplicado.id)).scalars().all()
        assert len(lineas) == 1
        assert lineas[0].item_code == "ART01" and lineas[0].amount == Decimal("20.0000")

        vinculos = (
            database.session.execute(
                select(DocumentRelation.id).where(
                    DocumentRelation.target_type == "stock_entry",
                    DocumentRelation.target_id == duplicado.id,
                )
            )
            .scalars()
            .all()
        )
        assert vinculos == [], "El duplicado no debe heredar vínculos documentales."

        movimientos_stock = (
            database.session.execute(
                select(StockLedgerEntry.id).where(
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
                select(GLEntry.id).where(
                    GLEntry.voucher_type == "stock_entry",
                    GLEntry.voucher_id == duplicado.id,
                )
            )
            .scalars()
            .all()
        )
        assert movimientos_gl == []

        timeline = format_document_timeline("stock_entry", duplicado.id)
        creados = [fila["event"] for fila in timeline if fila["event"].action == "created"]
        assert len(creados) == 1
        assert origen["document_no"] in (creados[0].comment or "")
        assert creados[0].actor_name or creados[0].actor_user_id
        duplicado_id = duplicado.id

    detalle = authenticated_client("admin").get(f"/inventory/stock-entry/{duplicado_id}")
    assert detalle.status_code == 200
    cuerpo = detalle.get_data(as_text=True)
    assert "Historial del documento" in cuerpo
    assert origen["document_no"] in cuerpo


def test_duplicacion_fallida_no_persiste_documento_ni_eventos(app, entorno_contable, monkeypatch):
    """Si falla el commit, la transacción no deja duplicado ni eventos."""
    origen = _seed_entry(app)
    _configurar_modo(app, monkeypatch, escritorio=False)
    actor_id = str(inspect(entorno_contable.admin_user).identity[0])
    with app.test_request_context(f"/inventory/stock-entry/{origen['entry']}/duplicate", method="POST"):
        login_user(database.session.get(User, actor_id))
        ids_antes = set(database.session.execute(select(StockEntry.id)).scalars().all())

        def _falla_commit(*args, **kwargs):
            raise RuntimeError("fallo de commit")

        monkeypatch.setattr(database.session, "commit", _falla_commit)

        with pytest.raises(RuntimeError, match="fallo de commit"):
            inventario_entrada_duplicar(origen["entry"])

        database.session.rollback()
        ids_despues = set(database.session.execute(select(StockEntry.id)).scalars().all())
        assert ids_despues == ids_antes
        eventos = (
            database.session.execute(
                select(AuditTrail.id).where(
                    AuditTrail.document_type == "stock_entry",
                    AuditTrail.action == "created",
                    AuditTrail.document_id.notin_(ids_antes),
                )
            )
            .scalars()
            .all()
        )
        assert eventos == []
