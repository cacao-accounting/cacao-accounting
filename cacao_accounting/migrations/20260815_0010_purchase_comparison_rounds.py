"""Add immutable negotiation rounds to purchase-order comparisons."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0010"
down_revision = "20260815_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Return whether a table exists in the current database."""
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    """Create comparison rounds and their explicit participant snapshots."""
    if not _table_exists("purchase_order_comparison_round"):
        op.create_table(
            "purchase_order_comparison_round",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("comparison_id", sa.String(length=26), nullable=False),
            sa.Column("round_number", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["comparison_id"], ["purchase_order_comparison.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comparison_id", "round_number", name="uq_purchase_order_comparison_round_number"),
        )
        op.create_index(
            "ix_purchase_order_comparison_round_comparison_id",
            "purchase_order_comparison_round",
            ["comparison_id"],
        )
        op.create_index(
            "ix_purchase_order_comparison_round_status",
            "purchase_order_comparison_round",
            ["status"],
        )

    if not _table_exists("purchase_order_comparison_round_order"):
        op.create_table(
            "purchase_order_comparison_round_order",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("round_id", sa.String(length=26), nullable=False),
            sa.Column("purchase_order_id", sa.String(length=26), nullable=False),
            sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["round_id"], ["purchase_order_comparison_round.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_order.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("round_id", "purchase_order_id", name="uq_purchase_order_comparison_round_order"),
        )
        op.create_index(
            "ix_purchase_order_comparison_round_order_round_id",
            "purchase_order_comparison_round_order",
            ["round_id"],
        )
        op.create_index(
            "ix_purchase_order_comparison_round_order_purchase_order_id",
            "purchase_order_comparison_round_order",
            ["purchase_order_id"],
        )


def downgrade() -> None:
    """Drop comparison round snapshots."""
    if _table_exists("purchase_order_comparison_round_order"):
        op.drop_table("purchase_order_comparison_round_order")
    if _table_exists("purchase_order_comparison_round"):
        op.drop_index("ix_purchase_order_comparison_round_status", table_name="purchase_order_comparison_round")
        op.drop_index("ix_purchase_order_comparison_round_comparison_id", table_name="purchase_order_comparison_round")
        op.drop_table("purchase_order_comparison_round")
