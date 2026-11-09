# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Elimina la tabla ORM ``gl_entry_dimension`` retirada en #1841.

La tabla no tenía lectores ni writers y el modelo se retiró. En bases nuevas
``create_all`` ya no la crea; esta migración limpia instalaciones existentes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261109_0004"
down_revision: str | None = "20261109_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Elimina ``gl_entry_dimension`` si existe."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("gl_entry_dimension"):
        op.drop_table("gl_entry_dimension")


def downgrade() -> None:
    """Recrea ``gl_entry_dimension`` con FKs e índices originales."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("gl_entry_dimension"):
        return
    op.create_table(
        "gl_entry_dimension",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("gl_entry_id", sa.String(26), nullable=False),
        sa.Column("dimension_type_id", sa.String(26), nullable=False),
        sa.Column("dimension_value_id", sa.String(26), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.ForeignKeyConstraint(["gl_entry_id"], ["gl_entry.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["dimension_type_id"], ["dimension_type.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["dimension_value_id"], ["dimension_value.id"], ondelete="RESTRICT", onupdate="CASCADE"),
    )
    op.create_index("ix_gl_entry_dimension_id", "gl_entry_dimension", ["id"])
    op.create_index("ix_gl_entry_dimension_gl_entry_id", "gl_entry_dimension", ["gl_entry_id"])
    op.create_index("ix_gl_entry_dimension_dimension_type_id", "gl_entry_dimension", ["dimension_type_id"])
    op.create_index("ix_gl_entry_dimension_dimension_value_id", "gl_entry_dimension", ["dimension_value_id"])
