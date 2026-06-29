# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Persistencia fiscal por documento y conversión a contexto contable."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.accounting_engine.common.context import TaxRuleContext
from cacao_accounting.database import DocumentTaxLine, DocumentTaxSummary, TaxRule, database
from cacao_accounting.document_flow.status import _


def persist_document_fiscal_snapshot(
    *,
    company: str,
    document_type: str,
    document_id: str,
    currency: str | None,
    tax_lines: Any,
    tax_summary: Any,
) -> None:
    """Reemplaza el snapshot fiscal persistido de un documento."""
    lines_payload = _normalize_lines_payload(tax_lines)
    summary_payload = _normalize_summary_payload(tax_summary)
    _delete_document_fiscal_snapshot(document_type=document_type, document_id=document_id)
    if not lines_payload and not summary_payload:
        return
    summary_row = _build_document_tax_summary(
        company=company,
        document_type=document_type,
        document_id=document_id,
        currency=currency,
        summary_payload=summary_payload,
    )
    database.session.add(summary_row)
    database.session.flush()
    _persist_document_tax_lines(company=company, summary_id=summary_row.id, lines_payload=lines_payload)


def build_tax_rule_contexts_from_snapshot(
    *,
    document_type: str,
    document_id: str,
    recognition_event: str,
) -> list[TaxRuleContext]:
    """Convierte líneas fiscales persistidas de un documento en reglas inmutables."""
    summary = _get_document_summary(document_type=document_type, document_id=document_id)
    if not summary:
        return []
    rows = _load_document_tax_lines(summary.id)
    return [
        _document_tax_context_from_row(document_type=document_type, recognition_event=recognition_event, row=row)
        for row in rows
    ]


def load_document_fiscal_lines(document_type: str, document_id: str) -> list[DocumentTaxLine]:
    """Obtiene líneas fiscales persistidas para pruebas o inspección."""
    summary = _get_document_summary(document_type=document_type, document_id=document_id)
    if not summary:
        return []
    return list(
        database.session.execute(
            select(DocumentTaxLine).filter_by(document_tax_summary_id=summary.id).order_by(DocumentTaxLine.line_index.asc())
        )
        .scalars()
        .all()
    )


def _get_document_summary(*, document_type: str, document_id: str) -> DocumentTaxSummary | None:
    return database.session.execute(
        select(DocumentTaxSummary).filter_by(document_type=document_type, document_id=document_id)
    ).scalar_one_or_none()


def _build_document_tax_summary(
    *,
    company: str,
    document_type: str,
    document_id: str,
    currency: str | None,
    summary_payload: dict[str, Any],
) -> DocumentTaxSummary:
    return DocumentTaxSummary(
        company=company,
        document_type=document_type,
        document_id=document_id,
        currency=currency,
        subtotal=_decimal_or_none(summary_payload.get("subtotal")),
        document_tax_total=_decimal_or_none(summary_payload.get("document_tax_total")),
        capitalizable_tax_total=_decimal_or_none(summary_payload.get("capitalizable_tax_total")),
        separate_tax_total=_decimal_or_none(summary_payload.get("separate_tax_total")),
        withholding_total=_decimal_or_none(summary_payload.get("withholding_total")),
        grand_total=_decimal_or_none(summary_payload.get("grand_total")),
        source_payload_json=json.dumps(summary_payload, ensure_ascii=False) if summary_payload else None,
    )


def _build_document_tax_line(
    *,
    company: str,
    summary_id: str,
    index: int,
    line_payload: dict[str, Any],
) -> DocumentTaxLine:
    return DocumentTaxLine(
        document_tax_summary_id=summary_id,
        line_index=index,
        rule_id=_document_tax_line_rule_id(line_payload),
        concept=_document_tax_line_concept(index, line_payload),
        tax_type=_document_tax_line_tax_type(line_payload),
        calculation_method=_document_tax_line_calculation_method(line_payload),
        base_amount=_decimal_or_none(line_payload.get("base_amount")),
        rate=_decimal_or_none(line_payload.get("rate")),
        amount=_decimal_or_none(line_payload.get("amount")) or Decimal("0"),
        accounting_treatment=_document_tax_line_accounting_treatment(line_payload),
        account_id=_clean_optional_id(line_payload.get("account_id")),
        affects_inventory=bool(line_payload.get("affects_inventory")),
        affects_document_total=bool(line_payload.get("affects_document_total", True)),
        included_in_price=bool(line_payload.get("included_in_price")),
        notes=str(line_payload.get("notes") or ""),
        allocation_method=_clean_optional_id(line_payload.get("allocation_method")),
        metadata_json=_document_tax_line_metadata_json(line_payload),
        rule_snapshot_json=_document_tax_line_snapshot_json(company=company, line_payload=line_payload),
        source_payload_json=json.dumps(line_payload, ensure_ascii=False),
    )


def _persist_document_tax_lines(*, company: str, summary_id: str, lines_payload: list[dict[str, Any]]) -> None:
    for index, line_payload in enumerate(lines_payload, start=1):
        database.session.add(
            _build_document_tax_line(
                company=company,
                summary_id=summary_id,
                index=index,
                line_payload=line_payload,
            )
        )


def _load_document_tax_lines(summary_id: str) -> list[DocumentTaxLine]:
    return list(
        database.session.execute(
            select(DocumentTaxLine).filter_by(document_tax_summary_id=summary_id).order_by(DocumentTaxLine.line_index.asc())
        )
        .scalars()
        .all()
    )


def _document_tax_context_from_row(
    *,
    document_type: str,
    recognition_event: str,
    row: DocumentTaxLine,
) -> TaxRuleContext:
    snapshot = _load_json_dict(row.rule_snapshot_json)
    rule_id = str(row.rule_id or snapshot.get("rule_id") or f"{document_type}-line-{row.line_index}")
    concept = str(row.concept or snapshot.get("concept") or f"line_{row.line_index}")
    return TaxRuleContext(
        rule_id=rule_id,
        name=str(snapshot.get("name") or concept),
        concept=concept,
        tax_type=str(row.tax_type or snapshot.get("tax_type") or "tax"),
        calculation_method="manual",
        rate=_to_decimal(row.rate),
        amount=_to_decimal(row.amount),
        base_mode=str(snapshot.get("base_mode") or "goods"),
        include_concepts=_as_list(snapshot.get("include_concepts")),
        exclude_concepts=_as_list(snapshot.get("exclude_concepts")),
        participates_in_next_base=bool(snapshot.get("participates_in_next_base", False)),
        order=int(snapshot.get("sequence") or snapshot.get("order") or row.line_index),
        accounting_treatment=str(row.accounting_treatment or snapshot.get("accounting_treatment") or "tax"),
        recognition_event=recognition_event,
        affects_inventory=bool(row.affects_inventory),
        affects_document_total=bool(row.affects_document_total),
        included_in_price=bool(row.included_in_price),
        allocation_method=row.allocation_method,
        account_id=row.account_id,
    )


def _document_tax_line_rule_id(line_payload: dict[str, Any]) -> str | None:
    return str(line_payload.get("source_rule_id") or line_payload.get("rule_id") or "").strip() or None


def _document_tax_line_concept(index: int, line_payload: dict[str, Any]) -> str:
    return str(line_payload.get("concept") or f"line_{index}")


def _document_tax_line_tax_type(line_payload: dict[str, Any]) -> str:
    return str(line_payload.get("type") or line_payload.get("tax_type") or "tax")


def _document_tax_line_calculation_method(line_payload: dict[str, Any]) -> str:
    return str(line_payload.get("calculation_method") or "manual")


def _document_tax_line_accounting_treatment(line_payload: dict[str, Any]) -> str:
    return str(line_payload.get("accounting_treatment") or "separate_tax_account")


def _document_tax_line_metadata_json(line_payload: dict[str, Any]) -> str | None:
    metadata_payload = line_payload.get("metadata")
    if not isinstance(metadata_payload, dict):
        return None
    return json.dumps(metadata_payload, ensure_ascii=False)


def _document_tax_line_snapshot_json(*, company: str, line_payload: dict[str, Any]) -> str:
    rule_id = _document_tax_line_rule_id(line_payload)
    return json.dumps(
        _resolve_rule_snapshot(company=company, rule_id=rule_id, line_payload=line_payload),
        ensure_ascii=False,
    )


def _delete_document_fiscal_snapshot(*, document_type: str, document_id: str) -> None:
    summary = _get_document_summary(document_type=document_type, document_id=document_id)
    if not summary:
        return
    for row in database.session.execute(select(DocumentTaxLine).filter_by(document_tax_summary_id=summary.id)).scalars():
        database.session.delete(row)
    database.session.delete(summary)
    database.session.flush()


def _resolve_rule_snapshot(*, company: str, rule_id: str | None, line_payload: dict[str, Any]) -> dict[str, Any]:
    payload_snapshot = line_payload.get("rule_snapshot")
    if isinstance(payload_snapshot, dict):
        return payload_snapshot
    tax_rule = _matching_tax_rule(company=company, rule_id=rule_id)
    if tax_rule:
        return _tax_rule_snapshot(tax_rule)
    return _line_payload_snapshot(rule_id=rule_id, line_payload=line_payload)


def _matching_tax_rule(*, company: str, rule_id: str | None) -> TaxRule | None:
    if not rule_id:
        return None
    tax_rule = database.session.get(TaxRule, rule_id)
    if tax_rule and (tax_rule.company is None or tax_rule.company == company):
        return tax_rule
    return None


def _tax_rule_snapshot(tax_rule: TaxRule) -> dict[str, Any]:
    return {
        "rule_id": tax_rule.id,
        "name": tax_rule.name,
        "concept": tax_rule.concept,
        "tax_type": tax_rule.tax_type,
        "calculation_method": tax_rule.calculation_method,
        "rate": str(tax_rule.rate or "0"),
        "amount": str(tax_rule.amount or "0"),
        "base_mode": tax_rule.base_mode,
        "include_concepts": _as_list(tax_rule.include_concepts),
        "exclude_concepts": _as_list(tax_rule.exclude_concepts),
        "sequence": int(tax_rule.sequence or 0),
        "accounting_treatment": tax_rule.accounting_treatment,
        "recognition_event": tax_rule.recognition_event,
        "affects_inventory": bool(tax_rule.affects_inventory),
        "affects_document_total": bool(tax_rule.affects_document_total),
        "included_in_price": bool(getattr(tax_rule, "included_in_price", False)),
        "participates_in_next_base": bool(tax_rule.participates_in_next_base),
        "allocation_method": tax_rule.allocation_method,
        "account_id": tax_rule.account_id,
    }


def _line_payload_snapshot(*, rule_id: str | None, line_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "name": line_payload.get("name") or line_payload.get("concept"),
        "concept": line_payload.get("concept"),
        "tax_type": line_payload.get("type") or line_payload.get("tax_type"),
        "calculation_method": line_payload.get("calculation_method"),
        "rate": str(line_payload.get("rate") or "0"),
        "amount": str(line_payload.get("amount") or "0"),
        "base_mode": line_payload.get("base_mode"),
        "include_concepts": _as_list(line_payload.get("include_concepts")),
        "exclude_concepts": _as_list(line_payload.get("exclude_concepts")),
        "sequence": line_payload.get("sequence"),
        "accounting_treatment": line_payload.get("accounting_treatment"),
        "recognition_event": line_payload.get("recognition_event"),
        "affects_inventory": bool(line_payload.get("affects_inventory")),
        "affects_document_total": bool(line_payload.get("affects_document_total", True)),
        "included_in_price": bool(line_payload.get("included_in_price")),
        "participates_in_next_base": bool(line_payload.get("participates_in_next_base")),
        "allocation_method": line_payload.get("allocation_method"),
        "account_id": _clean_optional_id(line_payload.get("account_id")),
    }


def _normalize_lines_payload(raw_payload: Any) -> list[dict[str, Any]]:
    if isinstance(raw_payload, str):
        text = raw_payload.strip()
        if not text:
            return []
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(_("tax_lines_payload inválido.")) from exc
    else:
        loaded = raw_payload
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def _normalize_summary_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, str):
        text = raw_payload.strip()
        if not text:
            return {}
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(_("tax_summary_payload inválido.")) from exc
    else:
        loaded = raw_payload
    return loaded if isinstance(loaded, dict) else {}


def _load_json_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None


def _clean_optional_id(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value if value not in (None, "") else "0"))
    except ArithmeticError:
        return Decimal("0")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
