# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1065: un archivo sin filas de datos no se presenta como importación exitosa.

La validación lo marca como fallido con un error claro y la ejecución defensiva
tampoco lo finaliza como completado.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService

HEADERS = "document_ref,fecha,cuenta,debito,credito\n"


@pytest.fixture
def empty_import_scenario(tmp_path):
    """Create an empty CSV batch ready to validate or execute."""
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
    source = tmp_path / "empty.csv"
    source.write_text(HEADERS, encoding="utf-8")

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
        ids = {}
        for status, label in ((1, "validate"), (3, "execute")):
            batch = ImportBatch(
                company_id="alpha",
                record_type="journal_entry",
                source_format="csv",
                source_filename="empty.csv",
                source_path=str(source),
                import_status=status,
            )
            database.session.add(batch)
            database.session.flush()
            ids[label] = batch.id
        database.session.commit()

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _batch(app, batch_id: str) -> ImportBatch:
    """Read the batch from a fresh transaction."""
    with app.app_context():
        batch = database.session.get(ImportBatch, batch_id)
        assert batch is not None
        return batch


def _errors(app, batch_id: str) -> list[ImportBatchError]:
    """Read the persisted batch errors."""
    with app.app_context():
        return list(database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all())


def test_validation_rejects_a_file_without_data_rows(empty_import_scenario):
    """A header-only file finishes in state 7 with NO_DATA_ROWS."""
    app, ids = empty_import_scenario

    with app.app_context():
        assert ImportService().validate(ids["validate"]) is True

    batch = _batch(app, ids["validate"])
    assert batch.import_status == 7
    assert batch.started_at is None
    errors = _errors(app, ids["validate"])
    assert [error.error_type for error in errors] == ["NO_DATA_ROWS"]


def test_execution_defensively_rejects_an_empty_legacy_batch(empty_import_scenario):
    """A batch already in state 3 cannot complete with zero documents."""
    app, ids = empty_import_scenario

    with app.app_context():
        assert ImportService().execute(ids["execute"]) is True

    batch = _batch(app, ids["execute"])
    assert batch.import_status == 7
    errors = _errors(app, ids["execute"])
    assert len(errors) == 1
    assert "no contiene filas" in errors[0].message.lower()


def test_worker_rejects_file_that_becomes_empty_after_execute(tmp_path):
    """#1200: si el archivo queda vacío entre execute() y la lectura del worker.

    `execute()` lee y valida; el worker vuelve a leer. Si en ese intervalo el
    archivo pasa a tener solo encabezados, el worker no debe finalizar en
    completado (estado 5) con cero datos.
    """
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
    source = tmp_path / "raced.csv"
    rows = HEADERS + "IMP-1,2026-05-15,110101,100,0\nIMP-1,2026-05-15,410101,0,100\n"
    source.write_text(rows, encoding="utf-8")

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
            source_filename="raced.csv",
            source_path=str(source),
            import_status=3,
        )
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

        service = ImportService()
        original_read = service._get_reader("csv").read
        calls = {"count": 0}

        def racing_read(path):  # noqa: ANN001 - firma del lector
            calls["count"] += 1
            # Primera lectura (execute): archivo con filas. Segunda (worker):
            # el archivo ya fue reemplazado por uno con solo encabezados.
            if calls["count"] == 2:
                source.write_text(HEADERS, encoding="utf-8")
            return original_read(path)

        service._get_reader = lambda _fmt: type("R", (), {"read": staticmethod(racing_read)})()  # type: ignore[assignment]
        assert service.execute(batch_id) is True

        database.session.expire_all()
        final = database.session.get(ImportBatch, batch_id)
        errors = list(database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch_id)).scalars().all())
        database.session.remove()

    assert calls["count"] >= 2
    assert final.import_status == 7
    assert final.success_rows == 0
    assert any("no contiene filas" in error.message.lower() for error in errors)
