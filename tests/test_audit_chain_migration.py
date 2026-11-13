# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regression coverage for audit-chain schema upgrades."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import mysql

migration = importlib.import_module("cacao_accounting.migrations.20261113_0004_audit_chain_state")


def _legacy_audit_table(connection, *, hashes: bool = False) -> None:
    """Create the narrowest historical audit table needed by revision 0004."""
    columns = ["id VARCHAR(26) PRIMARY KEY"]
    if hashes:
        columns.extend(["payload_hash VARCHAR(64)", "prev_hash VARCHAR(64)"])
    connection.exec_driver_sql(f"CREATE TABLE audit_trail ({', '.join(columns)})")


def _upgrade(connection, monkeypatch) -> None:
    """Run the real revision against the supplied SQLAlchemy connection."""
    monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
    migration.upgrade()


def test_upgrade_adds_hash_columns_and_initializes_empty_head(monkeypatch):
    """Upgrade legacy evidence without hashes and preserve its original row."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _legacy_audit_table(connection)
        connection.exec_driver_sql("INSERT INTO audit_trail (id) VALUES ('legacy-row')")

        _upgrade(connection, monkeypatch)

        columns = {column["name"] for column in sa.inspect(connection).get_columns("audit_trail")}
        assert {"payload_hash", "prev_hash", "hash_version"} <= columns
        assert connection.exec_driver_sql("SELECT id FROM audit_trail").scalar_one() == "legacy-row"
        assert connection.exec_driver_sql("SELECT head_hash FROM audit_chain_state WHERE id='main'").scalar_one() is None
    engine.dispose()


def test_upgrade_bootstraps_valid_legacy_chain_head(monkeypatch):
    """Initialize the singleton from the unique reachable legacy chain tail."""
    engine = sa.create_engine("sqlite://")
    root_hash = "a" * 64
    tail_hash = "b" * 64
    with engine.begin() as connection:
        _legacy_audit_table(connection, hashes=True)
        connection.exec_driver_sql(
            "INSERT INTO audit_trail (id, payload_hash, prev_hash) VALUES " "('root', :root, NULL), ('tail', :tail, :root)",
            {"root": root_hash, "tail": tail_hash},
        )

        _upgrade(connection, monkeypatch)

        assert connection.exec_driver_sql("SELECT head_hash FROM audit_chain_state WHERE id='main'").scalar_one() == tail_hash

    engine.dispose()


def test_upgrade_rejects_branched_chain_without_rewriting_evidence(monkeypatch):
    """Fail closed when two children make the legacy head ambiguous."""
    engine = sa.create_engine("sqlite://")
    root_hash = "a" * 64
    branch_hashes = ("b" * 64, "c" * 64)
    with engine.begin() as connection:
        _legacy_audit_table(connection, hashes=True)
        connection.exec_driver_sql(
            "INSERT INTO audit_trail (id, payload_hash, prev_hash) VALUES "
            "('root', :root, NULL), ('branch-a', :first, :root), ('branch-b', :second, :root)",
            {"root": root_hash, "first": branch_hashes[0], "second": branch_hashes[1]},
        )

        with pytest.raises(RuntimeError, match="cadena contiene ramas"):
            _upgrade(connection, monkeypatch)

        rows = set(connection.exec_driver_sql("SELECT payload_hash FROM audit_trail").scalars().all())
        assert rows == {root_hash, *branch_hashes}

    engine.dispose()


@pytest.mark.parametrize("has_hashed_rows", [False, True])
def test_mysql_timestamp_upgrade_preserves_existing_hashed_evidence(monkeypatch, has_hashed_rows):
    """Widen MySQL timestamp precision only when hashes cannot be invalidated."""
    altered = []
    inspector = SimpleNamespace(
        has_table=lambda _name: True,
        get_columns=lambda _name: [{"name": "timestamp", "type": mysql.DATETIME(fsp=0)}],
    )
    connection = SimpleNamespace(
        dialect=SimpleNamespace(name="mysql"),
        execute=lambda _statement: SimpleNamespace(first=lambda: (1,) if has_hashed_rows else None),
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda _connection: inspector)
    monkeypatch.setattr(migration, "op", SimpleNamespace(alter_column=lambda *args, **kwargs: altered.append((args, kwargs))))

    if has_hashed_rows:
        with pytest.raises(RuntimeError, match="No se alterará audit_trail"):
            migration._preserve_mysql_audit_timestamps(connection)
        assert altered == []
    else:
        migration._preserve_mysql_audit_timestamps(connection)
        assert len(altered) == 1
        assert altered[0][1]["type_"].fsp == 6
