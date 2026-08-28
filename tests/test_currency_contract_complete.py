# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del contrato de moneda completa (transaccional + base) en posting y derivados.

El issue exige que:

- Todo documento aprobable tenga ``transaction_currency`` y ``base_currency`` persistidos.
- El backend rechace payloads sin moneda transaccional explicita (sin inferencia silenciosa).
- El posting acumule y reporte todas las tasas faltantes en un solo mensaje.
- Los origenes de Document Flow compartan moneda o se rechace la derivacion.
- El usuario no pueda sobrescribir la moneda heredada por Document Flow.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Crea un contexto de aplicacion aislado para pruebas de contrato de moneda."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import (
            Book,
            Currency,
            Entity,
            PurchaseMatchingConfig,
            database,
        )

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True),
                Currency(code="USD", name="US Dollar", decimals=2, active=True),
                Currency(code="EUR", name="Euro", decimals=2, active=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                ),
                Book(
                    code="PRIMARY",
                    name="Libro principal",
                    entity="cacao",
                    currency="NIO",
                    is_primary=True,
                ),
                PurchaseMatchingConfig(company="cacao", require_purchase_order=False),
            ]
        )
        database.session.commit()
        yield app


@pytest.fixture()
def multi_book_ctx(app_ctx):
    """Extiende el contexto con un segundo libro en EUR y una tasa historica."""
    from cacao_accounting.database import Book, ExchangeRate, database

    database.session.add_all(
        [
            Book(
                code="EUR-BOOK",
                name="Libro consolidacion",
                entity="cacao",
                currency="EUR",
                status="activo",
            ),
            ExchangeRate(
                origin="USD",
                destination="NIO",
                rate=Decimal("36.5"),
                date=date(2026, 5, 4),
            ),
        ]
    )
    database.session.commit()
    return app_ctx


# --------------------------------------------------------------------------- #
# Prelacion y Document Flow
# --------------------------------------------------------------------------- #


def test_resolve_user_explicit_currency_wins(app_ctx):
    """Si el usuario eligio moneda, gana sobre tercero y compania."""
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    resolved = resolve_transaction_currency(
        company="cacao",
        user_selection="USD",
        context="documento",
    )
    assert resolved.transaction_currency == "USD"
    assert resolved.base_currency == "NIO"
    assert resolved.source == "user"


def test_resolve_company_default_when_no_party_or_user(app_ctx):
    """Sin eleccion de usuario ni origen, se usa la moneda funcional de la compania."""
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    resolved = resolve_transaction_currency(company="cacao", context="documento")
    assert resolved.transaction_currency == "NIO"
    assert resolved.base_currency == "NIO"
    assert resolved.source == "company"


def test_resolve_inherited_currency_from_source(app_ctx):
    """Cuando hay origen de Document Flow, la moneda se hereda."""
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    source = SimpleNamespace(transaction_currency="USD")
    resolved = resolve_transaction_currency(
        company="cacao",
        sources=[source],
        context="documento derivado",
    )
    assert resolved.transaction_currency == "USD"
    assert resolved.base_currency == "NIO"
    assert resolved.source == "source"


def test_resolve_rejects_user_override_of_inherited_currency(app_ctx):
    """El usuario no puede sobrescribir la moneda heredada por Document Flow."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    source = SimpleNamespace(transaction_currency="USD")
    with pytest.raises(DocumentFlowError, match="no puede diferir de la heredada"):
        resolve_transaction_currency(
            company="cacao",
            user_selection="EUR",
            sources=[source],
            context="documento derivado",
        )


def test_resolve_rejects_heterogeneous_sources(app_ctx):
    """Multiples origenes con monedas distintas se rechazan antes de crear el derivado."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import validate_flow_currency_homogeneity

    source_a = SimpleNamespace(transaction_currency="USD")
    source_b = SimpleNamespace(transaction_currency="EUR")
    with pytest.raises(DocumentFlowError, match="monedas distintas"):
        validate_flow_currency_homogeneity([source_a, source_b])


def test_resolve_rejects_source_without_currency(app_ctx):
    """Un origen sin moneda explicita no se infiere desde la compania."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import validate_flow_currency_homogeneity

    legacy_source = SimpleNamespace(transaction_currency=None)
    with pytest.raises(DocumentFlowError, match="moneda transaccional explicita"):
        validate_flow_currency_homogeneity([legacy_source])


def test_resolve_homogeneous_sources_share_currency(app_ctx):
    """Multiples origenes con la misma moneda producen una sola moneda comun."""
    from cacao_accounting.document_flow.currency_resolver import validate_flow_currency_homogeneity

    source_a = SimpleNamespace(transaction_currency="USD")
    source_b = SimpleNamespace(transaction_currency="USD")
    assert validate_flow_currency_homogeneity([source_a, source_b]) == "USD"


# --------------------------------------------------------------------------- #
# Posting rechaza contexto incompleto
# --------------------------------------------------------------------------- #


def test_posting_rejects_document_without_transaction_currency(app_ctx):
    """Posting rechaza un documento sin ``transaction_currency`` persistida."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import StockEntry

    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        base_currency="NIO",
        docstatus=1,
    )
    with pytest.raises(PostingError, match="moneda transaccional"):
        _document_contexts(document)


def test_posting_rejects_document_without_base_currency_snapshot(app_ctx):
    """Posting rechaza un documento sin snapshot de ``base_currency``."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import StockEntry

    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="NIO",
        docstatus=1,
    )
    with pytest.raises(PostingError, match="snapshot explicito de base_currency"):
        _document_contexts(document)


def test_posting_rejects_book_without_destination_currency(app_ctx):
    """Posting rechaza un libro activo sin moneda destino configurada."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import Book, StockEntry, database

    database.session.add(Book(entity="cacao", code="NO-CURRENCY", name="Libro incompleto", currency=None, status="activo"))
    database.session.commit()
    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
    )
    with pytest.raises(PostingError, match="NO-CURRENCY.*moneda funcional"):
        _document_contexts(document)


def test_posting_rejects_base_currency_snapshot_mismatch(app_ctx):
    """Posting rechaza un documento cuyo ``base_currency`` ya no coincide con la compania."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import StockEntry

    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="USD",
        base_currency="USD",
        docstatus=1,
    )
    with pytest.raises(PostingError, match="no coincide con la moneda funcional vigente"):
        _document_contexts(document)


def test_posting_rejects_zero_exchange_rate(app_ctx):
    """Posting rechaza tasa cero en documento con monedas distintas."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import StockEntry

    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("0"),
        docstatus=1,
    )
    with pytest.raises(PostingError, match="Faltan tipos de cambio"):
        _document_contexts(document)


def test_posting_aggregates_all_missing_rates_per_book(multi_book_ctx):
    """Si faltan varias tasas, el posting las reporta juntas en un solo error."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import StockEntry

    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="USD",
        base_currency="NIO",
        docstatus=1,
    )
    with pytest.raises(PostingError) as exc_info:
        _document_contexts(document)
    message = str(exc_info.value)
    assert "Faltan tipos de cambio" in message
    assert "EUR-BOOK" in message
    assert "USD -> EUR" in message


def test_posting_reports_missing_rate_for_each_book_without_rate(multi_book_ctx):
    """Cuando ambos libros carecen de tasa, ambos aparecen en el reporte."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import ExchangeRate, StockEntry, database

    database.session.execute(
        database.delete(ExchangeRate).where(ExchangeRate.origin == "USD", ExchangeRate.destination == "NIO")
    )
    database.session.commit()
    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="USD",
        base_currency="NIO",
        docstatus=1,
    )
    with pytest.raises(PostingError) as exc_info:
        _document_contexts(document)
    message = str(exc_info.value)
    assert "Faltan tipos de cambio" in message
    assert "PRIMARY" in message
    assert "EUR-BOOK" in message
    assert "USD -> NIO" in message
    assert "USD -> EUR" in message


# --------------------------------------------------------------------------- #
# Conversion atomica por libro
# --------------------------------------------------------------------------- #


def test_posting_returns_one_context_per_active_book(multi_book_ctx):
    """Con todas las tasas presentes, posting devuelve un contexto por libro."""
    from cacao_accounting.contabilidad.posting_service import _document_contexts
    from cacao_accounting.database import ExchangeRate, StockEntry, database

    database.session.add(ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.92"), date=date(2026, 5, 4)))
    database.session.commit()
    document = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="USD",
        base_currency="NIO",
        docstatus=1,
    )
    contexts = _document_contexts(document)
    assert len(contexts) == 2
    currencies = {context.company_currency for context in contexts}
    assert currencies == {"NIO", "EUR"}


# --------------------------------------------------------------------------- #
# Sin fallbacks silenciosos
# --------------------------------------------------------------------------- #


def test_effective_currency_does_not_fall_back_to_company(app_ctx):
    """``effective_currency`` ya no infiere desde la compania cuando no hay moneda explicita."""
    from cacao_accounting.document_flow.context import effective_currency

    document = SimpleNamespace(transaction_currency=None, company="cacao")
    assert effective_currency(document) is None


def test_inventory_currency_requires_persisted_base_snapshot(app_ctx):
    """``_inventory_currency`` exige el snapshot persistido, sin fallback a entidad."""
    from cacao_accounting.contabilidad.posting_service import _inventory_currency

    document = SimpleNamespace(base_currency=None)
    assert _inventory_currency(document) is None


def test_resolve_rejects_company_without_functional_currency(app_ctx):
    """Una compania sin moneda funcional hace fallar la resolucion."""
    from cacao_accounting.database import Entity, database
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    database.session.add(
        Entity(
            code="no-cur",
            name="Sin moneda",
            company_name="Sin moneda",
            tax_id="X",
            currency=None,
        )
    )
    database.session.commit()
    with pytest.raises(DocumentFlowError, match="moneda funcional configurada"):
        resolve_transaction_currency(company="no-cur", context="documento")
