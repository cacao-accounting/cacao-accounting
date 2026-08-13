"""Add party and company scope fields required by cloud portal users."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260813_0005"
down_revision = "20260811_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable portal identity scope to existing user tables."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("user")}
    with op.batch_alter_table("user", recreate="auto") as batch:
        if "party_id" not in columns:
            batch.add_column(sa.Column("party_id", sa.String(length=26), nullable=True))
            batch.create_foreign_key("fk_user_party_id", "party", ["party_id"], ["id"], ondelete="SET NULL")
        if "company" not in columns:
            batch.add_column(sa.Column("company", sa.String(length=10), nullable=True))
            batch.create_foreign_key("fk_user_company", "entity", ["company"], ["code"], ondelete="SET NULL")


def downgrade() -> None:
    """Remove the portal identity scope fields."""
    with op.batch_alter_table("user", recreate="auto") as batch:
        batch.drop_constraint("fk_user_company", type_="foreignkey")
        batch.drop_constraint("fk_user_party_id", type_="foreignkey")
        batch.drop_column("company")
        batch.drop_column("party_id")
