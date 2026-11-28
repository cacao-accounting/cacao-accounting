# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1672: la importación real rechaza comprobantes con cuentas no vigentes."""

from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4

from cacao_accounting.database import (
    ComprobanteContable,
    ComprobanteContableDetalle,
    GLEntry,
    User,
    database,
)
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService

ENCABEZADOS = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio"]


def _escribir_csv(ruta: Path, filas: list[tuple[str, str]], referencia: str) -> None:
    """Escribe el CSV real que leerá el servicio de importación."""
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(ENCABEZADOS)
        for debito, credito in filas:
            escritor.writerow([referencia, "2026-05-15", "1101", debito, credito, "NIO", "1"])
            escritor.writerow([referencia, "2026-05-15", "4101", "0", "100", "NIO", "1"])


def _crear_lote(app, tmp_path: Path) -> tuple[str, Path, str]:
    """Crea un lote pendiente y devuelve su ruta y referencia únicos."""
    referencia = f"AS-1672-{uuid4().hex[:8]}"
    ruta = tmp_path / f"{referencia}.csv"
    _escribir_csv(ruta, [("100", "0")], referencia)
    with app.app_context():
        actor = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()
        lote = ImportBatch(
            company_id="cacao",
            record_type="journal_entry",
            source_format="csv",
            source_filename=ruta.name,
            source_path=str(ruta),
            import_status=1,
            accounting_book_id="DEFAULT_BOOK",
            created_by=actor,
        )
        database.session.add(lote)
        database.session.commit()
        return lote.id, ruta, referencia


def _sin_documentos(referencia: str) -> bool:
    """Indica si no quedaron cabecera, detalle ni GL para la referencia."""
    cabeceras = (
        database.session.execute(database.select(ComprobanteContable).where(ComprobanteContable.reference == referencia))
        .scalars()
        .all()
    )
    if cabeceras:
        return False
    detalles = database.session.execute(database.select(ComprobanteContableDetalle)).scalars().all()
    gl = database.session.execute(database.select(GLEntry)).scalars().all()
    return not detalles and not gl


def test_importacion_invalida_deja_lote_en_estado_2_sin_documentos(entorno_contable_aislado, tmp_path):
    """Una cuenta inexistente bloquea el lote antes de crear cualquier documento."""
    app = entorno_contable_aislado.app
    lote_id, ruta, referencia = _crear_lote(app, tmp_path)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(ENCABEZADOS)
        escritor.writerow([referencia, "2026-05-15", "9999", "100", "0", "NIO", "1"])
        escritor.writerow([referencia, "2026-05-15", "8888", "0", "100", "NIO", "1"])

    with app.app_context():
        assert ImportService().validate(lote_id) is True
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 2
        errores = ImportBatchError.query.filter_by(batch_id=lote_id).all()
        assert any(error.error_type == "BUSINESS_RULE" and "no existe" in error.message for error in errores)
        assert ImportService().execute(lote_id) is False
        assert _sin_documentos(referencia)


def test_importacion_revalida_el_archivo_antes_de_ejecutar(entorno_contable_aislado, tmp_path):
    """Cambiar el CSV después de validar impide crear borradores en la ejecución."""
    app = entorno_contable_aislado.app
    lote_id, ruta, referencia = _crear_lote(app, tmp_path)
    with app.app_context():
        servicio = ImportService()
        assert servicio.validate(lote_id) is True
        assert database.session.get(ImportBatch, lote_id).import_status == 3

        with ruta.open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(ENCABEZADOS)
            escritor.writerow([referencia, "2026-05-15", "9999", "100", "0", "NIO", "1"])
            escritor.writerow([referencia, "2026-05-15", "8888", "0", "100", "NIO", "1"])

        assert servicio.execute(lote_id) is True
        database.session.remove()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 2
        assert ImportBatchError.query.filter_by(batch_id=lote_id, error_type="BUSINESS_RULE").count() >= 1
        assert _sin_documentos(referencia)


def test_importacion_valida_crea_borrador_y_asientos(entorno_contable_aislado, tmp_path):
    """El control positivo conserva el flujo real válido de comprobantes."""
    app = entorno_contable_aislado.app
    lote_id, _, referencia = _crear_lote(app, tmp_path)
    with app.app_context():
        servicio = ImportService()
        assert servicio.validate(lote_id) is True
        assert servicio.execute(lote_id) is True
        database.session.remove()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 5
        cabecera = database.session.execute(
            database.select(ComprobanteContable).where(ComprobanteContable.reference == referencia)
        ).scalar_one()
        detalles = (
            database.session.execute(
                database.select(ComprobanteContableDetalle).where(ComprobanteContableDetalle.transaction_id == cabecera.id)
            )
            .scalars()
            .all()
        )
        assert len(detalles) == 2
