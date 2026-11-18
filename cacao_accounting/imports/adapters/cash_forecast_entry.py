# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de entradas de pronóstico de caja."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any

from cacao_accounting.database import CashForecast, CashForecastEntry, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.i18n import _


def _finite_amount(value: Any) -> Decimal:
    """Convierte el monto del pronóstico y rechaza valores no finitos."""
    try:
        amount = Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(_("Monto inválido: %(value)s") % {"value": value}) from exc
    if not amount.is_finite():
        raise ValueError(_("El monto debe ser finito."))
    return amount


def _text(value: Any, default: str = "") -> str:
    """Normaliza celdas vacías de XLSX/ODS sin convertirlas en "None"."""
    if value is None:
        return default
    text = str(value)
    return text if text.strip() else default


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
        forecast = database.session.get(CashForecast, _text(row_data.get("forecast_id")))
        if forecast is None:
            errors.append(f"Pronóstico no encontrado: {row_data.get('forecast_id')}")
        elif str(forecast.status or "") != "Draft":
            errors.append(f"El pronóstico {forecast.id} no está en estado Borrador.")
        if self._normalize_entry_type(row_data.get("type")) is None:
            errors.append(_("El tipo debe ser Income o Expense."))
        try:
            _finite_amount(row_data.get("amount"))
        except ValueError as exc:
            errors.append(str(exc))
        try:
            if isinstance(row_data.get("estimated_date"), str):
                date.fromisoformat(row_data["estimated_date"])
        except (ValueError, TypeError):
            errors.append(f"Fecha inválida: {row_data.get('estimated_date')}")
        return errors

    @staticmethod
    def _normalize_entry_type(value: Any) -> str | None:
        """Return the canonical cash forecast entry type when supported."""
        entry_type = str(value or "").strip().capitalize()
        if entry_type not in ("Income", "Expense"):
            return None
        return entry_type

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Validate that every forecast belongs to the import company."""
        company_id = (context or {}).get("company_id") or ""
        errors: list[str] = []
        checked_forecasts: dict[str, CashForecast | None] = {}
        for row in document_data:
            forecast_id = _text(row.get("forecast_id"))
            if forecast_id not in checked_forecasts:
                checked_forecasts[forecast_id] = database.session.get(CashForecast, forecast_id)
            forecast = checked_forecasts[forecast_id]
            if forecast and forecast.company != company_id:
                errors.append(f"El pronóstico {forecast_id} pertenece a la compañía {forecast.company}, no a {company_id}.")
            if forecast and str(forecast.status or "") != "Draft":
                errors.append(f"El pronóstico {forecast_id} no está en estado Borrador.")
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build cash forecast entries from the imported data."""
        entries = []
        for row in document_data:
            estimated_date = row.get("estimated_date")
            if isinstance(estimated_date, str):
                estimated_date = date.fromisoformat(estimated_date)
            entry_type = self._normalize_entry_type(row.get("type"))
            if entry_type is None:
                raise ValueError(_("El tipo debe ser Income o Expense."))
            entries.append(
                {
                    "forecast_id": _text(row.get("forecast_id")),
                    "type": entry_type,
                    "concept": _text(row.get("concept")),
                    "currency": _text(row.get("currency"), "NIO"),
                    "amount": _finite_amount(row.get("amount")),
                    "estimated_date": estimated_date,
                    "notes": _text(row.get("notes")),
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
                raise ValueError(_("Pronóstico no encontrado: %(forecast)s") % {"forecast": entry_data["forecast_id"]})
            if company_id and forecast.company != company_id:
                raise ValueError(
                    _("El pronóstico %(forecast)s pertenece a la compañía %(owner)s, no a %(company)s.")
                    % {"forecast": forecast.id, "owner": forecast.company, "company": company_id}
                )
            # #1049: revalidar el estado inmediatamente antes de persistir; el
            # pronóstico pudo aprobarse después de la validación del lote.
            if str(forecast.status or "") != "Draft":
                raise ValueError(_("El pronóstico %(forecast)s no está en estado Borrador.") % {"forecast": forecast.id})
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
