"""Migración incremental: columnas de almacenamiento de adjuntos.

Agrega ``item.image_path`` y ``file.remarks`` en instalaciones que ya
existían antes de la funcionalidad de adjuntos.  La operación es
idempotente: si la columna ya está presente, no hace nada, permitiendo
que se ejecute tanto sobre esquemas nuevos (creados con ``create_all``
por ``cacaoctl db init``) como sobre esquemas existentes.

Revision ID: 20260823_0001
Revises: 20260809_0001
Create Date: 2026-08-23
"""

from alembic import op
import sqlalchemy as sa

revision = "20260823_0001"
down_revision = "20260809_0001"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Return True when the column already exists in the table."""
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    """Add attachment storage columns without failing on existing schemas."""
    if not _column_exists("item", "image_path"):
        op.add_column("item", sa.Column("image_path", sa.String(length=500), nullable=True))
    if not _column_exists("file", "remarks"):
        op.add_column("file", sa.Column("remarks", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove the attachment storage columns."""
    op.drop_column("item", "image_path")
    op.drop_column("file", "remarks")
