# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""Agrega ``audit_trail.hash_version`` para la cadena de auditor?a v2.

Las filas heredadas quedan con ``NULL`` y se verifican con formato v1.
El downgrade se rechaza si existen filas v2 para no invalidar evidencia
hist?rica verificable (#1849).
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
    rows_with_v2 = bind.execute(sa.text("SELECT COUNT(*) FROM audit_trail WHERE hash_version = 2")).scalar() or 0
    if int(rows_with_v2) > 0:
        raise RuntimeError(
            f"{int(rows_with_v2)} fila(s) audit_trail usan hash v2; downgrade rechazado para preservar verificaci?n."
        )
    op.drop_column("audit_trail", "hash_version")
