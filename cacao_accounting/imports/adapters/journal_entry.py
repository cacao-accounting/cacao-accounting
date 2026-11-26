# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de comprobantes contables."""

from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any
from sqlalchemy import or_, select

from cacao_accounting.database import Accounts, Book, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter, normalize_header_date
from cacao_accounting.contabilidad.journal_service import create_journal_draft
from cacao_accounting.imports.utils.validation import is_period_open
from cacao_accounting.imports.utils.dates import parse_import_date


from cacao_accounting.i18n import _


class JournalEntryAdapter(BaseImportAdapter):
    """Adaptador para Comprobantes Contables."""

    @staticmethod
    def _amount(value: Any) -> Decimal:
        """Parsea un importe sin perder precisión ni aceptar valores no finitos."""
        amount = Decimal(str(value or "0").strip())
        if not amount.is_finite():
            raise InvalidOperation(_("El importe debe ser finito"))
        return amount

    columns = [
        "document_ref",
        "fecha",
        "cuenta",
        "centro_costo",
        "tercero",
        "descripcion",
        "debito",
        "credito",
        "moneda",
        "tipo_cambio",
        "referencia",
        "is_advance",
    ]
    required_columns = ["document_ref", "fecha", "cuenta", "debito", "credito"]
    column_aliases = {
        "reference": "document_ref",
        "document_reference": "document_ref",
        "posting_date": "fecha",
        "date": "fecha",
        "account": "cuenta",
        "account_code": "cuenta",
        "debit": "debito",
        "debe": "debito",
        "credit": "credito",
        "haber": "credito",
    }

    @staticmethod
    def _value(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        """Return the first populated value, accepting legacy and canonical headers."""
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return default

    def _validate_amounts(self, document_data: List[Dict[str, Any]]) -> List[str]:
        """Valida importes parseables; el balance por libro lo resuelve el motor."""
        errors: List[str] = []
        if len(document_data) < 2:
            errors.append(_("Un comprobante contable debe tener al menos dos líneas."))
        for row in document_data:
            try:
                self._amount(self._value(row, "debito", "debit"))
                self._amount(self._value(row, "credito", "credit"))
            except (InvalidOperation, ValueError, TypeError):
                errors.append(
                    _("Monto inválido en referencia %(reference)s")
                    % {"reference": self._value(row, "document_ref", "reference")}
                )
        return errors

    def _validate_period(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None) -> List[str]:
        """Valida que la fecha del asiento pertenezca a un período abierto."""
        if not document_data:
            return []
        try:
            posting_date = parse_import_date(self._value(document_data[0], "fecha", "posting_date"))
        except (ValueError, TypeError):
            return [_("La fecha debe usar un formato válido.")]
        company_id = (context or {}).get("company_id") or ""
        if not is_period_open(company_id, posting_date):
            return [_("El periodo contable para la fecha %(date)s está cerrado o no existe.") % {"date": posting_date}]
        return []

    def _validate_accounting_lines(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None) -> List[str]:
        """Aplica las mismas validaciones de líneas que el formulario de asientos."""
        try:
            from cacao_accounting.contabilidad.journal_service import (
                _normalize_journal_payload,
                _validate_ar_ap_lines,
                _validate_balanced_lines,
                _validate_line_books,
            )

            payload = self.build_document(document_data, context or {})
            canonical_rows = payload.get("lines", [])
            company = str((context or {}).get("company_id") or "")
            for row in canonical_rows:
                account = database.session.execute(
                    select(Accounts).where(
                        Accounts.entity == company,
                        Accounts.code == row.get("account"),
                    )
                ).scalar_one_or_none()
                if account is None:
                    return [
                        _("La cuenta %(account_code)s no existe en la compania %(company)s.")
                        % {"account_code": row.get("account"), "company": company}
                    ]
                if not account.active or not account.enabled:
                    return [_("La cuenta contable debe estar activa y habilitada.")]
            data = _normalize_journal_payload(payload)
            _validate_balanced_lines(company, data.lines, data.transaction_currency, data.exchange_rate, data.books)
            _validate_line_books(company, data.books, data.lines)
            _validate_ar_ap_lines(company, data.lines)
        except RuntimeError as exc:
            from cacao_accounting.logs import log

            log.exception("Falló la validación contable del comprobante importado: {}", exc)
            return [_("No se pudo validar el comprobante contable. Revise el registro de errores.")]
        except (ValueError, InvalidOperation) as exc:
            return [str(exc)]
        return []

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Valida que el comprobante tenga al menos dos líneas y esté balanceado."""
        errors = self.validate_header_consistency(
            document_data,
            {"fecha": (("fecha", "posting_date"), normalize_header_date)},
        )
        errors.extend(self._validate_amounts(document_data))
        errors.extend(self._validate_period(document_data, context))
        if not errors:
            errors.extend(self._validate_accounting_lines(document_data, context))

        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Construye el payload para crear el borrador del comprobante."""
        lines = []
        for index, row in enumerate(document_data):
            lines.append(
                {
                    "order": index + 1,
                    "account": self._value(row, "cuenta", "account"),
                    "cost_center": self._value(row, "centro_costo", "cost_center"),
                    "party_type": self._value(row, "party_type", "tipo_tercero"),
                    "party": self._value(row, "tercero", "party"),
                    "debit": self._value(row, "debito", "debit", default=0),
                    "credit": self._value(row, "credito", "credit", default=0),
                    "currency": self._value(row, "moneda", "currency"),
                    "exchange_rate": self._value(row, "tipo_cambio", "exchange_rate"),
                    "reference_type": self._value(row, "reference_type", "tipo_referencia"),
                    "reference_name": self._value(
                        row, "reference_name", "reference_document", "documento_referencia", "referencia"
                    ),
                    "reference_open_item_id": self._value(row, "reference_open_item_id"),
                    "reference_exchange_rate": self._value(row, "reference_exchange_rate"),
                    "project": self._value(row, "project", "proyecto"),
                    "unit": self._value(row, "unit", "unidad"),
                    "bank_account": self._value(row, "bank_account", "bank_account_id"),
                    "is_advance": self._value(row, "is_advance", default=False),
                    "remarks": self._value(row, "descripcion", "description", "referencia"),
                }
            )

        posting_date = parse_import_date(self._value(document_data[0], "fecha", "posting_date"))
        reference = self._value(document_data[0], "document_ref", "reference", default="no_ref")
        payload = {
            "company": context.get("company_id"),
            "posting_date": posting_date,
            "books": self._resolve_books(context),
            "naming_series_id": context.get("sequence_id"),
            "reference": reference,
            "memo": f"Importación masiva: {reference}",
            "transaction_currency": context.get("transaction_currency") or self._value(document_data[0], "moneda", "currency"),
            "exchange_rate": context.get("exchange_rate") or self._value(document_data[0], "tipo_cambio", "exchange_rate"),
            "lines": lines,
            "created_by": context.get("created_by"),
        }
        return payload

    def persist_document(self, document: Any) -> None:
        """Persist the journal entry to the database."""
        user_id = document.get("created_by") or "admin"
        create_journal_draft(document, user_id=user_id)

    def _resolve_books(self, context: Dict[str, Any]) -> list[str]:
        """Resolve selected book or all active company books when none is selected."""
        selected_book = context.get("accounting_book_id")
        if selected_book:
            company_id = context.get("company_id")
            book = database.session.execute(
                select(Book).where(Book.entity == company_id, or_(Book.id == selected_book, Book.code == selected_book))
            ).scalar_one_or_none()
            if not book or book.entity != company_id:
                raise ValueError(_("El libro contable no pertenece a la compañía seleccionada."))
            return [book.code]

        company_id = context.get("company_id")
        if not company_id:
            return []

        books = database.session.execute(
            select(Book)
            .where(
                Book.entity == company_id,
                Book.status == "activo",
            )
            .order_by(Book.is_primary.desc(), Book.code)
        ).scalars()
        return [book.code for book in books if book.code]
