"""Enforce one active supplier invoice number per supplier at database level."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260810_0005"
down_revision = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _validate_no_duplicates() -> None:
    """Fail safely when historical duplicate active invoices need review.

    S2P-24 considera único el número de factura del proveedor para las facturas
    activas (docstatus != 2); las canceladas pueden reutilizar el número. El
    preflight replica la clave normalizada que mantiene la aplicacion.
    """
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            "SELECT supplier_id, TRIM(supplier_invoice_no) AS supplier_invoice_key "
            "FROM purchase_invoice "
            "WHERE docstatus <> 2 AND supplier_id IS NOT NULL "
            "AND supplier_invoice_no IS NOT NULL AND TRIM(supplier_invoice_no) <> '' "
            "GROUP BY supplier_id, TRIM(supplier_invoice_no) "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "No se puede crear la unicidad del numero de factura del proveedor: "
            f"existen facturas activas duplicadas para el proveedor "
            f"{duplicate[0]!r} con el numero {duplicate[1]!r}."
        )


def upgrade() -> None:
    """Add the supplier invoice number uniqueness constraint after validating history."""
    _validate_no_duplicates()
    op.add_column("purchase_invoice", sa.Column("supplier_invoice_key", sa.String(length=50), nullable=True))
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE purchase_invoice SET supplier_invoice_key = TRIM(supplier_invoice_no) "
            "WHERE docstatus <> 2 AND supplier_invoice_no IS NOT NULL AND TRIM(supplier_invoice_no) <> ''"
        )
    )
    with op.batch_alter_table("purchase_invoice", recreate="auto") as batch:
        batch.create_unique_constraint(
            "uq_purchase_invoice_supplier_number",
            ["supplier_id", "supplier_invoice_key"],
        )


def downgrade() -> None:
    """Remove the supplier invoice number uniqueness constraint."""
    with op.batch_alter_table("purchase_invoice", recreate="auto") as batch:
        batch.drop_constraint("uq_purchase_invoice_supplier_number", type_="unique")
    op.drop_column("purchase_invoice", "supplier_invoice_key")
