# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de entradas de pronóstico de caja."""

from datetime import date
from decimal import Decimal
from typing import List, Dict, Any

from cacao_accounting.database import CashForecast, CashForecastEntry, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter


class CashForecastEntryAdapter(BaseImportAdapter):
    """Adaptador para Entradas de Pronóstico de Caja."""

    columns = [
        "forecast_id",
        "type",
        "concept",
        "currency",
        "amount",
        "estimated_date",
        "notes",
    ]
    required_columns = ["forecast_id", "type", "concept", "currency", "amount", "estimated_date"]

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Validate a single cash forecast entry row."""
        errors = super().validate_row(row_data)
        forecast = database.session.get(CashForecast, str(row_data.get("forecast_id", "")))
        if forecast is None:
            errors.append(f"Pronóstico no encontrado: {row_data.get('forecast_id')}")
        entry_type = str(row_data.get("type", "")).strip().capitalize()
        if entry_type not in ("Income", "Expense"):
            errors.append(f"Tipo inválido: {row_data.get('type')}. Debe ser 'Income' o 'Expense'.")
        try:
            Decimal(str(row_data.get("amount") or 0))
        except (ValueError, TypeError):
            errors.append(f"Monto inválido: {row_data.get('amount')}")
        try:
            if isinstance(row_data.get("estimated_date"), str):
                date.fromisoformat(row_data["estimated_date"])
        except (ValueError, TypeError):
            errors.append(f"Fecha inválida: {row_data.get('estimated_date')}")
        return errors

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Validate that every forecast belongs to the import company."""
        company_id = (context or {}).get("company_id") or ""
        errors: list[str] = []
        checked_forecasts: dict[str, CashForecast | None] = {}
        for row in document_data:
            forecast_id = str(row.get("forecast_id", ""))
            if forecast_id not in checked_forecasts:
                checked_forecasts[forecast_id] = database.session.get(CashForecast, forecast_id)
            forecast = checked_forecasts[forecast_id]
            if forecast and forecast.company != company_id:
                errors.append(f"El pronóstico {forecast_id} pertenece a la compañía {forecast.company}, no a {company_id}.")
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build cash forecast entries from the imported data."""
        entries = []
        for row in document_data:
            estimated_date = row.get("estimated_date")
            if isinstance(estimated_date, str):
                estimated_date = date.fromisoformat(estimated_date)
            entries.append(
                {
                    "forecast_id": str(row.get("forecast_id", "")),
                    "type": str(row.get("type", "")).strip(),
                    "concept": str(row.get("concept", "")).strip(),
                    "currency": str(row.get("currency", "NIO")).strip(),
                    "amount": Decimal(str(row.get("amount", 0))),
                    "estimated_date": estimated_date,
                    "notes": str(row.get("notes", "")).strip(),
                    "created_by": context.get("created_by"),
                    "company_id": context.get("company_id"),
                }
            )
        return entries

    def persist_document(self, document: Any) -> None:
        """Persist cash forecast entries to the database."""
        for entry_data in document:
            forecast = database.session.get(CashForecast, entry_data["forecast_id"])
            company_id = entry_data.get("company_id")
            if forecast is None:
                raise ValueError(f"Pronóstico no encontrado: {entry_data['forecast_id']}")
            if company_id and forecast.company != company_id:
                raise ValueError(f"El pronóstico {forecast.id} pertenece a la compañía {forecast.company}, no a {company_id}.")
            entry = CashForecastEntry(
                forecast_id=entry_data["forecast_id"],
                type=entry_data["type"],
                concept=entry_data["concept"],
                currency=entry_data["currency"],
                amount=entry_data["amount"],
                estimated_date=entry_data["estimated_date"],
                notes=entry_data.get("notes", ""),
                created_by=entry_data.get("created_by"),
            )
            database.session.add(entry)
