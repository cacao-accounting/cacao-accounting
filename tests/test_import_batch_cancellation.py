# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cancelación de lotes de importación en ejecución.

Escenario de negocio (issue #1032): el operador de importaciones
solicita cancelar un lote mientras el ciclo de procesamiento está en
marcha (vía ``ImportService.cancel``). El estado 8 es terminal: la
finalización del ciclo debe respetarlo y conservar los contadores
parciales, nunca reescribirlo a 'completado' (5/6).
"""

from pathlib import Path

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database


@pytest.fixture
def importador_operando():
    """Aplicación de prueba con una compañía lista para importar clientes."""
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
        from cacao_accounting.database import Entity

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


def _lote_clientes(application, ruta_csv: str) -> str:
    from cacao_accounting.imports.models import ImportBatch

    lote = ImportBatch(
        company_id="cacao",
        record_type="customer",
        source_format="csv",
        source_filename="clientes.csv",
        source_path=ruta_csv,
        total_rows=3,
        import_status=3,
    )
    database.session.add(lote)
    database.session.commit()
    return lote.id


def test_la_cancelacion_en_ejecucion_se_mantiene_hasta_el_final(importador_operando, tmp_path: Path, monkeypatch):
    """El lote cancelado a mitad del ciclo termina cancelado, no completado."""
    application = importador_operando
    ruta_csv = tmp_path / "clientes.csv"
    ruta_csv.write_text("nombre\nCliente Uno\nCliente Dos\nCliente Tres\n", encoding="utf-8")

    with application.app_context():
        from cacao_accounting.imports.models import ImportBatch, ImportBatchError
        from cacao_accounting.imports.services.import_service import ImportService

        lote_id = _lote_clientes(application, str(ruta_csv))

        secuencia = {"procesados": 0}
        ejecucion_original = ImportService._process_document

        def procesa_y_cancela(self, adapter, ref, rows, context, batch, batch_id):
            resultado = ejecucion_original(self, adapter, ref, rows, context, batch, batch_id)
            secuencia["procesados"] += 1
            if secuencia["procesados"] == 1:
                # El operador confirma la cancelación desde otra sesión.
                self.cancel(batch_id)
            return resultado

        monkeypatch.setattr(ImportService, "_process_document", procesa_y_cancela)

        ImportService()._execute_task(application, lote_id)
        monkeypatch.undo()

        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 8, "La cancelación debe permanecer como estado terminal del lote."
        assert lote.success_rows == 1
        assert lote.cancel_requested is True
        assert lote.completed_at is not None
        errores = database.session.query(ImportBatchError).filter_by(batch_id=lote_id).all()
        assert not [error for error in errores if error.error_type in {"FATAL_ERROR", "IMPORT_ERROR"}]
