# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Reglas de comparación y adjudicación de ofertas de compra."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from collections.abc import Sequence
from logging import getLogger
from typing import cast

from sqlalchemy.exc import IntegrityError

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
    User,
    database,
)

from cacao_accounting.compras.purchase_request_comparison_service import comparison_line_base_rate
from cacao_accounting.i18n import _

REQUIRE_COMPARISON_KEY = "PURCHASE_REQUIRE_OFFER_COMPARISON"
MINIMUM_OFFERS_KEY = "PURCHASE_MINIMUM_REQUIRED_OFFERS"
TERMINAL_AWARD_STATUSES = ("finalized", "used", "closed")
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
        raise PurchaseSourcingError(_("El mínimo de ofertas debe ser mayor o igual a uno."))
    values = {
        REQUIRE_COMPARISON_KEY: "1" if require_comparison else "0",
        MINIMUM_OFFERS_KEY: str(minimum_offers),
    }
    from cacao_accounting.config_values import set_config_value

    for key, value in values.items():
        set_config_value(key, value)


def is_purchase_manager(user_id: str | None) -> bool:
    """Return whether a user owns the exact Gerente de Compras role."""
    if not user_id:
        return False
    role_ids = database.select(Roles.id).where((Roles.name == "Gerente de Compras") | (Roles.note == "Gerente de Compras"))
    return (
        database.session.execute(
            database.select(RolesUser).where(
                RolesUser.user_id == user_id,
                RolesUser.role_id.in_(role_ids),
                RolesUser.active.is_(True),
            )
        ).scalar_one_or_none()
        is not None
    )


def is_purchase_sourcing_authorizer(user_id: str | None) -> bool:
    """Return whether a user may authorize sourcing exceptions."""
    if not user_id:
        return False
    user = database.session.get(User, user_id)
    return bool(user and user.classification == "admin") or is_purchase_manager(user_id)


def current_negotiation_round(rfq_id: str) -> PurchaseNegotiationRound | None:
    """Return the latest negotiation round for an RFQ, if one exists."""
    return database.session.execute(
        database.select(PurchaseNegotiationRound)
        .where(PurchaseNegotiationRound.purchase_quotation_id == rfq_id)
        .order_by(PurchaseNegotiationRound.round_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def _terminal_award(rfq_id: str) -> PurchaseQuotationAward | None:
    """Return an existing award that prevents further sourcing changes."""
    return database.session.execute(
        database.select(PurchaseQuotationAward)
        .where(
            PurchaseQuotationAward.purchase_quotation_id == rfq_id,
            PurchaseQuotationAward.status.in_(TERMINAL_AWARD_STATUSES),
        )
        .order_by(PurchaseQuotationAward.created.desc())
        .limit(1)
    ).scalar_one_or_none()


def _raise_if_terminal_award(award: PurchaseQuotationAward | None) -> None:
    """Reject operations after a manual close or finalized award."""
    if award is None:
        return
    if award.status == "closed":
        raise PurchaseSourcingError(_("La solicitud de cotización ya tiene el comparativo cerrado."))
    raise PurchaseSourcingError(_("La solicitud de cotización ya tiene un comparativo finalizado."))


def _is_award_unique_conflict(exc: IntegrityError) -> bool:
    """Recognize only the database guard that permits one award per RFQ."""
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_purchase_quotation_award_quotation":
        return True
    message = str(exc.orig).lower()
    return "uq_purchase_quotation_award_quotation" in message or (
        "unique constraint failed: purchase_quotation_award.purchase_quotation_id" in message
    )


def _flush_award(award: PurchaseQuotationAward) -> None:
    """Persist the award inside a savepoint and translate its unique race."""
    # Flush caller work before the savepoint so only this award insert is caught.
    database.session.flush()
    try:
        with database.session.begin_nested():
            database.session.add(award)
            database.session.flush()
    except IntegrityError as exc:
        if not _is_award_unique_conflict(exc):
            raise
        raise PurchaseSourcingError(_("El comparativo ya tiene una adjudicación o cierre registrado.")) from exc


def open_negotiation_round(rfq_id: str, user_id: str | None) -> PurchaseNegotiationRound:
    """Close the previous round and open the next negotiation round."""
    from cacao_accounting.default_scope import lock_default_scope

    lock_default_scope("purchase_quotation_award", rfq_id)
    _raise_if_terminal_award(_terminal_award(rfq_id))
    latest = current_negotiation_round(rfq_id)
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


def _normalize_authorization_reason(reason: str | None) -> str | None:
    """Return the justification without surrounding whitespace, or None when blank."""
    normalized = reason.strip() if reason else ""
    return normalized or None


def validate_award_request(
    rfq: PurchaseQuotation,
    selections: dict[str, str],
    user_id: str | None,
    reason: str | None,
) -> tuple[list[PurchaseQuotationItem], list[SupplierQuotation], set[str]]:
    """Validate coverage, minimum offers and manual exceptions."""
    reason = _normalize_authorization_reason(reason)
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
        raise PurchaseSourcingError(_("Debe adjudicar al menos una línea."))
    manual_override_items = _find_manual_override_items(rfq, items, offers, selections)
    if manual_override_items and (not is_purchase_sourcing_authorizer(user_id) or not reason):
        raise PurchaseSourcingError(_("Seleccionar una oferta no recomendada requiere autorización y justificación."))
    return cast(list[PurchaseQuotationItem], items), offers, manual_override_items


def _validate_award_authorization(
    offers: Sequence[SupplierQuotation], minimum_offers: int, user_id: str | None, reason: str | None
) -> None:
    """Validate offer count and authorization for sourcing exceptions."""
    normalized_reason = _normalize_authorization_reason(reason)
    insufficient = len(offers) < minimum_offers
    authorizer = is_purchase_sourcing_authorizer(user_id)
    if insufficient and not authorizer:
        raise PurchaseSourcingError(
            _("Se requieren al menos %(minimum_offers)s ofertas; solo existen %(offer_count)s.")
            % {"minimum_offers": minimum_offers, "offer_count": len(offers)}
        )
    if insufficient and not normalized_reason:
        raise PurchaseSourcingError(_("La autorización de oferta única requiere una justificación."))
    if normalized_reason and not authorizer:
        raise PurchaseSourcingError(_("Solo un Administrador o el Gerente de Compras puede autorizar excepciones."))


def _find_manual_override_items(
    rfq: PurchaseQuotation,
    items: Sequence[PurchaseQuotationItem],
    offers: Sequence[SupplierQuotation],
    selections: dict[str, str],
) -> set[str]:
    """Return selected items whose base rate is above the best comparable offer."""
    rfq_items = cast(list[PurchaseQuotationItem], items)
    overrides: set[str] = set()
    for item in items:
        quotation_id = selections.get(item.id)
        if not quotation_id:
            continue
        quotation = next((offer for offer in offers if offer.id == quotation_id), None)
        selected_line = offer_line_for_item(quotation.id, item, rfq_items) if quotation else None
        if not quotation or not selected_line:
            raise PurchaseSourcingError(
                _("La oferta seleccionada no cubre el artículo %(item_code)s.") % {"item_code": item.item_code}
            )
        rates = [
            _award_comparable_rate(rfq, offer, line)
            for offer in offers
            if (line := offer_line_for_item(offer.id, item, rfq_items))
        ]
        if rates and _award_comparable_rate(rfq, quotation, selected_line) > min(rates):
            overrides.add(item.id)
    return overrides


def _award_comparable_rate(rfq: PurchaseQuotation, offer: SupplierQuotation, line: SupplierQuotationItem) -> Decimal:
    """Normaliza la tarifa de la oferta a la moneda base de la compañía."""
    try:
        return comparison_line_base_rate(offer, line, rfq.company or "", rfq.posting_date)
    except ValueError as exc:
        raise PurchaseSourcingError(str(exc)) from exc


def create_purchase_quotation_award(
    rfq: PurchaseQuotation,
    selections: dict[str, str],
    user_id: str | None,
    reason: str | None = None,
) -> PurchaseQuotationAward:
    """Create an editable line-level award from submitted supplier offers."""
    from cacao_accounting.default_scope import lock_default_scope

    reason = _normalize_authorization_reason(reason)
    lock_default_scope("purchase_quotation_award", rfq.id)
    _raise_if_terminal_award(_terminal_award(rfq.id))
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
    _flush_award(award)
    for item in items:
        quotation_id = selections.get(item.id)
        if not quotation_id:
            continue
        offer_line = offer_line_for_item(quotation_id, item, items)
        if not offer_line:
            raise PurchaseSourcingError(
                _("La oferta seleccionada no cubre el artículo %(item_code)s.") % {"item_code": item.item_code}
            )
        qty = _award_qty_in_supplier_uom(item, offer_line)
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


def _award_qty_in_supplier_uom(rfq_item: PurchaseQuotationItem, offer_line: SupplierQuotationItem) -> Decimal:
    """Cap the award to requested base quantity and express it in offer UOM."""
    requested_base_qty = _positive_base_quantity(rfq_item)
    offered_qty = Decimal(str(offer_line.qty or 0))
    offered_base_qty = _positive_base_quantity(offer_line)
    if not offered_qty.is_finite() or offered_qty <= 0:
        raise PurchaseSourcingError(_("La oferta seleccionada no tiene cantidad válida."))
    awarded_base_qty = min(requested_base_qty, offered_base_qty)
    awarded_qty = (awarded_base_qty * offered_qty / offered_base_qty).quantize(Decimal("0.000000001"), rounding=ROUND_DOWN)
    if awarded_qty <= 0:
        raise PurchaseSourcingError(_("La oferta seleccionada no permite una cantidad adjudicable."))
    return awarded_qty


def _positive_base_quantity(line: PurchaseQuotationItem | SupplierQuotationItem) -> Decimal:
    """Require the base quantity snapshot saved with the submitted line."""
    base_qty = Decimal(str(line.qty_in_base_uom or 0))
    if not base_qty.is_finite() or base_qty <= 0:
        raise PurchaseSourcingError(_("La línea de oferta adjudicada no conserva una cantidad base válida."))
    return base_qty


def close_purchase_quotation_comparison(
    rfq: PurchaseQuotation, user_id: str | None, reason: str | None
) -> PurchaseQuotationAward:
    """Close an RFQ comparison manually with an authorized explanation."""
    if not is_purchase_sourcing_authorizer(user_id):
        raise PurchaseSourcingError(_("Solo un Administrador o el Gerente de Compras puede cerrar el comparativo."))
    if not reason or not reason.strip():
        raise PurchaseSourcingError(_("El cierre manual del comparativo requiere una justificación."))
    from cacao_accounting.default_scope import lock_default_scope

    lock_default_scope("purchase_quotation_award", rfq.id)
    _raise_if_terminal_award(_terminal_award(rfq.id))
    negotiation_round = current_negotiation_round(rfq.id)
    award = PurchaseQuotationAward(
        purchase_quotation_id=rfq.id,
        negotiation_round_id=negotiation_round.id if negotiation_round else None,
        company=rfq.company or "",
        status="closed",
        created_by=user_id,
        authorized_by=user_id,
        authorization_reason=reason.strip(),
    )
    _flush_award(award)
    if negotiation_round:
        negotiation_round.status = "closed"
    return award
