# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#759: la evidencia de valoración por libro se protege en los motores Tier 1.

La matriz usa el motor configurado por la suite (SQLite local o el motor
externo habilitado con ``CHECK_DATABASE``) y conserva el aislamiento mediante
identificadores únicos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Book,
    Currency,
    Entity,
    Item,
    StockLedgerBookEntry,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)

pytestmark = pytest.mark.database


def _build_app(tmp_path, desktop: bool):
    """Use the configured engine, falling back to an isolated SQLite file."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'book-entry-matrix.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": desktop,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def _seed_entry(app) -> tuple[str, dict[str, object]]:
    """Persist one isolated book valuation and return its identity and values."""
    suffix = uuid4().hex[:8]
    company = f"E{suffix}"
    item_code = f"EITEM-{suffix}"
    warehouse = f"EWH-{suffix}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía libro matriz {suffix}",
                company_name=f"Compañía libro matriz {suffix}",
                tax_id=f"ETX-{suffix}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        database.session.add(
            Item(code=item_code, name="Artículo libro matriz", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.flush()
        database.session.add(Warehouse(code=warehouse, name="Bodega libro matriz", company=company))
        database.session.flush()
        book = Book(code=f"EB{suffix[:6]}", name="Libro matriz", entity=company, currency="NIO", status="activo")
        database.session.add(book)
        database.session.flush()
        movement = StockLedgerEntry(
            posting_date=date(2026, 5, 1),
            item_code=item_code,
            warehouse=warehouse,
            company=company,
            qty_change=Decimal("5"),
            qty_after_transaction=Decimal("5"),
            valuation_rate=Decimal("10"),
            stock_value_difference=Decimal("50"),
            stock_value=Decimal("50"),
            voucher_type="stock_entry",
            voucher_id=f"EV-{suffix}",
        )
        movement_alt = StockLedgerEntry(
            posting_date=date(2026, 5, 2),
            item_code=item_code,
            warehouse=warehouse,
            company=company,
            qty_change=Decimal("1"),
            qty_after_transaction=Decimal("6"),
            valuation_rate=Decimal("10"),
            stock_value_difference=Decimal("10"),
            stock_value=Decimal("60"),
            voucher_type="stock_entry",
            voucher_id=f"EV-ALT-{suffix}",
        )
        database.session.add_all([movement, movement_alt])
        database.session.flush()
        entry = StockLedgerBookEntry(
            stock_ledger_entry_id=movement.id,
            ledger_id=book.id,
            posting_date=movement.posting_date,
            book_currency="NIO",
            book_amount=Decimal("50"),
            exchange_rate=Decimal("36.5"),
        )
        database.session.add(entry)
        database.session.commit()
        snapshot = {
            "book_amount": entry.book_amount,
            "exchange_rate": entry.exchange_rate,
            "ledger_id": entry.ledger_id,
            "book_id": book.id,
            "movement_alt_id": movement_alt.id,
        }
        return entry.id, snapshot


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_rejects_book_entry_rewrite_on_configured_engine(tmp_path, desktop):
    """The mapped guard rejects book valuation changes on the configured engine."""
    app = _build_app(tmp_path, desktop)
    entry_id, snapshot = _seed_entry(app)

    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, entry_id)
        assert entry is not None
        entry.book_amount = Decimal("999")
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, entry_id)
        assert entry is not None
        assert entry.book_amount == snapshot["book_amount"]


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_delete_is_rejected_on_configured_engine(tmp_path, desktop):
    """Deleting a book valuation through the ORM is rejected."""
    app = _build_app(tmp_path, desktop)
    entry_id, snapshot = _seed_entry(app)

    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, entry_id)
        assert entry is not None
        database.session.delete(entry)
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, entry_id)
        assert entry is not None
        assert entry.ledger_id == snapshot["ledger_id"]


@pytest.mark.parametrize("desktop", [True, False])
def test_core_and_textual_writes_are_rejected_on_configured_engine(tmp_path, desktop):
    """Core and textual SQL cannot rewrite or delete book valuations."""
    app = _build_app(tmp_path, desktop)
    entry_id, snapshot = _seed_entry(app)

    with app.app_context():
        with pytest.raises(ValueError):
            database.session.execute(
                database.update(StockLedgerBookEntry)
                .where(StockLedgerBookEntry.id == entry_id)
                .values(exchange_rate=Decimal("99"))
            )
            database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                text("DELETE FROM stock_ledger_book_entry WHERE id = :row_id"),
                {"row_id": entry_id},
            )
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, entry_id)
        assert entry is not None
        assert entry.exchange_rate == snapshot["exchange_rate"]


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_insert_remains_open_on_configured_engine(tmp_path, desktop):
    """The append path can publish a new book valuation on the configured engine."""
    app = _build_app(tmp_path, desktop)
    entry_id, snapshot = _seed_entry(app)

    with app.app_context():
        new_entry = StockLedgerBookEntry(
            stock_ledger_entry_id=snapshot["movement_alt_id"],
            ledger_id=snapshot["book_id"],
            posting_date=date(2026, 5, 2),
            book_currency="NIO",
            book_amount=Decimal("10"),
            exchange_rate=Decimal("36.5"),
        )
        database.session.add(new_entry)
        database.session.commit()
        new_entry_id = new_entry.id

    with app.app_context():
        persisted = database.session.get(StockLedgerBookEntry, new_entry_id)
        assert persisted is not None
        assert persisted.book_amount == Decimal("10")
        original = database.session.get(StockLedgerBookEntry, entry_id)
        assert original is not None
        assert original.book_amount == snapshot["book_amount"]
