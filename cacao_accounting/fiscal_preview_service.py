# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio unificado para matriz fiscal y preview de impuestos/cargos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.tax_rule_service import build_tax_rule_contexts

try:  # pragma: no cover - fallback para contextos sin Babel.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        """Fallback identity translation."""
        return value

else:

    def _(value: str) -> str:
        """Translate user-facing text when Babel is available."""
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):  # pragma: no cover
            return value


@dataclass(frozen=True)
class FiscalDocumentProfile:
    """Matriz de comportamiento fiscal por tipo documental."""

    document_type: str
    label: str
    applies_to: str
    recognition_event: str
    supports_taxes: bool
    supports_charges: bool
    supports_line_modal: bool
    required_fields: tuple[str, ...]


_FISCAL_MATRIX: dict[str, FiscalDocumentProfile] = {
    "purchase_request": FiscalDocumentProfile(
        document_type="purchase_request",
        label=_("Solicitud de compra"),
        applies_to="purchase",
        recognition_event="purchase_request_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date"),
    ),
    "purchase_order": FiscalDocumentProfile(
        document_type="purchase_order",
        label=_("Orden de compra"),
        applies_to="purchase",
        recognition_event="purchase_order_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "party_id"),
    ),
    "purchase_receipt": FiscalDocumentProfile(
        document_type="purchase_receipt",
        label=_("Recepción de compra"),
        applies_to="purchase",
        recognition_event="purchase_receipt_confirmed",
        supports_taxes=False,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "party_id"),
    ),
    "purchase_invoice": FiscalDocumentProfile(
        document_type="purchase_invoice",
        label=_("Factura de compra"),
        applies_to="purchase",
        recognition_event="purchase_invoice_confirmed",
        supports_taxes=True,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "party_id"),
    ),
    "import_landed_cost": FiscalDocumentProfile(
        document_type="import_landed_cost",
        label=_("Costo de importación"),
        applies_to="purchase",
        recognition_event="import_landed_cost_confirmed",
        supports_taxes=False,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "purchase_invoice_id"),
    ),
    "sales_request": FiscalDocumentProfile(
        document_type="sales_request",
        label=_("Solicitud de venta"),
        applies_to="sales",
        recognition_event="sales_request_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date"),
    ),
    "sales_order": FiscalDocumentProfile(
        document_type="sales_order",
        label=_("Orden de venta"),
        applies_to="sales",
        recognition_event="sales_order_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "party_id"),
    ),
    "delivery_note": FiscalDocumentProfile(
        document_type="delivery_note",
        label=_("Nota de entrega"),
        applies_to="sales",
        recognition_event="delivery_note_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "party_id"),
    ),
    "sales_invoice": FiscalDocumentProfile(
        document_type="sales_invoice",
        label=_("Factura de venta"),
        applies_to="sales",
        recognition_event="sales_invoice_confirmed",
        supports_taxes=True,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "party_id"),
    ),
    "stock_entry": FiscalDocumentProfile(
        document_type="stock_entry",
        label=_("Movimiento de inventario"),
        applies_to="purchase",
        recognition_event="stock_entry_confirmed",
        supports_taxes=False,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "purpose"),
    ),
    "payment_entry": FiscalDocumentProfile(
        document_type="payment_entry",
        label=_("Pago"),
        applies_to="purchase",
        recognition_event="payment_confirmed",
        supports_taxes=True,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "payment_type"),
    ),
    "collection_entry": FiscalDocumentProfile(
        document_type="payment_entry",
        label=_("Cobro"),
        applies_to="sales",
        recognition_event="collection_confirmed",
        supports_taxes=True,
        supports_charges=True,
        supports_line_modal=True,
        required_fields=("company", "posting_date", "payment_type"),
    ),
    "bank_debit_note": FiscalDocumentProfile(
        document_type="bank_debit_note",
        label=_("Nota de débito bancaria"),
        applies_to="purchase",
        recognition_event="payment_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date"),
    ),
    "bank_credit_note": FiscalDocumentProfile(
        document_type="bank_credit_note",
        label=_("Nota de crédito bancaria"),
        applies_to="sales",
        recognition_event="collection_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date"),
    ),
    "bank_transfer": FiscalDocumentProfile(
        document_type="bank_transfer",
        label=_("Transferencia interna"),
        applies_to="both",
        recognition_event="bank_transfer_confirmed",
        supports_taxes=False,
        supports_charges=False,
        supports_line_modal=True,
        required_fields=("company", "posting_date"),
    ),
}


def get_fiscal_document_profile(document_type: str, payment_type: str | None = None) -> FiscalDocumentProfile:
    """Resuelve la matriz fiscal para el tipo documental recibido."""
    normalized = (document_type or "").strip().lower()
    if normalized == "payment_entry":
        payment = (payment_type or "").strip().lower()
        if payment == "receive":
            return _FISCAL_MATRIX["collection_entry"]
        if payment == "debit_note":
            return _FISCAL_MATRIX["bank_debit_note"]
        if payment == "credit_note":
            return _FISCAL_MATRIX["bank_credit_note"]
        if payment == "internal_transfer":
            return _FISCAL_MATRIX["bank_transfer"]
    profile = _FISCAL_MATRIX.get(normalized)
    if not profile:
        raise ValueError(_("Tipo documental no soportado para preview fiscal."))
    return profile


def fiscal_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Calcula el preview fiscal unificado para los formularios MVP."""
    document_type = str(payload.get("document_type") or "").strip()
    payment_type = str(payload.get("payment_type") or "").strip()
    profile = get_fiscal_document_profile(document_type, payment_type)
    company = str(payload.get("company") or "").strip()
    if not company:
        raise ValueError(_("La compañía es obligatoria para calcular impuestos y cargos."))
    posting_date = _parse_date(payload.get("posting_date"))
    currency = str(payload.get("currency") or "").strip() or "NIO"
    company_currency = str(payload.get("company_currency") or currency).strip() or currency
    lines_payload_raw = payload.get("lines")
    lines_payload = (
        [line for line in lines_payload_raw if isinstance(line, dict)] if isinstance(lines_payload_raw, list) else []
    )
    item_contexts = _build_item_contexts(lines_payload)
    subtotal = sum((item.net_amount for item in item_contexts), Decimal("0"))

    tax_rules = _build_tax_rules(
        payload=payload,
        profile=profile,
        company=company,
        currency=currency,
        posting_date=posting_date,
    )
    if not profile.supports_taxes and not profile.supports_charges:
        tax_rules = []

    context = CalculationContext(
        company_id=company,
        document_type=profile.document_type,
        event_type=profile.recognition_event,
        transaction_direction=_direction_for_profile(profile),
        transaction_date=posting_date,
        posting_date=posting_date,
        party_type=_party_type_for_profile(profile, payload),
        party_id=str(payload.get("party_id") or ""),
        currency=currency,
        company_currency=company_currency,
        items=item_contexts,
        tax_rules=tax_rules,
        references=AccountingReferences(),
    )
    result = FiscalEngine().calculate(context)
    tax_lines = [
        {
            "line_id": line.line_id,
            "source_rule_id": line.source_rule_id,
            "manual": _is_manual_rule_id(line.source_rule_id),
            "concept": line.concept,
            "type": line.type,
            "calculation_method": line.calculation_method,
            "base_amount": str(line.base_amount),
            "rate": str(line.rate),
            "amount": str(line.amount),
            "accounting_treatment": line.accounting_treatment,
            "allocation_method": line.allocation_method or "",
            "affects_inventory": bool(line.affects_inventory),
            "affects_document_total": bool(line.affects_document_total),
            "included_in_price": bool(line.included_in_price),
            "account_id": _line_account_id(payload, line.source_rule_id, line.account_id),
            "notes": _line_note(payload, line.source_rule_id),
        }
        for line in result.tax_lines
    ]
    grand_total = subtotal + result.document_tax_total
    return {
        "profile": {
            "document_type": profile.document_type,
            "label": profile.label,
            "applies_to": profile.applies_to,
            "recognition_event": profile.recognition_event,
            "supports_taxes": profile.supports_taxes,
            "supports_charges": profile.supports_charges,
            "supports_line_modal": profile.supports_line_modal,
            "required_fields": list(profile.required_fields),
        },
        "summary": {
            "subtotal": str(subtotal),
            "document_tax_total": str(result.document_tax_total),
            "capitalizable_tax_total": str(result.capitalizable_tax_total),
            "separate_tax_total": str(result.separate_tax_total),
            "withholding_total": str(result.withholding_total),
            "grand_total": str(grand_total),
        },
        "tax_lines": tax_lines,
        "errors": result.errors,
        "warnings": result.warnings,
    }


def _build_item_contexts(lines_payload: list[dict[str, Any]]) -> list[ItemContext]:
    """Construye líneas de contexto para el motor fiscal."""
    if not lines_payload:
        return [
            ItemContext(
                line_id="LINE-001",
                item_id="GENERIC",
                description="Generic line",
                quantity=Decimal("1"),
                unit_price=Decimal("0"),
                gross_amount=Decimal("0"),
                net_amount=Decimal("0"),
                item_type="service",
            )
        ]
    items: list[ItemContext] = []
    for index, line in enumerate(lines_payload, start=1):
        qty = _decimal_value(line.get("qty"), default="1")
        rate = _decimal_value(line.get("rate"), default="0")
        amount = _decimal_value(line.get("amount"), default=str(qty * rate))
        items.append(
            ItemContext(
                line_id=str(line.get("uid") or f"LINE-{index:03}"),
                item_id=str(line.get("item_code") or f"ITEM-{index:03}"),
                description=str(line.get("item_name") or line.get("item_code") or f"Line {index}"),
                quantity=qty,
                unit_price=rate,
                gross_amount=amount,
                net_amount=amount,
                item_type="inventory",
                uom=str(line.get("uom") or "unit"),
            )
        )
    return items


def _build_tax_rules(
    *,
    payload: dict[str, Any],
    profile: FiscalDocumentProfile,
    company: str,
    currency: str,
    posting_date: date,
) -> list[TaxRuleContext]:
    """Resuelve reglas fiscales desde payload manual o matriz persistida."""
    persisted_rules = build_tax_rule_contexts(
        company=company,
        applies_to=profile.applies_to,
        currency=currency,
        at_date=posting_date,
        recognition_event=profile.recognition_event,
    )
    payload_lines = payload.get("tax_lines")
    if persisted_rules:
        manual_rules = _manual_tax_rules_from_payload(
            payload_lines,
            profile.recognition_event,
            start_order=max((rule.order for rule in persisted_rules), default=0) + 1,
        )
        return [*persisted_rules, *manual_rules]
    if isinstance(payload_lines, list) and payload_lines:
        return [
            _tax_rule_context_from_payload(item, profile.recognition_event, order=index)
            for index, item in enumerate(payload_lines, start=1)
        ]
    return []


def _manual_tax_rules_from_payload(payload_lines: Any, recognition_event: str, *, start_order: int) -> list[TaxRuleContext]:
    """Extrae líneas manuales sin duplicar reglas canónicas reenviadas por el cliente."""
    if not isinstance(payload_lines, list):
        return []
    manual_lines = [item for item in payload_lines if _is_manual_tax_line(item)]
    return [
        _tax_rule_context_from_payload(item, recognition_event, order=start_order + index)
        for index, item in enumerate(manual_lines)
    ]


def _tax_rule_context_from_payload(raw_line: Any, recognition_event: str, order: int) -> TaxRuleContext:
    """Convierte una línea JSON a `TaxRuleContext`."""
    item = raw_line if isinstance(raw_line, dict) else {}
    return TaxRuleContext(
        rule_id=str(item.get("source_rule_id") or item.get("rule_id") or f"MANUAL-{order:03}"),
        name=str(item.get("concept") or item.get("name") or f"rule_{order}"),
        concept=str(item.get("concept") or item.get("name") or f"rule_{order}"),
        tax_type=str(item.get("type") or item.get("tax_type") or "tax"),
        calculation_method=str(item.get("calculation_method") or "percentage"),
        rate=_decimal_value(item.get("rate"), default="0"),
        amount=_decimal_value(item.get("amount"), default="0"),
        base_mode=str(item.get("base_mode") or "goods"),
        include_concepts=_as_list(item.get("include_concepts")),
        exclude_concepts=_as_list(item.get("exclude_concepts")),
        order=order,
        accounting_treatment=str(item.get("accounting_treatment") or "separate_tax_account"),
        recognition_event=recognition_event,
        affects_inventory=bool(item.get("affects_inventory")),
        affects_document_total=bool(item.get("affects_document_total", True)),
        included_in_price=bool(item.get("included_in_price")),
        allocation_method=str(item.get("allocation_method") or "") or None,
        account_id=item.get("account_id"),
    )


def _is_manual_tax_line(raw_line: Any) -> bool:
    """Identifica líneas fiscales creadas manualmente por el usuario."""
    if not isinstance(raw_line, dict):
        return False
    return bool(raw_line.get("manual")) or _is_manual_rule_id(
        str(raw_line.get("source_rule_id") or raw_line.get("rule_id") or "")
    )


def _is_manual_rule_id(rule_id: str) -> bool:
    """Identifica reglas sintéticas del formulario transaccional."""
    return str(rule_id or "").startswith("MANUAL-")


def _line_note(payload: dict[str, Any], rule_id: str) -> str:
    """Devuelve nota de una línea fiscal previa si existe."""
    return str(_line_payload_value(payload, rule_id, "notes") or "")


def _line_account_id(payload: dict[str, Any], rule_id: str, default: str | None) -> str | None:
    """Conserva la cuenta editada en el preview previo si fue informada."""
    account_id = _line_payload_value(payload, rule_id, "account_id")
    return str(account_id).strip() if account_id else default


def _line_payload_value(payload: dict[str, Any], rule_id: str, key: str) -> Any:
    """Busca un valor de línea fiscal previa por regla fuente."""
    lines = payload.get("tax_lines")
    if not isinstance(lines, list):
        return None
    for line in lines:
        if not isinstance(line, dict):
            continue
        line_rule_id = str(line.get("source_rule_id") or line.get("rule_id") or "")
        if line_rule_id == rule_id:
            return line.get(key)
    return None


def _direction_for_profile(profile: FiscalDocumentProfile) -> str:
    """Mapea `applies_to` de la matriz al sentido transaccional del motor."""
    if profile.applies_to == "purchase":
        return "purchase"
    if profile.applies_to == "sales":
        return "sales"
    return "purchase"


def _party_type_for_profile(profile: FiscalDocumentProfile, payload: dict[str, Any]) -> str:
    """Resuelve tipo de tercero por perfil y payload."""
    payload_party_type = str(payload.get("party_type") or "").strip().lower()
    if payload_party_type in {"supplier", "customer"}:
        return payload_party_type
    if profile.applies_to == "purchase":
        return "supplier"
    return "customer"


def _parse_date(value: Any) -> date:
    """Convierte fecha ISO del payload o usa la fecha actual."""
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    return date.fromisoformat(text)


def _decimal_value(value: Any, *, default: str) -> Decimal:
    """Convierte valores numéricos de payload en Decimal."""
    raw = value if value not in (None, "") else default
    try:
        return Decimal(str(raw))
    except ArithmeticError:
        return Decimal(default)


def _as_list(value: Any) -> list[str]:
    """Normaliza listas flexibles recibidas por JSON."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]
