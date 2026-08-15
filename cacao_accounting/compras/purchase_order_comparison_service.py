"""Servicios para comparar órdenes de compra entre sí."""

from __future__ import annotations

from collections.abc import Sequence

from cacao_accounting.database import (
    DocumentRelation,
    PurchaseOrder,
    PurchaseOrderComparison,
    PurchaseOrderComparisonOrder,
    database,
)


def purchase_request_ids_for_order(order_id: str) -> set[str]:
    """Return active purchase-request origins for a purchase order."""
    rows = database.session.execute(
        database.select(DocumentRelation.source_id).where(
            DocumentRelation.source_type == "purchase_request",
            DocumentRelation.target_type == "purchase_order",
            DocumentRelation.target_id == order_id,
            DocumentRelation.status == "active",
        )
    ).scalars()
    return set(rows)


def comparable_purchase_orders(base_order: PurchaseOrder) -> list[PurchaseOrder]:
    """Return submitted purchase orders sharing an origin with the base order."""
    source_ids = purchase_request_ids_for_order(base_order.id)
    if not source_ids:
        return [base_order] if base_order.docstatus == 1 else []
    order_ids = database.select(DocumentRelation.target_id).where(
        DocumentRelation.source_type == "purchase_request",
        DocumentRelation.source_id.in_(source_ids),
        DocumentRelation.target_type == "purchase_order",
        DocumentRelation.status == "active",
    )
    statement = database.select(PurchaseOrder).where(
        PurchaseOrder.id.in_(order_ids),
        PurchaseOrder.company == base_order.company,
        PurchaseOrder.docstatus == 1,
    )
    return list(
        database.session.execute(statement.order_by(PurchaseOrder.supplier_name, PurchaseOrder.document_no, PurchaseOrder.id))
        .scalars()
        .all()
    )


def create_purchase_order_comparison(
    base_order: PurchaseOrder, participant_ids: Sequence[str], user_id: str | None
) -> PurchaseOrderComparison:
    """Persist a comparison with the base order and selected participant orders."""
    candidates = {order.id: order for order in comparable_purchase_orders(base_order)}
    selected_ids = set(participant_ids) | {base_order.id}
    if not selected_ids.issubset(candidates):
        raise ValueError("Solo se pueden comparar órdenes de compra del mismo origen y compañía.")

    comparison = PurchaseOrderComparison(
        company=base_order.company,
        base_purchase_order_id=base_order.id,
        status="draft",
        created_by=user_id,
    )
    database.session.add(comparison)
    database.session.flush()
    for order_id in sorted(selected_ids):
        database.session.add(
            PurchaseOrderComparisonOrder(
                comparison_id=comparison.id,
                purchase_order_id=order_id,
                is_base=order_id == base_order.id,
                created_by=user_id,
            )
        )
    database.session.flush()
    return comparison
