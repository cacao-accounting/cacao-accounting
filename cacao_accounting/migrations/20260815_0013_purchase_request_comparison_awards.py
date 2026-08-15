"""Add line-level awards and purchase-order links for request comparisons."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0013"
down_revision = "20260815_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether a column exists."""
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _table_exists(table_name: str) -> bool:
    """Return whether a table exists."""
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    """Add comparison authorization metadata, selections, and order links."""
    comparison_columns = (
        ("authorization_reason", sa.Text()),
        ("authorized_by", sa.String(length=26)),
        ("authorized_at", sa.DateTime(timezone=True)),
        ("finalized_by", sa.String(length=26)),
        ("finalized_at", sa.DateTime(timezone=True)),
        ("used_at", sa.DateTime(timezone=True)),
    )
    with op.batch_alter_table("purchase_request_comparison", recreate="auto") as batch:
        for name, column_type in comparison_columns:
            if not _column_exists("purchase_request_comparison", name):
                batch.add_column(sa.Column(name, column_type, nullable=True))

    if not _column_exists("purchase_order", "purchase_request_comparison_id"):
        with op.batch_alter_table("purchase_order", recreate="auto") as batch:
            batch.add_column(sa.Column("purchase_request_comparison_id", sa.String(length=26), nullable=True))
            batch.create_index(
                "ix_purchase_order_purchase_request_comparison_id",
                ["purchase_request_comparison_id"],
            )
            batch.create_foreign_key(
                "fk_purchase_order_purchase_request_comparison_id",
                "purchase_request_comparison",
                ["purchase_request_comparison_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _table_exists("purchase_request_comparison_line"):
        op.create_table(
            "purchase_request_comparison_line",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("comparison_id", sa.String(length=26), nullable=False),
            sa.Column("purchase_request_item_id", sa.String(length=26), nullable=False),
            sa.Column("recommended_supplier_quotation_id", sa.String(length=26), nullable=True),
            sa.Column("recommended_supplier_quotation_item_id", sa.String(length=26), nullable=True),
            sa.Column("selected_supplier_quotation_id", sa.String(length=26), nullable=True),
            sa.Column("selected_supplier_quotation_item_id", sa.String(length=26), nullable=True),
            sa.Column("qty", sa.Numeric(precision=20, scale=9), nullable=True),
            sa.Column("rate", sa.Numeric(precision=20, scale=4), nullable=True),
            sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=True),
            sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("override_reason", sa.Text(), nullable=True),
            sa.Column("authorized_by", sa.String(length=26), nullable=True),
            sa.ForeignKeyConstraint(["comparison_id"], ["purchase_request_comparison.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["purchase_request_item_id"], ["purchase_request_item.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["recommended_supplier_quotation_id"], ["supplier_quotation.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["recommended_supplier_quotation_item_id"], ["supplier_quotation_item.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["selected_supplier_quotation_id"], ["supplier_quotation.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["selected_supplier_quotation_item_id"], ["supplier_quotation_item.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["authorized_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comparison_id", "purchase_request_item_id", name="uq_purchase_request_comparison_line_item"),
        )
        for name, columns in (
            ("comparison_id", ["comparison_id"]),
            ("purchase_request_item_id", ["purchase_request_item_id"]),
            ("recommended_supplier_quotation_id", ["recommended_supplier_quotation_id"]),
            ("recommended_supplier_quotation_item_id", ["recommended_supplier_quotation_item_id"]),
            ("selected_supplier_quotation_id", ["selected_supplier_quotation_id"]),
            ("selected_supplier_quotation_item_id", ["selected_supplier_quotation_item_id"]),
        ):
            op.create_index(f"ix_purchase_request_comparison_line_{name}", "purchase_request_comparison_line", columns)


def downgrade() -> None:
    """Remove line-level awards and authorization metadata."""
    if _table_exists("purchase_request_comparison_line"):
        op.drop_table("purchase_request_comparison_line")
    if _column_exists("purchase_order", "purchase_request_comparison_id"):
        with op.batch_alter_table("purchase_order", recreate="auto") as batch:
            batch.drop_constraint("fk_purchase_order_purchase_request_comparison_id", type_="foreignkey")
            batch.drop_index("ix_purchase_order_purchase_request_comparison_id")
            batch.drop_column("purchase_request_comparison_id")
    with op.batch_alter_table("purchase_request_comparison", recreate="auto") as batch:
        for name in ("used_at", "finalized_at", "finalized_by", "authorized_at", "authorized_by", "authorization_reason"):
            if _column_exists("purchase_request_comparison", name):
                batch.drop_column(name)
