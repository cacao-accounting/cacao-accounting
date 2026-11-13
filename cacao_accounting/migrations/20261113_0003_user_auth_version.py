# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Track credential generations to revoke pre-reset sessions and JWTs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0003"
down_revision: str | None = "20261113_0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add the monotonic version checked by browser sessions and API tokens."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("user"):
        return
    if any(column["name"] == "auth_version" for column in inspector.get_columns("user")):
        return
    op.add_column(
        "user",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Refuse downgrade because it would make pre-reset credentials usable again."""
    raise RuntimeError("Credential versions protect existing sessions; do not downgrade this migration.")
