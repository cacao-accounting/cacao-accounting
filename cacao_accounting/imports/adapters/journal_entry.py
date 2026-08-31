# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de comprobantes contables."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any
from sqlalchemy import or_, select

from cacao_accounting.database import Book, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.contabilidad.journal_service import create_journal_draft
from cacao_accounting.imports.utils.validation import is_period_open


class JournalEntryAdapter(BaseImportAdapter):
    """Adaptador para Comprobantes Contables."""

    _BALANCE_TOLERANCE = Decimal("0.0001")

    @staticmethod
    def _amount(value: Any) -> Decimal:
        """Parsea un importe sin perder precisión ni aceptar valores no finitos."""
        amount = Decimal(str(value or "0").strip())
        if not amount.is_finite():
            raise InvalidOperation("El importe debe ser finito")
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
        "referencia",
    ]
    required_columns = ["document_ref", "fecha", "cuenta", "debito", "credito"]

    @staticmethod
    def _value(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        """Return the first populated value, accepting legacy and canonical headers."""
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return default

    def _validate_amounts(self, document_data: List[Dict[str, Any]]) -> List[str]:
        """Valida importes y balance global de las líneas importadas."""
        errors: List[str] = []
        if len(document_data) < 2:
            errors.append("Un comprobante contable debe tener al menos dos líneas.")
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for row in document_data:
            try:
                total_debit += self._amount(self._value(row, "debito", "debit"))
                total_credit += self._amount(self._value(row, "credito", "credit"))
            except (InvalidOperation, ValueError, TypeError):
                errors.append(f"Monto inválido en referencia {self._value(row, 'document_ref', 'reference')}")
        if document_data and abs(total_debit - total_credit) > self._BALANCE_TOLERANCE:
            errors.append(f"El comprobante {self._value(document_data[0], 'document_ref', 'reference')} no está balanceado.")
        return errors

    def _validate_period(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None) -> List[str]:
        """Valida que la fecha del asiento pertenezca a un período abierto."""
        if not document_data:
            return []
        try:
            posting_date = date.fromisoformat(str(self._value(document_data[0], "fecha", "posting_date")))
            company_id = (context or {}).get("company_id") or ""
            if not is_period_open(company_id, posting_date):
                return [f"El periodo contable para la fecha {posting_date} está cerrado o no existe."]
        except (ValueError, TypeError):
            pass
        return []

    def _validate_accounting_lines(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None) -> List[str]:
        """Aplica las mismas validaciones de líneas que el formulario de asientos."""
        try:
            from cacao_accounting.contabilidad.journal_service import (
                _normalize_line,
                _validate_ar_ap_lines,
                _validate_balanced_lines,
                _validate_line_books,
            )

            canonical_rows = self.build_document(document_data, context or {}).get("lines", [])
            lines = [_normalize_line(row, index + 1) for index, row in enumerate(canonical_rows)]
            company = str((context or {}).get("company_id") or "")
            _validate_balanced_lines(company, lines, (context or {}).get("transaction_currency"))
            _validate_line_books(company, (context or {}).get("books"), lines)
            _validate_ar_ap_lines(company, lines)
        except RuntimeError:
            return []
        except (ValueError, InvalidOperation) as exc:
            return [str(exc)]
        return []

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Valida que el comprobante tenga al menos dos líneas y esté balanceado."""
        errors = self._validate_amounts(document_data)
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

        posting_date = self._value(document_data[0], "fecha", "posting_date")
        reference = self._value(document_data[0], "document_ref", "reference", default="no_ref")
        payload = {
            "company": context.get("company_id"),
            "posting_date": posting_date,
            "books": self._resolve_books(context),
            "naming_series_id": context.get("sequence_id"),
            "reference": reference,
            "memo": f"Importación masiva: {reference}",
            "transaction_currency": context.get("transaction_currency") or self._value(document_data[0], "moneda", "currency"),
            "exchange_rate": context.get("exchange_rate"),
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
                raise ValueError("El libro contable no pertenece a la compañía seleccionada.")
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
