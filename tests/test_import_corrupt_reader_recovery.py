# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1031: un lector corrupto no deja el lote zombi en proceso.

La validación convierte cualquier fallo del lector en un lote fallido con
error registrado, y la recuperación incluye lotes con `started_at` nulo.
"""

from __future__ import annotations

from uuid import uuid4
import zipfile

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.utils.recovery import recover_crashed_batches


@pytest.fixture
def corrupt_reader_scenario(tmp_path):
    """Create a batch pointing at a file with a valid ZIP magic but bad body."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    corrupt_file = tmp_path / "corrupt.xlsx"
    with zipfile.ZipFile(corrupt_file, "w") as archive:
        archive.writestr("foo.txt", "not a workbook")

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
            source_format="xlsx",
            source_filename="corrupt.xlsx",
            source_path=str(corrupt_file),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        ids = {"batch": batch.id}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _batch(app, batch_id: str) -> ImportBatch:
    """Read the batch from a fresh session."""
    with app.app_context():
        batch = database.session.get(ImportBatch, batch_id)
        assert batch is not None
        return batch


def _errors(app, batch_id: str) -> list[ImportBatchError]:
    """Read the persisted batch errors."""
    with app.app_context():
        return list(database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all())


def test_corrupt_reader_marks_the_batch_failed(corrupt_reader_scenario):
    """The validation finishes in state 7 with a SYSTEM_ERROR row."""
    app, ids = corrupt_reader_scenario

    with app.app_context():
        assert ImportService().validate(ids["batch"]) is True

    batch = _batch(app, ids["batch"])
    assert batch.import_status == 7
    assert batch.started_at is None
    errors = _errors(app, ids["batch"])
    assert len(errors) == 1
    assert errors[0].error_type == "SYSTEM_ERROR"


def test_recovery_includes_batches_with_a_null_started_at(corrupt_reader_scenario):
    """A zombie in state 4 without started_at is recovered."""
    app, ids = corrupt_reader_scenario

    with app.app_context():
        batch = database.session.get(ImportBatch, ids["batch"])
        batch.import_status = 4
        batch.started_at = None
        database.session.commit()
        assert recover_crashed_batches() == 1

    batch = _batch(app, ids["batch"])
    assert batch.import_status == 7
    errors = _errors(app, ids["batch"])
    assert [error.error_type for error in errors] == ["SYSTEM_TIMEOUT"]
