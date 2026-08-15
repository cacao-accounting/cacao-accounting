"""Add document numbering to purchase-request comparisons."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0012"
down_revision = "20260815_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether a table has a column."""
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return column_name in {column["name"] for column in columns}


def upgrade() -> None:
    """Add posting date and naming-series fields to comparisons."""
    with op.batch_alter_table("purchase_request_comparison", recreate="auto") as batch:
        if not _column_exists("purchase_request_comparison", "posting_date"):
            batch.add_column(sa.Column("posting_date", sa.Date(), nullable=True))
            batch.create_index("ix_purchase_request_comparison_posting_date", ["posting_date"])
        if not _column_exists("purchase_request_comparison", "document_no"):
            batch.add_column(sa.Column("document_no", sa.String(length=100), nullable=True))
            batch.create_index("ix_purchase_request_comparison_document_no", ["document_no"])
        if not _column_exists("purchase_request_comparison", "naming_series_id"):
            batch.add_column(sa.Column("naming_series_id", sa.String(length=26), nullable=True))
            batch.create_index("ix_purchase_request_comparison_naming_series_id", ["naming_series_id"])
            batch.create_foreign_key(
                "fk_purchase_request_comparison_naming_series_id",
                "naming_series",
                ["naming_series_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    """Remove document numbering fields from comparisons."""
    with op.batch_alter_table("purchase_request_comparison", recreate="auto") as batch:
        if _column_exists("purchase_request_comparison", "naming_series_id"):
            batch.drop_constraint("fk_purchase_request_comparison_naming_series_id", type_="foreignkey")
            batch.drop_index("ix_purchase_request_comparison_naming_series_id")
            batch.drop_column("naming_series_id")
        if _column_exists("purchase_request_comparison", "document_no"):
            batch.drop_index("ix_purchase_request_comparison_document_no")
            batch.drop_column("document_no")
        if _column_exists("purchase_request_comparison", "posting_date"):
            batch.drop_index("ix_purchase_request_comparison_posting_date")
            batch.drop_column("posting_date")
