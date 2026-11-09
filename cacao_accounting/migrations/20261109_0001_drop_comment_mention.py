# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Elimina la tabla ORM ``comment_mention`` retirada en #1841.

La tabla no tenía lectores ni writers y el modelo se retiró. En bases nuevas
``create_all`` ya no la crea; esta migración limpia instalaciones existentes de
forma idempotente.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261109_0001"
down_revision: str | None = "20261015_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Elimina ``comment_mention`` si existe."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("comment_mention"):
        op.drop_table("comment_mention")


def downgrade() -> None:
    """Recrea ``comment_mention`` si no existe."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("comment_mention"):
        return
    op.create_table(
        "comment_mention",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("comment_id", sa.String(26), nullable=False, index=True),
        sa.Column("user_id", sa.String(26), nullable=False, index=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
    )
