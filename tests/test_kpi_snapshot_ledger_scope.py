# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1130: los KPI solo aceptan un libro de la compañía solicitada.

Un libro ajeno o inexistente no debe etiquetar el snapshot con una moneda
distinta ni devolver métricas aparentemente válidas.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Book, Currency, Entity, database
from cacao_accounting.reportes.analytics import get_kpi_snapshot


@pytest.fixture
def kpi_ledger_scenario():
    """Create two companies with books in different currencies."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name=f"Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="USD",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        alpha_book = Book(
            entity="alpha", code=f"ALPHA-{suffix}", name="Libro Alfa", status="activo", is_primary=True, currency="NIO"
        )
        beta_book = Book(
            entity="beta", code=f"BETA-{suffix}", name="Libro Beta", status="activo", is_primary=True, currency="USD"
        )
        database.session.add_all([alpha_book, beta_book])
        database.session.commit()
        ids = {
            "alpha_book_code": alpha_book.code,
            "alpha_book_id": alpha_book.id,
            "beta_book_code": beta_book.code,
            "beta_book_id": beta_book.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_kpi_snapshot_rejects_book_from_another_company(kpi_ledger_scenario):
    """A foreign book ID or code cannot set the KPI currency."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["beta_book_id"])
        with pytest.raises(ValueError):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["beta_book_code"])


def test_kpi_snapshot_rejects_unknown_book(kpi_ledger_scenario):
    """An unknown ledger is rejected instead of returning empty GL metrics."""
    app, _ids = kpi_ledger_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger="NO-SUCH-BOOK")


def test_kpi_snapshot_accepts_own_book_by_code_and_id(kpi_ledger_scenario):
    """The company's book works by code or ULID and keeps its currency."""
    app, ids = kpi_ledger_scenario

    with app.app_context():
        by_code = get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["alpha_book_code"])
        by_id = get_kpi_snapshot("alpha", date(2026, 1, 1), date(2026, 12, 31), ledger=ids["alpha_book_id"])

    assert by_code["currency"] == "NIO"
    assert by_id["currency"] == "NIO"
