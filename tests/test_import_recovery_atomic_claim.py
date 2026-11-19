# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1669: la recuperación de importaciones reclama el lote una sola vez.

Dos recuperaciones que leen el mismo lote vencido no deben insertar dos
errores `SYSTEM_TIMEOUT`; la actualización condicional decide un único dueño.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.utils import recovery

WORKERS = 2


@pytest.fixture
def import_recovery_scenario(tmp_path):
    """Create a file-backed SQLite app with one expired running batch."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'import-recovery.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        batch = ImportBatch(
            company_id="alpha",
            record_type="journal_entry",
            source_format="csv",
            import_status=4,
            started_at=datetime.now() - timedelta(hours=5),
        )
        database.session.add(batch)
        database.session.commit()
        ids = {"batch": batch.id}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _sync_expired_read(monkeypatch) -> None:
    """Pause both recoveries after reading the expired batch list."""
    barrier = Barrier(WORKERS)
    original = recovery._expired_batch_ids

    def synchronized(timeout_limit):
        batch_ids = original(timeout_limit)
        barrier.wait(timeout=20)
        return batch_ids

    monkeypatch.setattr(recovery, "_expired_batch_ids", synchronized)


def _run_recoveries(app) -> list[int]:
    """Run one recovery per worker and return the recovered counts."""

    def recover() -> int:
        with app.app_context():
            try:
                return recovery.recover_crashed_batches()
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        return list(workers.map(lambda _: recover(), range(WORKERS)))


def _retry_locked(callable_, attempts: int = 5):
    """Retry a SQLite write that hits the transient database lock."""
    for _ in range(attempts):
        try:
            return callable_()
        except OperationalError as exc:  # pragma: no cover - depends on scheduler
            if "locked" not in str(exc).lower():
                raise
    return callable_()


def _errors_for(app, batch_id: str) -> list[ImportBatchError]:
    """Read the persisted recovery errors for one batch."""
    with app.app_context():
        return list(database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all())


def test_concurrent_recovery_creates_a_single_timeout_error(import_recovery_scenario, monkeypatch):
    """Only one recovery owns the expired batch and records its error."""
    app, ids = import_recovery_scenario
    _sync_expired_read(monkeypatch)

    results = _retry_locked(lambda: _run_recoveries(app))

    assert sorted(results) == [0, 1]
    errors = _errors_for(app, ids["batch"])
    assert len(errors) == 1
    assert errors[0].error_type == "SYSTEM_TIMEOUT"


def test_recovery_leaves_the_batch_failed_and_is_idempotent(import_recovery_scenario):
    """A second sequential run finds nothing to recover."""
    app, ids = import_recovery_scenario

    with app.app_context():
        assert recovery.recover_crashed_batches() == 1
        batch = database.session.get(ImportBatch, ids["batch"])
        assert batch is not None and batch.import_status == 7
        assert recovery.recover_crashed_batches() == 0

    assert len(_errors_for(app, ids["batch"])) == 1


def test_recovery_skips_batches_within_the_timeout(import_recovery_scenario):
    """Un lote en proceso reciente no se marca como fallido."""
    app, _ids = import_recovery_scenario
    with app.app_context():
        fresh = ImportBatch(
            company_id="alpha",
            record_type="journal_entry",
            source_format="csv",
            import_status=4,
            started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )
        database.session.add(fresh)
        database.session.commit()
        fresh_id = fresh.id

        assert recovery.recover_crashed_batches() == 1

        assert database.session.get(ImportBatch, fresh_id).import_status == 4
