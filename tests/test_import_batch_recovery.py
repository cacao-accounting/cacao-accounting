# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Resiliencia del servicio de importación ante lectores corruptos.

Escenario de negocio (issue #1031): un archivo con extensión xlsx cuyo
contenido es un zip truncado puede pasar el chequeo de tipo y hacer que el
lector lance una excepción ajena a la tupla capturada. La fila del lote
no debe quedar atrapada en 'procesando' (estado 4 con started_at vacío)
sin salida por revalidar, cancelar o recuperar; la recuperación debe
rescatar también lotes en estado 4 sin marca de inicio.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database


@pytest.fixture
def importador():
    """Aplicación de prueba con una compañía para lotes de importación."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import Currency, Entity

        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao Accounting",
                company_name="Cacao Accounting SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _archivo_corrupto(tmp_path: Path) -> str:
    """Crea un 'xlsx' con la firma PK y contenido truncado inválido."""
    ruta = tmp_path / "extracto_corrupto.xlsx"
    ruta.write_bytes(b"PK\x03\x04" + b"contenido truncado que openpyxl no puede abrir")
    return str(ruta)


def _lote(application, ruta: str, *, estado: int = 1):
    from cacao_accounting.imports.models import ImportBatch

    lote = ImportBatch(
        company_id="cacao",
        record_type="customer",
        source_format="xlsx",
        source_filename="extracto_corrupto.xlsx",
        source_path=ruta,
        import_status=estado,
    )
    database.session.add(lote)
    database.session.commit()
    return lote.id


def test_validar_rechaza_lector_corrupto_con_lote_invalido(importador, tmp_path):
    """Un lector que lanza excepción cierra el lote en estado 7, no en 4."""
    application = importador
    with application.app_context():
        from cacao_accounting.imports.models import ImportBatch, ImportBatchError
        from cacao_accounting.imports.services.import_service import ImportService

        lote_id = _lote(application, _archivo_corrupto(tmp_path))
        assert ImportService().validate(lote_id) is True
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 7
        errores = database.session.query(ImportBatchError).filter_by(batch_id=lote_id).all()
        assert any(error.error_type == "SYSTEM_ERROR" for error in errores)


def test_recuperacion_rescata_lotes_en_procesamiento_sin_marca_de_inicio(importador, tmp_path):
    """Un lote en estado 4 con started_at NULL no queda perdido para siempre."""
    application = importador
    with application.app_context():
        from cacao_accounting.imports.models import ImportBatch, ImportBatchError
        from cacao_accounting.imports.utils.recovery import recover_crashed_batches

        lote_id = _lote(application, _archivo_corrupto(tmp_path), estado=4)
        lote = database.session.get(ImportBatch, lote_id)
        lote.started_at = None
        database.session.commit()

        assert recover_crashed_batches() >= 1
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 7
        errores = ImportBatchError.query.filter_by(batch_id=lote_id).all()
        assert any(error.error_type == "SYSTEM_TIMEOUT" for error in errores)


def test_recuperacion_no_toca_lotes_en_procesamiento_recientes(importador, tmp_path):
    """Un lote activo dentro del límite de 4 horas conserva su estado."""
    application = importador
    with application.app_context():
        from cacao_accounting.imports.models import ImportBatch
        from cacao_accounting.imports.utils.recovery import recover_crashed_batches

        lote_id = _lote(application, _archivo_corrupto(tmp_path), estado=4)
        lote = database.session.get(ImportBatch, lote_id)
        lote.started_at = datetime.now(UTC)
        database.session.commit()

        assert recover_crashed_batches() == 0
        assert database.session.get(ImportBatch, lote_id).import_status == 4
