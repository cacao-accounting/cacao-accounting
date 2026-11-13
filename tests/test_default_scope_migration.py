# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Upgrade checks for serialization and uniqueness of default configuration."""

from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

migration = importlib.import_module("cacao_accounting.migrations.20261113_0006_default_scope_locks")


def _upgrade(connection, monkeypatch) -> None:
    """Execute the real migration against the test database connection."""
    monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
    migration.upgrade()


def _legacy_tables(connection) -> None:
    """Create the relevant legacy tables without the new constraints."""
    connection.exec_driver_sql(
        "CREATE TABLE naming_series (id VARCHAR(26) PRIMARY KEY, entity_type VARCHAR(50), "
        "company VARCHAR(10), is_default BOOLEAN NOT NULL)"
    )
    connection.exec_driver_sql(
        "CREATE TABLE petty_cash_account (id VARCHAR(26) PRIMARY KEY, company VARCHAR(10), is_default BOOLEAN NOT NULL)"
    )


def test_upgrade_adds_lock_table_and_partial_unique_indexes(monkeypatch):
    """Existing defaults survive and each supported scope gains uniqueness."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _legacy_tables(connection)
        connection.exec_driver_sql(
            "INSERT INTO naming_series VALUES ('series-1', 'sales_invoice', 'COMP', 1), "
            "('series-global', 'customer', NULL, 1)"
        )
        connection.exec_driver_sql("INSERT INTO petty_cash_account VALUES ('cash-1', 'COMP', 1)")

        _upgrade(connection, monkeypatch)
        _upgrade(connection, monkeypatch)

        assert sa.inspect(connection).has_table("default_scope_lock")
        assert {index["name"] for index in sa.inspect(connection).get_indexes("naming_series")} >= {
            "uq_naming_series_default_company",
            "uq_naming_series_default_global",
        }
        assert "uq_petty_cash_account_default_company" in {
            index["name"] for index in sa.inspect(connection).get_indexes("petty_cash_account")
        }
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM naming_series WHERE is_default").scalar_one() == 2
        with pytest.raises(sa.exc.IntegrityError):
            connection.exec_driver_sql("INSERT INTO petty_cash_account VALUES ('cash-2', 'COMP', 1)")
    engine.dispose()


def test_upgrade_rejects_duplicate_defaults_without_rewriting_rows(monkeypatch):
    """Ambiguous legacy defaults fail closed and remain available for repair."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _legacy_tables(connection)
        connection.exec_driver_sql(
            "INSERT INTO naming_series VALUES ('series-1', 'sales_invoice', 'COMP', 1), "
            "('series-2', 'sales_invoice', 'COMP', 1)"
        )

        with pytest.raises(RuntimeError, match="naming_series contiene más de un valor predeterminado"):
            _upgrade(connection, monkeypatch)

        assert connection.exec_driver_sql("SELECT COUNT(*) FROM naming_series WHERE is_default").scalar_one() == 2
        assert not sa.inspect(connection).has_table("default_scope_lock")
    engine.dispose()
