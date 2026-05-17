# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios para reglas fiscales configurables."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_, select

from cacao_accounting.accounting_engine.common.context import TaxRuleContext
from cacao_accounting.database import TaxRule, database


class TaxRuleServiceError(ValueError):
    """Error controlado en la gestion de reglas fiscales."""


def list_tax_rules(*, company: str | None = None, only_active: bool = False) -> list[TaxRule]:
    """Obtiene reglas fiscales ordenadas para administracion o carga."""
    query = select(TaxRule)
    if company:
        query = query.where(or_(TaxRule.company == company, TaxRule.company.is_(None)))
    if only_active:
        query = query.where(TaxRule.is_active.is_(True))
    query = query.order_by(TaxRule.company.is_(None), TaxRule.company, TaxRule.sequence, TaxRule.name)
    return list(database.session.execute(query).scalars().all())


def get_tax_rule(rule_id: str) -> TaxRule | None:
    """Obtiene una regla fiscal por id."""
    return database.session.get(TaxRule, rule_id)


def create_tax_rule(values: Mapping[str, str | None]) -> TaxRule:
    """Crea una regla fiscal desde datos de formulario."""
    rule = TaxRule()
    _apply_tax_rule_values(rule, values)
    database.session.add(rule)
    return rule


def update_tax_rule(rule: TaxRule, values: Mapping[str, str | None]) -> TaxRule:
    """Actualiza una regla fiscal existente."""
    _apply_tax_rule_values(rule, values)
    return rule


def delete_tax_rule(rule: TaxRule) -> None:
    """Elimina una regla fiscal."""
    database.session.delete(rule)


def build_tax_rule_contexts(
    *,
    company: str | None,
    applies_to: str,
    currency: str | None,
    at_date: date | None = None,
    recognition_event: str | None = None,
) -> list[TaxRuleContext]:
    """Convierte reglas persistidas en `TaxRuleContext` consumible por el motor."""
    query = select(TaxRule).where(TaxRule.is_active.is_(True))
    if company:
        query = query.where(or_(TaxRule.company == company, TaxRule.company.is_(None)))
    query = query.where(TaxRule.applies_to.in_((applies_to, "both")))
    if currency:
        query = query.where(or_(TaxRule.currency.is_(None), TaxRule.currency == currency))
    if recognition_event:
        query = query.where(TaxRule.recognition_event == recognition_event)
    if at_date:
        query = query.where(or_(TaxRule.valid_from.is_(None), TaxRule.valid_from <= at_date))
        query = query.where(or_(TaxRule.valid_to.is_(None), TaxRule.valid_to >= at_date))
    rules = database.session.execute(query.order_by(TaxRule.sequence, TaxRule.name)).scalars().all()
    return [_to_context(rule) for rule in rules]


def _apply_tax_rule_values(rule: TaxRule, values: Mapping[str, str | None]) -> None:
    """Aplica datos validados a una regla fiscal ORM."""
    name = (values.get("name") or "").strip()
    concept = (values.get("concept") or "").strip()
    if not name:
        raise TaxRuleServiceError("El nombre de la regla fiscal es obligatorio.")
    if not concept:
        raise TaxRuleServiceError("El concepto fiscal es obligatorio.")
    rule.company = _clean_text(values.get("company"))
    rule.name = name
    rule.applies_to = _clean_text(values.get("applies_to")) or "both"
    rule.level = _clean_text(values.get("level")) or "transaction"
    rule.concept = concept
    rule.tax_type = _clean_text(values.get("tax_type")) or "tax"
    rule.calculation_method = _clean_text(values.get("calculation_method")) or "percentage"
    rule.rate = _decimal_value(values.get("rate"), default="0")
    rule.amount = _decimal_value(values.get("amount"), default="0")
    rule.base_mode = _clean_text(values.get("base_mode")) or "goods"
    rule.include_concepts = _normalized_csv(values.get("include_concepts"))
    rule.exclude_concepts = _normalized_csv(values.get("exclude_concepts"))
    rule.sequence = _int_value(values.get("sequence"), default=10)
    rule.accounting_treatment = _clean_text(values.get("accounting_treatment")) or "separate_tax_account"
    rule.recognition_event = _clean_text(values.get("recognition_event")) or "invoice"
    rule.account_id = _clean_text(values.get("account_id"))
    rule.affects_inventory = values.get("affects_inventory") is not None
    rule.affects_cost = values.get("affects_cost") is not None
    rule.affects_document_total = values.get("affects_document_total") is not None
    rule.affects_settlement = values.get("affects_settlement") is not None
    rule.participates_in_next_base = values.get("participates_in_next_base") is not None
    rule.allocation_method = _clean_text(values.get("allocation_method"))
    rule.currency = _clean_text(values.get("currency"))
    rule.country = _clean_text(values.get("country"))
    rule.valid_from = _date_value(values.get("valid_from"))
    rule.valid_to = _date_value(values.get("valid_to"))
    rule.is_active = values.get("is_active") is not None


def _to_context(rule: TaxRule) -> TaxRuleContext:
    """Convierte una regla ORM a contexto puro."""
    return TaxRuleContext(
        rule_id=rule.id,
        name=rule.name,
        concept=rule.concept,
        tax_type=rule.tax_type,
        calculation_method=rule.calculation_method,
        rate=_decimal_value(rule.rate, default="0"),
        amount=_decimal_value(rule.amount, default="0"),
        base_mode=rule.base_mode,
        include_concepts=_csv_to_list(rule.include_concepts),
        exclude_concepts=_csv_to_list(rule.exclude_concepts),
        participates_in_next_base=bool(rule.participates_in_next_base),
        order=int(rule.sequence or 0),
        accounting_treatment=rule.accounting_treatment,
        recognition_event=rule.recognition_event,
        affects_inventory=bool(rule.affects_inventory or rule.affects_cost),
        affects_document_total=bool(rule.affects_document_total),
        level=rule.level,
        allocation_method=rule.allocation_method,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        allowed_currencies=[rule.currency] if rule.currency else [],
        country=rule.country,
        account_id=rule.account_id,
    )


def _clean_text(value: str | None) -> str | None:
    """Normaliza textos opcionales."""
    cleaned = (value or "").strip()
    return cleaned or None


def _normalized_csv(value: str | None) -> str | None:
    """Normaliza texto CSV para persistencia estable."""
    values = _csv_to_list(value)
    return ", ".join(values) if values else None


def _csv_to_list(value: str | None) -> list[str]:
    """Convierte un CSV tolerante a una lista limpia."""
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _int_value(value: str | None, *, default: int) -> int:
    """Convierte valores enteros de formulario."""
    try:
        return int(str(value).strip()) if value not in (None, "") else default
    except ValueError as exc:
        raise TaxRuleServiceError("La secuencia de la regla fiscal debe ser un entero.") from exc


def _decimal_value(value: object, *, default: str) -> Decimal:
    """Convierte valores decimales de formulario o BD."""
    if value in (None, ""):
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise TaxRuleServiceError("La tasa o monto de la regla fiscal es invalido.") from exc


def _date_value(value: str | None) -> date | None:
    """Convierte fechas ISO enviadas por el formulario."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise TaxRuleServiceError("La fecha de vigencia de la regla fiscal es invalida.") from exc
