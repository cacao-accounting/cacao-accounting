"""Servicios para comparar cotizaciones de proveedor desde una solicitud de compra."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import or_

from cacao_accounting.database import (
    DocumentRelation,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    SupplierQuotation,
    database,
)


def purchase_quotation_ids_for_request(purchase_request: PurchaseRequest) -> set[str]:
    """Return active RFQ identifiers derived from a purchase request."""
    rows = database.session.execute(
        database.select(DocumentRelation.target_id).where(
            DocumentRelation.source_type == "purchase_request",
            DocumentRelation.source_id == purchase_request.id,
            DocumentRelation.target_type == "purchase_quotation",
            DocumentRelation.status == "active",
        )
    ).scalars()
    return set(rows)


def supplier_quotations_for_request(purchase_request: PurchaseRequest) -> list[SupplierQuotation]:
    """Return all submitted supplier quotations linked through the request RFQs."""
    rfq_ids = purchase_quotation_ids_for_request(purchase_request)
    if not rfq_ids:
        return []
    related_offer_ids = database.select(DocumentRelation.target_id).where(
        DocumentRelation.source_type == "purchase_quotation",
        DocumentRelation.source_id.in_(rfq_ids),
        DocumentRelation.target_type == "supplier_quotation",
        DocumentRelation.status == "active",
    )
    statement = database.select(SupplierQuotation).where(
        SupplierQuotation.company == purchase_request.company,
        SupplierQuotation.docstatus == 1,
        or_(SupplierQuotation.purchase_quotation_id.in_(rfq_ids), SupplierQuotation.id.in_(related_offer_ids)),
    )
    return list(
        database.session.execute(
            statement.order_by(SupplierQuotation.supplier_name, SupplierQuotation.document_no, SupplierQuotation.id)
        )
        .scalars()
        .all()
    )


def create_purchase_request_comparison(
    purchase_request: PurchaseRequest,
    supplier_quotation_ids: Sequence[str],
    user_id: str | None,
) -> PurchaseRequestComparison:
    """Persist a comparison with selected offers belonging to the request."""
    candidates = {quotation.id: quotation for quotation in supplier_quotations_for_request(purchase_request)}
    selected_ids = set(supplier_quotation_ids)
    if not selected_ids or not selected_ids.issubset(candidates):
        raise ValueError("Seleccione únicamente cotizaciones de proveedor asociadas a la Solicitud de Compra.")

    comparison = PurchaseRequestComparison(
        company=purchase_request.company,
        purchase_request_id=purchase_request.id,
        status="draft",
        created_by=user_id,
    )
    database.session.add(comparison)
    database.session.flush()
    for quotation_id in sorted(selected_ids):
        database.session.add(
            PurchaseRequestComparisonOffer(
                comparison_id=comparison.id,
                supplier_quotation_id=quotation_id,
                created_by=user_id,
            )
        )
    database.session.flush()
    return comparison


def supplier_quotations_for_comparison(comparison_id: str) -> list[SupplierQuotation]:
    """Return the persisted offers in comparison display order."""
    offer_ids = database.select(PurchaseRequestComparisonOffer.supplier_quotation_id).where(
        PurchaseRequestComparisonOffer.comparison_id == comparison_id
    )
    return list(
        database.session.execute(
            database.select(SupplierQuotation)
            .where(SupplierQuotation.id.in_(offer_ids))
            .order_by(SupplierQuotation.supplier_name, SupplierQuotation.document_no, SupplierQuotation.id)
        )
        .scalars()
        .all()
    )
