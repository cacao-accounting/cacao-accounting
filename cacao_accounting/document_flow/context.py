# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Helpers for immutable header values in document-flow forms.

Refs: #758

La regla de no-inferencia de moneda aplica tambien a las cabeceras heredadas.
Un documento sin ``transaction_currency`` explicita no debe poder pasar como
origen de un derivado; de lo contrario se reintroduce el fallback silencioso
que el issue busca eliminar.
"""

from __future__ import annotations

from typing import Any

from cacao_accounting.database import Entity, database
from cacao_accounting.document_flow import DocumentFlowError


def effective_currency(document: Any | None) -> str | None:
    """Return a document currency, never falling back to the company currency.

    Si el documento no tiene ``transaction_currency`` explicita devuelve
    ``None``. La inferencia silenciosa desde la compania fue retirada en
    cumplimiento del contrato de moneda completa del issue #758.
    """
    if document is None:
        return None
    value = getattr(document, "transaction_currency", None)
    return str(value) if value else None


def company_currency(company: str | None) -> str | None:
    """Return the accounting base currency configured for a company."""
    entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalars().first() if company else None
    return str(entity.currency) if entity and entity.currency else None


def validate_immutable_header(source: Any | None, company: str | None, currency: str | None) -> tuple[str | None, str | None]:
    """Validate and resolve company/currency inherited from a source document."""
    if source is None:
        return company, currency
    source_company = getattr(source, "company", None)
    source_currency = effective_currency(source)
    if not source_currency:
        raise DocumentFlowError(
            "El documento origen no tiene moneda transaccional explicita; no se permite inferirla desde la compania.",
            400,
        )
    if company != source_company:
        raise DocumentFlowError("La compania debe coincidir con el documento origen.", 400)
    if source_currency and currency and currency != source_currency:
        raise DocumentFlowError("La moneda debe coincidir con el documento origen.", 400)
    return source_company, source_currency or currency
