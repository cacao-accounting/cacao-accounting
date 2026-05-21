# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de comprobantes contables."""

from datetime import date
from typing import List, Dict, Any
from sqlalchemy import or_, select

from cacao_accounting.database import Book, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.contabilidad.journal_service import create_journal_draft
from cacao_accounting.imports.utils.validation import is_period_open


class JournalEntryAdapter(BaseImportAdapter):
    """Adaptador para Comprobantes Contables."""

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

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Valida que el comprobante tenga al menos dos líneas y esté balanceado."""
        errors = []
        if len(document_data) < 2:
            errors.append("Un comprobante contable debe tener al menos dos líneas.")

        total_debit = 0.0
        total_credit = 0.0
        for row in document_data:
            try:
                total_debit += float(row.get("debito") or 0)
                total_credit += float(row.get("credito") or 0)
            except (ValueError, TypeError):
                errors.append(f"Monto inválido en referencia {row.get('document_ref')}")

        if abs(total_debit - total_credit) > 0.0001:
            errors.append(f"El comprobante {document_data[0].get('document_ref')} no está balanceado.")

        # Período contable
        try:
            posting_date = date.fromisoformat(str(document_data[0].get("fecha")))
            company_id = (context or {}).get("company_id") or ""
            if not is_period_open(company_id, posting_date):
                errors.append(f"El periodo contable para la fecha {posting_date} está cerrado o no existe.")
        except (ValueError, TypeError):
            # Formato de fecha inválido se manejará en otro lugar o ya fue reportado
            pass

        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Construye el payload para crear el borrador del comprobante."""
        lines = []
        for index, row in enumerate(document_data):
            lines.append(
                {
                    "order": index + 1,
                    "account": row.get("cuenta"),
                    "cost_center": row.get("centro_costo"),
                    "party_type": None,  # Should be inferred or provided
                    "party": row.get("tercero"),
                    "debit": row.get("debito") or 0,
                    "credit": row.get("credito") or 0,
                    "remarks": row.get("descripcion") or row.get("referencia"),
                }
            )

        payload = {
            "company": context.get("company_id"),
            "posting_date": document_data[0].get("fecha"),
            "books": self._resolve_books(context),
            "naming_series_id": context.get("sequence_id"),
            "reference": document_data[0].get("document_ref"),
            "memo": f"Importación masiva: {document_data[0].get('document_ref')}",
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
            return [str(selected_book)]

        company_id = context.get("company_id")
        if not company_id:
            return []

        books = database.session.execute(
            select(Book)
            .where(
                Book.entity == company_id,
                or_(Book.status == "activo", Book.status.is_(None)),
            )
            .order_by(Book.is_primary.desc(), Book.code)
        ).scalars()
        return [book.code for book in books if book.code]
