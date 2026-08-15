"""Add an operational status to purchase requests."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260815_0014"
down_revision = "20260815_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether a table has a column."""
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    """Add the open/closed status used by the purchase-request workflow."""
    if _column_exists("purchase_request", "status"):
        return
    with op.batch_alter_table("purchase_request", recreate="auto") as batch:
        batch.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="open"))
        batch.create_index("ix_purchase_request_status", ["status"])


def downgrade() -> None:
    """Remove the purchase-request operational status."""
    if not _column_exists("purchase_request", "status"):
        return
    with op.batch_alter_table("purchase_request", recreate="auto") as batch:
        batch.drop_index("ix_purchase_request_status")
        batch.drop_column("status")
