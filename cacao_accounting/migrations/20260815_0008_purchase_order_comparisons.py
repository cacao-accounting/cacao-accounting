"""Add comparisons based on purchase orders."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0008"
down_revision = "20260814_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Return whether a table exists in the current database."""
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    """Create purchase-order comparison tables."""
    if not _table_exists("purchase_order_comparison"):
        op.create_table(
            "purchase_order_comparison",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("company", sa.String(length=10), nullable=False),
            sa.Column("base_purchase_order_id", sa.String(length=26), nullable=False),
            sa.ForeignKeyConstraint(["company"], ["entity.code"], ondelete="RESTRICT", onupdate="CASCADE"),
            sa.ForeignKeyConstraint(["base_purchase_order_id"], ["purchase_order.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_purchase_order_comparison_base_purchase_order_id",
            "purchase_order_comparison",
            ["base_purchase_order_id"],
        )

    if not _table_exists("purchase_order_comparison_order"):
        op.create_table(
            "purchase_order_comparison_order",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("comparison_id", sa.String(length=26), nullable=False),
            sa.Column("purchase_order_id", sa.String(length=26), nullable=False),
            sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["comparison_id"], ["purchase_order_comparison.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_order.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comparison_id", "purchase_order_id", name="uq_purchase_order_comparison_order"),
        )
        op.create_index(
            "ix_purchase_order_comparison_order_comparison_id",
            "purchase_order_comparison_order",
            ["comparison_id"],
        )
        op.create_index(
            "ix_purchase_order_comparison_order_purchase_order_id",
            "purchase_order_comparison_order",
            ["purchase_order_id"],
        )


def downgrade() -> None:
    """Drop purchase-order comparison tables."""
    if _table_exists("purchase_order_comparison_order"):
        op.drop_table("purchase_order_comparison_order")
    if _table_exists("purchase_order_comparison"):
        op.drop_index("ix_purchase_order_comparison_base_purchase_order_id", table_name="purchase_order_comparison")
        op.drop_table("purchase_order_comparison")
