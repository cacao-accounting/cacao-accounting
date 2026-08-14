"""Reglas de comparación y adjudicación de ofertas de compra."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from collections.abc import Sequence
from logging import getLogger
from typing import cast

from cacao_accounting.database import (
    CacaoConfig,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseQuotationAwardItem,
    PurchaseNegotiationRound,
    PurchaseQuotationItem,
    Roles,
    RolesUser,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)

REQUIRE_COMPARISON_KEY = "PURCHASE_REQUIRE_OFFER_COMPARISON"
MINIMUM_OFFERS_KEY = "PURCHASE_MINIMUM_REQUIRED_OFFERS"
logger = getLogger(__name__)


class PurchaseSourcingError(ValueError):
    """Error de validación del abastecimiento competitivo."""


@dataclass(frozen=True)
class PurchaseSourcingConfig:
    """Configuración global para comparación y adjudicación."""

    require_comparison: bool = False
    minimum_offers: int = 2


def _config_value(key: str, default: str) -> str:
    """Read a global CacaoConfig value."""
    row = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    return row.value if row else default


def get_purchase_sourcing_config() -> PurchaseSourcingConfig:
    """Return validated global sourcing configuration."""
    raw_minimum = _config_value(MINIMUM_OFFERS_KEY, "2")
    try:
        minimum = max(1, int(raw_minimum))
    except (TypeError, ValueError):
        minimum = 2
    return PurchaseSourcingConfig(
        require_comparison=_config_value(REQUIRE_COMPARISON_KEY, "0") == "1",
        minimum_offers=minimum,
    )


def set_purchase_sourcing_config(require_comparison: bool, minimum_offers: int) -> None:
    """Persist global sourcing configuration."""
    if minimum_offers < 1:
        raise PurchaseSourcingError("El mínimo de ofertas debe ser mayor o igual a uno.")
    values = {
        REQUIRE_COMPARISON_KEY: "1" if require_comparison else "0",
        MINIMUM_OFFERS_KEY: str(minimum_offers),
    }
    for key, value in values.items():
        row = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
        if row:
            row.value = value
        else:
            database.session.add(CacaoConfig(key=key, value=value))


def is_purchase_manager(user_id: str | None) -> bool:
    """Return whether a user owns the exact Gerente de Compras role."""
    if not user_id:
        return False
    role_ids = database.select(Roles.id).where((Roles.name == "Gerente de Compras") | (Roles.note == "Gerente de Compras"))
    return (
        database.session.execute(
            database.select(RolesUser).where(RolesUser.user_id == user_id, RolesUser.role_id.in_(role_ids))
        ).scalar_one_or_none()
        is not None
    )


def current_negotiation_round(rfq_id: str) -> PurchaseNegotiationRound | None:
    """Return the latest negotiation round for an RFQ, if one exists."""
    return database.session.execute(
        database.select(PurchaseNegotiationRound)
        .where(PurchaseNegotiationRound.purchase_quotation_id == rfq_id)
        .order_by(PurchaseNegotiationRound.round_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def open_negotiation_round(rfq_id: str, user_id: str | None) -> PurchaseNegotiationRound:
    """Close the previous round and open the next negotiation round."""
    latest = current_negotiation_round(rfq_id)
    if database.session.execute(
        database.select(PurchaseQuotationAward.id).where(
            PurchaseQuotationAward.purchase_quotation_id == rfq_id,
            PurchaseQuotationAward.status.in_(("finalized", "used")),
        )
    ).scalar_one_or_none():
        raise PurchaseSourcingError("No se puede abrir una ronda después de finalizar el comparativo.")
    if latest:
        latest.status = "closed"
    round_record = PurchaseNegotiationRound(
        purchase_quotation_id=rfq_id,
        round_number=(latest.round_number + 1) if latest else 1,
        created_by=user_id,
    )
    database.session.add(round_record)
    database.session.flush()
    return round_record


def submitted_supplier_quotations(rfq_id: str) -> list[SupplierQuotation]:
    """Return submitted supplier quotations for an RFQ."""
    current_round = current_negotiation_round(rfq_id)
    statement = database.select(SupplierQuotation).where(
        SupplierQuotation.purchase_quotation_id == rfq_id, SupplierQuotation.docstatus == 1
    )
    if current_round:
        statement = statement.where(SupplierQuotation.negotiation_round_id == current_round.id)
    return list(
        database.session.execute(statement.order_by(SupplierQuotation.supplier_name, SupplierQuotation.document_no))
        .scalars()
        .all()
    )


def _offer_lines(quotation_id: str, item_code: str) -> list[SupplierQuotationItem]:
    """Return matching submitted offer lines."""
    return list(
        database.session.execute(
            database.select(SupplierQuotationItem)
            .where(
                SupplierQuotationItem.supplier_quotation_id == quotation_id,
                SupplierQuotationItem.item_code == item_code,
            )
            .order_by(SupplierQuotationItem.id)
        )
        .scalars()
        .all()
    )


def offer_line_for_item(
    quotation_id: str, item: PurchaseQuotationItem, rfq_items: Sequence[PurchaseQuotationItem]
) -> SupplierQuotationItem | None:
    """Match an offer line to the corresponding RFQ line occurrence."""
    matching_items = [row for row in rfq_items if row.item_code == item.item_code]
    occurrence = next((index for index, row in enumerate(matching_items) if row.id == item.id), -1)
    lines = _offer_lines(quotation_id, item.item_code)
    if occurrence >= len(lines):
        logger.warning(
            "Supplier quotation %s has fewer lines for item %s than RFQ %s expects",
            quotation_id,
            item.item_code,
            item.purchase_quotation_id,
        )
    return lines[occurrence] if 0 <= occurrence < len(lines) else None


def validate_award_request(
    rfq: PurchaseQuotation,
    selections: dict[str, str],
    user_id: str | None,
    reason: str | None,
) -> tuple[list[PurchaseQuotationItem], list[SupplierQuotation], set[str]]:
    """Validate coverage, minimum offers and manual exceptions."""
    offers = submitted_supplier_quotations(rfq.id)
    config = get_purchase_sourcing_config()
    _validate_award_authorization(offers, config.minimum_offers, user_id, reason)
    items = list(
        database.session.execute(
            database.select(PurchaseQuotationItem)
            .where(PurchaseQuotationItem.purchase_quotation_id == rfq.id)
            .order_by(PurchaseQuotationItem.id)
        )
        .scalars()
        .all()
    )
    if not selections:
        raise PurchaseSourcingError("Debe adjudicar al menos una línea.")
    manual_override_items = _find_manual_override_items(items, offers, selections)
    if manual_override_items and (not is_purchase_manager(user_id) or not reason):
        raise PurchaseSourcingError("Seleccionar una oferta no recomendada requiere autorización y justificación.")
    return cast(list[PurchaseQuotationItem], items), offers, manual_override_items


def _validate_award_authorization(
    offers: Sequence[SupplierQuotation], minimum_offers: int, user_id: str | None, reason: str | None
) -> None:
    """Validate offer count and authorization for sourcing exceptions."""
    insufficient = len(offers) < minimum_offers
    manager = is_purchase_manager(user_id)
    if insufficient and not manager:
        raise PurchaseSourcingError(f"Se requieren al menos {minimum_offers} ofertas; solo existen {len(offers)}.")
    if insufficient and not reason:
        raise PurchaseSourcingError("La autorización de oferta única requiere una justificación.")
    if reason and not manager:
        raise PurchaseSourcingError("Solo el Gerente de Compras puede autorizar excepciones.")


def _find_manual_override_items(
    items: Sequence[PurchaseQuotationItem], offers: Sequence[SupplierQuotation], selections: dict[str, str]
) -> set[str]:
    """Return selected items whose rate is above the best comparable offer."""
    rfq_items = cast(list[PurchaseQuotationItem], items)
    overrides: set[str] = set()
    for item in items:
        quotation_id = selections.get(item.id)
        if not quotation_id:
            continue
        quotation = next((offer for offer in offers if offer.id == quotation_id), None)
        selected_line = offer_line_for_item(quotation.id, item, rfq_items) if quotation else None
        if not quotation or not selected_line:
            raise PurchaseSourcingError(f"La oferta seleccionada no cubre el artículo {item.item_code}.")
        rates = [line.rate or Decimal("0") for offer in offers if (line := offer_line_for_item(offer.id, item, rfq_items))]
        if rates and (selected_line.rate or Decimal("0")) > min(rates):
            overrides.add(item.id)
    return overrides


def create_purchase_quotation_award(
    rfq: PurchaseQuotation,
    selections: dict[str, str],
    user_id: str | None,
    reason: str | None = None,
) -> PurchaseQuotationAward:
    """Create an editable line-level award from submitted supplier offers."""
    existing = database.session.execute(
        database.select(PurchaseQuotationAward)
        .filter_by(purchase_quotation_id=rfq.id)
        .where(PurchaseQuotationAward.status.in_(("finalized", "used")))
    ).scalar_one_or_none()
    if existing:
        raise PurchaseSourcingError("La solicitud de cotización ya tiene un comparativo finalizado.")
    items, _offers, manual_override_items = validate_award_request(rfq, selections, user_id, reason)
    negotiation_round = current_negotiation_round(rfq.id)
    award = PurchaseQuotationAward(
        purchase_quotation_id=rfq.id,
        company=rfq.company or "",
        negotiation_round_id=negotiation_round.id if negotiation_round else None,
        created_by=user_id,
        authorized_by=user_id if reason else None,
        authorization_reason=reason,
    )
    database.session.add(award)
    database.session.flush()
    for item in items:
        quotation_id = selections.get(item.id)
        if not quotation_id:
            continue
        offer_line = offer_line_for_item(quotation_id, item, items)
        if not offer_line:
            raise PurchaseSourcingError(f"La oferta seleccionada no cubre el artículo {item.item_code}.")
        qty = min(Decimal(str(item.qty)), Decimal(str(offer_line.qty)))
        database.session.add(
            PurchaseQuotationAwardItem(
                award_id=award.id,
                purchase_quotation_item_id=item.id,
                supplier_quotation_id=quotation_id,
                supplier_quotation_item_id=offer_line.id,
                item_code=item.item_code,
                qty=qty,
                rate=offer_line.rate or Decimal("0"),
                amount=(qty * (offer_line.rate or Decimal("0"))).quantize(Decimal("0.0001")),
                manual_override=item.id in manual_override_items,
                override_reason=reason if item.id in manual_override_items else None,
            )
        )
    if negotiation_round:
        negotiation_round.status = "closed"
    return award
