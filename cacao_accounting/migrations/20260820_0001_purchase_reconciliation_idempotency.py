"""Idempotency key y restricción única para conciliaciones de compra.

Añade una columna ``idempotency_key`` a ``purchase_reconciliation`` y una
restricción parcial única sobre ``purchase_invoice_id`` para que el
matching S2P sea a prueba de reintentos, replays y concurrencia de
workers (issue #283 — AUDIT-008).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260820_0001"
down_revision: str | None = "20260819_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Comprueba si una columna ya existe en la tabla."""
    inspector = sa.inspect(op.get_bind())
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Comprueba si un unique constraint ya existe en la tabla."""
    inspector = sa.inspect(op.get_bind())
    constraints = inspector.get_unique_constraints(table_name)
    return any(c["name"] == constraint_name for c in constraints)


def _index_exists(table_name: str, index_name: str) -> bool:
    """Comprueba si un índice ya existe en la tabla."""
    inspector = sa.inspect(op.get_bind())
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Add idempotency_key and unique constraints to purchase_reconciliation."""
    if not _column_exists("purchase_reconciliation", "idempotency_key"):
        op.add_column(
            "purchase_reconciliation",
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        )

    if not _constraint_exists("purchase_reconciliation", "uq_purchase_reconciliation_idempotency"):
        op.create_unique_constraint(
            "uq_purchase_reconciliation_idempotency",
            "purchase_reconciliation",
            ["idempotency_key"],
        )

    if not _index_exists("purchase_reconciliation", "ix_purchase_recon_active_invoice"):
        op.create_index(
            "ix_purchase_recon_active_invoice",
            "purchase_reconciliation",
            ["purchase_invoice_id"],
            unique=True,
            sqlite_where=sa.text("status != 'cancelled'"),
            postgresql_where=sa.text("status != 'cancelled'"),
        )


def downgrade() -> None:
    """Remove idempotency_key and unique constraints from purchase_reconciliation."""
    if _index_exists("purchase_reconciliation", "ix_purchase_recon_active_invoice"):
        op.drop_index("ix_purchase_recon_active_invoice", table_name="purchase_reconciliation")

    if _constraint_exists("purchase_reconciliation", "uq_purchase_reconciliation_idempotency"):
        op.drop_constraint(
            "uq_purchase_reconciliation_idempotency",
            "purchase_reconciliation",
            type_="unique",
        )

    if _column_exists("purchase_reconciliation", "idempotency_key"):
        op.drop_column("purchase_reconciliation", "idempotency_key")
