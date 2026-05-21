# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from datetime import date

from cacao_accounting import create_app
from cacao_accounting.database import Book, database
from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.imports.models import ImportBatch
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.adapters import journal_entry as journal_entry_adapter
from ulid import ULID


def test_import_service_validate(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()

        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("codigo,nombre,clasificacion\n1,Test Account,activo")

        batch = ImportBatch(
            id=str(ULID()),
            record_type="chart_of_accounts",
            company_id="cacao",
            source_format="csv",
            source_path=str(csv_file),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()

        service = ImportService()
        service.validate(batch.id)

        updated_batch = database.session.get(ImportBatch, batch.id)
        assert updated_batch.import_status == 3
        assert updated_batch.total_rows == 1


def test_import_service_forbidden_columns(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()

        # Create a test CSV with forbidden column
        csv_file = tmp_path / "test_forbidden.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("codigo,nombre,clasificacion,company_id\n")
            f.write("1,Test,activo,other_company\n")

        batch = ImportBatch(
            id=str(ULID()),
            record_type="chart_of_accounts",
            company_id="cacao",
            source_format="csv",
            source_path=str(csv_file),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()

        service = ImportService()
        service.validate(batch.id)

        updated_batch = database.session.get(ImportBatch, batch.id)
        assert updated_batch.import_status == 7  # Fallido


def test_validate_uses_batch_company_for_period_check(tmp_path, monkeypatch):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()

        csv_file = tmp_path / "journal.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("document_ref,fecha,cuenta,debito,credito\n")
            f.write("JE-1,2026-01-10,1105,100,0\n")
            f.write("JE-1,2026-01-10,2105,0,100\n")

        captured = {}

        def _fake_is_period_open(company, posting_date):
            captured["company"] = company
            captured["posting_date"] = posting_date
            return True

        monkeypatch.setattr(journal_entry_adapter, "is_period_open", _fake_is_period_open)

        batch = ImportBatch(
            id=str(ULID()),
            record_type="journal_entry",
            company_id="cacao",
            source_format="csv",
            source_path=str(csv_file),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()

        service = ImportService()
        service.validate(batch.id)

        assert captured["company"] == "cacao"
        assert captured["posting_date"] == date(2026, 1, 10)


def test_journal_import_without_book_uses_all_active_company_books():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True),
                Book(entity="cacao", code="IFRS", name="IFRS", status=None),
                Book(entity="cacao", code="TAX", name="Tax", status="inactivo"),
            ]
        )
        database.session.commit()

        payload = JournalEntryAdapter().build_document(
            [
                {"document_ref": "JE-1", "fecha": "2026-01-10", "cuenta": "1105", "debito": "100", "credito": "0"},
                {"document_ref": "JE-1", "fecha": "2026-01-10", "cuenta": "2105", "debito": "0", "credito": "100"},
            ],
            {"company_id": "cacao", "accounting_book_id": None},
        )

        assert payload["books"] == ["FISC", "IFRS"]


def test_journal_import_with_book_uses_only_selected_book():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()

        payload = JournalEntryAdapter().build_document(
            [
                {"document_ref": "JE-1", "fecha": "2026-01-10", "cuenta": "1105", "debito": "100", "credito": "0"},
                {"document_ref": "JE-1", "fecha": "2026-01-10", "cuenta": "2105", "debito": "0", "credito": "100"},
            ],
            {"company_id": "cacao", "accounting_book_id": "FISC"},
        )

        assert payload["books"] == ["FISC"]
