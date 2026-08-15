"""Servicios para comparar órdenes de compra entre sí."""

from __future__ import annotations

from collections.abc import Sequence

from cacao_accounting.database import (
    DocumentRelation,
    PurchaseOrder,
    PurchaseOrderComparison,
    PurchaseOrderComparisonOrder,
    PurchaseOrderComparisonRound,
    PurchaseOrderComparisonRoundOrder,
    PurchaseRequest,
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


def purchase_orders_for_request(purchase_request: PurchaseRequest) -> list[PurchaseOrder]:
    """Return submitted purchase orders created from a purchase request."""
    order_ids = database.select(DocumentRelation.target_id).where(
        DocumentRelation.source_type == "purchase_request",
        DocumentRelation.source_id == purchase_request.id,
        DocumentRelation.target_type == "purchase_order",
        DocumentRelation.status == "active",
    )
    statement = database.select(PurchaseOrder).where(
        PurchaseOrder.id.in_(order_ids),
        PurchaseOrder.company == purchase_request.company,
        PurchaseOrder.docstatus == 1,
    )
    return list(
        database.session.execute(statement.order_by(PurchaseOrder.supplier_name, PurchaseOrder.document_no, PurchaseOrder.id))
        .scalars()
        .all()
    )


def create_purchase_order_comparison(
    purchase_request: PurchaseRequest,
    base_order: PurchaseOrder,
    participant_ids: Sequence[str],
    user_id: str | None,
) -> PurchaseOrderComparison:
    """Persist a comparison from a request with selected purchase-order offers."""
    candidates = {order.id: order for order in purchase_orders_for_request(purchase_request)}
    selected_ids = set(participant_ids) | {base_order.id}
    if not selected_ids.issubset(candidates):
        raise ValueError("Solo se pueden comparar órdenes de compra del mismo origen y compañía.")

    comparison = PurchaseOrderComparison(
        company=base_order.company,
        purchase_request_id=purchase_request.id,
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
    open_purchase_order_comparison_round(comparison, purchase_request, selected_ids, user_id)
    database.session.flush()
    return comparison


def current_purchase_order_comparison_round(comparison_id: str) -> PurchaseOrderComparisonRound | None:
    """Return the latest round for a purchase-order comparison."""
    return database.session.execute(
        database.select(PurchaseOrderComparisonRound)
        .where(PurchaseOrderComparisonRound.comparison_id == comparison_id)
        .order_by(PurchaseOrderComparisonRound.round_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def purchase_order_comparison_round_orders(round_id: str) -> list[PurchaseOrderComparisonRoundOrder]:
    """Return the immutable participant snapshot for a comparison round."""
    return list(
        database.session.execute(
            database.select(PurchaseOrderComparisonRoundOrder)
            .where(PurchaseOrderComparisonRoundOrder.round_id == round_id)
            .order_by(PurchaseOrderComparisonRoundOrder.is_base.desc(), PurchaseOrderComparisonRoundOrder.created)
        )
        .scalars()
        .all()
    )


def open_purchase_order_comparison_round(
    comparison: PurchaseOrderComparison,
    purchase_request: PurchaseRequest,
    participant_ids: Sequence[str],
    user_id: str | None,
) -> PurchaseOrderComparisonRound:
    """Close the current round and open a new explicit participant snapshot."""
    from cacao_accounting.audit_trail_service import log_create, log_update

    candidates = {order.id: order for order in purchase_orders_for_request(purchase_request)}
    selected_ids = set(participant_ids) | {comparison.base_purchase_order_id}
    if not selected_ids.issubset(candidates):
        raise ValueError("Solo se pueden comparar órdenes de compra del mismo origen y compañía.")

    latest = database.session.execute(
        database.select(PurchaseOrderComparisonRound)
        .where(PurchaseOrderComparisonRound.comparison_id == comparison.id)
        .order_by(PurchaseOrderComparisonRound.round_number.desc())
        .with_for_update()
        .limit(1)
    ).scalar_one_or_none()
    if latest and latest.status == "open":
        previous = {
            "id": latest.id,
            "document_type": "purchase_order_comparison_round",
            "document_no": f"Ronda {latest.round_number}",
            "company": comparison.company,
            "status": latest.status,
        }
        latest.status = "closed"
        log_update(
            {
                **previous,
                "status": latest.status,
            },
            before=previous,
            after={**previous, "status": latest.status},
        )
    round_record = PurchaseOrderComparisonRound(
        comparison_id=comparison.id,
        round_number=(latest.round_number + 1) if latest else 1,
        created_by=user_id,
    )
    database.session.add(round_record)
    database.session.flush()
    for order_id in sorted(selected_ids):
        database.session.add(
            PurchaseOrderComparisonRoundOrder(
                round_id=round_record.id,
                purchase_order_id=order_id,
                is_base=order_id == comparison.base_purchase_order_id,
                created_by=user_id,
            )
        )
    database.session.flush()
    log_create(
        {
            "id": round_record.id,
            "document_type": "purchase_order_comparison_round",
            "document_no": f"Ronda {round_record.round_number}",
            "company": comparison.company,
            "status": round_record.status,
        }
    )
    return round_record
