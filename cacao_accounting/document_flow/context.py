"""Helpers for immutable header values in document-flow forms."""

from __future__ import annotations

from typing import Any

from cacao_accounting.database import Entity, database
from cacao_accounting.document_flow import DocumentFlowError


def effective_currency(document: Any | None) -> str | None:
    """Return a document currency, falling back to its company currency."""
    if document is None:
        return None
    for attribute in ("transaction_currency", "currency", "base_currency"):
        value = getattr(document, attribute, None)
        if value:
            return str(value)
    return company_currency(getattr(document, "company", None))


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
    if company != source_company:
        raise DocumentFlowError("La compañía debe coincidir con el documento origen.", 400)
    if source_currency and currency and currency != source_currency:
        raise DocumentFlowError("La moneda debe coincidir con el documento origen.", 400)
    return source_company, source_currency or currency
