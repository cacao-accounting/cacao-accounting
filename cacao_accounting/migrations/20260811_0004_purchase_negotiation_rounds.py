"""Add optional supplier negotiation rounds to purchase quotations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260811_0004"
down_revision = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists in the database."""
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in the given table."""
    bind = op.get_bind()
    columns = [c["name"] for c in sa.inspect(bind).get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Create rounds and associate supplier quotations and awards with them."""
    if not _table_exists("purchase_negotiation_round"):
        op.create_table(
            "purchase_negotiation_round",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("purchase_quotation_id", sa.String(length=26), nullable=False),
            sa.Column("round_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["purchase_quotation_id"], ["purchase_quotation.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("purchase_quotation_id", "round_number", name="uq_purchase_negotiation_round_number"),
        )
        op.create_index(
            "ix_purchase_negotiation_round_purchase_quotation_id",
            "purchase_negotiation_round",
            ["purchase_quotation_id"],
        )
        op.create_index("ix_purchase_negotiation_round_status", "purchase_negotiation_round", ["status"])

    if not _column_exists("supplier_quotation", "negotiation_round_id"):
        with op.batch_alter_table("supplier_quotation", recreate="auto") as batch:
            batch.add_column(sa.Column("negotiation_round_id", sa.String(length=26), nullable=True))
            batch.create_index("ix_supplier_quotation_negotiation_round_id", ["negotiation_round_id"])
            batch.create_foreign_key(
                "fk_supplier_quotation_negotiation_round_id",
                "purchase_negotiation_round",
                ["negotiation_round_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _column_exists("purchase_quotation_award", "negotiation_round_id"):
        with op.batch_alter_table("purchase_quotation_award", recreate="auto") as batch:
            batch.add_column(sa.Column("negotiation_round_id", sa.String(length=26), nullable=True))
            batch.create_index("ix_purchase_quotation_award_negotiation_round_id", ["negotiation_round_id"])
            batch.create_foreign_key(
                "fk_purchase_quotation_award_negotiation_round_id",
                "purchase_negotiation_round",
                ["negotiation_round_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    """Remove negotiation-round associations and round records."""
    with op.batch_alter_table("purchase_quotation_award", recreate="auto") as batch:
        batch.drop_constraint("fk_purchase_quotation_award_negotiation_round_id", type_="foreignkey")
        batch.drop_index("ix_purchase_quotation_award_negotiation_round_id")
        batch.drop_column("negotiation_round_id")
    with op.batch_alter_table("supplier_quotation", recreate="auto") as batch:
        batch.drop_constraint("fk_supplier_quotation_negotiation_round_id", type_="foreignkey")
        batch.drop_index("ix_supplier_quotation_negotiation_round_id")
        batch.drop_column("negotiation_round_id")
    op.drop_index("ix_purchase_negotiation_round_status", table_name="purchase_negotiation_round")
    op.drop_index("ix_purchase_negotiation_round_purchase_quotation_id", table_name="purchase_negotiation_round")
    op.drop_table("purchase_negotiation_round")
