# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1731/#db_version: la versión se resuelve por dialecto real del motor."""

from __future__ import annotations

import pytest

from cacao_accounting.database import database
from cacao_accounting.database.helpers import db_version


class _Resultado:
    def __iter__(self):
        return iter([("PostgreSQL 17",)])


class _Dialecto:
    def __init__(self, name: str) -> None:
        self.name = name


class _Engine:
    def __init__(self, name: str) -> None:
        self.dialect = _Dialecto(name)


@pytest.mark.parametrize("dialect_name", ["postgresql", "postgres"])
def test_db_version_usa_version_en_postgres(app, monkeypatch, dialect_name):
    """El dialecto PostgreSQL consulta VERSION() sin depender del prefijo URI."""
    sentencias: list[str] = []

    def execute(statement, *args, **kwargs):
        sentencias.append(str(statement))
        return _Resultado()

    with app.app_context():
        monkeypatch.setattr(database.session, "get_bind", lambda *args, **kwargs: _Engine(dialect_name))
        monkeypatch.setattr(database.session, "execute", execute)
        version = db_version()

    assert version == "('PostgreSQL 17',)"
    assert any("VERSION()" in sentencia.upper() for sentencia in sentencias)
    assert not any("sqlite_version" in sentencia.lower() for sentencia in sentencias)


def test_db_version_usa_sqlite_version_en_sqlite(app, monkeypatch):
    """SQLite usa sqlite_version() aunque la URI configurada sea ambigua."""
    sentencias: list[str] = []

    def execute(statement, *args, **kwargs):
        sentencias.append(str(statement))
        return _Resultado()

    with app.app_context():
        monkeypatch.setattr(database.session, "get_bind", lambda *args, **kwargs: _Engine("sqlite"))
        monkeypatch.setattr(database.session, "execute", execute)
        app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://u:p@h/db"
        version = db_version()

    assert version == "('PostgreSQL 17',)"
    assert any("sqlite_version" in sentencia.lower() for sentencia in sentencias)
    assert not any(sentencia.strip().upper().startswith("SELECT VERSION") for sentencia in sentencias)
