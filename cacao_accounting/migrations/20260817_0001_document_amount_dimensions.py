"""Add columns introduced after the initial schema baseline.

The application bootstrap uses ``create_all`` for new databases, but
existing installations still need an incremental migration for columns added
to models after the baseline revision.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = "20260817_0001"
down_revision: str | None = "20260809_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    """Add a column only when the target installation predates it."""
    inspector = sa.inspect(op.get_bind())
    existing = {column_info["name"] for column_info in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    """Upgrade installations created from the initial schema baseline."""
    _add_column_if_missing(
        "purchase_receipt",
        sa.Column("base_total", sa.Numeric(precision=20, scale=4), nullable=True),
    )
    _add_column_if_missing(
        "document_relation",
        sa.Column("qty_in_base_uom", sa.Numeric(precision=20, scale=9), nullable=True),
    )


def downgrade() -> None:
    """Remove the columns introduced by this revision."""
    inspector = sa.inspect(op.get_bind())
    for table_name, column_name in (
        ("document_relation", "qty_in_base_uom"),
        ("purchase_receipt", "base_total"),
    ):
        existing = {column_info["name"] for column_info in inspector.get_columns(table_name)}
        if column_name in existing:
            op.drop_column(table_name, column_name)
