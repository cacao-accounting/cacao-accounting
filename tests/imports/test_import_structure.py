# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de preservación y validación estructural de importaciones."""

import csv
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import pytest
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Party, database
from cacao_accounting.imports.adapters.customer import CustomerAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.readers.base import NormalizedTable
from cacao_accounting.imports.readers.ods_reader import ODSReader
from cacao_accounting.imports.services.import_service import ImportService


def _write_ods(path, rows):
    """Crea un archivo ODS pequeño con las filas indicadas."""
    document = OpenDocumentSpreadsheet()
    sheet = Table(name="Customers")
    for values in rows:
        row = TableRow()
        for value in values:
            cell = TableCell()
            if value:
                cell.addElement(P(text=value))
            row.addElement(cell)
        sheet.addElement(row)
    document.spreadsheet.addElement(sheet)
    document.save(str(path))


def _create_customer_batch(path, status, source_format="csv"):
    """Crea un lote de clientes asociado al archivo de prueba."""
    batch = ImportBatch(
        company_id="cacao",
        record_type="customer",
        source_format=source_format,
        source_filename=path.name,
        source_path=str(path),
        import_status=status,
    )
    database.session.add(batch)
    database.session.commit()
    return batch


def _write_customer_csv(path, extra_cell=None, customer_name="Structural Test Customer"):
    """Escribe un CSV con los campos del adaptador de clientes."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CustomerAdapter.columns)
        writer.writerow([customer_name, "", "", "", ""])
        if extra_cell is not None:
            writer.writerow(["Later Structural Customer", "", "", "", "", extra_cell])


def test_ods_reader_preserves_data_under_blank_header(tmp_path):
    """El servicio debe recibir la celda sin título para poder rechazarla."""
    path = tmp_path / "customers.ods"
    _write_ods(path, [["nombre", ""], ["Ana", "contenido sin título"]])

    table = ODSReader().read(str(path))
    errors = ImportService()._collect_structural_errors("batch-id", table, CustomerAdapter())

    assert table.columns == ["nombre", ""]
    assert table.rows == [["Ana", "contenido sin título"]]
    assert [(error.error_type, error.row_number) for error in errors] == [("MISSING_HEADER", 1)]


def test_ods_validation_rejects_data_under_blank_header_and_can_recover(app, tmp_path):
    """La validación integral ODS rechaza y permite corregir columnas anónimas."""
    with app.app_context():
        path = tmp_path / "customers.ods"
        headers = [*CustomerAdapter.columns, ""]
        _write_ods(path, [headers, ["Structural Test Customer", "", "", "", "", "sin encabezado"]])
        batch = _create_customer_batch(path, status=1, source_format="ods")
        service = ImportService()

        assert service.validate(batch.id)
        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 7
        assert [(error.error_type, error.row_number) for error in errors] == [("MISSING_HEADER", 1)]
        preview = service.preview(batch.id)
        assert [(error.error_type, error.row_number) for error in preview["errors"]] == [("MISSING_HEADER", 1)]
        assert not Party.query.filter_by(name="Structural Test Customer").first()

        _write_ods(path, [headers, ["Structural Test Customer", "", "", "", "", ""]])
        preview = service.preview(batch.id)
        assert not [error for error in preview["errors"] if error.error_type == "MISSING_HEADER"]
        assert service.validate(batch.id)
        assert batch.import_status == 3
        assert not ImportBatchError.query.filter_by(batch_id=batch.id).first()

        database.session.delete(batch)
        database.session.commit()


def test_ods_without_header_row_fails_required_column_validation(app, tmp_path):
    """Una hoja sin nombres de campos no se interpreta como una fila importable."""
    with app.app_context():
        path = tmp_path / "customers_without_headers.ods"
        _write_ods(path, [["Structural Test Customer"]])
        batch = _create_customer_batch(path, status=1, source_format="ods")

        assert ImportService().validate(batch.id)

        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 7
        assert [(error.error_type, error.field_name) for error in errors] == [("MISSING_COLUMN", "nombre")]
        assert not Party.query.filter_by(name="Structural Test Customer").first()

        database.session.delete(batch)
        database.session.commit()


def test_normalization_pads_short_rows_and_keeps_named_cells():
    """Las filas cortas se completan; el contenido con encabezado se conserva."""
    normalized = ImportService()._normalize_rows(["nombre", "grupo"], [["Ana"], ["Luis", "A"]])

    assert normalized == [{"nombre": "Ana", "grupo": ""}, {"nombre": "Luis", "grupo": "A"}]


def test_validation_rejects_populated_cells_after_header_without_importing(app, tmp_path):
    """La validación falla antes de que un adaptador persista filas truncadas."""
    with app.app_context():
        path = tmp_path / "customers.csv"
        _write_customer_csv(path, "unexpected value")
        batch = _create_customer_batch(path, status=1)
        service = ImportService()

        assert service.validate(batch.id)

        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 7
        assert batch.started_at is None
        assert [(error.error_type, error.row_number) for error in errors] == [("EXTRA_CELLS", 2)]
        assert not Party.query.filter_by(name="Structural Test Customer").first()

        _write_customer_csv(path)
        assert service.validate(batch.id)
        assert batch.import_status == 3
        assert not ImportBatchError.query.filter_by(batch_id=batch.id).first()

        database.session.delete(batch)
        database.session.commit()


def test_validation_reader_failure_releases_batch_for_retry(app, tmp_path):
    """Una fuente corrupta puede corregirse y volver a validarse."""
    with app.app_context():
        path = tmp_path / "customers.csv"
        path.write_bytes(b"\xff")
        batch = _create_customer_batch(path, status=1)
        service = ImportService()

        assert service.validate(batch.id)
        assert batch.import_status == 7
        assert batch.started_at is None
        assert ImportBatchError.query.filter_by(batch_id=batch.id, error_type="SYSTEM_ERROR").first()

        _write_customer_csv(path)
        assert service.validate(batch.id)
        assert batch.import_status == 3
        assert not ImportBatchError.query.filter_by(batch_id=batch.id).first()

        database.session.delete(batch)
        database.session.commit()


def test_execution_rechecks_file_structure_before_persisting(app, tmp_path):
    """Un archivo alterado tras validar no puede importar filas parcialmente."""
    with app.app_context():
        path = tmp_path / "customers.csv"
        _write_customer_csv(path)
        batch = _create_customer_batch(path, status=1)
        service = ImportService()
        assert service.validate(batch.id)
        assert batch.import_status == 3

        _write_customer_csv(path, "unexpected value")
        assert service.execute(batch.id)

        database.session.refresh(batch)
        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 7
        assert [(error.error_type, error.row_number) for error in errors] == [("EXTRA_CELLS", 2)]
        assert not Party.query.filter_by(name="Structural Test Customer").first()
        assert not Party.query.filter_by(name="Later Structural Customer").first()

        database.session.delete(batch)
        database.session.commit()


def test_execution_reader_failure_releases_active_marker(app, tmp_path):
    """Un error de lectura pública termina en fallo y limpia started_at."""
    with app.app_context():
        path = tmp_path / "missing.ods"
        batch = _create_customer_batch(path, status=3, source_format="ods")

        assert ImportService().execute(batch.id)

        database.session.refresh(batch)
        assert batch.import_status == 7
        assert batch.started_at is None
        assert ImportBatchError.query.filter_by(batch_id=batch.id, error_type="FATAL_ERROR").first()

        database.session.delete(batch)
        database.session.commit()


def test_unexpected_adapter_failure_rolls_back_pending_rows(app, tmp_path, monkeypatch):
    """Un fallo inesperado tras flush no confirma filas parciales."""
    with app.app_context():
        path = tmp_path / "customers.csv"
        _write_customer_csv(path)
        batch = _create_customer_batch(path, status=4)

        class FailingAdapter:
            """Adaptador que simula un fallo tras escribir una fila pendiente."""

            columns = CustomerAdapter.columns
            required_columns = []

            def validate_row(self, row):
                """La fila pasa la validación de negocio simulada."""
                return []

            def validate_document(self, rows, context=None):
                """El documento pasa la validación de negocio simulada."""
                return []

            def build_document(self, rows, context):
                """Devuelve un documento de prueba."""
                return {}

            def persist_document(self, document):
                """Escribe una fila y falla antes del commit del documento."""
                database.session.add(Party(code="PENDING-IMPORT-FAILURE", is_customer=True, name="Pending Partial Customer"))
                database.session.flush()
                raise TypeError("fallo inesperado tras flush")

        service = ImportService()
        monkeypatch.setattr(service, "_get_adapter", lambda record_type: FailingAdapter())
        service._execute_task(app, batch.id)

        database.session.refresh(batch)
        assert batch.import_status == 7
        assert batch.started_at is None
        assert not Party.query.filter_by(code="PENDING-IMPORT-FAILURE").first()
        assert ImportBatchError.query.filter_by(batch_id=batch.id, error_type="FATAL_ERROR").first()

        database.session.delete(batch)
        database.session.commit()


def test_execution_revalidates_business_rules_for_changed_content(app, tmp_path):
    """La ejecución no persiste una fila modificada que falla reglas de negocio."""
    with app.app_context():
        path = tmp_path / "customers.csv"
        _write_customer_csv(path)
        batch = _create_customer_batch(path, status=1)
        service = ImportService()
        assert service.validate(batch.id)
        assert batch.import_status == 3

        _write_customer_csv(path, customer_name="")
        assert service.execute(batch.id)

        database.session.refresh(batch)
        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 2
        assert batch.started_at is None
        assert [(error.error_type, error.row_number) for error in errors] == [("ROW_VALIDATION", 1)]
        assert not Party.query.filter_by(name="Structural Test Customer").first()

        database.session.delete(batch)
        database.session.commit()


def test_structural_error_detection_reports_unnamed_and_overflow_cells():
    """Los errores identifican filas con datos sin título o fuera del esquema."""
    table = NormalizedTable(columns=["nombre", ""], rows=[["Ana", "extra", "overflow"]])

    errors = ImportService()._collect_structural_errors("batch-id", table, CustomerAdapter())

    assert [(error.error_type, error.row_number) for error in errors] == [
        ("MISSING_HEADER", 1),
        ("EXTRA_CELLS", 1),
    ]


@pytest.mark.database
def test_batch_claim_is_atomic_for_concurrent_callers(tmp_path):
    """Dos validaciones concurrentes no pueden tomar el mismo lote activo."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    is_sqlite = database_uri.startswith("sqlite:")
    if not is_sqlite and os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    if is_sqlite:
        database_uri = f"sqlite:///{tmp_path / 'import-claim.sqlite'}"

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    suffix = uuid4().hex[:6].upper()
    company_code = f"C{suffix}"
    created_currency = False
    with app.app_context():
        database.create_all()
        existing_currency = database.session.execute(select(Currency).where(Currency.code == "NIO")).scalar_one_or_none()
        if existing_currency is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            created_currency = True
        database.session.flush()
        database.session.add(
            Entity(
                code=company_code,
                name="Import claim test",
                company_name=f"Import claim {suffix} SA",
                tax_id=f"IMPORT-{suffix}",
                currency="NIO",
                enabled=True,
            )
        )
        batch = ImportBatch(company_id=company_code, record_type="customer", import_status=1)
        database.session.add(batch)
        database.session.commit()
        batch_id = batch.id

    barrier = Barrier(2)

    def claim_batch():
        with app.app_context():
            barrier.wait(timeout=10)
            return ImportService()._claim_batch(batch_id, {1})

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result() for future in [executor.submit(claim_batch) for _ in range(2)]]

        assert sorted(results) == [False, True]
        with app.app_context():
            claimed_batch = database.session.get(ImportBatch, batch_id)
            assert claimed_batch.import_status == 4
            assert claimed_batch.started_at is not None
    finally:
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            company = database.session.get(Entity, company_code)
            if batch:
                database.session.delete(batch)
            if company:
                database.session.delete(company)
            if created_currency:
                currency = database.session.get(Currency, "NIO")
                if currency:
                    database.session.delete(currency)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
