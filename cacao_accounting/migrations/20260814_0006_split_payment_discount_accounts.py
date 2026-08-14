"""Split the payment discount default into sales and purchase sides.

``payment_discount_account_id`` se usaba para ambos sentidos del flujo de
pagos, lo que obligaba a usar la misma cuenta para descuentos de ventas
(gasto) y de compras (ingreso). Esta revision separa el campo en
``sales_discount_account_id`` y ``purchase_discount_account_id``, migrando el
valor existente a ambos y eliminando la columna original.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from alembic.operations.base import BatchOperations

revision = "20260814_0006"
down_revision = "20260813_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "company_default_account"
SALES_FK = "fk_company_default_account_sales_discount_account_id"
PURCHASE_FK = "fk_company_default_account_purchase_discount_account_id"
LEGACY_FK = "fk_company_default_account_payment_discount_account_id"


def _columns() -> set[str]:
    """Return the current column names of the company default account table."""
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(TABLE)}


def _add_discount_column(batch: BatchOperations, column: str, fk_name: str) -> None:
    """Add a nullable account reference column with its foreign key."""
    batch.add_column(sa.Column(column, sa.String(length=26), nullable=True))
    batch.create_foreign_key(
        fk_name,
        "accounts",
        [column],
        ["id"],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )


def upgrade() -> None:
    """Add the split discount columns, backfill them and drop the legacy one."""
    columns = _columns()
    if not columns:
        return
    with op.batch_alter_table(TABLE, recreate="auto") as batch:
        if "sales_discount_account_id" not in columns:
            _add_discount_column(batch, "sales_discount_account_id", SALES_FK)
        if "purchase_discount_account_id" not in columns:
            _add_discount_column(batch, "purchase_discount_account_id", PURCHASE_FK)
    if "payment_discount_account_id" in columns:
        op.execute(
            sa.text(
                "UPDATE company_default_account "
                "SET sales_discount_account_id = payment_discount_account_id, "
                "purchase_discount_account_id = payment_discount_account_id "
                "WHERE payment_discount_account_id IS NOT NULL"
            )
        )
        with op.batch_alter_table(TABLE, recreate="auto") as batch:
            batch.drop_column("payment_discount_account_id")


def downgrade() -> None:
    """Restore the single payment discount column from the split values."""
    columns = _columns()
    if not columns:
        return
    if "payment_discount_account_id" not in columns:
        with op.batch_alter_table(TABLE, recreate="auto") as batch:
            batch.add_column(sa.Column("payment_discount_account_id", sa.String(length=26), nullable=True))
            batch.create_foreign_key(
                LEGACY_FK,
                "accounts",
                ["payment_discount_account_id"],
                ["id"],
                ondelete="RESTRICT",
                onupdate="CASCADE",
            )
        if "sales_discount_account_id" in columns or "purchase_discount_account_id" in columns:
            op.execute(
                sa.text(
                    "UPDATE company_default_account "
                    "SET payment_discount_account_id = COALESCE("
                    "sales_discount_account_id, purchase_discount_account_id) "
                    "WHERE sales_discount_account_id IS NOT NULL "
                    "OR purchase_discount_account_id IS NOT NULL"
                )
            )
    with op.batch_alter_table(TABLE, recreate="auto") as batch:
        if "sales_discount_account_id" in columns:
            batch.drop_constraint(SALES_FK, type_="foreignkey")
            batch.drop_column("sales_discount_account_id")
        if "purchase_discount_account_id" in columns:
            batch.drop_constraint(PURCHASE_FK, type_="foreignkey")
            batch.drop_column("purchase_discount_account_id")
