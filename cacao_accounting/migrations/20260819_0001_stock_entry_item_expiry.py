"""Add expiry tracking to stock entry lines."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = "20260819_0001"
down_revision: str | None = "20260817_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the optional expiry date to existing stock entry line tables."""
    inspector = sa.inspect(op.get_bind())
    columns = {column_info["name"] for column_info in inspector.get_columns("stock_entry_item")}
    if "expiry_date" not in columns:
        op.add_column("stock_entry_item", sa.Column("expiry_date", sa.Date(), nullable=True))


def downgrade() -> None:
    """Remove the expiry date from stock entry lines when rolling back."""
    inspector = sa.inspect(op.get_bind())
    columns = {column_info["name"] for column_info in inspector.get_columns("stock_entry_item")}
    if "expiry_date" in columns:
        op.drop_column("stock_entry_item", "expiry_date")
