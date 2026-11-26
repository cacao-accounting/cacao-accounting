# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Agrega ``audit_trail.hash_version`` para la cadena de auditoría v2.

Las filas heredadas quedan con ``NULL`` y se verifican con formato v1.
El downgrade se rechaza si existen filas con un hash versionado (versión
mayor que 1) para no invalidar evidencia histórica verificable (#1849).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261015_0001"
down_revision: str | None = "20260809_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega ``audit_trail.hash_version`` si no existe (idempotente)."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("audit_trail"):
        return
    columns = {column["name"] for column in inspector.get_columns("audit_trail")}
    if "hash_version" not in columns:
        op.add_column("audit_trail", sa.Column("hash_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Elimina ``audit_trail.hash_version`` solo si no hay filas v2."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("audit_trail"):
        return
    columns = {column["name"] for column in inspector.get_columns("audit_trail")}
    if "hash_version" not in columns:
        return
    # Toda fila cuyo hash no sea el formato heredado implícito (v1) necesita la
    # columna para poder re-verificarse. Se compara contra 1 y no contra
    # ``audit_chain.CHAIN_HASH_VERSION`` para que el guard no dependa del número
    # vigente ni importe código de la aplicación dentro de una migración: si la
    # cadena sube a v3, ``hash_version > 1`` sigue protegiendo la evidencia.
    #
    # El mensaje es texto de consola de despliegue, no de producto: las migraciones
    # pueden ejecutarse sin el contexto de babel de la aplicación, por lo que va sin
    # ``_()`` y sin entrada en ``messages.po`` (#1849).
    rows_with_versioned_hash = bind.execute(sa.text("SELECT COUNT(*) FROM audit_trail WHERE hash_version > 1")).scalar() or 0
    if int(rows_with_versioned_hash) > 0:
        raise RuntimeError(
            f"{int(rows_with_versioned_hash)} fila(s) audit_trail usan un hash versionado (versión > 1); "
            "downgrade rechazado para preservar la evidencia verificable."
        )
    op.drop_column("audit_trail", "hash_version")
