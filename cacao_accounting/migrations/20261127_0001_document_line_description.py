# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Agrega ``description`` a las líneas de venta y compra que la importaban.

Las plantillas de importación ya ofrecían una columna de descripción para
órdenes y facturas de venta, recepciones y facturas de compra, y notas de
entrega, pero esos modelos no tenían columna donde persistirla. El alta y la
duplicación ahora conservan el texto específico de la línea (#2351).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261127_0001"
down_revision: str | None = "20261015_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "sales_order_item",
    "sales_invoice_item",
    "delivery_note_item",
    "purchase_receipt_item",
    "purchase_invoice_item",
)


def _missing_description(inspector: sa.Inspector, table: str) -> bool:
    """Indica si la tabla existe y aún no tiene la columna."""
    if not inspector.has_table(table):
        return False
    return "description" not in {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    """Agrega ``description`` de forma idempotente a las líneas soportadas."""
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        if _missing_description(inspector, table):
            op.add_column(table, sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Retira ``description`` de las líneas que la recibieron."""
    inspector = sa.inspect(op.get_bind())
    for table in reversed(_TABLES):
        if inspector.has_table(table) and not _missing_description(inspector, table):
            op.drop_column(table, "description")
