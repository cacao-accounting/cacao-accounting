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
    op.execute(
        sa.text(
            """
            UPDATE purchase_order_comparison AS comparison
            SET purchase_request_id = (
                SELECT MIN(relation.source_id)
                FROM purchase_order_comparison_order AS participant
                JOIN document_relation AS relation
                  ON relation.target_type = 'purchase_order'
                 AND relation.target_id = participant.purchase_order_id
                 AND relation.source_type = 'purchase_request'
                 AND relation.status = 'active'
                WHERE participant.comparison_id = comparison.id
            )
            WHERE comparison.purchase_request_id IS NULL
              AND EXISTS (
                SELECT 1
                FROM purchase_order_comparison_order AS participant
                JOIN document_relation AS relation
                  ON relation.target_type = 'purchase_order'
                 AND relation.target_id = participant.purchase_order_id
                 AND relation.source_type = 'purchase_request'
                 AND relation.status = 'active'
                WHERE participant.comparison_id = comparison.id
              )
            """
        )
    )


def downgrade() -> None:
    """Remove the purchase-request origin from comparisons."""
    if _column_exists("purchase_order_comparison", "purchase_request_id"):
        with op.batch_alter_table("purchase_order_comparison", recreate="auto") as batch:
            batch.drop_constraint("fk_purchase_order_comparison_purchase_request_id", type_="foreignkey")
            batch.drop_index("ix_purchase_order_comparison_purchase_request_id")
            batch.drop_column("purchase_request_id")
