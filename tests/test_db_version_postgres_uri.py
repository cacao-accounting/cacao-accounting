# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1731: db_version reconoce PostgreSQL aunque la URI no declare driver."""

from __future__ import annotations

import pytest

from cacao_accounting.database import database
from cacao_accounting.database.helpers import db_version


class _Resultado:
    def __iter__(self):
        return iter([("PostgreSQL 17",)])


@pytest.mark.parametrize("uri", ["postgresql://u:p@h/db", "postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"])
def test_cualquier_uri_de_postgres_consulta_version(app, monkeypatch, uri):
    """``postgres://`` también debe usar SELECT VERSION()."""
    sentencias: list[str] = []

    def execute(statement, *args, **kwargs):
        sentencias.append(str(statement))
        return _Resultado()

    monkeypatch.setattr(database.session, "execute", execute)
    app.config["SQLALCHEMY_DATABASE_URI"] = uri

    assert db_version() == "('PostgreSQL 17',)"
    assert any("VERSION()" in sentencia.upper() for sentencia in sentencias)
    assert not any("sqlite_version" in sentencia.lower() for sentencia in sentencias)
