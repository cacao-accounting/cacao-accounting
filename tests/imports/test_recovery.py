# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para la recuperación de lotes de importación interrumpidos."""

from datetime import datetime, timedelta

import cacao_accounting
from cacao_accounting import create_app
from cacao_accounting.database import database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.utils.recovery import recover_crashed_batches
from ulid import ULID


def test_create_app_does_not_log_recovery_error_without_import_tables(monkeypatch):
    """Crear la app sin esquema inicializado no debe emitir error de recuperación."""

    def fail_on_error(*args, **kwargs):
        raise AssertionError("No debe registrar error si no existen tablas de importación.")

    monkeypatch.setattr(cacao_accounting.log, "error", fail_on_error)

    create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})


def test_recover_crashed_batches_returns_zero_without_pending_batches():
    """La recuperación sin lotes vencidos debe ser silenciosa."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    with app.app_context():
        database.create_all()

        recovered = recover_crashed_batches()

        assert recovered == 0
        assert ImportBatchError.query.count() == 0


def test_recover_crashed_batches_marks_stale_processing_batch_failed():
    """Los lotes en proceso por más de cuatro horas se marcan como fallidos."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    with app.app_context():
        database.create_all()
        batch = ImportBatch(
            id=str(ULID()),
            record_type="chart_of_accounts",
            company_id="cacao",
            import_status=4,
            started_at=datetime.now() - timedelta(hours=5),
        )
        database.session.add(batch)
        database.session.commit()

        recovered = recover_crashed_batches()

        assert recovered == 1
        assert batch.import_status == 7
        assert ImportBatchError.query.filter_by(batch_id=batch.id, error_type="SYSTEM_TIMEOUT").count() == 1
