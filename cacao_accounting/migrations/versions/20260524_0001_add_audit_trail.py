"""create audit_trail table

Revision ID: 20260524_0001
Revises:
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "20260524_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_trail",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=False),
        sa.Column("document_id", sa.String(length=26), nullable=False),
        sa.Column("document_no", sa.String(length=100), nullable=True),
        sa.Column("company", sa.String(length=10), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.String(length=26), nullable=True),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("changes_json", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source_module", sa.String(length=80), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["company"], ["entity.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_trail_document_type", "audit_trail", ["document_type"], unique=False)
    op.create_index("ix_audit_trail_document_id", "audit_trail", ["document_id"], unique=False)
    op.create_index("ix_audit_trail_document_no", "audit_trail", ["document_no"], unique=False)
    op.create_index("ix_audit_trail_company", "audit_trail", ["company"], unique=False)
    op.create_index("ix_audit_trail_action", "audit_trail", ["action"], unique=False)
    op.create_index("ix_audit_trail_actor_user_id", "audit_trail", ["actor_user_id"], unique=False)
    op.create_index("ix_audit_trail_timestamp", "audit_trail", ["timestamp"], unique=False)
    op.create_index("ix_audit_trail_source_module", "audit_trail", ["source_module"], unique=False)
    op.create_index(
        "ix_audit_trail_document_lookup",
        "audit_trail",
        ["document_type", "document_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_trail_document_lookup", table_name="audit_trail")
    op.drop_index("ix_audit_trail_source_module", table_name="audit_trail")
    op.drop_index("ix_audit_trail_timestamp", table_name="audit_trail")
    op.drop_index("ix_audit_trail_actor_user_id", table_name="audit_trail")
    op.drop_index("ix_audit_trail_action", table_name="audit_trail")
    op.drop_index("ix_audit_trail_company", table_name="audit_trail")
    op.drop_index("ix_audit_trail_document_no", table_name="audit_trail")
    op.drop_index("ix_audit_trail_document_id", table_name="audit_trail")
    op.drop_index("ix_audit_trail_document_type", table_name="audit_trail")
    op.drop_table("audit_trail")
