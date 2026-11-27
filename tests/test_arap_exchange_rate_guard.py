# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El ledger AR/AP nunca inventa una tasa para monedas distintas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting import PostingError
from cacao_accounting.contabilidad.arap_ledger_service import _book_exchange_rate
from cacao_accounting.database import Currency, Entity, ExchangeRate, database


@pytest.fixture
def arap_currency_app():
    """Crea catálogo de monedas aislado para resolver tasas por libro."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", active=True),
                Currency(code="USD", name="Dólar", active=True),
                Currency(code="EUR", name="Euro", active=True),
                Currency(code="GBP", name="Libra", active=True),
            ]
        )
        database.session.flush()
        database.session.add(Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="T-ARAP", currency="NIO"))
        database.session.flush()
        database.session.add_all(
            [
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 8, 1)),
                ExchangeRate(origin="EUR", destination="NIO", rate=Decimal("40"), date=date(2026, 8, 1)),
            ]
        )
        database.session.commit()
        yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_book_exchange_rate_uses_direct_inverse_and_functional_fallback(arap_currency_app):
    """Las tasas disponibles se resuelven por libro sin confundir monedas."""
    with arap_currency_app.app_context():
        as_of = date(2026, 8, 2)

        assert _book_exchange_rate("cacao", "USD", "NIO", as_of, Decimal("0")) == Decimal("36")
        assert _book_exchange_rate("cacao", "NIO", "EUR", as_of, Decimal("1")) == Decimal("0.025")
        assert _book_exchange_rate("cacao", "GBP", "NIO", as_of, Decimal("5")) == Decimal("5")
        assert _book_exchange_rate("cacao", "GBP", "GBP", as_of, Decimal("0")) == Decimal("1")


def test_book_exchange_rate_rejects_missing_nonfunctional_conversion(arap_currency_app):
    """Sin tasa directa, inversa o funcional no se crea una valoración ficticia."""
    with arap_currency_app.app_context():
        with pytest.raises(PostingError, match="No existe tipo de cambio registrado"):
            _book_exchange_rate("cacao", "GBP", "EUR", date(2026, 8, 2), Decimal("0"))
