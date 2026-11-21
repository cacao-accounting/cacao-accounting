# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""P3/#1355: la columna `auth_version` se instala en bases existentes.

Sin la rutina `_ensure_*`, una base previa a la columna no puede cargar `User`
y el login queda inutilizable.
"""

from __future__ import annotations

import sqlite3

from sqlalchemy import inspect as sa_inspect

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import User, database


def test_existing_database_receives_user_auth_version(tmp_path):
    """A legacy user table gets the column at startup, idempotently."""
    database_path = tmp_path / "legacy-user.sqlite"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE user (id VARCHAR(26) PRIMARY KEY, e_mail VARCHAR(150), modified DATETIME)")
    connection.execute("INSERT INTO user VALUES ('u1', 'user@example.test', NULL)")
    connection.commit()
    connection.close()

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )

    with app.app_context():
        columns = {column["name"]: column for column in sa_inspect(database.engine).get_columns(User.__tablename__)}
        assert "auth_version" in columns
        assert columns["auth_version"]["nullable"] is False
        row = database.session.execute(database.text('SELECT auth_version FROM "user" WHERE id = :id'), {"id": "u1"}).one()
        assert row[0] == 0
        database.session.remove()
        database.engine.dispose()
