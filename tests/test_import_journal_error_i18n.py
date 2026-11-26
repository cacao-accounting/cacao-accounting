# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2305: los errores visibles del comprobante importado se traducen."""

from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4

import pytest
from flask_babel import force_locale

from cacao_accounting.database import ComprobanteContable, User, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService

ENCABEZADOS = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio"]

CASOS = [
    (
        "monto",
        "2026-05-15",
        "no-numero",
        {
            "es": "Monto inválido en referencia {referencia}",
            "en": "Invalid amount in reference {referencia}",
        },
    ),
    (
        "fecha",
        "no-es-fecha",
        "100",
        {
            "es": "La fecha debe usar un formato válido.",
            "en": "The date must use a valid format.",
        },
    ),
    (
        "periodo",
        "2020-01-15",
        "100",
        {
            "es": "El periodo contable para la fecha 2020-01-15 está cerrado o no existe.",
            "en": "The accounting period for date 2020-01-15 is closed or does not exist.",
        },
    ),
]


def _crear_lote(app, ruta: Path, referencia: str, fecha: str, debito: str) -> str:
    """Prepara un lote real con un comprobante de dos líneas."""
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(ENCABEZADOS)
        escritor.writerow([referencia, fecha, "1101", debito, "0", "NIO", "1"])
        escritor.writerow([referencia, fecha, "4101", "0", "100", "NIO", "1"])

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


@pytest.mark.parametrize(("nombre", "fecha", "debito", "mensajes"), CASOS, ids=[caso[0] for caso in CASOS])
@pytest.mark.parametrize("locale", ["es", "en"])
def test_error_de_comprobante_importado_se_traduce(
    entorno_contable_aislado, tmp_path, nombre, fecha, debito, mensajes, locale
):
    """La validación real persiste el error en el idioma activo sin cambiar el rechazo."""
    app = entorno_contable_aislado.app
    referencia = f"AS-2305-{uuid4().hex[:8]}"
    lote_id = _crear_lote(app, tmp_path / f"{referencia}.csv", referencia, fecha, debito)

    with app.app_context(), force_locale(locale):
        assert ImportService().validate(lote_id) is True
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 2
        errores = [error.message for error in ImportBatchError.query.filter_by(batch_id=lote_id).all()]
        esperado = mensajes[locale].format(referencia=referencia)
        assert any(esperado in mensaje for mensaje in errores), errores
        assert not (
            database.session.execute(database.select(ComprobanteContable).where(ComprobanteContable.reference == referencia))
            .scalars()
            .all()
        )
