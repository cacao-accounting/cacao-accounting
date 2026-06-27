# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de impuestos, cargos y precios para documentos operativos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import ItemPrice, PriceList, Tax, TaxTemplate, TaxTemplateItem, database


class TaxPricingError(ValueError):
    """Error controlado de impuestos, cargos o precios."""


@dataclass(frozen=True)
class TaxLineResult:
    """Resultado calculado para una linea de impuesto o cargo."""

    tax_id: str
    name: str
    account_id: str | None
    amount: Decimal
    behavior: str
    is_inclusive: bool
    is_charge: bool
    is_capitalizable: bool


@dataclass(frozen=True)
class TaxCalculationResult:
    """Resultado completo de impuestos de un documento."""

    lines: list[TaxLineResult]
    additive_total: Decimal
    deductive_total: Decimal
    inclusive_total: Decimal
    payable_delta: Decimal


@dataclass(frozen=True)
class PriceSuggestion:
    """Precio sugerido para un item."""

    item_code: str
    price_list_id: str
    price: Decimal
    currency: str | None
    uom: str | None


@dataclass(frozen=True)
class PriceToleranceResult:
    """Resultado de validacion de tolerancia de precio."""

    allowed: bool
    suggested_price: Decimal | None
    variance_percentage: Decimal
    message: str | None = None


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _document_items_total(document: Any) -> Decimal:
    items = getattr(document, "_tax_items", None)
    if items is None:
        items = []
    total = sum((_decimal_value(getattr(item, "amount", None)) for item in items), Decimal("0"))
    if total == 0:
        total = _decimal_value(getattr(document, "total", None) or getattr(document, "grand_total", None))
    return total


def calculate_taxes(document: Any, template_id: str) -> TaxCalculationResult:
    """Calcula impuestos/cargos de un documento usando una plantilla."""
    template = database.session.get(TaxTemplate, template_id)
    if not template or not template.is_active:
        raise TaxPricingError("La plantilla de impuestos no existe o esta inactiva.")
    company = getattr(document, "company", None)
    if template.company and company and template.company != company:
        raise TaxPricingError("La plantilla de impuestos pertenece a otra compania.")

    base_amount = _document_items_total(document)
    if base_amount < 0:
        base_amount = abs(base_amount)
    running_total = base_amount
    lines: list[TaxLineResult] = []
    additive_total = Decimal("0")
    deductive_total = Decimal("0")
    inclusive_total = Decimal("0")

    items = (
        database.session.execute(
            select(TaxTemplateItem).filter_by(tax_template_id=template_id).order_by(TaxTemplateItem.sequence)
        )
        .scalars()
        .all()
    )
    for template_item in items:
        tax = database.session.get(Tax, template_item.tax_id)
        if not tax or not tax.is_active:
            continue
        calculation_base = template_item.calculation_base or "net_document"
        taxable_base = running_total if calculation_base == "previous_total" else base_amount
        rate = _decimal_value(tax.rate)
        amount = rate if tax.tax_type == "fixed" else (taxable_base * rate / Decimal("100"))
        amount = amount.quantize(Decimal("0.0001"))
        behavior = template_item.behavior or "additive"
        if template_item.is_inclusive:
            inclusive_total += amount
        elif behavior == "deductive":
            deductive_total += amount
            running_total -= amount
        else:
            additive_total += amount
            running_total += amount
        lines.append(
            TaxLineResult(
                tax_id=tax.id,
                name=tax.name,
                account_id=tax.account_id,
                amount=amount,
                behavior=behavior,
                is_inclusive=bool(template_item.is_inclusive),
                is_charge=bool(tax.is_charge),
                is_capitalizable=bool(tax.is_capitalizable),
            )
        )

    return TaxCalculationResult(
        lines=lines,
        additive_total=additive_total,
        deductive_total=deductive_total,
        inclusive_total=inclusive_total,
        payable_delta=additive_total - deductive_total,
    )


def get_item_price(
    item_code: str,
    price_list_id: str,
    qty: Decimal,
    uom: str | None,
    posting_date: date,
) -> PriceSuggestion:
    """Obtiene el precio vigente mas especifico de una lista de precios."""
    price_list = database.session.get(PriceList, price_list_id)
    if not price_list or not price_list.is_active:
        raise TaxPricingError("La lista de precios no existe o esta inactiva.")

    query = (
        select(ItemPrice)
        .filter_by(item_code=item_code, price_list_id=price_list_id)
        .where((ItemPrice.valid_from.is_(None)) | (ItemPrice.valid_from <= posting_date))
        .where((ItemPrice.valid_upto.is_(None)) | (ItemPrice.valid_upto >= posting_date))
        .where((ItemPrice.min_qty.is_(None)) | (ItemPrice.min_qty <= qty))
        .order_by(ItemPrice.min_qty.desc().nullslast(), ItemPrice.valid_from.desc().nullslast())
    )
    if uom:
        query = query.where((ItemPrice.uom.is_(None)) | (ItemPrice.uom == uom))
    price = database.session.execute(query).scalars().first()
    if not price:
        raise TaxPricingError("No existe precio vigente para el item en la lista indicada.")
    return PriceSuggestion(
        item_code=item_code,
        price_list_id=price_list_id,
        price=_decimal_value(price.price),
        currency=price_list.currency,
        uom=price.uom,
    )


def validate_price_tolerance(document_type: str, line: Any, user_id: str | None = None) -> PriceToleranceResult:
    """Valida tolerancia de precio con politica conservadora del 10%."""
    del user_id
    suggested = getattr(line, "suggested_rate", None)
    if suggested is None:
        return PriceToleranceResult(True, None, Decimal("0"), None)
    suggested_price = _decimal_value(suggested)
    actual = _decimal_value(getattr(line, "rate", None))
    if suggested_price <= 0:
        return PriceToleranceResult(True, suggested_price, Decimal("0"), None)
    variance = abs(actual - suggested_price) / suggested_price * Decimal("100")
    allowed = variance <= Decimal("10")
    message = None if allowed else f"El precio excede la tolerancia permitida para {document_type}."
    return PriceToleranceResult(allowed, suggested_price, variance, message)
