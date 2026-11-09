# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Elimina las tablas ORM de workflow retiradas en #1841.

Las tablas no tenían lectores ni writers y los modelos se retiraron. En bases
nuevas ``create_all`` ya no las crea; esta migración limpia instalaciones
existentes de forma idempotente.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261109_0003"
down_revision: str | None = "20261109_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "workflow_action_log",
    "workflow_instance",
    "workflow_transition",
    "workflow_state",
    "workflow",
)


def upgrade() -> None:
    """Elimina las tablas de workflow si existen, de hijas a padre."""
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        if inspector.has_table(table):
            op.drop_table(table)


def downgrade() -> None:
    """Recrea las tablas de workflow con sus FKs, índices y defaults."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("workflow"):
        return
    op.create_table(
        "workflow",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.UniqueConstraint("entity_type", "name", name="uq_workflow_type_name"),
    )
    op.create_index("ix_workflow_entity_type", "workflow", ["entity_type"])
    op.create_index("ix_workflow_id", "workflow", ["id"])
    op.create_table(
        "workflow_state",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("workflow_id", sa.String(26), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("is_initial", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_final", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("workflow_id", "name", name="uq_workflow_state_name"),
    )
    op.create_index("ix_workflow_state_workflow_id", "workflow_state", ["workflow_id"])
    op.create_index("ix_workflow_state_id", "workflow_state", ["id"])
    op.create_table(
        "workflow_transition",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("from_state_id", sa.String(26), nullable=False),
        sa.Column("to_state_id", sa.String(26), nullable=False),
        sa.Column("action_name", sa.String(100), nullable=False),
        sa.Column("role_required", sa.String(50), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.ForeignKeyConstraint(["from_state_id"], ["workflow_state.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["to_state_id"], ["workflow_state.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("from_state_id", "to_state_id", "action_name", name="uq_workflow_transition"),
    )
    op.create_index("ix_workflow_transition_from_state_id", "workflow_transition", ["from_state_id"])
    op.create_index("ix_workflow_transition_to_state_id", "workflow_transition", ["to_state_id"])
    op.create_index("ix_workflow_transition_id", "workflow_transition", ["id"])
    op.create_table(
        "workflow_instance",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("workflow_id", sa.String(26), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(26), nullable=False),
        sa.Column("current_state_id", sa.String(26), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["current_state_id"], ["workflow_state.id"], ondelete="RESTRICT", onupdate="CASCADE"),
    )
    op.create_index("ix_workflow_instance_workflow_id", "workflow_instance", ["workflow_id"])
    op.create_index("ix_workflow_instance_reference_type", "workflow_instance", ["reference_type"])
    op.create_index("ix_workflow_instance_reference_id", "workflow_instance", ["reference_id"])
    op.create_index("ix_workflow_instance_id", "workflow_instance", ["id"])
    op.create_table(
        "workflow_action_log",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("workflow_instance_id", sa.String(26), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("performed_by", sa.String(26), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("from_state", sa.String(50), nullable=True),
        sa.Column("to_state", sa.String(50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=True),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_by", sa.String(26), nullable=True),
        sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instance.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by"], ["user.id"], ondelete="RESTRICT", onupdate="CASCADE"),
    )
    op.create_index("ix_workflow_action_log_workflow_instance_id", "workflow_action_log", ["workflow_instance_id"])
    op.create_index("ix_workflow_action_log_id", "workflow_action_log", ["id"])
