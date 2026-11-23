# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1203: cada commit del adapter renueva la propiedad del lote."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services import import_service
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.utils import recovery
from cacao_accounting.imports.utils.recovery import _expired_batch_ids


def _file_app(path):
    """Create an isolated SQLite database for the independent-session race."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{path}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "import-lease-test-secret",
        }
    )
    with application.app_context():
        database.create_all()
    return application


def test_commit_interno_del_adapter_renueva_el_lease(app, entorno_contable, monkeypatch):
    """Un commit interno durante un documento largo evita una recuperación prematura."""
    now = datetime.now(UTC).replace(tzinfo=None)
    advanced_time = now + timedelta(hours=5)

    with app.app_context():
        batch = ImportBatch(
            company_id="cacao",
            record_type="journal_entry",
            source_format="csv",
            source_filename=f"lease-{uuid4().hex[:8]}.csv",
            import_status=4,
            started_at=now,
        )
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

        class AdapterWithInternalCommit:
            """Mirrors domain adapters whose service commits inside persist_document."""

            @staticmethod
            def build_document(rows, context):
                return {}

            @staticmethod
            def persist_document(document):
                monkeypatch.setattr(import_service, "_utc_now_naive", lambda: advanced_time)
                database.session.add(ImportBatchError(batch_id=batch_id, error_type="TEST_DOCUMENT", message="Persistido"))
                database.session.commit()

        result = ImportService()._process_document(
            AdapterWithInternalCommit(), "doc-1", [{}], {}, SimpleNamespace(company_id="cacao"), batch_id
        )

        assert result == (1, 0)
        database.session.refresh(batch)
        assert batch.import_status == 4
        assert batch.started_at == advanced_time
        assert batch_id not in _expired_batch_ids(advanced_time - timedelta(hours=4))


def test_recovery_en_sesion_separada_espera_commit_del_documento(tmp_path, monkeypatch):
    """Recovery no puede reclamar un lote mientras el worker confirma el documento."""
    application = _file_app(tmp_path / "lease-race.sqlite")
    worker_ready = Event()
    release_worker = Event()
    recovery_attempted = Event()
    recovery_done = Event()
    result: dict[str, object] = {}

    with application.app_context():
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="lease",
                    name="Lease",
                    company_name="Lease SA",
                    tax_id="LEASE-1",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        batch = ImportBatch(
            company_id="lease",
            record_type="journal_entry",
            source_format="csv",
            source_filename="lease.csv",
            import_status=4,
            started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=5),
        )
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

    original_claim = recovery._claim_expired_batch

    def observe_recovery_claim(candidate_id, timeout_limit):
        if candidate_id == batch_id:
            recovery_attempted.set()
        return original_claim(candidate_id, timeout_limit)

    monkeypatch.setattr(recovery, "_claim_expired_batch", observe_recovery_claim)

    def run_worker():
        try:
            with application.app_context():
                try:
                    batch_record = database.session.get(ImportBatch, batch_id)

                    class Adapter:
                        """Stage an import result and pause before its transaction commits."""

                        @staticmethod
                        def build_document(rows, context):
                            return {}

                        @staticmethod
                        def persist_document(document):
                            database.session.add(
                                ImportBatchError(batch_id=batch_id, error_type="WORKER_DOCUMENT", message="Committed")
                            )
                            worker_ready.set()
                            if not release_worker.wait(timeout=10):
                                raise TimeoutError("The test did not release the worker in time.")

                    result["worker"] = ImportService()._process_document(Adapter(), "doc", [{}], {}, batch_record, batch_id)
                finally:
                    database.session.remove()
        except Exception as error:  # captured and asserted by the test thread
            result["worker_error"] = error

    def run_recovery():
        try:
            with application.app_context():
                try:
                    result["recovered"] = recovery.recover_crashed_batches()
                finally:
                    database.session.remove()
        except Exception as error:  # captured and asserted by the test thread
            result["recovery_error"] = error
        finally:
            recovery_done.set()

    worker = Thread(target=run_worker)
    recovery_thread = Thread(target=run_recovery)
    try:
        worker.start()
        assert worker_ready.wait(timeout=10)
        recovery_thread.start()
        assert recovery_attempted.wait(timeout=10)
        assert not recovery_done.wait(timeout=0.1)
        release_worker.set()
        worker.join(timeout=10)
        recovery_thread.join(timeout=10)

        assert not worker.is_alive()
        assert not recovery_thread.is_alive()
        assert "worker_error" not in result
        assert "recovery_error" not in result
        assert result["worker"] == (1, 0)
        assert result["recovered"] == 0

        with application.app_context():
            final_batch = database.session.get(ImportBatch, batch_id)
            assert final_batch.import_status == 4
            assert final_batch.started_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
            errors = database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all()
            assert [error.error_type for error in errors] == ["WORKER_DOCUMENT"]
    finally:
        release_worker.set()
        worker.join(timeout=10)
        recovery_thread.join(timeout=10)
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
