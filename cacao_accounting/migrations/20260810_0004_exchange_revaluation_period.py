"""Prevent duplicate exchange revaluation runs for one company and period."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260810_0004"
down_revision = "20260810_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _validate_duplicates() -> None:
    """Reject duplicate populated company periods before adding the constraint."""
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            "SELECT company, year, month FROM exchange_revaluation "
            "WHERE company IS NOT NULL AND year IS NOT NULL AND month IS NOT NULL "
            "GROUP BY company, year, month HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "No se puede crear la unicidad de revaluaciones: "
            f"existen ejecuciones duplicadas para {duplicate[0]!r}/{duplicate[1]!r}/{duplicate[2]!r}."
        )


def upgrade() -> None:
    """Enforce one exchange revaluation per company and year/month."""
    _validate_duplicates()
    with op.batch_alter_table("exchange_revaluation", recreate="auto") as batch:
        batch.create_unique_constraint(
            "uq_exchange_revaluation_company_period",
            ["company", "year", "month"],
        )


def downgrade() -> None:
    """Remove the exchange revaluation period uniqueness constraint."""
    with op.batch_alter_table("exchange_revaluation", recreate="auto") as batch:
        batch.drop_constraint("uq_exchange_revaluation_company_period", type_="unique")
