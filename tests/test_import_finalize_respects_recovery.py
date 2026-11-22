# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1203: el finalizador del worker respeta el estado tomado por recovery.

Si la recuperación marca un lote vencido como fallido (7) mientras el worker
sigue procesando, `_finalize_execution()` no debe sobrescribirlo con estado
5/6 y contadores de completado.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import update

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.readers.base import TabularBook
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.utils import recovery


def _app(tmp_path):
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'finalize.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
    return app


def _batch(app, *, status: int = 4, started_at=None):
    with app.app_context():
        suffix = uuid4().hex[:6]
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )
        batch = ImportBatch(
            company_id="alpha",
            record_type="journal_entry",
            source_format="csv",
            import_status=status,
            started_at=started_at if started_at is not None else datetime.now() - timedelta(hours=5),
        )
        database.session.add(batch)
        database.session.commit()
        return batch.id


def test_finalize_no_sobrescribe_estado_de_recovery(tmp_path):
    """Si recovery dejó el lote en 7, el worker no lo convierte en 5/6."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            # Interleaving: recovery reclama el lote vencido y lo marca fallido.
            assert recovery._claim_expired_batch(batch_id, datetime.now()) is True
            database.session.commit()

            ImportService()._finalize_execution(batch, batch_id, success_count=10, error_count=0)
            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert final.import_status == 7
            assert final.success_rows != 10
            errores = database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all()
            assert errores == []
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_finalize_completa_cuando_el_worker_sigue_dueno(tmp_path):
    """Control positivo: con el lote aun en 4, el worker finaliza en 5."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            ImportService()._finalize_execution(batch, batch_id, success_count=3, error_count=0)
            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert final.import_status == 5
            assert final.success_rows == 3
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_finalize_marca_parcial_si_hay_errores(tmp_path):
    """Control positivo: errores sin recovery llevan a estado 6."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            ImportService()._finalize_execution(batch, batch_id, success_count=2, error_count=1)
            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert final.import_status == 6
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_finalize_conserva_estado_si_recovery_gana_entre_lectura_y_update(tmp_path, monkeypatch):
    """#1203: la transición terminal es condicional a nivel SQL.

    Se fuerza el interleaving: el worker lee el lote (estado 4), recovery toma
    el lote y lo marca fallido (7), y luego el worker intenta finalizar. El
    UPDATE condicional `WHERE import_status = 4` no debe sobrescribir el 7.
    """
    from cacao_accounting.imports.services import import_service as import_service_module

    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            service = ImportService()
            original_execute = database.session.execute
            notified: dict[str, bool] = {"done": False}

            def racing_execute(statement, *args, **kwargs):
                # Antes de que el worker ejecute su UPDATE, recovery reclama el
                # lote en una sesión independiente y lo deja en 7.
                if not notified["done"] and getattr(statement, "is_update", False):
                    notified["done"] = True
                    with app.app_context():
                        recovery._claim_expired_batch(batch_id, datetime.now())
                        database.session.commit()
                        database.session.remove()
                return original_execute(statement, *args, **kwargs)

            monkeypatch.setattr(import_service_module.database.session, "execute", racing_execute)
            service._finalize_execution(batch, batch_id, success_count=10, error_count=0)
            monkeypatch.undo()

            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert notified["done"] is True
            assert final.import_status == 7
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_finalize_resuelve_cancelacion_llegada_entre_lectura_y_update(tmp_path, monkeypatch):
    """#1203: una cancelación que llega antes del UPDATE termina en estado 8.

    El worker lee el lote con cancel_requested=False, luego `/cancel` marca
    True y confirma; el UPDATE atómico del finalizador debe resolver a 8 (no
    dejar el lote en 4).
    """
    from cacao_accounting.imports.services import import_service as import_service_module

    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            service = ImportService()
            original_execute = database.session.execute
            notified: dict[str, bool] = {"done": False}

            def racing_execute(statement, *args, **kwargs):
                if not notified["done"] and getattr(statement, "is_update", False):
                    notified["done"] = True
                    with app.app_context():
                        database.session.execute(
                            update(ImportBatch)
                            .where(ImportBatch.id == batch_id)
                            .values(cancel_requested=True)
                            .execution_options(synchronize_session=False)
                        )
                        database.session.commit()
                        database.session.remove()
                return original_execute(statement, *args, **kwargs)

            monkeypatch.setattr(import_service_module.database.session, "execute", racing_execute)
            service._finalize_execution(batch, batch_id, success_count=5, error_count=0)
            monkeypatch.undo()

            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert notified["done"] is True
            assert final.cancel_requested is True
            assert final.import_status == 8
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_worker_cancelled_con_archivo_vacio_termina_en_estado_terminal(tmp_path, monkeypatch):
    """#1032: una cancelación durante la lectura vacía no queda en procesamiento."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():

            class _Reader:  # pylint: disable=too-few-public-methods
                """Reader that submits cancellation while reading an empty file."""

                def read(self, _file_path):
                    """Set the cancellation flag before returning no rows."""
                    database.session.execute(
                        update(ImportBatch).where(ImportBatch.id == batch_id).values(cancel_requested=True)
                    )
                    database.session.commit()
                    return TabularBook(columns=["nombre"], rows=[], source_format="csv")

            monkeypatch.setattr(ImportService, "_get_reader", lambda _self, _format: _Reader())
            ImportService()._execute_task(app, batch_id)

            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert final.import_status == 8
            assert final.cancel_requested is True
            assert final.started_at is None
            assert final.completed_at is not None
            assert (
                database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all() == []
            )
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_recovery_conserva_estado_si_gana_antes_de_confirmar_cancelacion(tmp_path, monkeypatch):
    """#1032: una cancelación no sobrescribe el estado 7 que ganó recovery."""
    from cacao_accounting.imports.services import import_service as import_service_module

    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            database.session.execute(update(ImportBatch).where(ImportBatch.id == batch_id).values(cancel_requested=True))
            database.session.commit()
            original_execute = database.session.execute
            interleaving = {"done": False}

            def racing_execute(statement, *args, **kwargs):
                if not interleaving["done"] and getattr(statement, "is_update", False):
                    interleaving["done"] = True
                    with app.app_context():
                        assert recovery._claim_expired_batch(batch_id, datetime.now()) is True
                        database.session.commit()
                        database.session.remove()
                return original_execute(statement, *args, **kwargs)

            monkeypatch.setattr(import_service_module.database.session, "execute", racing_execute)
            assert ImportService()._check_batch_cancellation(batch, batch_id) is True
            monkeypatch.undo()

            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert interleaving["done"] is True
            assert final.cancel_requested is True
            assert final.import_status == 7
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_error_fatal_coincidente_con_cancelacion_cierra_en_estado_terminal(tmp_path):
    """#1032: un error fatal concurrente no reabre ni deja incompleta la cancelación."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            database.session.execute(update(ImportBatch).where(ImportBatch.id == batch_id).values(cancel_requested=True))
            database.session.commit()

            ImportService()._handle_execution_error(batch_id, ValueError("archivo vacío"))

            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert final.import_status == 8
            assert final.started_at is None
            assert final.completed_at is not None
            assert not database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all()
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cancel_solo_se_acepta_para_worker_activo(tmp_path):
    """Un lote terminal no puede aceptar una cancelación tardía."""
    app = _app(tmp_path)
    try:
        running_batch_id = _batch(app)
        terminal_batch_id = _batch(app, status=5)
        with app.app_context():
            service = ImportService()
            assert service.cancel(running_batch_id) is True
            assert service.cancel(terminal_batch_id) is False

            running_batch = database.session.get(ImportBatch, running_batch_id)
            terminal_batch = database.session.get(ImportBatch, terminal_batch_id)
            assert running_batch.cancel_requested is True
            assert terminal_batch.cancel_requested is False
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cancel_despues_de_un_documento_conserva_contadores_parciales(tmp_path):
    """#1032: el estado cancelado refleja documentos ya confirmados antes del corte."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            batch.total_rows = 2
            database.session.commit()
            service = ImportService()
            processed = []

            class _Adapter:
                """Adapter that requests cancellation after the first persisted document."""

                def build_document(self, rows, _context):
                    """Return the document rows for the test service."""
                    return {"rows": list(rows)}

                def persist_document(self, _document):
                    """Commit cancellation after the first document."""
                    processed.append("document")
                    if len(processed) == 1:
                        database.session.execute(
                            update(ImportBatch).where(ImportBatch.id == batch_id).values(cancel_requested=True)
                        )

            success, errors = service._process_all_documents(
                batch,
                batch_id,
                _Adapter(),
                {"one": [{"row": 1}], "two": [{"row": 2}]},
                {"company_id": "alpha"},
            )
            assert processed == ["document"]
            service._finalize_execution(batch, batch_id, success, errors)

            database.session.expire_all()
            final = database.session.get(ImportBatch, batch_id)
            assert final.import_status == 8
            assert final.success_rows == 1
            assert final.error_rows == 0
            assert final.processed_rows == 1
            assert final.completed_at is not None
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_worker_se_detiene_cuando_recovery_reclama_entre_documentos(tmp_path):
    """#1203: si recovery reclama el lote entre documentos, el siguiente no se crea."""
    app = _app(tmp_path)
    try:
        batch_id = _batch(app)
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            service = ImportService()
            processed: list[str] = []

            class _Adapter:
                def build_document(self, rows, context):
                    return {"rows": list(rows)}

                def persist_document(self, document):
                    processed.append("doc")
                    # Tras el primer documento, recovery reclama el lote vencido.
                    if len(processed) == 1:
                        assert recovery._claim_expired_batch(batch_id, datetime.now()) is True
                        database.session.commit()

            docs = {"doc_1": [{"row": 1}], "doc_2": [{"row": 2}]}
            success, error = service._process_all_documents(batch, batch_id, _Adapter(), docs, {"company_id": "alpha"})

            assert processed == ["doc"]
            assert success == 1
            database.session.expire_all()
            assert database.session.get(ImportBatch, batch_id).import_status == 7
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
