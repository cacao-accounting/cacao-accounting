# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Preserve MIME format for queued email retries."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0005"
down_revision: str | None = "20261113_0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add a backward-compatible format flag to existing email queue rows."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("email_queue"):
        return
    columns = {column["name"] for column in inspector.get_columns("email_queue")}
    if "is_html" not in columns:
        op.add_column(
            "email_queue",
            sa.Column("is_html", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    """Remove the format flag when reverting this schema revision."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("email_queue"):
        return
    columns = {column["name"] for column in inspector.get_columns("email_queue")}
    if "is_html" in columns:
        op.drop_column("email_queue", "is_html")
