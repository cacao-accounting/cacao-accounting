# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1675: un lote opcional en blanco se trata como ausente al construir la línea."""

from __future__ import annotations

import csv
from datetime import date
from uuid import uuid4

from cacao_accounting.database import Batch, Party, PurchaseReceipt, PurchaseReceiptItem, User, database
from cacao_accounting.imports.adapters.transaction_documents import PurchaseReceiptAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


def test_lote_en_blanco_no_se_resuelve_como_numero(app, entorno_contable):
    """El constructor no busca un lote con cadena vacía tras el strip."""
    del entorno_contable
    adapter = PurchaseReceiptAdapter()
    with app.app_context():
        assert adapter._resolve_batch_id("ART01", "   ") is None
        assert adapter._resolve_batch_id("ART01", "") is None
        assert adapter._resolve_batch_id("ART01", None) is None


def test_lote_valido_se_resuelve_sin_espacios(app, entorno_contable):
    """Un número real de lote, con espacios accidentales, resuelve al registro."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    adapter = PurchaseReceiptAdapter()
    with app.app_context():
        lote = Batch(item_code="ART01", batch_no=f"LOTE-{sufijo}", is_active=True)
        database.session.add(lote)
        database.session.commit()
        lote_id = lote.id

    try:
        with app.app_context():
            assert adapter._resolve_batch_id("ART01", f"  LOTE-{sufijo}  ") == lote_id
    finally:
        with app.app_context():
            database.session.execute(database.delete(Batch).where(Batch.id == lote_id))
            database.session.commit()


def _archivo_y_lote(app, tmp_path, *, sufijo: str, lote: str) -> str:
    """Crea un lote de recepciones con el campo de lote en blanco."""
    with app.app_context():
        proveedor_id = database.session.execute(database.select(Party.id).filter_by(code="PRV001")).scalar_one()
    ruta = tmp_path / f"recepcion-blanco-{sufijo}.csv"
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
                date(2026, 5, 19).isoformat(),
                "NIO",
                "1",
                str(proveedor_id),
                "ART01",
                "Artículo sin lote obligatorio",
                "UND",
                "2",
                "10",
                "BOD01",
                lote,
                "",
                f"NOTA-{sufijo}",
            ]
        )
    with app.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        lote_importacion = ImportBatch(
            company_id="cacao",
            record_type="purchase_receipt",
            source_format="csv",
            source_filename=ruta.name,
            source_path=str(ruta),
            import_status=1,
            created_by=usuario.id,
        )
        database.session.add(lote_importacion)
        database.session.commit()
        return lote_importacion.id


def test_validacion_y_ejecucion_aceptan_lote_opcional_en_blanco(entorno_contable_aislado, tmp_path) -> None:
    """Los espacios se tratan como ausencia y permiten crear el borrador."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    lote_id = _archivo_y_lote(app, tmp_path, sufijo=sufijo, lote="   ")
    with app.app_context():
        assert ImportService().validate(lote_id) is True
        lote = database.session.get(ImportBatch, lote_id)
        mensajes_validacion = [
            error.message
            for error in database.session.execute(database.select(ImportBatchError).filter_by(batch_id=lote_id)).scalars()
        ]
        assert lote.import_status == 3, mensajes_validacion

        assert ImportService().execute(lote_id) is True
        database.session.expire_all()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 5
        assert lote.success_rows == 1

        recepcion = database.session.execute(
            database.select(PurchaseReceipt).where(PurchaseReceipt.remarks == f"NOTA-{sufijo}")
        ).scalar_one()
        assert recepcion.docstatus == 0
        lineas = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=recepcion.id))
            .scalars()
            .all()
        )
        assert len(lineas) == 1
        assert lineas[0].batch_id is None
        mensajes = [
            error.message
            for error in database.session.execute(database.select(ImportBatchError).filter_by(batch_id=lote_id)).scalars()
        ]
        assert not any("lote" in mensaje.lower() for mensaje in mensajes), mensajes
