# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2269: moneda y tasa por línea atraviesan la importación real de comprobantes."""

from __future__ import annotations

import csv
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import ComprobanteContableDetalle, User, database
from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


def _crear_lote(app, tmp_path, encabezados, filas):
    """Persiste un CSV real y su lote de importación pendiente de validar."""
    ruta = tmp_path / f"comprobante-{uuid4().hex[:8]}.csv"
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(encabezados)
        escritor.writerows(filas)

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
        return lote.id


def _filas(credito: str, tasa: str = "36") -> list[list[str]]:
    return [
        ["AS-2269", "2026-05-15", "1101", "100", "0", "USD", tasa, "Caja en dolares"],
        ["AS-2269", "2026-05-15", "4101", "0", credito, "NIO", "1", "Ingreso en cordobas"],
    ]


def test_plantilla_ofrece_moneda_y_tasa_en_ambos_idiomas():
    """Los encabezados que consume el adaptador también se descargan."""
    assert {"moneda", "tipo_cambio"}.issubset(JournalEntryAdapter().localized_columns("es"))
    assert {"currency", "exchange_rate"}.issubset(JournalEntryAdapter().localized_columns("en"))


def test_importacion_real_conserva_moneda_y_tasa_por_linea(entorno_contable_aislado, tmp_path):
    """El lote valida, ejecuta y guarda la moneda y la tasa de cada línea."""
    app = entorno_contable_aislado.app
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    lote_id = _crear_lote(app, tmp_path, encabezados, _filas("3600"))
    servicio = ImportService()

    with app.app_context():
        assert servicio.validate(lote_id)
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 3
        assert ImportBatchError.query.filter_by(batch_id=lote_id).count() == 0

        assert servicio.execute(lote_id)
        # El worker se ejecuta en otro contexto de aplicación: se descarta la
        # sesión local para leer el estado ya confirmado por la importación.
        database.session.remove()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 5

        detalles = (
            database.session.execute(
                database.select(ComprobanteContableDetalle)
                .filter_by(entity="cacao")
                .order_by(ComprobanteContableDetalle.order)
            )
            .scalars()
            .all()
        )
        assert [(detalle.currency_id, detalle.exchange_rate) for detalle in detalles] == [
            ("USD", Decimal("36")),
            ("NIO", Decimal("1")),
        ]


def test_importacion_acepta_encabezados_localizados_de_moneda_y_tasa(entorno_contable_aislado, tmp_path):
    """Los encabezados en inglés de la plantilla se normalizan al contrato."""
    app = entorno_contable_aislado.app
    encabezados = ["document_reference", "date", "account", "debit", "credit", "currency", "exchange_rate"]
    filas = [
        ["AS-2269-EN", "2026-05-15", "1101", "100", "0", "USD", "36"],
        ["AS-2269-EN", "2026-05-15", "4101", "0", "3600", "NIO", "1"],
    ]
    lote_id = _crear_lote(app, tmp_path, encabezados, filas)

    with app.app_context():
        assert ImportService().validate(lote_id)
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 3
        assert ImportBatchError.query.filter_by(batch_id=lote_id).count() == 0


def test_importacion_rechaza_desbalance_en_moneda_funcional(entorno_contable_aislado, tmp_path):
    """La conversión por línea no permite aprobar un comprobante descuadrado."""
    app = entorno_contable_aislado.app
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    lote_id = _crear_lote(app, tmp_path, encabezados, _filas("3500"))

    with app.app_context():
        assert ImportService().validate(lote_id)
        errores = ImportBatchError.query.filter_by(batch_id=lote_id).all()
        assert any("no esta balanceado por libro" in error.message for error in errores)
        assert not any(error.error_type == "UNKNOWN_COLUMN" for error in errores)


def test_importacion_rechaza_tasa_invalida(entorno_contable_aislado, tmp_path):
    """Una tasa no numérica se detecta en la validación del borrador."""
    app = entorno_contable_aislado.app
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    lote_id = _crear_lote(app, tmp_path, encabezados, _filas("3600", tasa="no-numerica"))

    with app.app_context():
        assert ImportService().validate(lote_id)
        errores = ImportBatchError.query.filter_by(batch_id=lote_id).all()
        assert any(error.error_type == "BUSINESS_RULE" for error in errores)
        assert not any(error.error_type == "UNKNOWN_COLUMN" for error in errores)
