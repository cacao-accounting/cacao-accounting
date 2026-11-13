# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Index audit-chain links for current locking reads."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
from typing import Any

revision = "20261113_0004"
down_revision: str | None = "20261113_0003"
branch_labels: str | None = None
depends_on: str | None = None


def _ensure_audit_indexes(connection) -> None:
    """Create indexes used to bootstrap the current chain pointer."""
    inspector = sa.inspect(connection)
    if not inspector.has_table("audit_trail"):
        return
    existing = {index["name"] for index in inspector.get_indexes("audit_trail")}
    for name, column in (
        ("ix_audit_trail_payload_hash", "payload_hash"),
        ("ix_audit_trail_prev_hash", "prev_hash"),
    ):
        if name not in existing:
            op.create_index(name, "audit_trail", [column], unique=False)


def _ensure_audit_hash_columns(connection) -> None:
    """Add nullable chain metadata columns to audit tables created before hashing."""
    inspector = sa.inspect(connection)
    if not inspector.has_table("audit_trail"):
        return
    existing = {column["name"] for column in inspector.get_columns("audit_trail")}
    for name, column_type in (
        ("prev_hash", sa.String(length=64)),
        ("payload_hash", sa.String(length=64)),
        ("hash_version", sa.Integer()),
    ):
        if name not in existing:
            op.add_column("audit_trail", sa.Column(name, column_type, nullable=True))


def _preserve_mysql_audit_timestamps(connection) -> None:
    """Use MySQL DATETIME(6) so the stored timestamp matches its hash input."""
    if connection.dialect.name != "mysql":
        return
    inspector = sa.inspect(connection)
    if not inspector.has_table("audit_trail"):
        return
    timestamp = next(column for column in inspector.get_columns("audit_trail") if column["name"] == "timestamp")
    if getattr(timestamp["type"], "fsp", 0) == 6:
        return
    has_hashed_rows = connection.execute(sa.text("SELECT 1 FROM audit_trail WHERE payload_hash IS NOT NULL LIMIT 1")).first()
    if has_hashed_rows:
        raise RuntimeError(
            "No se alterará audit_trail: MySQL ya truncó timestamps usados en hashes históricos. "
            "La evidencia append-only requiere una política de recuperación aprobada."
        )
    op.alter_column(
        "audit_trail",
        "timestamp",
        existing_type=mysql.DATETIME(),
        type_=mysql.DATETIME(fsp=6),
        existing_nullable=False,
    )


def _ensure_state_table(connection) -> None:
    """Create the mutable chain-head pointer table for existing schemas."""
    if sa.inspect(connection).has_table("audit_chain_state"):
        return
    op.create_table(
        "audit_chain_state",
        sa.Column("id", sa.String(length=16), primary_key=True),
        sa.Column("head_hash", sa.String(length=64), nullable=True),
    )


def _existing_chain_head(connection) -> str | None:
    """Validate and return the unique reachable terminal hash in audit_trail."""
    inspector = sa.inspect(connection)
    if not inspector.has_table("audit_trail"):
        return None
    audit = sa.table(
        "audit_trail",
        sa.column("id", sa.String(length=26)),
        sa.column("payload_hash", sa.String(length=64)),
        sa.column("prev_hash", sa.String(length=64)),
    )
    rows = connection.execute(
        sa.select(audit.c.id, audit.c.payload_hash, audit.c.prev_hash).where(audit.c.payload_hash.is_not(None))
    ).all()
    if not rows:
        return None
    children: dict[str | None, list[Any]] = {}
    for row in rows:
        children.setdefault(row.prev_hash, []).append(row)
    roots = children.get(None, [])
    if len(roots) != 1:
        raise RuntimeError("No se puede inicializar el puntero: la cadena no tiene una raíz única.")
    visited: set[str] = set()
    current = roots[0]
    tail_hash = None
    while current is not None:
        if current.id in visited:
            raise RuntimeError("No se puede inicializar el puntero: la cadena contiene un ciclo.")
        visited.add(current.id)
        tail_hash = current.payload_hash
        successors = children.get(current.payload_hash, [])
        if len(successors) > 1:
            raise RuntimeError("No se puede inicializar el puntero: la cadena contiene ramas.")
        current = successors[0] if successors else None
    if len(visited) != len(rows):
        raise RuntimeError("No se puede inicializar el puntero: hay filas huérfanas en la cadena.")
    return tail_hash


def _initialize_state(connection, head: str | None) -> None:
    """Insert or fill the singleton pointer without changing audit evidence."""
    state = sa.table(
        "audit_chain_state",
        sa.column("id", sa.String(length=16)),
        sa.column("head_hash", sa.String(length=64)),
    )
    existing_row = connection.execute(sa.select(state.c.head_hash).where(state.c.id == "main")).first()
    if existing_row is None:
        connection.execute(state.insert().values(id="main", head_hash=head))
    elif existing_row[0] is None and head is not None:
        connection.execute(state.update().where(state.c.id == "main").values(head_hash=head))


def upgrade() -> None:
    """Add efficient chain lookups and initialize the mutable head pointer."""
    connection = op.get_bind()
    _ensure_audit_hash_columns(connection)
    _preserve_mysql_audit_timestamps(connection)
    _ensure_audit_indexes(connection)
    _ensure_state_table(connection)
    _initialize_state(connection, _existing_chain_head(connection))


def downgrade() -> None:
    """Remove the head pointer and lookup indexes without changing evidence rows."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("audit_trail"):
        return
    existing = {index["name"] for index in inspector.get_indexes("audit_trail")}
    for name in ("ix_audit_trail_payload_hash", "ix_audit_trail_prev_hash"):
        if name in existing:
            op.drop_index(name, table_name="audit_trail")
    if inspector.has_table("audit_chain_state"):
        op.drop_table("audit_chain_state")
