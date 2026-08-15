"""Link purchase-order comparisons to their purchase request origin."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0009"
down_revision = "20260815_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether a table has a column."""
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return column_name in {column["name"] for column in columns}


def upgrade() -> None:
    """Add the purchase-request origin to comparisons."""
    if not _column_exists("purchase_order_comparison", "purchase_request_id"):
        with op.batch_alter_table("purchase_order_comparison", recreate="auto") as batch:
            batch.add_column(sa.Column("purchase_request_id", sa.String(length=26), nullable=True))
            batch.create_index("ix_purchase_order_comparison_purchase_request_id", ["purchase_request_id"])
            batch.create_foreign_key(
                "fk_purchase_order_comparison_purchase_request_id",
                "purchase_request",
                ["purchase_request_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    """Remove the purchase-request origin from comparisons."""
    if _column_exists("purchase_order_comparison", "purchase_request_id"):
        with op.batch_alter_table("purchase_order_comparison", recreate="auto") as batch:
            batch.drop_constraint("fk_purchase_order_comparison_purchase_request_id", type_="foreignkey")
            batch.drop_index("ix_purchase_order_comparison_purchase_request_id")
            batch.drop_column("purchase_request_id")
