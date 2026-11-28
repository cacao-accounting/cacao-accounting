# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Serializa cambios a valores predeterminados por ámbito estable."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cacao_accounting.database import DefaultScopeLock, database


def lock_default_scope(category: str, *parts: str | None) -> None:
    """Toma el lock transaccional para un ámbito de configuración predeterminada."""
    scope = "\x1f".join((category, *("<global>" if part is None else part for part in parts)))
    scope_key = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    session = database.session
    connection = session.connection()
    dialect = connection.dialect.name

    if dialect == "sqlite":
        raw_connection = connection.connection.driver_connection
        assert raw_connection is not None
        if not raw_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        statement: Any = sqlite_insert(DefaultScopeLock).values(scope_key=scope_key).on_conflict_do_nothing()
    elif dialect == "postgresql":
        statement = postgresql_insert(DefaultScopeLock).values(scope_key=scope_key).on_conflict_do_nothing()
    elif dialect == "mysql":
        mysql_statement = mysql_insert(DefaultScopeLock).values(scope_key=scope_key)
        statement = mysql_statement.on_duplicate_key_update(scope_key=mysql_statement.inserted.scope_key)
    else:
        raise RuntimeError(f"Motor de base de datos no soportado para locks de configuración: {dialect}")

    session.execute(statement)
    lock = session.execute(
        database.select(DefaultScopeLock)
        .where(DefaultScopeLock.scope_key == scope_key)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    del lock


def lock_default_scopes(category: str, scopes: list[tuple[str | None, ...]]) -> None:
    """Lock several related scopes in stable order before moving a default."""
    unique_scopes = set(scopes)
    for scope in sorted(unique_scopes, key=lambda parts: tuple("<global>" if part is None else part for part in parts)):
        lock_default_scope(category, *scope)
