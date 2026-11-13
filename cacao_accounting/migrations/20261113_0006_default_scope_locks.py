# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Serialize default selection and enforce its uniqueness where supported."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0006"
down_revision: str | None = "20261113_0005"
branch_labels: str | None = None
depends_on: str | None = None


def _validate_existing_defaults(connection) -> None:
    """Abort rather than silently choose between conflicting defaults."""
    for table, scope_columns in (
        ("naming_series", ("entity_type", "company")),
        ("petty_cash_account", ("company",)),
    ):
        if not sa.inspect(connection).has_table(table):
            continue
        columns = {column["name"] for column in sa.inspect(connection).get_columns(table)}
        if "is_default" not in columns or any(column not in columns for column in scope_columns):
            continue
        scope = ", ".join(scope_columns)
        duplicate = connection.execute(
            sa.text(
                f"SELECT {scope}, COUNT(*) AS amount FROM {table} "
                f"WHERE is_default IS TRUE GROUP BY {scope} HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate:
            raise RuntimeError(
                f"No se puede aplicar la migración: {table} contiene más de un valor predeterminado "
                f"para el ámbito {scope}. Corrija la configuración antes de migrar."
            )


def _ensure_scope_lock_table(connection) -> None:
    if not sa.inspect(connection).has_table("default_scope_lock"):
        op.create_table("default_scope_lock", sa.Column("scope_key", sa.String(length=64), primary_key=True))


def _ensure_partial_index(connection, table: str, name: str, columns: list[str], predicate: str) -> None:
    if connection.dialect.name not in ("sqlite", "postgresql"):
        return
    if not sa.inspect(connection).has_table(table):
        return
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes(table)}
    if name not in indexes:
        op.create_index(
            name, table, columns, unique=True, sqlite_where=sa.text(predicate), postgresql_where=sa.text(predicate)
        )


def upgrade() -> None:
    """Add per-scope lock rows and partial uniqueness constraints."""
    connection = op.get_bind()
    _validate_existing_defaults(connection)
    _ensure_scope_lock_table(connection)
    _ensure_partial_index(
        connection,
        "naming_series",
        "uq_naming_series_default_company",
        ["entity_type", "company"],
        (
            "is_default = 1 AND company IS NOT NULL"
            if connection.dialect.name == "sqlite"
            else "is_default IS TRUE AND company IS NOT NULL"
        ),
    )
    _ensure_partial_index(
        connection,
        "naming_series",
        "uq_naming_series_default_global",
        ["entity_type"],
        (
            "is_default = 1 AND company IS NULL"
            if connection.dialect.name == "sqlite"
            else "is_default IS TRUE AND company IS NULL"
        ),
    )
    _ensure_partial_index(
        connection,
        "petty_cash_account",
        "uq_petty_cash_account_default_company",
        ["company"],
        "is_default = 1" if connection.dialect.name == "sqlite" else "is_default IS TRUE",
    )


def downgrade() -> None:
    """Remove the partial indexes and scope lock table."""
    connection = op.get_bind()
    for table, name in (
        ("naming_series", "uq_naming_series_default_company"),
        ("naming_series", "uq_naming_series_default_global"),
        ("petty_cash_account", "uq_petty_cash_account_default_company"),
    ):
        if sa.inspect(connection).has_table(table):
            indexes = {index["name"] for index in sa.inspect(connection).get_indexes(table)}
            if name in indexes:
                op.drop_index(name, table_name=table)
    if sa.inspect(connection).has_table("default_scope_lock"):
        op.drop_table("default_scope_lock")
