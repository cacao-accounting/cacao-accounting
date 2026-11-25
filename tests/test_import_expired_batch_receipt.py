# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1674: la importación rechaza lotes vencidos para la fecha del documento."""

from __future__ import annotations

import csv
from datetime import date
from uuid import uuid4

from cacao_accounting.database import Batch, Item, Party, PurchaseReceipt, PurchaseReceiptItem, User, database
from cacao_accounting.imports.adapters.transaction_documents import PurchaseReceiptAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


def test_lote_vencido_se_rechaza_al_validar_la_fila(app, entorno_contable):
    """El prechequeo replica la regla de posting: expiry <= fecha es vencido."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    codigo = f"VENC-{sufijo}"
    with app.app_context():
        database.session.add(
            Item(
                code=codigo,
                name=f"Item vencimiento {sufijo}",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                has_expiry_date=True,
            )
        )
        database.session.flush()
        lote = Batch(item_code=codigo, batch_no=f"LOTE-{sufijo}", expiry_date=date(2026, 10, 31), is_active=True)
        database.session.add(lote)
        database.session.commit()
        lote_id = lote.id

    try:
        adapter = PurchaseReceiptAdapter()
        with app.app_context():
            errores_vencido = adapter._validate_row_batch(codigo, f"LOTE-{sufijo}", date(2026, 11, 1))
            assert errores_vencido == [
                f"El lote 'LOTE-{sufijo}' del item '{codigo}' está vencido para la fecha de contabilización."
            ]

            assert adapter._validate_row_batch(codigo, f"LOTE-{sufijo}", date(2026, 10, 31)) == errores_vencido
            assert adapter._validate_row_batch(codigo, f"LOTE-{sufijo}", date(2026, 10, 30)) == []
    finally:
        with app.app_context():
            database.session.execute(database.delete(Batch).where(Batch.id == lote_id))
            database.session.execute(database.delete(Item).where(Item.code == codigo))
            database.session.commit()


def _archivo_y_lote(app, tmp_path, *, sufijo: str, fecha: date, numero_lote: str) -> str:
    """Crea un lote de importación de recepciones con una fila de datos."""
    with app.app_context():
        proveedor_id = database.session.execute(database.select(Party.id).filter_by(code="PRV001")).scalar_one()
    ruta = tmp_path / f"recepcion-{sufijo}.csv"
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            [
                "document_ref",
                "fecha",
                "moneda",
                "tipo_cambio",
                "tercero",
                "producto",
                "descripcion",
                "uom",
                "cantidad",
                "precio_unitario",
                "bodega",
                "lote",
                "numero_serie",
                "notas",
            ]
        )
        escritor.writerow(
            [
                f"REC-{sufijo}",
                fecha.isoformat(),
                "NIO",
                "1",
                str(proveedor_id),
                "ART01",
                "Artículo de prueba",
                "UND",
                "2",
                "10",
                "BOD01",
                numero_lote,
                "",
                f"NOTA-{sufijo}",
            ]
        )
    with app.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        lote = ImportBatch(
            company_id="cacao",
            record_type="purchase_receipt",
            source_format="csv",
            source_filename=ruta.name,
            source_path=str(ruta),
            import_status=3,
            created_by=usuario.id,
        )
        database.session.add(lote)
        database.session.commit()
        return lote.id


def test_el_flujo_de_importacion_no_crea_borrador_con_lote_vencido(entorno_contable_aislado, tmp_path):
    """La fecha igual al vencimiento se rechaza antes de persistir la recepción."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    numero_lote = f"LOTE-{sufijo}"
    with app.app_context():
        item = database.session.get(
            Item, database.session.execute(database.select(Item.id).filter_by(code="ART01")).scalar_one()
        )
        item.has_expiry_date = True
        database.session.add(Batch(item_code="ART01", batch_no=numero_lote, expiry_date=date(2026, 5, 20), is_active=True))
        database.session.commit()

    lote_id = _archivo_y_lote(app, tmp_path, sufijo=sufijo, fecha=date(2026, 5, 21), numero_lote=numero_lote)
    with app.app_context():
        assert ImportService().execute(lote_id) is True
        database.session.expire_all()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 2
        assert (
            database.session.execute(
                database.select(PurchaseReceipt.id).where(PurchaseReceipt.remarks == f"NOTA-{sufijo}")
            ).scalar_one_or_none()
            is None
        )
        mensajes = [
            error.message
            for error in database.session.execute(
                database.select(ImportBatchError).where(ImportBatchError.batch_id == lote_id)
            ).scalars()
        ]
        assert any("vencido" in mensaje for mensaje in mensajes), mensajes


def test_el_flujo_de_importacion_acepta_fecha_anterior_al_vencimiento(entorno_contable_aislado, tmp_path):
    """La misma fila con fecha previa al vencimiento crea el borrador."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    numero_lote = f"LOTE-{sufijo}"
    with app.app_context():
        item = database.session.get(
            Item, database.session.execute(database.select(Item.id).filter_by(code="ART01")).scalar_one()
        )
        item.has_expiry_date = True
        database.session.add(Batch(item_code="ART01", batch_no=numero_lote, expiry_date=date(2026, 5, 20), is_active=True))
        database.session.commit()

    lote_id = _archivo_y_lote(app, tmp_path, sufijo=sufijo, fecha=date(2026, 5, 19), numero_lote=numero_lote)
    with app.app_context():
        assert ImportService().execute(lote_id) is True
        database.session.expire_all()
        lote = database.session.get(ImportBatch, lote_id)
        mensajes = [
            error.message
            for error in database.session.execute(
                database.select(ImportBatchError).where(ImportBatchError.batch_id == lote_id)
            ).scalars()
        ]
        assert lote.import_status != 2, mensajes
        recepcion = database.session.execute(
            database.select(PurchaseReceipt).where(PurchaseReceipt.remarks == f"NOTA-{sufijo}")
        ).scalar_one()
        assert recepcion.docstatus == 0
        assert (
            database.session.execute(
                database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=recepcion.id)
            ).scalar_one()
            is not None
        )
