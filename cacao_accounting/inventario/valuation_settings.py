# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Helpers para administrar la valuacion global de inventario por compania."""

from __future__ import annotations

from cacao_accounting.database import Entity, StockLedgerEntry, StockValuationLayer, database

MOVING_AVERAGE = "moving_average"
FIFO = "fifo"
VALUATION_METHOD_CHOICES = (
    (MOVING_AVERAGE, "Costo promedio"),
    (FIFO, "FIFO"),
)
VALUATION_METHOD_LABELS = dict(VALUATION_METHOD_CHOICES)


def valuation_method_choices() -> list[tuple[str, str]]:
    """Devuelve las opciones permitidas para la valuacion global."""
    return list(VALUATION_METHOD_CHOICES)


def valuation_method_label(method: str | None) -> str:
    """Devuelve la etiqueta visible del metodo de valuacion."""
    return VALUATION_METHOD_LABELS.get(normalize_valuation_method(method), VALUATION_METHOD_LABELS[MOVING_AVERAGE])


def normalize_valuation_method(method: str | None) -> str:
    """Normaliza un metodo de valuacion y aplica el default del sistema."""
    value = (method or MOVING_AVERAGE).strip().lower()
    if value not in VALUATION_METHOD_LABELS:
        raise ValueError("El metodo de valuacion seleccionado no es valido.")
    return value


def get_company_valuation_method(company_code: str) -> str:
    """Obtiene el metodo de valuacion configurado para una compania."""
    entity = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
    if entity is None:
        raise ValueError("La compania seleccionada no existe.")
    return normalize_valuation_method(entity.valuation_method)


def company_has_inventory_activity(company_code: str) -> bool:
    """Indica si la compania ya tiene operacion real de inventario."""
    stock_ledger_exists = database.session.execute(
        database.select(StockLedgerEntry.id).filter_by(company=company_code).limit(1)
    ).scalar_one_or_none()
    if stock_ledger_exists is not None:
        return True

    valuation_layer_exists = database.session.execute(
        database.select(StockValuationLayer.id).filter_by(company=company_code).limit(1)
    ).scalar_one_or_none()
    return valuation_layer_exists is not None


def update_company_valuation_method(company_code: str, method: str) -> Entity:
    """Actualiza el metodo de valuacion de una compania si el cambio esta permitido."""
    normalized_method = normalize_valuation_method(method)
    entity = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
    if entity is None:
        raise ValueError("La compania seleccionada no existe.")

    current_method = normalize_valuation_method(entity.valuation_method)
    if current_method == normalized_method:
        return entity

    if company_has_inventory_activity(company_code):
        raise ValueError("No se puede cambiar la valuacion porque la compania ya tiene operacion de inventario.")

    entity.valuation_method = normalized_method
    database.session.add(entity)
    return entity


def list_companies_with_valuation() -> list[dict[str, str]]:
    """Lista companias con su metodo actual de valuacion para la vista admin."""
    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    return [
        {
            "code": company.code,
            "label": f"{company.code} - {company.name or company.company_name}",
            "valuation_method": normalize_valuation_method(company.valuation_method),
            "valuation_label": valuation_method_label(company.valuation_method),
        }
        for company in companies
    ]
