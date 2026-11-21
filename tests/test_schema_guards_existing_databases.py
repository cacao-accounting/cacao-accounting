# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""QA2 B-1: los guards se instalan también en bases existentes.

`create_all` no modifica tablas existentes; las rutinas `_ensure_*` deben
consolidar duplicados históricos y crear los índices únicos al arrancar.
"""

from __future__ import annotations

import sqlite3

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.config_values import set_config_value
from cacao_accounting.database import CacaoConfig, database


def _legacy_database(path):
    """Create the two tables without unique guards and with duplicates."""
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE cacao_config (
            id VARCHAR(26) PRIMARY KEY,
            key VARCHAR(50) NOT NULL,
            value VARCHAR(500) NOT NULL
        );
        INSERT INTO cacao_config VALUES ('01A', 'dup', 'old');
        INSERT INTO cacao_config VALUES ('01B', 'dup', 'new');
        INSERT INTO cacao_config VALUES ('01C', 'single', 'only');

        CREATE TABLE roles_user (
            id VARCHAR(26) PRIMARY KEY,
            user_id VARCHAR(26) NOT NULL,
            role_id VARCHAR(26) NOT NULL,
            active BOOLEAN
        );
        INSERT INTO roles_user VALUES ('01A', 'u1', 'r1', 0);
        INSERT INTO roles_user VALUES ('01B', 'u1', 'r1', 1);
        INSERT INTO roles_user VALUES ('01C', 'u1', 'r2', NULL);
        """)
    connection.commit()
    connection.close()


def _indexes(path):
    """Return the unique indexes declared on a SQLite database."""
    connection = sqlite3.connect(path)
    indexes = {
        row[0]: row[2]
        for row in connection.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
    }
    connection.close()
    return indexes


def test_startup_installs_guards_and_consolidates_history(tmp_path):
    """A legacy database gets the unique indexes and one row per key."""
    database_path = tmp_path / "legacy.sqlite"
    _legacy_database(database_path)

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

    indexes = _indexes(database_path)
    assert "uq_cacao_config_key" in indexes
    assert "uq_roles_user" in indexes

    connection = sqlite3.connect(database_path)
    config_rows = connection.execute("SELECT id, key, value FROM cacao_config ORDER BY key").fetchall()
    role_rows = connection.execute("SELECT id, user_id, role_id, active FROM roles_user ORDER BY role_id").fetchall()
    connection.close()

    assert config_rows == [("01B", "dup", "new"), ("01C", "single", "only")]
    assert role_rows == [("01B", "u1", "r1", 1), ("01C", "u1", "r2", None)]

    with app.app_context():
        set_config_value("dup", "latest")
        database.session.commit()
        row = database.session.execute(database.select(CacaoConfig).filter_by(key="dup")).scalar_one()
        assert row.id == "01B"
        assert row.value == "latest"
        database.session.remove()
        database.engine.dispose()


def test_guard_routines_are_idempotent(tmp_path):
    """Running the routines again keeps the consolidated state."""
    database_path = tmp_path / "legacy-idempotent.sqlite"
    _legacy_database(database_path)

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

    from cacao_accounting.database.helpers import (
        _ensure_cacao_config_key_unique,
        _ensure_roles_user_unique,
    )

    with app.app_context():
        _ensure_cacao_config_key_unique()
        _ensure_roles_user_unique()
        _ensure_cacao_config_key_unique()
        _ensure_roles_user_unique()
        database.session.remove()
        database.engine.dispose()

    connection = sqlite3.connect(database_path)
    assert connection.execute("SELECT COUNT(*) FROM cacao_config WHERE key = 'dup'").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM roles_user WHERE user_id = 'u1' AND role_id = 'r1'").fetchone()[0] == 1
    connection.close()
