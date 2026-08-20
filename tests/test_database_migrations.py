"""Regression tests for the Alembic migration entry point."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_db_init_and_migrate_record_a_real_revision(tmp_path: Path) -> None:
    """The documented bootstrap flow must leave a non-empty Alembic revision."""
    database_path = tmp_path / "migration.sqlite"
    environment = os.environ.copy()
    environment.update(
        {
            "CACAO_TEST": "True",
            "CACAO_DATABASE_URL": f"sqlite:///{database_path}",
            "SECRET_KEY": "ASD123kljaAddS",
            "CACAO_USER": "cacao",
            "CACAO_PSWD": "cacao",
            "LOGURU_LEVEL": "WARNING",
        }
    )
    command = [sys.executable, "-c", "from cacao_accounting import command; command()"]

    initialized = subprocess.run(
        [*command, "db", "init"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    migrated = subprocess.run(
        [*command, "db", "migrate"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchall()

    assert revision == [("20260809_0001",)]

    with sqlite3.connect(database_path) as connection:
        entity_code = connection.execute("PRAGMA table_info(entity)").fetchall()
        book_code = connection.execute("PRAGMA table_info(book)").fetchall()

        comparison_columns = {column[1] for column in connection.execute("PRAGMA table_info(purchase_request_comparison)")}
        comparison_line_columns = {
            column[1] for column in connection.execute("PRAGMA table_info(purchase_request_comparison_line)")
        }
        purchase_order_columns = {column[1] for column in connection.execute("PRAGMA table_info(purchase_order)")}
        purchase_request_columns = {column[1] for column in connection.execute("PRAGMA table_info(purchase_request)")}
        purchase_receipt_columns = {column[1] for column in connection.execute("PRAGMA table_info(purchase_receipt)")}
        document_relation_columns = {column[1] for column in connection.execute("PRAGMA table_info(document_relation)")}

    assert next(column[3] for column in entity_code if column[1] == "code") == 1
    assert next(column[3] for column in book_code if column[1] == "code") == 1
    assert {"authorized_by", "finalized_at", "used_at"}.issubset(comparison_columns)
    assert {"purchase_request_item_id", "recommended_supplier_quotation_id", "selected_supplier_quotation_id"}.issubset(
        comparison_line_columns
    )
    assert "purchase_request_comparison_id" in purchase_order_columns
    assert "status" in purchase_request_columns
    assert "base_total" in purchase_receipt_columns
    assert "qty_in_base_uom" in document_relation_columns

    with sqlite3.connect(database_path) as connection:
        entity_code = connection.execute("PRAGMA table_info(entity)").fetchall()
        book_code = connection.execute("PRAGMA table_info(book)").fetchall()

    assert next(column[3] for column in entity_code if column[1] == "code") == 1
    assert next(column[3] for column in book_code if column[1] == "code") == 1


def test_db_migrate_rejects_an_uninitialized_database(tmp_path: Path) -> None:
    """Migration must not report success when there is no application schema."""
    database_path = tmp_path / "uninitialized.sqlite"
    environment = os.environ.copy()
    environment.update(
        {
            "CACAO_TEST": "True",
            "CACAO_DATABASE_URL": f"sqlite:///{database_path}",
            "SECRET_KEY": "ASD123kljaAddS",
            "LOGURU_LEVEL": "WARNING",
        }
    )

    migrated = subprocess.run(
        [sys.executable, "-c", "from cacao_accounting import command; command()", "db", "migrate"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert migrated.returncode == 1
    assert "La base de datos no está inicializada" in migrated.stdout
