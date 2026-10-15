# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Versiona el hash de la cadena de auditoría (``audit_trail.hash_version``).

El hash v2 de ``audit_chain`` ata la identidad de la fila al payload; para
bases existentes la columna se agrega aquí idempotentemente vía
``cacaoctl db migrate`` (la rutina de arranque ``db init`` suple el mismo
camino con ``_ensure_audit_trail_hash_version_column``). Las filas heredadas
quedan con ``NULL`` y se verifican con el formato v1 (sin identidad de fila),
por lo que la estrategia es compatible con datos existentes.
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
    """Elimina ``audit_trail.hash_version`` si existe."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("audit_trail"):
        return
    columns = {column["name"] for column in inspector.get_columns("audit_trail")}
    if "hash_version" in columns:
        op.drop_column("audit_trail", "hash_version")
