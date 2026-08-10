"""Migración dummy que nunca falla.

Cacao Accounting crea su esquema completo con ``create_all`` durante la
inicialización (``cacaoctl db init``), por lo que no se aplican migraciones
incrementales. Esta revisión no modifica ningún dato: solo existe para que
el comando ``cacaoctl db migrate`` funcione como no-op idempotente.
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
