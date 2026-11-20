# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1877: durante el posting, la escritura interna de líneas del movimiento está permitida."""

from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, StockEntry, StockEntryItem, UOM, database


@pytest.fixture
def app_controles():
    """Aplicación Cloud con controles internos activos (#1877)."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-worker-secret",
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_updates_on_posted_lines_allowed_only_during_posting(app_controles):
    """Los cambios internos de posting quedan bloqueados después de la transacción (#1877)."""
    with app_controles.app_context():
        database.session.add(UOM(code="UNI-X", name="Unidad X"))
        database.session.flush()
        database.session.add(
            Item(code="ART-X", name="Articulo X", item_type="goods", is_stock_item=False, default_uom="UNI-X")
        )
        database.session.flush()
        entry = StockEntry(company="cacao", purpose="stock_reconciliation", docstatus=0)
        database.session.add(entry)
        database.session.flush()
        item = StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ART-X",
            qty=Decimal("10"),
            uom="UNI-X",
            qty_in_base_uom=Decimal("10"),
        )
        database.session.add(item)
        database.session.commit()

        entry.docstatus = 1
        database.session.flush()

        item.current_qty = Decimal("10")
        item.counted_qty = Decimal("8")
        item.qty = Decimal("2")
        database.session.flush()

        persisted = database.session.get(StockEntryItem, item.id)
        assert persisted is not None
        assert persisted.current_qty == Decimal("10")
        assert persisted.counted_qty == Decimal("8")

        database.session.commit()

        item = database.session.get(StockEntryItem, item.id)
        item.current_qty = Decimal("5")
        with pytest.raises(ValueError, match="inmutables"):
            database.session.flush()
