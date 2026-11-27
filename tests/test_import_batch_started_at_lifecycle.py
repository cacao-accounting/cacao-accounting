# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1528: el ciclo de vida de lotes no conserva started_at tras validar."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.utils.recovery import recover_crashed_batches


def _crear_app_aislada():
    """Crea una aplicación con una base SQLite exclusiva y el mínimo indispensable."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-import-lifecycle-isolated",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.commit()
    return application


@pytest.fixture
def app():
    """Sustituye la app compartida por una base propia, destruida al terminar."""
    application = _crear_app_aislada()
    try:
        yield application
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def _company(suffix: str) -> str:
    code = f"c{suffix[:7]}"
    database.session.add(
        Entity(
            code=code,
            name=code,
            company_name=f"Company {suffix}",
            tax_id=f"TAX-{suffix}",
            currency="NIO",
            enabled=True,
        )
    )
    database.session.flush()
    return code


def _csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_validate_success_clears_started_at_and_allows_execute(app, tmp_path):
    """Validación exitosa libera started_at y permite ejecutar."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        company = _company(suffix)
        path = tmp_path / "customers.csv"
        _csv(path, [{"nombre": f"Cliente {suffix}"}])
        batch = ImportBatch(
            company_id=company,
            record_type="customer",
            source_format="csv",
            source_filename="customers.csv",
            source_path=str(path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

        service = ImportService()
        assert service.validate(batch_id) is True
        validated = database.session.get(ImportBatch, batch_id)
        assert validated.import_status == 3
        assert validated.started_at is None

        assert service.execute(batch_id) is True
        executed = database.session.get(ImportBatch, batch_id)
        assert executed.import_status == 5
        assert executed.started_at is None
        assert executed.success_rows == 1


def test_validate_error_clears_started_at_and_allows_revalidate(app, tmp_path):
    """Validación con error libera started_at y permite revalidar."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        company = _company(suffix)
        path = tmp_path / "customers.csv"
        # Header válido, fila inválida: produce status 2 (validado con errores).
        _csv(path, [{"nombre": "", "nombre_comercial": "Sin nombre"}])
        batch = ImportBatch(
            company_id=company,
            record_type="customer",
            source_format="csv",
            source_filename="customers.csv",
            source_path=str(path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

        service = ImportService()
        assert service.validate(batch_id) is True
        failed = database.session.get(ImportBatch, batch_id)
        assert failed.import_status == 2
        assert failed.started_at is None

        _csv(path, [{"nombre": f"Cliente {suffix}"}])
        assert service.validate(batch_id) is True
        repaired = database.session.get(ImportBatch, batch_id)
        assert repaired.import_status == 3
        assert repaired.started_at is None


def test_recovered_batch_clears_started_at_for_revalidation(app):
    """Recovery de lote vencido limpia started_at para permitir reintento."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        company = _company(suffix)
        batch = ImportBatch(
            company_id=company,
            record_type="customer",
            source_format="csv",
            source_filename="customers.csv",
            source_path="customers.csv",
            import_status=4,
            started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=5),
        )
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

        recovered = recover_crashed_batches()
        assert recovered >= 1
        crashed = database.session.get(ImportBatch, batch_id)
        assert crashed.import_status == 7
        assert crashed.started_at is None


def test_datos_confirmados_no_aparecen_en_otra_app_aislada(app):
    """Una app de prueba no comparte base con otra instancia del mismo helper."""
    suffix = uuid4().hex[:8]
    code = f"c{suffix[:7]}"
    with app.app_context():
        _company(suffix)
        database.session.commit()

    otra_app = _crear_app_aislada()
    try:
        with otra_app.app_context():
            assert database.session.execute(database.select(Entity).filter_by(code=code)).scalar_one_or_none() is None
    finally:
        with otra_app.app_context():
            database.session.remove()
            database.engine.dispose()
