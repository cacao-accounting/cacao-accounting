# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Elimina la tabla ORM ``assignment`` retirada en #1841.

La tabla no tenía lectores ni writers y el modelo se retiró. En bases nuevas
``create_all`` ya no la crea; esta migración limpia instalaciones existentes de
forma idempotente.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261109_0002"
down_revision: str | None = "20261109_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Elimina ``assignment`` si existe."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("assignment"):
        op.drop_table("assignment")


def downgrade() -> None:
    """Recrea ``assignment`` con sus FKs, índices y defaults originales."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("assignment"):
        return
    op.create_table(
        "assignment",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(26), nullable=False),
        sa.Column("assigned_to", sa.String(26), nullable=False),
        sa.Column("assigned_by", sa.String(26), nullable=True),
        sa.Column("assignment_status", sa.String(20), server_default="open", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to"], ["user.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="RESTRICT", onupdate="CASCADE"),
    )
    op.create_index("ix_assignment_reference_type", "assignment", ["reference_type"])
    op.create_index("ix_assignment_reference_id", "assignment", ["reference_id"])
    op.create_index("ix_assignment_assigned_to", "assignment", ["assigned_to"])
