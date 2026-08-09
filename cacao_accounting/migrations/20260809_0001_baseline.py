"""Register the schema created by ``cacaoctl db init`` as the Alembic baseline.

The application currently creates its complete schema with SQLAlchemy's
``create_all`` during first-time initialization. This revision deliberately
does not alter existing data; it records the known schema state so subsequent
schema changes can be delivered as real, ordered Alembic revisions.
"""

from collections.abc import Sequence

revision = "20260809_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the initial SQLAlchemy-created schema as the migration baseline."""


def downgrade() -> None:
    """Remove the baseline marker without dropping application tables."""
