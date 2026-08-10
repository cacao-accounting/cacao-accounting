"""Enforce non-null and unique company/book codes on existing databases.

The ORM already declares these columns as required. This revision brings
databases created before that declaration into the same contract without
inventing accounting master-data values.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260809_0002"
down_revision = "20260809_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _validate_codes(table_name: str) -> None:
    """Reject null or duplicate codes before changing the schema."""
    bind = op.get_bind()
    null_count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE code IS NULL")).scalar_one()
    if null_count:
        raise RuntimeError(
            f"No se puede migrar {table_name}.code: existen {null_count} registros nulos; "
            "asigne códigos contables antes de reintentar."
        )

    duplicate = bind.execute(
        sa.text(f"SELECT code FROM {table_name} WHERE code IS NOT NULL " "GROUP BY code HAVING COUNT(*) > 1 LIMIT 1")
    ).first()
    if duplicate is not None:
        raise RuntimeError(f"No se puede migrar {table_name}.code: el código {duplicate[0]!r} está duplicado.")


def _make_non_nullable(table_name: str) -> None:
    """Make ``code`` non-nullable using a portable Alembic operation."""
    bind = op.get_bind()
    column = next(
        (item for item in sa.inspect(bind).get_columns(table_name) if item["name"] == "code"),
        None,
    )
    if column is None:
        raise RuntimeError(f"No existe la columna {table_name}.code; revise el esquema antes de migrar.")
    if not column["nullable"]:
        return

    with op.batch_alter_table(table_name, recreate="auto") as batch:
        batch.alter_column("code", existing_type=sa.String(length=10), nullable=False)


def upgrade() -> None:
    """Validate master data and enforce required company/book codes."""
    for table_name in ("entity", "book"):
        _validate_codes(table_name)
        _make_non_nullable(table_name)


def downgrade() -> None:
    """Allow null codes again without modifying existing values."""
    for table_name in ("entity", "book"):
        with op.batch_alter_table(table_name, recreate="auto") as batch:
            batch.alter_column("code", existing_type=sa.String(length=10), nullable=True)
