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
    """Posting rechaza tasa cero con mensaje especifico de tasa invalida."""
    from cacao_accounting.contabilidad.posting_service import InvalidExchangeRateError, PostingError, _document_contexts
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
    with pytest.raises(PostingError, match="tipo de cambio debe ser mayor que cero"):
        _document_contexts(document)
    with pytest.raises(InvalidExchangeRateError, match="tipo de cambio debe ser mayor que cero"):
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
    assert effective_currency(None) is None


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


# --------------------------------------------------------------------------- #
# Primitivas del contrato (resolver, validation, context)
# --------------------------------------------------------------------------- #


def test_assert_currency_explicit_returns_currency(app_ctx):
    from cacao_accounting.document_flow.currency_resolver import assert_currency_explicit

    document = SimpleNamespace(transaction_currency="USD")
    assert assert_currency_explicit(document, context="documento") == "USD"


def test_assert_currency_explicit_rejects_missing(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_currency_explicit

    with pytest.raises(DocumentFlowError, match="transaction_currency explicita"):
        assert_currency_explicit(SimpleNamespace(transaction_currency=None), context="documento")


def test_assert_currency_explicit_rejects_blank(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_currency_explicit

    with pytest.raises(DocumentFlowError, match="transaction_currency explicita"):
        assert_currency_explicit(SimpleNamespace(transaction_currency="  "), context="documento")


def test_assert_base_currency_snapshot_accepts_matching(app_ctx):
    from cacao_accounting.document_flow.currency_resolver import assert_base_currency_snapshot

    document = SimpleNamespace(base_currency="NIO")
    assert assert_base_currency_snapshot(document, company="cacao", context="documento") == "NIO"


def test_assert_base_currency_snapshot_rejects_mismatch(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_base_currency_snapshot

    with pytest.raises(DocumentFlowError, match="no coincide con la moneda funcional"):
        assert_base_currency_snapshot(SimpleNamespace(base_currency="USD"), company="cacao", context="documento")


def test_assert_base_currency_snapshot_rejects_missing(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_base_currency_snapshot

    with pytest.raises(DocumentFlowError, match="snapshot de base_currency"):
        assert_base_currency_snapshot(SimpleNamespace(base_currency=None), company="cacao", context="documento")


def test_source_transaction_currencies_collects_all(app_ctx):
    from cacao_accounting.document_flow.currency_resolver import source_transaction_currencies

    sources = [SimpleNamespace(transaction_currency="USD"), SimpleNamespace(transaction_currency="USD")]
    assert source_transaction_currencies(sources) == ["USD", "USD"]


def test_source_transaction_currencies_rejects_missing(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import source_transaction_currencies

    with pytest.raises(DocumentFlowError, match="moneda transaccional explicita"):
        source_transaction_currencies([SimpleNamespace(transaction_currency=None)])


def test_resolve_party_currency_uses_default(app_ctx):
    from cacao_accounting.document_flow.currency_resolver import resolve_party_currency

    assert resolve_party_currency(SimpleNamespace(default_currency="USD")) == "USD"


def test_resolve_party_currency_none_without_currency(app_ctx):
    from cacao_accounting.document_flow.currency_resolver import resolve_party_currency

    assert resolve_party_currency(SimpleNamespace(default_currency=None, currency=None)) is None
    assert resolve_party_currency(None) is None


def test_collect_sources_from_relations_skips_empty(app_ctx):
    from cacao_accounting.document_flow.currency_resolver import collect_sources_from_relations

    source = SimpleNamespace(transaction_currency="USD")
    document = SimpleNamespace(source_relations=[SimpleNamespace(source=source), SimpleNamespace(source=None)])
    assert collect_sources_from_relations(document) == [source]


def test_assert_currency_contract_or_raise_homogeneous(app_ctx):
    from cacao_accounting.document_flow.validation import assert_currency_contract_or_raise

    document = SimpleNamespace(company="cacao", transaction_currency="USD", base_currency="NIO")
    sources = [SimpleNamespace(transaction_currency="USD")]
    assert assert_currency_contract_or_raise(document, context="documento", sources=sources) is None


def test_assert_currency_contract_or_raise_rejects_heterogeneous(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.validation import assert_currency_contract_or_raise

    document = SimpleNamespace(company="cacao", transaction_currency="USD", base_currency="NIO")
    sources = [SimpleNamespace(transaction_currency="USD"), SimpleNamespace(transaction_currency="EUR")]
    with pytest.raises(DocumentFlowError, match="moneda"):
        assert_currency_contract_or_raise(document, context="documento", sources=sources)


def test_validate_currency_contract_requires_base_snapshot(app_ctx):
    from cacao_accounting.database import StockEntry
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.validation import validate_currency_contract

    document = StockEntry(
        company="cacao", posting_date=date(2026, 5, 4), purpose="material_receipt", transaction_currency="USD", docstatus=1
    )
    with pytest.raises(DocumentFlowError, match="base_currency"):
        validate_currency_contract(document, context="stock_entry")


def test_validate_immutable_header_accepts_source(app_ctx):
    from cacao_accounting.document_flow.context import validate_immutable_header

    source = SimpleNamespace(company="cacao", transaction_currency="USD")
    company, currency = validate_immutable_header(source, "cacao", "USD")
    assert company == "cacao"
    assert currency == "USD"
    company, currency = validate_immutable_header(None, "cacao", "USD")
    assert company == "cacao"
    assert currency == "USD"


def test_validate_immutable_header_rejects_source_without_currency(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.context import validate_immutable_header

    source = SimpleNamespace(company="cacao", transaction_currency=None)
    with pytest.raises(DocumentFlowError, match="moneda transaccional explicita"):
        validate_immutable_header(source, "cacao", "USD")


def test_validate_immutable_header_rejects_company_mismatch(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.context import validate_immutable_header

    source = SimpleNamespace(company="cacao", transaction_currency="USD")
    with pytest.raises(DocumentFlowError, match="compania debe coincidir"):
        validate_immutable_header(source, "otra", "USD")


def test_validate_immutable_header_rejects_currency_mismatch(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.context import validate_immutable_header

    source = SimpleNamespace(company="cacao", transaction_currency="USD")
    with pytest.raises(DocumentFlowError, match="moneda debe coincidir"):
        validate_immutable_header(source, "cacao", "EUR")


# --------------------------------------------------------------------------- #
# Cambios de dominio: rechazo sin moneda explicita
# --------------------------------------------------------------------------- #


def test_set_sales_document_totals_rejects_missing_currency(app_ctx):
    from cacao_accounting.ventas.services import _set_sales_document_totals

    document = SimpleNamespace(company="cacao", transaction_currency=None, posting_date=date(2026, 5, 4))
    with pytest.raises(ValueError, match="moneda transaccional explicita"):
        _set_sales_document_totals(document, Decimal("100"))


def test_set_purchase_receipt_totals_rejects_missing_currency(app_ctx):
    from cacao_accounting.compras.services import _set_purchase_receipt_totals

    receipt = SimpleNamespace(company="cacao", transaction_currency=None)
    with pytest.raises(ValueError, match="moneda transaccional explicita"):
        _set_purchase_receipt_totals(receipt, Decimal("100"))


def test_set_purchase_document_totals_rejects_missing_currency(app_ctx):
    from cacao_accounting.compras.services import _set_purchase_document_totals

    document = SimpleNamespace(company="cacao", transaction_currency=None)
    with pytest.raises(ValueError, match="moneda transaccional explicita"):
        _set_purchase_document_totals(document, Decimal("100"))


def test_sales_invoice_currency_and_rate_inherits_source_rate(app_ctx):
    from cacao_accounting.ventas.services import _sales_invoice_currency_and_rate

    source = SimpleNamespace(transaction_currency="USD", exchange_rate=Decimal("36.5"))
    transaction_currency, base_currency, rate = _sales_invoice_currency_and_rate("cacao", date(2026, 5, 4), source, "USD")
    assert transaction_currency == "USD"
    assert base_currency == "NIO"
    assert rate == Decimal("36.5")


def test_sales_invoice_currency_and_rate_rejects_override(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.ventas.services import _sales_invoice_currency_and_rate

    source = SimpleNamespace(transaction_currency="USD", exchange_rate=Decimal("36.5"))
    with pytest.raises(DocumentFlowError, match="heredada"):
        _sales_invoice_currency_and_rate("cacao", date(2026, 5, 4), source, "EUR")


# --------------------------------------------------------------------------- #
# Ramas restantes del contrato (prelacion por tercero, fuentes vacias y 404)
# --------------------------------------------------------------------------- #


def test_resolve_party_currency_when_no_user_selection(app_ctx):
    """Sin eleccion de usuario ni origen, la moneda del tercero gana sobre la compania."""
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    party = SimpleNamespace(default_currency="USD")
    resolved = resolve_transaction_currency(company="cacao", party=party, context="documento")
    assert resolved.transaction_currency == "USD"
    assert resolved.base_currency == "NIO"
    assert resolved.source == "party"


def test_resolve_rejects_blank_user_selection(app_ctx):
    """Una moneda seleccionada en blanco no pasa la primitiva de moneda explicita."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import resolve_transaction_currency

    with pytest.raises(DocumentFlowError, match="moneda transaccional explicita"):
        resolve_transaction_currency(company="cacao", user_selection="   ", context="documento")


def test_company_functional_currency_none_for_missing_company(app_ctx):
    """Compania inexistente no produce moneda funcional (sin inferencia)."""
    from cacao_accounting.document_flow.currency_resolver import company_functional_currency

    assert company_functional_currency("no-existe") is None
    assert company_functional_currency(None) is None
    assert company_functional_currency("") is None


def test_company_functional_currency_none_without_entity_currency(app_ctx):
    """Compania sin moneda funcional configurada devuelve ``None``, nunca una inferencia."""
    from cacao_accounting.database import Entity, database
    from cacao_accounting.document_flow.currency_resolver import company_functional_currency

    database.session.add(Entity(code="sin-moneda", name="Sin moneda", company_name="Sin moneda", tax_id="J0002"))
    database.session.commit()
    assert company_functional_currency("sin-moneda") is None


def test_source_transaction_currencies_empty(app_ctx):
    """Sin origenes, la lista de monedas transaccionales es vacia."""
    from cacao_accounting.document_flow.currency_resolver import source_transaction_currencies

    assert source_transaction_currencies([]) == []
    assert source_transaction_currencies(None) == []


def test_validate_flow_currency_homogeneity_empty(app_ctx):
    """Sin origenes no hay moneda comun que validar."""
    from cacao_accounting.document_flow.currency_resolver import validate_flow_currency_homogeneity

    assert validate_flow_currency_homogeneity([]) is None
    assert validate_flow_currency_homogeneity(None) is None


def test_assert_currency_explicit_rejects_none_document(app_ctx):
    """Un documento inexistente se rechaza con 404 en la validacion de moneda."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_currency_explicit

    with pytest.raises(DocumentFlowError) as exc:
        assert_currency_explicit(None, context="documento")
    assert exc.value.status_code == 404


def test_assert_base_currency_snapshot_rejects_none_document(app_ctx):
    """Un documento inexistente se rechaza con 404 en la validacion de snapshot base."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_base_currency_snapshot

    with pytest.raises(DocumentFlowError) as exc:
        assert_base_currency_snapshot(None, company="cacao", context="documento")
    assert exc.value.status_code == 404


def test_assert_base_currency_snapshot_rejects_company_without_functional_currency(app_ctx):
    """Sin moneda funcional de compania, el snapshot base no puede validarse."""
    from cacao_accounting.database import Entity, database
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.currency_resolver import assert_base_currency_snapshot

    database.session.add(Entity(code="sin-moneda", name="Sin moneda", company_name="Sin moneda", tax_id="J0002"))
    database.session.commit()
    document = SimpleNamespace(base_currency="NIO")
    with pytest.raises(DocumentFlowError, match="moneda funcional configurada"):
        assert_base_currency_snapshot(document, company="sin-moneda", context="documento")


def test_collect_sources_from_relations_without_collection(app_ctx):
    """Sin atributo de relaciones, no hay origenes que recopilar."""
    from cacao_accounting.document_flow.currency_resolver import collect_sources_from_relations

    assert collect_sources_from_relations(SimpleNamespace()) == []


def test_assert_currency_contract_or_raise_rejects_currency_mismatch(app_ctx):
    """La variante con fuentes externas rechaza un documento cuya moneda difiere del origen."""
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.validation import assert_currency_contract_or_raise

    document = SimpleNamespace(company="cacao", transaction_currency="USD", base_currency="NIO")
    sources = [SimpleNamespace(transaction_currency="EUR")]
    with pytest.raises(DocumentFlowError, match="no coincide con la moneda"):
        assert_currency_contract_or_raise(document, context="documento", sources=sources)


def test_validate_currency_contract_rejects_source_currency_mismatch(app_ctx):
    """Al aprobar, el documento derivado no puede diferir de la moneda de su origen persistido."""
    from cacao_accounting.database import DocumentRelation, StockEntry, database
    from cacao_accounting.document_flow import DocumentFlowError
    from cacao_accounting.document_flow.validation import validate_currency_contract

    source = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="EUR",
        base_currency="NIO",
    )
    target = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        transaction_currency="USD",
        base_currency="NIO",
    )
    database.session.add_all([source, target])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="stock_entry",
            source_id=source.id,
            target_type="stock_entry",
            target_id=target.id,
            company="cacao",
            qty=Decimal("1"),
            amount=Decimal("1"),
            relation_type="transfer",
            status="active",
        )
    )
    database.session.commit()
    with pytest.raises(DocumentFlowError, match="no coincide con la moneda heredada"):
        validate_currency_contract(target, context="stock_entry")


def test_validate_currency_contract_accepts_matching_source(app_ctx):
    """Al aprobar, un documento derivado con la moneda heredada del origen se acepta."""
    from cacao_accounting.database import DocumentRelation, StockEntry, database
    from cacao_accounting.document_flow.validation import validate_currency_contract

    source = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="USD",
        base_currency="NIO",
    )
    target = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        transaction_currency="USD",
        base_currency="NIO",
    )
    database.session.add_all([source, target])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="stock_entry",
            source_id=source.id,
            target_type="stock_entry",
            target_id=target.id,
            company="cacao",
            qty=Decimal("1"),
            amount=Decimal("1"),
            relation_type="transfer",
            status="active",
        )
    )
    database.session.commit()
    assert validate_currency_contract(target, context="stock_entry") is None


def test_collect_currency_sources_unpersisted_document_returns_empty(app_ctx):
    """Un documento sin id persistido no puede tener origenes de Document Flow."""
    from cacao_accounting.database import StockEntry
    from cacao_accounting.document_flow.validation import _collect_currency_sources

    document = StockEntry(company="cacao")
    assert _collect_currency_sources(document) == []


def test_collect_currency_sources_skips_unknown_and_empty_sources(app_ctx):
    """Los origenes sin tipo registrado o sin ids se omiten sin error."""
    from cacao_accounting.database import DocumentRelation, StockEntry, database
    from cacao_accounting.document_flow.validation import _collect_currency_sources

    target = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        transaction_currency="USD",
        base_currency="NIO",
    )
    database.session.add(target)
    database.session.flush()
    database.session.add_all(
        [
            DocumentRelation(
                source_type="bank_transaction",
                source_id="legacy",
                target_type="stock_entry",
                target_id=target.id,
                company="cacao",
                qty=Decimal("1"),
                amount=Decimal("1"),
                relation_type="transfer",
                status="active",
            ),
            DocumentRelation(
                source_type="",
                source_id="",
                target_type="stock_entry",
                target_id=target.id,
                company="cacao",
                qty=Decimal("1"),
                amount=Decimal("1"),
                relation_type="transfer",
                status="active",
            ),
        ]
    )
    database.session.commit()
    assert _collect_currency_sources(target) == []


def test_posting_rejects_company_without_functional_currency(app_ctx):
    """Posting rechaza una compania sin moneda funcional configurada."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _document_contexts
    from cacao_accounting.database import Entity, StockEntry, database

    database.session.add(Entity(code="sin-moneda", name="Sin moneda", company_name="Sin moneda", tax_id="J0002"))
    database.session.commit()
    document = StockEntry(
        company="sin-moneda",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        transaction_currency="NIO",
        base_currency="NIO",
    )
    with pytest.raises(PostingError, match="moneda funcional configurada"):
        _document_contexts(document)


def test_ledger_exchange_rate_fiscal_year_closing_returns_one(app_ctx):
    """Un cierre de ano fiscal convierte a tasa 1 sin consultar la tabla historica."""
    from cacao_accounting.contabilidad.posting_service import _ledger_exchange_rate

    rate = _ledger_exchange_rate(
        transaction_currency="USD",
        ledger_currency="EUR",
        document_base_currency="NIO",
        document_exchange_rate=None,
        posting_date=date(2026, 5, 4),
        is_fiscal_year_closing=True,
    )
    assert rate == Decimal("1")
