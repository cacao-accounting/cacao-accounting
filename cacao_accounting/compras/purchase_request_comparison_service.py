"""Servicios para comparar cotizaciones de proveedor desde una solicitud de compra."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_

from cacao_accounting.database import (
    DocumentRelation,
    PurchaseRequest,
    PurchaseRequestComparisonLine,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    PurchaseRequestItem,
    PurchaseOrder,
    PurchaseOrderItem,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)
from cacao_accounting.document_flow import create_document_relation, create_target_document
from cacao_accounting.document_flow.context import company_currency
from cacao_accounting.document_identifiers import assign_document_identifier


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
    return _request_item_key(item)


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
    """Persist a comparison with selected offers belonging to the request.

    A request may need several comparisons when offers arrive in batches or a
    previous offer set is rejected. Closed comparison lines determine whether
    the request can be closed; the comparison header is not unique per request.
    """
    if purchase_request.docstatus != 1:
        raise ValueError("Solo se pueden comparar Solicitudes de Compra aprobadas.")
    candidates = {quotation.id: quotation for quotation in supplier_quotations_for_request(purchase_request)}
    selected_ids = set(supplier_quotation_ids)
    if not selected_ids or not selected_ids.issubset(candidates):
        raise ValueError("Seleccione únicamente cotizaciones de proveedor asociadas a la Solicitud de Compra.")

    comparison = PurchaseRequestComparison(
        company=purchase_request.company,
        purchase_request_id=purchase_request.id,
        posting_date=purchase_request.posting_date,
        status="draft",
        created_by=user_id,
    )
    database.session.add(comparison)
    database.session.flush()
    assign_document_identifier(
        document=comparison,
        entity_type="purchase_request_comparison",
        posting_date_raw=comparison.posting_date,
        naming_series_id=None,
    )
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
    comparison = database.session.get(PurchaseRequestComparison, comparison_id)
    if comparison is None:
        return []
    offer_ids = database.select(PurchaseRequestComparisonOffer.supplier_quotation_id).where(
        PurchaseRequestComparisonOffer.comparison_id == comparison_id
    )
    return list(
        database.session.execute(
            database.select(SupplierQuotation)
            .where(
                SupplierQuotation.id.in_(offer_ids),
                SupplierQuotation.company == comparison.company,
                SupplierQuotation.docstatus == 1,
            )
            .order_by(SupplierQuotation.supplier_name, SupplierQuotation.document_no, SupplierQuotation.id)
        )
        .scalars()
        .all()
    )


def _request_item_key(item: PurchaseRequestItem) -> tuple[str | None, ...]:
    """Return the stable commercial identity for a purchase-request line."""
    return (
        item.item_code,
        item.uom,
        item.warehouse,
        item.description,
    )


def _line_coverage_qty(line_or_item: Any) -> Decimal:
    """Return a line quantity normalized to base UOM for coverage comparison."""
    if getattr(line_or_item, "qty_in_base_uom", None) is not None:
        return Decimal(str(line_or_item.qty_in_base_uom))
    return Decimal(str(getattr(line_or_item, "qty", 0) or 0))


def _request_item_offer_line(
    item: PurchaseRequestItem,
    occurrence: int,
    offer_items: Mapping[str, Sequence[SupplierQuotationItem]],
    offer_id: str,
) -> SupplierQuotationItem | None:
    """Return the supplier line matching a request item commercial identity."""
    key = _request_item_key(item)
    matching = [line for line in offer_items.get(offer_id, ()) if _request_item_key(line) == key]
    return matching[occurrence] if occurrence < len(matching) else None


def _comparison_line_base_rate(
    offer: SupplierQuotation,
    line: SupplierQuotationItem,
    company: str,
    comparison_date: Any,
) -> Decimal:
    """Resolve a supplier line rate in the company's base currency."""
    rate = Decimal(str(line.rate or 0))
    stored_base_rate = Decimal(str(line.base_rate or 0))
    if stored_base_rate > 0:
        return stored_base_rate.quantize(Decimal("0.0001"))

    base_currency = company_currency(company)
    transaction_currency = offer.transaction_currency or base_currency
    if not transaction_currency or not base_currency or transaction_currency == base_currency:
        return rate.quantize(Decimal("0.0001"))

    document_exchange_rate = Decimal(str(getattr(offer, "exchange_rate", 0) or 0))
    if document_exchange_rate > 0:
        return (rate * document_exchange_rate).quantize(Decimal("0.0001"))

    from cacao_accounting.contabilidad.posting import PostingError, _lookup_exchange_rate

    try:
        exchange_rate = _lookup_exchange_rate(
            transaction_currency,
            base_currency,
            offer.posting_date or comparison_date,
        )
    except PostingError as exc:
        raise ValueError(
            f"No existe tipo de cambio para comparar una oferta en {transaction_currency} contra {base_currency}."
        ) from exc
    return (rate * exchange_rate).quantize(Decimal("0.0001"))


def purchase_request_comparison_recommendations(
    purchase_request: PurchaseRequest,
    offers: Sequence[SupplierQuotation],
) -> list[dict[str, Any]]:
    """Build one lowest-price recommendation for every purchase-request line."""
    request_items = list(
        database.session.execute(
            database.select(PurchaseRequestItem)
            .where(PurchaseRequestItem.purchase_request_id == purchase_request.id)
            .order_by(PurchaseRequestItem.id)
        )
        .scalars()
        .all()
    )
    offer_items = {
        offer.id: list(
            database.session.execute(
                database.select(SupplierQuotationItem)
                .where(SupplierQuotationItem.supplier_quotation_id == offer.id)
                .order_by(SupplierQuotationItem.id)
            )
            .scalars()
            .all()
        )
        for offer in offers
    }
    occurrences: dict[tuple[str | None, ...], int] = {}
    rows: list[dict[str, Any]] = []
    for item in request_items:
        key = _request_item_key(item)
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        required_qty = _line_coverage_qty(item)
        candidates: list[dict[str, Any]] = []
        for offer in offers:
            line = _request_item_offer_line(item, occurrence, offer_items, offer.id)
            offered_qty = _line_coverage_qty(line) if line else Decimal("0")
            if line is None or offered_qty < required_qty:
                continue
            candidates.append(
                {
                    "offer": offer,
                    "line": line,
                    "rate": Decimal(str(line.rate or 0)),
                    "base_rate": _comparison_line_base_rate(
                        offer,
                        line,
                        purchase_request.company,
                        purchase_request.posting_date,
                    ),
                }
            )
        candidates.sort(
            key=lambda candidate: (
                candidate["base_rate"],
                candidate["rate"],
                candidate["offer"].document_no or "",
                candidate["offer"].id,
            )
        )
        rows.append(
            {
                "item": item,
                "candidates": candidates,
                "by_offer": {candidate["offer"].id: candidate for candidate in candidates},
                "recommended": candidates[0] if candidates else None,
            }
        )
    return rows


def comparison_recommendations(comparison: PurchaseRequestComparison) -> list[dict[str, Any]]:
    """Build recommendations using the persisted comparison participants."""
    purchase_request = database.session.get(PurchaseRequest, comparison.purchase_request_id)
    if not purchase_request:
        raise ValueError("La Solicitud de Compra del comparativo no existe.")
    offers = supplier_quotations_for_comparison(comparison.id)
    if not offers:
        raise ValueError("El comparativo no tiene Cotizaciones de Proveedor vigentes.")
    return purchase_request_comparison_recommendations(purchase_request, offers)


def save_purchase_request_comparison_draft(
    comparison: PurchaseRequestComparison,
    selections: Mapping[str, str | None],
    reasons: Mapping[str, str | None],
    user_id: str | None,
) -> list[PurchaseRequestComparisonLine]:
    """Save editable per-line selections without final authorization."""
    if comparison.status in {"finalized", "used"}:
        raise ValueError("El comparativo ya fue finalizado y no admite cambios.")
    rows = comparison_recommendations(comparison)
    database.session.query(PurchaseRequestComparisonLine).filter_by(comparison_id=comparison.id).delete(
        synchronize_session=False
    )
    saved_lines: list[PurchaseRequestComparisonLine] = []
    has_override = False
    for row in rows:
        item = row["item"]
        candidates = {candidate["offer"].id: candidate for candidate in row["candidates"]}
        selected_id = selections.get(item.id) or None
        selected = candidates.get(selected_id) if selected_id else None
        if selected_id and selected is None:
            raise ValueError(f"La oferta seleccionada no cubre la línea {item.item_code}.")
        recommended = row["recommended"]
        manual_override = bool(selected and (not recommended or selected["offer"].id != recommended["offer"].id))
        has_override = has_override or manual_override
        selected_line = selected["line"] if selected else None
        recommended_line = recommended["line"] if recommended else None
        reason = (reasons.get(item.id) or "").strip() or None
        saved_line = PurchaseRequestComparisonLine(
            comparison_id=comparison.id,
            purchase_request_item_id=item.id,
            recommended_supplier_quotation_id=recommended["offer"].id if recommended else None,
            recommended_supplier_quotation_item_id=recommended_line.id if recommended_line else None,
            selected_supplier_quotation_id=selected["offer"].id if selected else None,
            selected_supplier_quotation_item_id=selected_line.id if selected_line else None,
            qty=item.qty if selected else None,
            rate=selected["rate"] if selected else None,
            amount=(Decimal(str(item.qty or 0)) * selected["rate"]).quantize(Decimal("0.0001")) if selected else None,
            manual_override=manual_override,
            override_reason=reason,
            created_by=user_id,
        )
        database.session.add(saved_line)
        saved_lines.append(saved_line)
    comparison.status = "pending_authorization" if has_override else "draft"
    comparison.modified_by = user_id
    database.session.flush()
    return saved_lines


def finalize_purchase_request_comparison(
    comparison: PurchaseRequestComparison,
    user_id: str | None,
    is_authorizer: bool,
) -> None:
    """Authorize and finalize every selected request line."""
    if not is_authorizer:
        raise ValueError("Solo un Gerente de Compras o Administrador puede autorizar el comparativo.")
    if comparison.status == "used":
        raise ValueError("El comparativo ya fue utilizado para crear Órdenes de Compra.")
    rows = comparison_recommendations(comparison)
    saved = {
        line.purchase_request_item_id: line
        for line in database.session.execute(
            database.select(PurchaseRequestComparisonLine).where(PurchaseRequestComparisonLine.comparison_id == comparison.id)
        )
        .scalars()
        .all()
    }
    selected_line_count = 0
    for row in rows:
        item = row["item"]
        line = saved.get(item.id)
        if not line or not line.selected_supplier_quotation_id:
            continue
        if line.selected_supplier_quotation_id not in row["by_offer"]:
            raise ValueError(f"La oferta seleccionada para la línea {item.item_code} ya no está vigente.")
        if line.manual_override and not line.override_reason:
            raise ValueError(f"La línea {item.item_code} requiere justificar el cambio de recomendación.")
        line.authorized_by = user_id
        selected_line_count += 1
    if selected_line_count == 0:
        raise ValueError("Debe seleccionar al menos una oferta para cerrar el comparativo.")
    now = datetime.now(timezone.utc)
    comparison.status = "finalized"
    comparison.authorized_by = user_id
    comparison.authorized_at = now
    comparison.finalized_by = user_id
    comparison.finalized_at = now
    comparison.modified_by = user_id
    database.session.flush()


def purchase_request_comparison_is_closed(purchase_request: PurchaseRequest) -> bool:
    """Return whether closed comparisons cover every request line."""
    request_item_ids = set(
        database.session.execute(
            database.select(PurchaseRequestItem.id).where(PurchaseRequestItem.purchase_request_id == purchase_request.id)
        )
        .scalars()
        .all()
    )
    if not request_item_ids:
        return False
    covered_item_ids = set(
        database.session.execute(
            database.select(PurchaseRequestComparisonLine.purchase_request_item_id)
            .join(
                PurchaseRequestComparison,
                PurchaseRequestComparison.id == PurchaseRequestComparisonLine.comparison_id,
            )
            .where(
                PurchaseRequestComparison.purchase_request_id == purchase_request.id,
                PurchaseRequestComparison.status.in_(("finalized", "used")),
                PurchaseRequestComparisonLine.selected_supplier_quotation_id.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    return request_item_ids.issubset(covered_item_ids)


def create_purchase_orders_from_comparison(comparison: PurchaseRequestComparison) -> list[PurchaseOrder]:
    """Create one draft purchase order per supplier from a finalized comparison."""
    if comparison.status != "finalized":
        raise ValueError("El comparativo debe estar finalizado antes de crear Órdenes de Compra.")
    existing = list(
        database.session.execute(
            database.select(PurchaseOrder).where(PurchaseOrder.purchase_request_comparison_id == comparison.id)
        )
        .scalars()
        .all()
    )
    if existing:
        raise ValueError("El comparativo ya tiene Órdenes de Compra generadas.")
    purchase_request = database.session.get(PurchaseRequest, comparison.purchase_request_id)
    if not purchase_request:
        raise ValueError("La Solicitud de Compra del comparativo no existe.")
    lines = list(
        database.session.execute(
            database.select(PurchaseRequestComparisonLine)
            .where(
                PurchaseRequestComparisonLine.comparison_id == comparison.id,
                PurchaseRequestComparisonLine.selected_supplier_quotation_id.is_not(None),
            )
            .order_by(PurchaseRequestComparisonLine.id)
        )
        .scalars()
        .all()
    )
    grouped: dict[str, list[PurchaseRequestComparisonLine]] = {}
    quotations_by_group: dict[str, SupplierQuotation] = {}
    for line in lines:
        quotation = database.session.get(SupplierQuotation, line.selected_supplier_quotation_id)
        if not quotation:
            raise ValueError("Una cotización seleccionada ya no existe.")
        if quotation.company != comparison.company:
            raise ValueError("Una cotización seleccionada pertenece a otra compañía.")
        if quotation.docstatus != 1:
            raise ValueError("Una cotización seleccionada ya no está aprobada.")
        group_key = quotation.supplier_id or f"quotation:{quotation.id}"
        grouped.setdefault(group_key, []).append(line)
        quotations_by_group.setdefault(group_key, quotation)
    orders: list[PurchaseOrder] = []
    for group_key, selected_lines in grouped.items():
        quotation = quotations_by_group[group_key]
        flow_lines = []
        for selected in selected_lines:
            selected_quotation = database.session.get(SupplierQuotation, selected.selected_supplier_quotation_id)
            if not selected_quotation:
                raise ValueError("Una cotización seleccionada ya no existe.")
            if selected_quotation.company != comparison.company:
                raise ValueError("Una cotización seleccionada pertenece a otra compañía.")
            if selected_quotation.docstatus != 1:
                raise ValueError("Una cotización seleccionada ya no está aprobada.")
            if selected_quotation.transaction_currency != quotation.transaction_currency:
                raise ValueError("No se pueden combinar cotizaciones de un mismo proveedor con monedas distintas.")
            flow_lines.append(
                {
                    "source_document_type": "supplier_quotation",
                    "source_document_id": selected_quotation.id,
                    "source_row_id": selected.selected_supplier_quotation_item_id,
                    "qty": selected.qty,
                }
            )
        result = create_target_document(
            {
                "target_document_type": "purchase_order",
                "company": comparison.company,
                "posting_date": purchase_request.posting_date,
                "supplier_id": quotation.supplier_id,
                "supplier_name": quotation.supplier_name,
                "lines": flow_lines,
            },
            commit=False,
        )
        order = database.session.get(PurchaseOrder, result["target_id"])
        if not order:
            raise ValueError("No se pudo crear la Orden de Compra desde el framework documental.")
        from cacao_accounting.compras import _copy_logistics, _landed_cost_snapshot
        from cacao_accounting.logistics import ensure_compatible_logistics

        selected_quotations = [
            database.session.get(SupplierQuotation, selected.selected_supplier_quotation_id) for selected in selected_lines
        ]
        selected_quotations = [quotation for quotation in selected_quotations if quotation is not None]
        ensure_compatible_logistics(selected_quotations, terms_field="purchase_terms")
        selected_quotation = next((quotation for quotation in selected_quotations if quotation is not None), None)
        _copy_logistics(order, selected_quotation)
        order.landed_cost_estimates_json = _landed_cost_snapshot(source=selected_quotation)
        order.purchase_request_comparison_id = comparison.id
        order.transaction_currency = quotation.transaction_currency
        order.base_currency = company_currency(comparison.company)
        total_qty = Decimal("0")
        total = Decimal("0")
        for index, selected in enumerate(selected_lines):
            request_item = database.session.get(PurchaseRequestItem, selected.purchase_request_item_id)
            target_item_id = result["lines"][index]["target_item_id"]
            order_item = database.session.get(PurchaseOrderItem, target_item_id)
            if not request_item or not order_item:
                raise ValueError("Una línea seleccionada ya no existe.")
            order_item.item_name = request_item.item_name or order_item.item_name
            order_item.description = request_item.description or order_item.description
            order_item.qty_in_base_uom = request_item.qty_in_base_uom
            order_item.warehouse = request_item.warehouse
            order_item.rate = selected.rate
            order_item.amount = selected.amount
            create_document_relation(
                source_type="purchase_request",
                source_id=purchase_request.id,
                source_item_id=request_item.id,
                target_type="purchase_order",
                target_id=order.id,
                target_item_id=order_item.id,
                qty=selected.qty,
                uom=order_item.uom,
                rate=selected.rate,
                amount=selected.amount,
            )
            total_qty += Decimal(str(selected.qty or 0))
            total += Decimal(str(selected.amount or 0))
        order.total_qty = total_qty
        order.total = total
        order.net_total = total
        order.grand_total = total
        from cacao_accounting.compras import _purchase_exchange_rate

        exchange_rate = _purchase_exchange_rate(order.company, order.posting_date, order.transaction_currency)
        order.exchange_rate = exchange_rate
        order.base_total = (total * exchange_rate).quantize(Decimal("0.0001"))
        orders.append(order)
    comparison.status = "used"
    comparison.used_at = datetime.now(timezone.utc)
    comparison.modified_by = comparison.finalized_by
    database.session.flush()
    return orders
