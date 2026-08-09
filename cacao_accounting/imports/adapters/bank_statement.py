# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de extractos bancarios."""

from datetime import date
from decimal import Decimal, InvalidOperation
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

    @staticmethod
    def _optional_amount(value: Any) -> Decimal | None:
        """Convierte una columna vacía o cero en un lado bancario ausente."""
        if value in (None, ""):
            return None
        amount = Decimal(str(value))
        return amount if amount != 0 else None

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Validate a single bank statement row."""
        errors = super().validate_row(row_data)
        bank_account = database.session.get(BankAccount, str(row_data.get("bank_account_id", "")))
        if bank_account is None:
            errors.append(f"Cuenta bancaria no encontrada: {row_data.get('bank_account_id')}")
        raw_date = row_data.get("posting_date")
        try:
            if isinstance(raw_date, date):
                parsed_date = raw_date
            else:
                parsed_date = date.fromisoformat(str(raw_date))
            if not parsed_date:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"Fecha bancaria inválida: {raw_date}")

        amounts: dict[str, Decimal | None] = {}
        for field in ("deposit", "withdrawal"):
            try:
                amounts[field] = self._optional_amount(row_data.get(field))
            except (InvalidOperation, TypeError, ValueError):
                amounts[field] = None
                errors.append(f"Monto bancario inválido en columna '{field}': {row_data.get(field)}")
        if (
            amounts["deposit"] is None
            and amounts["withdrawal"] is None
            and not any(f"columna '{field}'" in error for error in errors for field in ("deposit", "withdrawal"))
        ):
            errors.append("La fila bancaria debe contener un depósito o un retiro mayor que cero.")
        if amounts["deposit"] is not None and amounts["withdrawal"] is not None:
            errors.append("Una fila bancaria no puede contener depósito y retiro simultáneamente.")
        return errors

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Valida compañía de la cuenta y período de cada transacción."""
        from cacao_accounting.imports.utils.validation import is_period_open

        company_id = (context or {}).get("company_id") or ""
        errors: list[str] = []
        for row in document_data:
            bank_account = database.session.get(BankAccount, str(row.get("bank_account_id", "")))
            if bank_account and bank_account.company != company_id:
                errors.append(
                    f"La cuenta bancaria {bank_account.id} pertenece a la compañía "
                    f"{bank_account.company}, no a {company_id}."
                )
            try:
                posting_date = row.get("posting_date")
                posting_date = posting_date if isinstance(posting_date, date) else date.fromisoformat(str(posting_date))
            except (TypeError, ValueError):
                continue
            if not is_period_open(company_id, posting_date):
                errors.append(f"El periodo contable para la fecha {posting_date} está cerrado o no existe.")
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build bank transactions from the imported data."""
        transactions = []
        for row in document_data:
            posting_date = row.get("posting_date")
            if isinstance(posting_date, str):
                try:
                    posting_date = date.fromisoformat(posting_date)
                except ValueError as exc:
                    raise ValueError(f"Fecha bancaria inválida: {posting_date}") from exc
            transactions.append(
                {
                    "bank_account_id": str(row.get("bank_account_id", "")),
                    "company_id": context.get("company_id"),
                    "posting_date": posting_date,
                    "reference_number": str(row.get("reference_number", "")),
                    "description": str(row.get("description", "")),
                    "deposit": self._optional_amount(row.get("deposit")),
                    "withdrawal": self._optional_amount(row.get("withdrawal")),
                }
            )
        return transactions

    def persist_document(self, document: Any) -> None:
        """Persist bank transactions to the database."""
        for tx_data in document:
            bank_account = database.session.get(BankAccount, tx_data["bank_account_id"])
            if bank_account is None:
                raise ValueError(f"Cuenta bancaria no encontrada: {tx_data['bank_account_id']}")
            company_id = tx_data.get("company_id")
            if company_id and bank_account.company != company_id:
                raise ValueError(
                    f"La cuenta bancaria {bank_account.id} pertenece a la compañía {bank_account.company}, "
                    f"no a {company_id}."
                )
            tx = BankTransaction(
                bank_account_id=tx_data["bank_account_id"],
                posting_date=tx_data["posting_date"],
                reference_number=tx_data.get("reference_number", ""),
                description=tx_data.get("description", ""),
                deposit=tx_data.get("deposit"),
                withdrawal=tx_data.get("withdrawal"),
            )
            database.session.add(tx)
