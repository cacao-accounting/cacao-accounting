"""Alembic migration for DB performance and integrity optimizations.

Revision ID: 20260918_0002
Revises: 20260809_0001
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision = "20260918_0002"
down_revision: str | None = "20260809_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply targeted indexes and constraints for performance and integrity."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Create new composite indexes
    op.create_index(
        "ix_roles_access_rol_module",
        "roles_access",
        ["rol_id", "module_id"],
        unique=False,
    )
    op.create_index(
        "ix_roles_user_role_user",
        "roles_user",
        ["role_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_comprobante_detalle_tx",
        "comprobante_contable_detalle",
        ["transaction", "transaction_id"],
        unique=False,
    )

    # Update NULL values to empty string for existing data in all dialects
    op.execute("UPDATE document_relation SET source_item_id = '' WHERE source_item_id IS NULL")
    op.execute("UPDATE document_relation SET target_item_id = '' WHERE target_item_id IS NULL")

    # DocumentRelation source_item_id / target_item_id non-null default update
    if dialect == "sqlite":
        with op.batch_alter_table("document_relation") as batch_op:
            batch_op.alter_column(
                "source_item_id",
                existing_type=sa.String(26),
                nullable=False,
                server_default="",
            )
            batch_op.alter_column(
                "target_item_id",
                existing_type=sa.String(26),
                nullable=False,
                server_default="",
            )
    else:
        op.alter_column(
            "document_relation",
            "source_item_id",
            existing_type=sa.String(26),
            nullable=False,
            server_default="",
        )
        op.alter_column(
            "document_relation",
            "target_item_id",
            existing_type=sa.String(26),
            nullable=False,
            server_default="",
        )


def downgrade() -> None:
    """Revert schema optimizations."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_index("ix_comprobante_detalle_tx", table_name="comprobante_contable_detalle")
    op.drop_index("ix_roles_user_role_user", table_name="roles_user")
    op.drop_index("ix_roles_access_rol_module", table_name="roles_access")

    if dialect == "sqlite":
        with op.batch_alter_table("document_relation") as batch_op:
            batch_op.alter_column(
                "source_item_id",
                existing_type=sa.String(26),
                nullable=True,
                server_default=None,
            )
            batch_op.alter_column(
                "target_item_id",
                existing_type=sa.String(26),
                nullable=True,
                server_default=None,
            )
    else:
        op.alter_column(
            "document_relation",
            "source_item_id",
            existing_type=sa.String(26),
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            "document_relation",
            "target_item_id",
            existing_type=sa.String(26),
            nullable=True,
            server_default=None,
        )
