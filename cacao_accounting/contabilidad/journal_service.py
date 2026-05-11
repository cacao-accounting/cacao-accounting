# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio de comprobantes contables manuales."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from cacao_accounting.contabilidad.journal_repository import (
    add_journal,
    get_journal,
    list_journal_lines,
    replace_journal_lines,
)
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, post_comprobante_contable
from cacao_accounting.database import Accounts, ComprobanteContable, ComprobanteContableDetalle, CostCenter, database
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier

JOURNAL_ENTITY_TYPE = "journal_entry"
JOURNAL_TRANSACTION_TYPE = "journal_entry"
JOURNAL_STATUS_DRAFT = "draft"
JOURNAL_STATUS_REJECTED = "rejected"
JOURNAL_STATUS_SUBMITTED = "submitted"
JOURNAL_STATUS_CANCELLED = "cancelled"
JOURNAL_DUPLICABLE_STATUSES = {JOURNAL_STATUS_DRAFT, JOURNAL_STATUS_REJECTED, JOURNAL_STATUS_SUBMITTED}


class JournalValidationError(ValueError):
    """Error validado en la captura de comprobantes manuales."""


@dataclass(frozen=True)
class JournalLineInput:
    """Linea normalizada de comprobante contable manual."""

    order: int
    account: str
    cost_center: str | None
    party_type: str | None
    party: str | None
    debit: Decimal
    credit: Decimal
    unit: str | None
    project: str | None
    currency: str | None
    exchange_rate: Decimal | None
    reference_type: str | None
    reference_name: str | None
    reference1: str | None
    reference2: str | None
    remarks: str | None
    is_advance: bool
    bank_account_id: str | None


@dataclass(frozen=True)
class JournalDraftInput:
    """Datos normalizados de cabecera y lineas de un comprobante."""

    company: str
    posting_date: date
    books: list[str] | None
    naming_series_id: str | None
    reference: str | None
    memo: str | None
    transaction_currency: str | None
    exchange_rate: Decimal | None
    is_closing: bool
    lines: list[JournalLineInput]


def create_journal_draft(payload: dict[str, Any], user_id: str, assign_identifier: bool = True) -> ComprobanteContable:
    """Crea un comprobante contable manual en borrador."""
    data = _normalize_journal_payload(payload)
    _validate_balanced_lines(data.company, data.lines)
    primary_book = data.books[0] if data.books else None
    journal = ComprobanteContable(
        entity=data.company,
        book=primary_book,
        user_id=user_id,
        date=data.posting_date,
        reference=data.reference,
        memo=data.memo,
        status=JOURNAL_STATUS_DRAFT,
        voucher_type=JOURNAL_TRANSACTION_TYPE,
        naming_series_id=data.naming_series_id,
        book_codes=_serialize_book_codes(data.books),
        transaction_currency=data.transaction_currency,
        exchange_rate=data.exchange_rate,
        is_closing=data.is_closing,
    )
    lines = [
        _line_model(data.company, data.posting_date, primary_book, data.transaction_currency, line) for line in data.lines
    ]
    journal = add_journal(journal, lines)
    if assign_identifier:
        _assign_identifier_if_needed(journal, data.naming_series_id)
    database.session.commit()
    return journal


def submit_journal(journal_id: str) -> list[Any]:
    """Contabiliza un comprobante manual en borrador."""
    journal = get_journal(journal_id)
    if journal is None:
        raise JournalValidationError("El comprobante indicado no existe.")
    if journal.status != JOURNAL_STATUS_DRAFT:
        raise JournalValidationError("Solo se puede contabilizar un comprobante en borrador.")
    if not journal.document_no:
        _assign_identifier_if_needed(journal, journal.naming_series_id)
    try:
        entries = post_comprobante_contable(journal, ledger_code=_selected_books_for_journal(journal))
    except (PostingError, IdentifierConfigurationError) as exc:
        database.session.rollback()
        raise JournalValidationError(str(exc)) from exc
    journal.status = JOURNAL_STATUS_SUBMITTED
    database.session.add(journal)
    database.session.commit()
    return entries


def reject_journal_draft(journal_id: str, user_id: str | None = None) -> ComprobanteContable:
    """Marca un comprobante manual en borrador como rechazado sin afectar ledger."""
    journal = get_journal(journal_id)
    if journal is None:
        raise JournalValidationError("El comprobante indicado no existe.")
    if journal.status != JOURNAL_STATUS_DRAFT:
        raise JournalValidationError("Solo se puede rechazar un comprobante en borrador.")
    journal.status = JOURNAL_STATUS_REJECTED
    if user_id:
        journal.modified_by = user_id
    database.session.add(journal)
    database.session.commit()
    return journal


def cancel_submitted_journal(journal_id: str, user_id: str | None = None) -> list[Any]:
    """Anula un comprobante contabilizado mediante reversa GL append-only."""
    journal = get_journal(journal_id)
    if journal is None:
        raise JournalValidationError("El comprobante indicado no existe.")
    if journal.status != JOURNAL_STATUS_SUBMITTED:
        raise JournalValidationError("Solo se puede anular un comprobante contabilizado.")
    setattr(journal, "docstatus", 1)
    try:
        entries = cancel_document(journal)
    except (PostingError, IdentifierConfigurationError) as exc:
        database.session.rollback()
        raise JournalValidationError(str(exc)) from exc
    journal.status = JOURNAL_STATUS_CANCELLED
    if user_id:
        journal.modified_by = user_id
    database.session.add(journal)
    database.session.commit()
    return entries


def duplicate_journal_as_draft(journal_id: str, user_id: str) -> ComprobanteContable:
    """Duplica un comprobante existente creando uno nuevo en borrador."""
    source = get_journal(journal_id)
    if source is None:
        raise JournalValidationError("El comprobante indicado no existe.")
    if source.status not in JOURNAL_DUPLICABLE_STATUSES:
        raise JournalValidationError("Solo se puede duplicar un comprobante en borrador, rechazado o contabilizado.")

    payload = serialize_journal_for_form(source)
    payload["reference"] = source.document_no or source.id
    payload["memo"] = f"Duplicado de {source.document_no or source.id}"
    duplicated = create_journal_draft(payload, user_id=user_id, assign_identifier=False)
    duplicated.status = JOURNAL_STATUS_DRAFT
    duplicated.document_no = None
    duplicated.serie = None
    database.session.add(duplicated)
    database.session.commit()
    return duplicated


def duplicate_journal_as_reversal_draft(journal_id: str, user_id: str) -> ComprobanteContable:
    """Genera borrador de reversión invirtiendo debe/haber del comprobante origen."""
    source = get_journal(journal_id)
    if source is None:
        raise JournalValidationError("El comprobante indicado no existe.")
    if source.status not in JOURNAL_DUPLICABLE_STATUSES:
        raise JournalValidationError("Solo se puede revertir un comprobante en borrador, rechazado o contabilizado.")

    payload = serialize_journal_for_form(source)
    payload["reference"] = source.document_no or source.id
    payload["memo"] = f"Reversión de {source.document_no or source.id}"
    payload["lines"] = _reversed_payload_lines(payload.get("lines", []))

    reversed_draft = create_journal_draft(payload, user_id=user_id, assign_identifier=False)
    reversed_draft.status = JOURNAL_STATUS_DRAFT
    reversed_draft.document_no = None
    reversed_draft.serie = None
    database.session.add(reversed_draft)
    database.session.commit()
    return reversed_draft


def update_journal_draft(journal_id: str, payload: dict[str, Any], user_id: str) -> ComprobanteContable:
    """Actualiza un comprobante manual en borrador."""
    journal = get_journal(journal_id)
    if journal is None:
        raise JournalValidationError("El comprobante indicado no existe.")
    if journal.status != JOURNAL_STATUS_DRAFT:
        raise JournalValidationError("Solo se puede editar un comprobante en borrador.")

    data = _normalize_journal_payload(payload)
    _validate_balanced_lines(data.company, data.lines)
    primary_book = data.books[0] if data.books else None

    journal.entity = data.company
    journal.book = primary_book
    journal.book_codes = _serialize_book_codes(data.books)
    journal.date = data.posting_date
    journal.reference = data.reference
    journal.memo = data.memo
    journal.naming_series_id = data.naming_series_id
    journal.transaction_currency = data.transaction_currency
    journal.exchange_rate = data.exchange_rate
    journal.is_closing = data.is_closing
    journal.user_id = user_id

    lines = [
        _line_model(data.company, data.posting_date, primary_book, data.transaction_currency, line) for line in data.lines
    ]
    journal = replace_journal_lines(journal, lines)
    if not journal.document_no:
        _assign_identifier_if_needed(journal, data.naming_series_id)
    database.session.commit()
    return journal


def serialize_journal_for_form(journal: ComprobanteContable) -> dict[str, Any]:
    """Convierte un comprobante manual a un payload compatible con el formulario."""
    lines = list_journal_lines(journal.id)
    selected_books = _selected_books_for_journal(journal)
    account_codes = {line.account for line in lines if line.account}
    cost_center_codes = {line.cost_center for line in lines if line.cost_center}
    account_labels = _account_labels_for_company(journal.entity, account_codes)
    cost_center_labels = _cost_center_labels_for_company(journal.entity, cost_center_codes)
    return {
        "company": journal.entity,
        "company_label": journal.entity,
        "posting_date": journal.date.isoformat() if journal.date else None,
        "books": selected_books or [],
        "naming_series_id": journal.naming_series_id,
        "naming_series_label": journal.document_no or journal.serie or "",
        "reference": journal.reference or "",
        "memo": journal.memo or "",
        "transaction_currency": journal.transaction_currency,
        "transaction_currency_label": journal.transaction_currency,
        "exchange_rate": str(journal.exchange_rate) if journal.exchange_rate is not None else "",
        "is_closing": bool(getattr(journal, "is_closing", False)),
        "lines": [_serialize_journal_line(line, account_labels, cost_center_labels) for line in lines],
    }


def parse_journal_form(form_data: Any) -> dict[str, Any]:
    """Convierte datos del formulario HTML en payload de servicio."""
    raw_payload = form_data.get("journal_payload")
    if raw_payload:
        try:
            parsed_payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise JournalValidationError("El detalle del comprobante no tiene un formato valido.") from exc
        if not isinstance(parsed_payload, dict):
            raise JournalValidationError("El detalle del comprobante no tiene un formato valido.")
        return parsed_payload
    return {
        "company": form_data.get("company"),
        "posting_date": form_data.get("posting_date"),
        "book": form_data.get("book"),
        "books": form_data.getlist("books") if hasattr(form_data, "getlist") else [],
        "naming_series_id": form_data.get("naming_series_id"),
        "reference": form_data.get("reference"),
        "memo": form_data.get("memo"),
        "transaction_currency": form_data.get("transaction_currency"),
        "exchange_rate": form_data.get("exchange_rate"),
        "is_closing": form_data.get("is_closing") in ("true", "True", "1", "on"),
        "lines": [],
    }


def _normalize_journal_payload(payload: dict[str, Any]) -> JournalDraftInput:
    company = _required_text(payload.get("company"), "La compañia es obligatoria.")
    posting_date = _parse_date(payload.get("posting_date"))
    lines_payload = payload.get("lines") or []
    if not isinstance(lines_payload, list):
        raise JournalValidationError("Las lineas del comprobante no tienen un formato valido.")
    lines = [_normalize_line(line, index + 1) for index, line in enumerate(lines_payload)]
    lines = [line for line in lines if line.account or line.debit or line.credit]
    if not lines:
        raise JournalValidationError("El comprobante debe contener al menos una linea.")
    books = _normalize_books(payload.get("books"))
    if books is None and (book := _optional_text(payload.get("book"))):
        books = [book]
    transaction_currency, lines = _normalize_transaction_currency(_optional_text(payload.get("transaction_currency")), lines)
    return JournalDraftInput(
        company=company,
        posting_date=posting_date,
        books=books,
        naming_series_id=_optional_text(payload.get("naming_series_id")),
        reference=_optional_text(payload.get("reference")),
        memo=_optional_text(payload.get("memo")),
        transaction_currency=transaction_currency,
        exchange_rate=None,
        is_closing=_optional_bool(payload.get("is_closing")),
        lines=lines,
    )


def _normalize_line(raw_line: Any, fallback_order: int) -> JournalLineInput:
    if not isinstance(raw_line, dict):
        raise JournalValidationError("Cada linea del comprobante debe ser un objeto.")
    debit = _decimal(raw_line.get("debit"))
    credit = _decimal(raw_line.get("credit"))
    return JournalLineInput(
        order=int(raw_line.get("order") or fallback_order),
        account=_optional_text(raw_line.get("account")) or "",
        cost_center=_optional_text(raw_line.get("cost_center")),
        party_type=_optional_text(raw_line.get("party_type")),
        party=_optional_text(raw_line.get("party")),
        debit=debit,
        credit=credit,
        unit=_optional_text(raw_line.get("unit")),
        project=_optional_text(raw_line.get("project")),
        currency=_optional_text(raw_line.get("currency")),
        exchange_rate=_optional_decimal(raw_line.get("exchange_rate")),
        reference_type=_optional_text(raw_line.get("reference_type")),
        reference_name=_optional_text(raw_line.get("reference_name")),
        reference1=_optional_text(raw_line.get("reference1")),
        reference2=_optional_text(raw_line.get("reference2")),
        remarks=_optional_text(raw_line.get("remarks")),
        is_advance=bool(raw_line.get("is_advance")),
        bank_account_id=_optional_text(raw_line.get("bank_account") or raw_line.get("bank_account_id")),
    )


def _validate_balanced_lines(company: str, lines: list[JournalLineInput]) -> None:
    account_cache: dict[str, Accounts | None] = {}
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        if not line.account:
            raise JournalValidationError("Cada linea debe tener una cuenta contable.")
        if line.debit < 0 or line.credit < 0:
            raise JournalValidationError("Los importes de debe y haber no pueden ser negativos.")
        if line.debit > 0 and line.credit > 0:
            raise JournalValidationError("Una linea no puede tener debe y haber positivos al mismo tiempo.")
        if line.debit == 0 and line.credit == 0:
            raise JournalValidationError("Cada linea debe tener un importe en debe o en haber.")
        account = account_cache.get(line.account)
        if line.account not in account_cache:
            account = _account_record(company, line.account)
            account_cache[line.account] = account
        if account is not None and account.account_type == "expense" and not line.cost_center:
            raise JournalValidationError("Las cuentas de gasto requieren centro de costo.")
        total_debit += line.debit
        total_credit += line.credit
    if total_debit != total_credit:
        raise JournalValidationError("El comprobante contable no esta balanceado.")


def _line_model(
    company: str,
    posting_date: date,
    book: str | None,
    transaction_currency: str | None,
    line: JournalLineInput,
) -> ComprobanteContableDetalle:
    amount = line.debit if line.debit > 0 else -line.credit
    return ComprobanteContableDetalle(
        entity=company,
        account=_account_code(company, line.account),
        cost_center=line.cost_center,
        unit=line.unit,
        project=line.project,
        book=book,
        date=posting_date,
        transaction=ComprobanteContable.__tablename__,
        order=line.order,
        value=amount,
        currency_id=transaction_currency,
        exchange_rate=line.exchange_rate,
        value_default=amount,
        memo=line.remarks,
        reference=line.reference_name,
        line_memo=line.remarks,
        internal_reference=line.reference_type,
        internal_reference_id=line.reference_name,
        reference1=line.reference1,
        reference2=line.reference2,
        third_type=line.party_type,
        third_code=line.party,
        bank_account_id=line.bank_account_id,
        is_advance=line.is_advance,
        voucher_type=JOURNAL_TRANSACTION_TYPE,
    )


def _assign_identifier_if_needed(journal: ComprobanteContable, naming_series_id: str | None) -> None:
    setattr(journal, "company", journal.entity)
    try:
        assign_document_identifier(
            document=journal,
            entity_type=JOURNAL_ENTITY_TYPE,
            posting_date_raw=journal.date,
            naming_series_id=naming_series_id,
        )
    except IdentifierConfigurationError:
        return
    journal.serie = journal.document_no


def _normalize_books(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = _optional_text(value)
        return [normalized] if normalized else None
    if not isinstance(value, list):
        raise JournalValidationError("La selección de libros no tiene un formato valido.")

    books: list[str] = []
    for item in value:
        normalized = _optional_text(item)
        if normalized and normalized not in books:
            books.append(normalized)
    return books or None


def _serialize_book_codes(books: list[str] | None) -> str | None:
    if not books:
        return None
    return json.dumps(books)


def _selected_books_for_journal(journal: ComprobanteContable) -> list[str] | None:
    if journal.book_codes:
        try:
            return _normalize_books(json.loads(journal.book_codes))
        except json.JSONDecodeError as exc:
            raise JournalValidationError("La selección de libros del comprobante no es valida.") from exc
    if journal.book:
        return [str(journal.book)]
    return None


def _serialize_journal_line(
    line: ComprobanteContableDetalle,
    account_labels: dict[str, str],
    cost_center_labels: dict[str, str],
) -> dict[str, Any]:
    value = Decimal(str(line.value or 0))
    account_code = line.account or ""
    cost_center_code = line.cost_center or ""
    return {
        "order": line.order or 0,
        "account": account_code,
        "account_label": account_labels.get(account_code, account_code),
        "cost_center": cost_center_code,
        "cost_center_label": cost_center_labels.get(cost_center_code, cost_center_code),
        "party_type": line.third_type or "",
        "party": line.third_code or "",
        "debit": str(value) if value > 0 else "",
        "credit": str(abs(value)) if value < 0 else "",
        "unit": line.unit or "",
        "project": line.project or "",
        "currency": line.currency_id or "",
        "exchange_rate": str(line.exchange_rate) if line.exchange_rate is not None else "",
        "reference_type": line.internal_reference or "",
        "reference_name": line.internal_reference_id or line.reference or "",
        "reference1": line.reference1 or "",
        "reference2": line.reference2 or "",
        "remarks": line.memo or line.line_memo or "",
        "is_advance": bool(getattr(line, "is_advance", False)),
        "bank_account": getattr(line, "bank_account_id", "") or "",
    }


def _account_labels_for_company(company: str, account_codes: set[str]) -> dict[str, str]:
    if not account_codes:
        return {}
    rows = (
        database.session.execute(select(Accounts).filter(Accounts.entity == company).where(Accounts.code.in_(account_codes)))
        .scalars()
        .all()
    )
    labels: dict[str, str] = {}
    for row in rows:
        if not row.code:
            continue
        label = f"{row.code} - {row.name}" if row.name else row.code
        labels[row.code] = label
    return labels


def _cost_center_labels_for_company(company: str, cost_center_codes: set[str]) -> dict[str, str]:
    if not cost_center_codes:
        return {}
    rows = (
        database.session.execute(
            select(CostCenter).filter(CostCenter.entity == company).where(CostCenter.code.in_(cost_center_codes))
        )
        .scalars()
        .all()
    )
    labels: dict[str, str] = {}
    for row in rows:
        if not row.code:
            continue
        label = f"{row.code} - {row.name}" if row.name else row.code
        labels[row.code] = label
    return labels


def _reversed_payload_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reversed_lines: list[dict[str, Any]] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        debit_value = line.get("debit") or ""
        credit_value = line.get("credit") or ""
        reversed_line = dict(line)
        reversed_line["debit"] = credit_value
        reversed_line["credit"] = debit_value
        reversed_lines.append(reversed_line)
    return reversed_lines


def _normalize_transaction_currency(
    transaction_currency: str | None, lines: list[JournalLineInput]
) -> tuple[str | None, list[JournalLineInput]]:
    line_currencies = {line.currency for line in lines if line.currency}
    if transaction_currency:
        if line_currencies and line_currencies != {transaction_currency}:
            raise JournalValidationError("Todas las lineas deben usar la moneda del comprobante.")
        return transaction_currency, _apply_currency_to_lines(lines, transaction_currency)
    if len(line_currencies) > 1:
        raise JournalValidationError("No se permite mezclar monedas en un mismo comprobante.")
    if not line_currencies:
        return None, lines
    inferred_currency = next(iter(line_currencies))
    return inferred_currency, _apply_currency_to_lines(lines, inferred_currency)


def _apply_currency_to_lines(lines: list[JournalLineInput], currency: str) -> list[JournalLineInput]:
    return [replace(line, currency=currency) for line in lines]


def _account_record(company: str, account_value: str) -> Accounts | None:
    account = database.session.get(Accounts, account_value)
    if account is not None:
        return account if account.entity == company else None
    return database.session.execute(database.select(Accounts).filter_by(entity=company, code=account_value)).scalars().first()


def _account_code(company: str, account_value: str) -> str:
    account = database.session.get(Accounts, account_value)
    if account is not None:
        if account.entity != company:
            raise JournalValidationError("La cuenta contable no pertenece a la compañia del comprobante.")
        return str(account.code)
    account = (
        database.session.execute(database.select(Accounts).filter_by(entity=company, code=account_value)).scalars().first()
    )
    if account is None:
        raise JournalValidationError("La cuenta contable indicada no existe para la compañia.")
    return str(account.code)


def _required_text(value: Any, message: str) -> str:
    normalized = _optional_text(value)
    if not normalized:
        raise JournalValidationError(message)
    return normalized


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_date(value: Any) -> date:
    normalized = _required_text(value, "La fecha de contabilizacion es obligatoria.")
    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise JournalValidationError("La fecha de contabilizacion no es valida.") from exc


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise JournalValidationError("Los importes del comprobante no son validos.") from exc


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return _decimal(value)


def _optional_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in ("true", "1", "yes", "on")
