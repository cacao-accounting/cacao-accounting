"""Servicios para comparar cotizaciones de proveedor desde una solicitud de compra."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import or_

from cacao_accounting.database import (
    DocumentRelation,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    SupplierQuotation,
    SupplierQuotationItem,
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
    """Return submitted supplier quotations linked directly or through request RFQs."""
    direct_offer_ids = database.select(DocumentRelation.target_id).where(
        DocumentRelation.source_type == "purchase_request",
        DocumentRelation.source_id == purchase_request.id,
        DocumentRelation.target_type == "supplier_quotation",
        DocumentRelation.status == "active",
    )
    rfq_ids = purchase_quotation_ids_for_request(purchase_request)
    if not rfq_ids and not database.session.execute(direct_offer_ids.limit(1)).scalar_one_or_none():
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
        or_(
            SupplierQuotation.id.in_(direct_offer_ids),
            SupplierQuotation.purchase_quotation_id.in_(rfq_ids),
            SupplierQuotation.id.in_(related_offer_ids),
        ),
    )
    return list(
        database.session.execute(
            statement.order_by(SupplierQuotation.supplier_name, SupplierQuotation.document_no, SupplierQuotation.id)
        )
        .scalars()
        .all()
    )


def supplier_quotation_comparison_rows(
    offers: Sequence[SupplierQuotation],
    offer_items: Mapping[str, Sequence[SupplierQuotationItem]],
) -> list[dict[str, object]]:
    """Build comparison rows from the union of all participating offer lines."""
    rows: list[dict[str, object]] = []
    seen_keys: set[tuple[tuple[str | None, ...], int]] = set()
    occurrences_by_offer: dict[str, dict[tuple[str | None, ...], int]] = {}

    for offer in offers:
        occurrences = occurrences_by_offer.setdefault(offer.id, {})
        for item in offer_items.get(offer.id, []):
            key = _supplier_quotation_item_key(item)
            occurrence = occurrences.get(key, 0)
            occurrences[key] = occurrence + 1
            row_key = (key, occurrence)
            if row_key not in seen_keys:
                seen_keys.add(row_key)
                rows.append(
                    {
                        "item": item,
                        "item_key": key,
                        "occurrence": occurrence,
                        "offers": {
                            participant.id: _supplier_quotation_item_at_occurrence(
                                offer_items.get(participant.id, ()), key, occurrence
                            )
                            for participant in offers
                        },
                    }
                )

    return rows


def _supplier_quotation_item_key(item: SupplierQuotationItem) -> tuple[str | None, ...]:
    """Return the stable commercial identity for a supplier quotation line."""
    return (
        item.item_code,
        item.uom,
        str(item.qty_in_base_uom) if item.qty_in_base_uom is not None else None,
        item.warehouse,
        item.description,
    )


def _supplier_quotation_item_at_occurrence(
    items: Sequence[SupplierQuotationItem], key: tuple[str | None, ...], occurrence: int
) -> SupplierQuotationItem | None:
    """Return the line matching a commercial identity and occurrence."""
    matching_items = [item for item in items if _supplier_quotation_item_key(item) == key]
    return matching_items[occurrence] if occurrence < len(matching_items) else None


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
