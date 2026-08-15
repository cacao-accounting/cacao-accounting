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

    assert revision == [("20260815_0010",)]

    with sqlite3.connect(database_path) as connection:
        entity_code = connection.execute("PRAGMA table_info(entity)").fetchall()
        book_code = connection.execute("PRAGMA table_info(book)").fetchall()

    assert next(column[3] for column in entity_code if column[1] == "code") == 1
    assert next(column[3] for column in book_code if column[1] == "code") == 1

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


def test_db_migrate_rejects_legacy_null_master_codes(tmp_path: Path) -> None:
    """Legacy null codes must stop migration instead of being guessed."""
    database_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE user (id TEXT PRIMARY KEY);
            CREATE TABLE entity (id TEXT PRIMARY KEY, code TEXT);
            CREATE TABLE book (id TEXT PRIMARY KEY, code TEXT);
            INSERT INTO entity (id, code) VALUES ('entity-1', NULL);
            INSERT INTO book (id, code) VALUES ('book-1', 'FISC');
            """
        )

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
    assert "entity.code" in migrated.stdout
    assert "registros nulos" in migrated.stdout
