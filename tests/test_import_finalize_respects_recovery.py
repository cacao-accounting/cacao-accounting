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

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.utils import recovery
from sqlalchemy import update


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
