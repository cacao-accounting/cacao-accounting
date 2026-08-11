"""Add line-level purchase quotation awards and global sourcing controls."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260811_0003"
down_revision = "20260809_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create award tables and link purchase orders to an award."""
    op.create_table(
        "purchase_quotation_award",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("purchase_quotation_id", sa.String(length=26), nullable=False),
        sa.Column("company", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="finalized"),
        sa.Column("created_by", sa.String(length=26), nullable=True),
        sa.Column("authorized_by", sa.String(length=26), nullable=True),
        sa.Column("authorization_reason", sa.Text(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["purchase_quotation_id"], ["purchase_quotation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company"], ["entity.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["authorized_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_quotation_award_purchase_quotation_id", "purchase_quotation_award", ["purchase_quotation_id"])
    op.create_index("ix_purchase_quotation_award_company", "purchase_quotation_award", ["company"])
    op.create_index("ix_purchase_quotation_award_status", "purchase_quotation_award", ["status"])

    op.create_table(
        "purchase_quotation_award_item",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("award_id", sa.String(length=26), nullable=False),
        sa.Column("purchase_quotation_item_id", sa.String(length=26), nullable=False),
        sa.Column("supplier_quotation_id", sa.String(length=26), nullable=False),
        sa.Column("supplier_quotation_item_id", sa.String(length=26), nullable=False),
        sa.Column("item_code", sa.String(length=50), nullable=False),
        sa.Column("qty", sa.Numeric(precision=20, scale=9), nullable=False),
        sa.Column("rate", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["award_id"], ["purchase_quotation_award.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_quotation_item_id"], ["purchase_quotation_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_quotation_id"], ["supplier_quotation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_quotation_item_id"], ["supplier_quotation_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_quotation_award_item_award_id", "purchase_quotation_award_item", ["award_id"])
    op.create_index("ix_purchase_quotation_award_item_item_code", "purchase_quotation_award_item", ["item_code"])

    with op.batch_alter_table("purchase_order", recreate="auto") as batch:
        batch.add_column(sa.Column("purchase_award_id", sa.String(length=26), nullable=True))
        batch.create_index("ix_purchase_order_purchase_award_id", ["purchase_award_id"])
        batch.create_foreign_key(
            "fk_purchase_order_purchase_award_id",
            "purchase_quotation_award",
            ["purchase_award_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Remove award tables and the purchase-order award reference."""
    with op.batch_alter_table("purchase_order", recreate="auto") as batch:
        batch.drop_constraint("fk_purchase_order_purchase_award_id", type_="foreignkey")
        batch.drop_index("ix_purchase_order_purchase_award_id")
        batch.drop_column("purchase_award_id")
    op.drop_index("ix_purchase_quotation_award_item_item_code", table_name="purchase_quotation_award_item")
    op.drop_index("ix_purchase_quotation_award_item_award_id", table_name="purchase_quotation_award_item")
    op.drop_table("purchase_quotation_award_item")
    op.drop_index("ix_purchase_quotation_award_status", table_name="purchase_quotation_award")
    op.drop_index("ix_purchase_quotation_award_company", table_name="purchase_quotation_award")
    op.drop_index("ix_purchase_quotation_award_purchase_quotation_id", table_name="purchase_quotation_award")
    op.drop_table("purchase_quotation_award")
