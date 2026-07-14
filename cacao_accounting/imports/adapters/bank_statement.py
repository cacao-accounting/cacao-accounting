# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de extractos bancarios."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any

from cacao_accounting.database import BankAccount, BankTransaction, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter


class BankStatementAdapter(BaseImportAdapter):
    """Adaptador para Extractos Bancarios."""

    columns = [
        "bank_account_id",
        "posting_date",
        "reference_number",
        "description",
        "deposit",
        "withdrawal",
    ]
    required_columns = ["bank_account_id", "posting_date"]

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Validate a single bank statement row."""
        errors = super().validate_row(row_data)
        bank_account = database.session.get(BankAccount, str(row_data.get("bank_account_id", "")))
        if bank_account is None:
            errors.append(f"Cuenta bancaria no encontrada: {row_data.get('bank_account_id')}")
        return errors

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Validate the full bank statement document."""
        return []

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build bank transactions from the imported data."""
        transactions = []
        for row in document_data:
            posting_date = row.get("posting_date")
            if isinstance(posting_date, str):
                try:
                    posting_date = date.fromisoformat(posting_date)
                except ValueError:
                    posting_date = datetime.now().date()
            transactions.append(
                {
                    "bank_account_id": str(row.get("bank_account_id", "")),
                    "posting_date": posting_date,
                    "reference_number": str(row.get("reference_number", "")),
                    "description": str(row.get("description", "")),
                    "deposit": Decimal(str(row.get("deposit") or 0)),
                    "withdrawal": Decimal(str(row.get("withdrawal") or 0)),
                }
            )
        return transactions

    def persist_document(self, document: Any) -> None:
        """Persist bank transactions to the database."""
        for tx_data in document:
            tx = BankTransaction(
                bank_account_id=tx_data["bank_account_id"],
                posting_date=tx_data["posting_date"],
                reference_number=tx_data.get("reference_number", ""),
                description=tx_data.get("description", ""),
                deposit=tx_data.get("deposit", Decimal("0")),
                withdrawal=tx_data.get("withdrawal", Decimal("0")),
            )
            database.session.add(tx)
