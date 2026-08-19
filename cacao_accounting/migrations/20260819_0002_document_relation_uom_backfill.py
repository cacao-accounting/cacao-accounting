"""Backfill base quantities for legacy document relations."""

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from alembic import op
import sqlalchemy as sa

revision = "20260819_0002"
down_revision: str | None = "20260819_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_ITEM_TABLES = {
    "purchase_order": "purchase_order_item",
    "purchase_request": "purchase_request_item",
    "purchase_quotation": "purchase_quotation_item",
    "supplier_quotation": "supplier_quotation_item",
    "purchase_receipt": "purchase_receipt_item",
    "purchase_invoice": "purchase_invoice_item",
    "purchase_return": "purchase_invoice_item",
    "purchase_credit_note": "purchase_invoice_item",
    "purchase_debit_note": "purchase_invoice_item",
    "import_landed_cost": "import_landed_cost_item",
    "sales_order": "sales_order_item",
    "sales_request": "sales_request_item",
    "sales_quotation": "sales_quotation_item",
    "delivery_note": "delivery_note_item",
    "sales_invoice": "sales_invoice_item",
    "sales_return": "sales_invoice_item",
    "sales_credit_note": "sales_invoice_item",
    "sales_debit_note": "sales_invoice_item",
    "stock_entry": "stock_entry_item",
}


def _decimal(value: Any) -> Decimal:
    """Convert a database value to ``Decimal`` without losing precision."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _load_conversions(bind: sa.Connection) -> dict[tuple[str, str, str], Decimal]:
    """Load item-specific UOM conversion factors for the migration."""
    conversion = sa.table(
        "item_uom_conversion",
        sa.column("item_code"),
        sa.column("from_uom"),
        sa.column("to_uom"),
        sa.column("conversion_factor"),
    )
    rows = bind.execute(sa.select(conversion)).mappings()
    return {(row["item_code"], row["from_uom"], row["to_uom"]): _decimal(row["conversion_factor"]) for row in rows}


def _base_quantity(
    qty: Any,
    item_code: str | None,
    from_uom: str | None,
    default_uom: str | None,
    conversions: dict[tuple[str, str, str], Decimal],
) -> Decimal:
    """Convert a legacy relation quantity using the item's base UOM."""
    quantity = _decimal(qty)
    source_uom = from_uom or default_uom
    if not item_code or not source_uom or not default_uom or source_uom == default_uom:
        return quantity

    direct_factor = conversions.get((item_code, source_uom, default_uom))
    if direct_factor is not None:
        return quantity * direct_factor

    inverse_factor = conversions.get((item_code, default_uom, source_uom))
    if inverse_factor not in (None, Decimal("0")):
        return quantity / inverse_factor
    return quantity


def _backfill_source_type(
    bind: sa.Connection,
    source_type: str,
    item_table_name: str,
    conversions: dict[tuple[str, str, str], Decimal],
) -> None:
    """Backfill relations for one source type using its item table."""
    if not sa.inspect(bind).has_table(item_table_name):
        return
    relation = sa.table(
        "document_relation",
        sa.column("id", sa.String(26)),
        sa.column("source_type"),
        sa.column("source_item_id"),
        sa.column("qty", sa.Numeric(20, 9)),
        sa.column("qty_in_base_uom", sa.Numeric(20, 9)),
        sa.column("uom"),
    )
    source_item = sa.table(
        item_table_name,
        sa.column("id"),
        sa.column("item_code"),
        sa.column("uom"),
    )
    item = sa.table("item", sa.column("code"), sa.column("default_uom"))
    query = (
        sa.select(
            relation.c.id,
            relation.c.qty,
            relation.c.uom,
            source_item.c.item_code,
            source_item.c.uom.label("source_uom"),
            item.c.default_uom,
        )
        .select_from(
            relation.outerjoin(source_item, relation.c.source_item_id == source_item.c.id).outerjoin(
                item, source_item.c.item_code == item.c.code
            )
        )
        .where(
            relation.c.source_type == source_type,
            relation.c.qty_in_base_uom.is_(None),
        )
    )
    for row in bind.execute(query).mappings():
        base_quantity = _base_quantity(
            row["qty"],
            row["item_code"],
            row["uom"] or row["source_uom"],
            row["default_uom"],
            conversions,
        )
        bind.execute(sa.update(relation).where(relation.c.id == row["id"]).values(qty_in_base_uom=base_quantity))


def backfill_document_relations(bind: sa.Connection) -> None:
    """Persist base quantities for all legacy document relations."""
    conversions = _load_conversions(bind)
    for source_type, item_table_name in _SOURCE_ITEM_TABLES.items():
        _backfill_source_type(bind, source_type, item_table_name, conversions)

    relation = sa.table(
        "document_relation",
        sa.column("qty", sa.Numeric(20, 9)),
        sa.column("qty_in_base_uom", sa.Numeric(20, 9)),
    )
    bind.execute(sa.update(relation).where(relation.c.qty_in_base_uom.is_(None)).values(qty_in_base_uom=relation.c.qty))


def upgrade() -> None:
    """Persist normalized quantities so legacy relations use one dimension."""
    backfill_document_relations(op.get_bind())


def downgrade() -> None:
    """Leave normalized historical quantities intact when rolling back."""
