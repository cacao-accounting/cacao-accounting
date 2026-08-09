"""Enforce a stable identity for imported bank statement transactions."""

from collections.abc import Sequence
import hashlib

import sqlalchemy as sa
from alembic import op

revision = "20260810_0003"
down_revision = "20260809_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _validate_duplicates() -> None:
    """Fail safely when historical duplicates need review before migration."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, bank_account_id, posting_date, reference_number, deposit, withdrawal FROM bank_transaction")
    ).mappings()
    identities: dict[str, str] = {}
    for row in rows:
        values = (
            str(row["bank_account_id"] or ""),
            str(row["posting_date"] or ""),
            str(row["reference_number"] or ""),
            str(row["deposit"] if row["deposit"] is not None else ""),
            str(row["withdrawal"] if row["withdrawal"] is not None else ""),
        )
        identity = hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()
        previous = identities.setdefault(identity, str(row["id"]))
        if previous != str(row["id"]):
            raise RuntimeError(
                "No se puede crear la identidad única de bank_transaction: "
                f"existen registros duplicados {previous!r} y {row['id']!r}."
            )
        bind.execute(
            sa.text("UPDATE bank_transaction SET identity_key = :identity WHERE id = :id"),
            {"identity": identity, "id": row["id"]},
        )


def upgrade() -> None:
    """Create the bank transaction identity constraint after validating history."""
    op.add_column("bank_transaction", sa.Column("identity_key", sa.String(length=64), nullable=True))
    _validate_duplicates()
    with op.batch_alter_table("bank_transaction", recreate="auto") as batch:
        batch.alter_column("identity_key", existing_type=sa.String(length=64), nullable=False)
        batch.create_unique_constraint(
            "uq_bank_transaction_identity",
            ["identity_key"],
        )


def downgrade() -> None:
    """Remove the bank transaction identity constraint."""
    with op.batch_alter_table("bank_transaction", recreate="auto") as batch:
        batch.drop_constraint("uq_bank_transaction_identity", type_="unique")
    op.drop_column("bank_transaction", "identity_key")
