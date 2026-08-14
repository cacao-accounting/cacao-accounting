"""Add Balance Confirmation schema and PaymentEntry is_advance column."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260814_0007"
down_revision = "20260814_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create balance_confirmation tables and alter payment_entry."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # 1. Create balance_confirmation table
    if "balance_confirmation" not in tables:
        op.create_table(
            "balance_confirmation",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("company", sa.String(length=10), nullable=False),
            sa.Column("document_no", sa.String(length=100), nullable=True),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("party_type", sa.String(length=20), nullable=False),
            sa.Column("party_id", sa.String(length=26), nullable=False),
            sa.Column("cutoff_date", sa.Date(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("snapshot_json", sa.Text(), nullable=True),
            sa.Column("snapshot_hash", sa.String(length=64), nullable=True),
            sa.Column("response_type", sa.String(length=50), nullable=True),
            sa.Column("response_comment", sa.Text(), nullable=True),
            sa.Column("respondent_first_name", sa.String(length=100), nullable=True),
            sa.Column("respondent_last_name", sa.String(length=100), nullable=True),
            sa.Column("respondent_email", sa.String(length=150), nullable=True),
            sa.Column("respondent_ip", sa.String(length=64), nullable=True),
            sa.Column("respondent_user_agent", sa.String(length=512), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["company"], ["entity.code"], ondelete="RESTRICT", onupdate="CASCADE"),
            sa.ForeignKeyConstraint(["party_id"], ["party.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        )
        with op.batch_alter_table("balance_confirmation") as batch:
            batch.create_index("ix_balance_confirmation_company", ["company"])
            batch.create_index("ix_balance_confirmation_party_id", ["party_id"])
            batch.create_index("ix_balance_confirmation_document_no", ["document_no"])

    # 2. Create balance_confirmation_invitation table
    if "balance_confirmation_invitation" not in tables:
        op.create_table(
            "balance_confirmation_invitation",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(length=26), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column("modified_by", sa.String(length=26), nullable=True),
            sa.Column("balance_confirmation_id", sa.String(length=26), nullable=False),
            sa.Column("email", sa.String(length=150), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("verification_code_hash", sa.String(length=64), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_access_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("balance_confirmation_id", "email", name="uq_balance_confirmation_invitation"),
            sa.ForeignKeyConstraint(
                ["balance_confirmation_id"], ["balance_confirmation.id"], ondelete="CASCADE", onupdate="CASCADE"
            ),
        )
        with op.batch_alter_table("balance_confirmation_invitation") as batch:
            batch.create_index("ix_balance_confirmation_invitation_balance_confirmation_id", ["balance_confirmation_id"])
            batch.create_index("ix_balance_confirmation_invitation_token_hash", ["token_hash"])

    # 3. Add is_advance column to payment_entry
    if "payment_entry" in tables:
        columns = {column["name"] for column in inspector.get_columns("payment_entry")}
        if "is_advance" not in columns:
            with op.batch_alter_table("payment_entry", recreate="auto") as batch:
                batch.add_column(sa.Column("is_advance", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    """Drop tables and alter payment_entry."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "balance_confirmation_invitation" in tables:
        op.drop_table("balance_confirmation_invitation")
    if "balance_confirmation" in tables:
        op.drop_table("balance_confirmation")
    if "payment_entry" in tables:
        columns = {column["name"] for column in inspector.get_columns("payment_entry")}
        if "is_advance" in columns:
            with op.batch_alter_table("payment_entry", recreate="auto") as batch:
                batch.drop_column("is_advance")
