"""Create purchase-request comparisons of supplier quotations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0011"
down_revision = "20260815_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Return whether a table exists in the current database."""
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    """Create the comparison header and supplier quotation participants."""
    if not _table_exists("purchase_request_comparison"):
        op.create_table(
            "purchase_request_comparison",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("company", sa.String(length=10), nullable=False),
            sa.Column("purchase_request_id", sa.String(length=26), nullable=False),
            sa.ForeignKeyConstraint(["company"], ["entity.code"], ondelete="RESTRICT", onupdate="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["purchase_request_id"], ["purchase_request.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_purchase_request_comparison_purchase_request_id",
            "purchase_request_comparison",
            ["purchase_request_id"],
        )

    if not _table_exists("purchase_request_comparison_offer"):
        op.create_table(
            "purchase_request_comparison_offer",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("comparison_id", sa.String(length=26), nullable=False),
            sa.Column("supplier_quotation_id", sa.String(length=26), nullable=False),
            sa.ForeignKeyConstraint(["comparison_id"], ["purchase_request_comparison.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["supplier_quotation_id"], ["supplier_quotation.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comparison_id", "supplier_quotation_id", name="uq_purchase_request_comparison_offer"),
        )
        op.create_index(
            "ix_purchase_request_comparison_offer_comparison_id",
            "purchase_request_comparison_offer",
            ["comparison_id"],
        )
        op.create_index(
            "ix_purchase_request_comparison_offer_supplier_quotation_id",
            "purchase_request_comparison_offer",
            ["supplier_quotation_id"],
        )


def downgrade() -> None:
    """Drop purchase-request comparison tables."""
    if _table_exists("purchase_request_comparison_offer"):
        op.drop_table("purchase_request_comparison_offer")
    if _table_exists("purchase_request_comparison"):
        op.drop_index(
            "ix_purchase_request_comparison_purchase_request_id",
            table_name="purchase_request_comparison",
        )
        op.drop_table("purchase_request_comparison")
