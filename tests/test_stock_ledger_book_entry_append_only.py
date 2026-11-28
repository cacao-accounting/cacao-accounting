# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#759: la valoración por libro del inventario es evidencia append-only.

``StockLedgerBookEntry`` publica el valor de cada movimiento de inventario en
cada libro activo. Esa fila alimenta los reportes multilibro y debe conservarse
como evidencia histórica: solo se agregan movimientos y contrapartidas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import post_stock_entry
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    Item,
    StockEntry,
    StockEntryItem,
    StockLedgerBookEntry,
    StockLedgerEntry,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)

BOOK_ENTRY_FIELDS = (
    "book_amount",
    "exchange_rate",
    "ledger_id",
    "posting_date",
    "book_currency",
    "stock_ledger_entry_id",
)


def _build_app(desktop: bool):
    """Create an isolated app with the structural guards explicitly enabled."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": desktop,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def _book_entry_snapshot(entry: StockLedgerBookEntry) -> dict[str, object]:
    """Return the persisted values that define the book valuation evidence."""
    return {name: getattr(entry, name) for name in BOOK_ENTRY_FIELDS}


def _seed_book_entry(app) -> dict[str, object]:
    """Persist one stock ledger movement and its valuation in two books."""
    suffix = uuid4().hex[:8]
    company = f"B{suffix}"
    item_code = f"BITEM-{suffix}"
    warehouse = f"BWH-{suffix}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Currency).filter_by(code="USD")).scalar_one_or_none() is None:
            database.session.add(Currency(code="USD", name="Dólar", decimals=2, active=True, default=False))
        if database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía libro {suffix}",
                company_name=f"Compañía libro {suffix}",
                tax_id=f"BTX-{suffix}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        database.session.add(
            Item(code=item_code, name="Artículo libro", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.flush()
        database.session.add(Warehouse(code=warehouse, name="Bodega libro", company=company))
        database.session.flush()
        book = Book(code=f"BK{suffix[:6]}", name="Libro NIO", entity=company, currency="NIO", status="activo")
        book_alt = Book(code=f"BA{suffix[:6]}", name="Libro USD", entity=company, currency="USD", status="activo")
        database.session.add_all([book, book_alt])
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
            voucher_id=f"BV-{suffix}",
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
            voucher_id=f"BV-ALT-{suffix}",
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
        seed = {
            "id": entry.id,
            "company": company,
            "item_code": item_code,
            "warehouse": warehouse,
            "book_id": book.id,
            "book_alt_id": book_alt.id,
            "movement_id": movement.id,
            "movement_alt_id": movement_alt.id,
            "snapshot": _book_entry_snapshot(entry),
        }
    return seed


def _tampered_value(field_name: str, seed: dict[str, object]):
    """Return a different valid value for each protected book-entry field."""
    values = {
        "book_amount": Decimal("999"),
        "exchange_rate": Decimal("99"),
        "ledger_id": seed["book_alt_id"],
        "posting_date": date(2030, 1, 1),
        "book_currency": "USD",
        "stock_ledger_entry_id": seed["movement_alt_id"],
    }
    return values[field_name]


def _assert_persisted_snapshot(app, seed: dict[str, object]) -> None:
    """Reload the book entry in a fresh context and compare its evidence."""
    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, seed["id"])
        assert entry is not None
        assert _book_entry_snapshot(entry) == seed["snapshot"]


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("field_name", BOOK_ENTRY_FIELDS)
def test_orm_rejects_book_entry_rewrite(field_name, desktop):
    """A mapped UPDATE cannot rewrite the book valuation evidence."""
    app = _build_app(desktop)
    seed = _seed_book_entry(app)

    with app.app_context():
        entry = database.session.get(StockLedgerBookEntry, seed["id"])
        assert entry is not None
        setattr(entry, field_name, _tampered_value(field_name, seed))
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("channel", ["core", "textual"])
@pytest.mark.parametrize("field_name", ["book_amount", "exchange_rate", "ledger_id"])
def test_bulk_rejects_book_entry_rewrite(channel, field_name, desktop):
    """Core and textual SQL cannot rewrite the book valuation evidence."""
    app = _build_app(desktop)
    seed = _seed_book_entry(app)
    value = _tampered_value(field_name, seed)

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "core":
                database.session.execute(
                    database.update(StockLedgerBookEntry)
                    .where(StockLedgerBookEntry.id == seed["id"])
                    .values({field_name: value})
                )
            else:
                database.session.execute(
                    text(f"UPDATE stock_ledger_book_entry SET {field_name} = :value WHERE id = :row_id"),
                    {"value": str(value), "row_id": seed["id"]},
                )
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
def test_delete_of_book_entry_is_rejected(channel, desktop):
    """No write path can physically remove a book valuation row."""
    app = _build_app(desktop)
    seed = _seed_book_entry(app)

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "orm":
                entry = database.session.get(StockLedgerBookEntry, seed["id"])
                assert entry is not None
                database.session.delete(entry)
            elif channel == "core":
                database.session.execute(database.delete(StockLedgerBookEntry).where(StockLedgerBookEntry.id == seed["id"]))
            else:
                database.session.execute(
                    text("DELETE FROM stock_ledger_book_entry WHERE id = :row_id"),
                    {"row_id": seed["id"]},
                )
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_insert_of_new_book_entry_remains_open(desktop):
    """The legitimate append path can still publish a new book valuation."""
    app = _build_app(desktop)
    seed = _seed_book_entry(app)

    with app.app_context():
        entry = StockLedgerBookEntry(
            stock_ledger_entry_id=seed["movement_alt_id"],
            ledger_id=seed["book_id"],
            posting_date=date(2026, 5, 2),
            book_currency="NIO",
            book_amount=Decimal("10"),
            exchange_rate=Decimal("36.5"),
        )
        database.session.add(entry)
        database.session.commit()
        entry_id = entry.id

    with app.app_context():
        persisted = database.session.get(StockLedgerBookEntry, entry_id)
        assert persisted is not None
        assert persisted.book_amount == Decimal("10")
        assert persisted.stock_ledger_entry_id == seed["movement_alt_id"]


def _post_adjustment(app, item_code: str, warehouse: str, purpose: str, qty: str, amount: str) -> StockEntry:
    """Persist and post a positive or negative stock adjustment."""
    entry = StockEntry(
        purpose=purpose,
        company="cacao",
        posting_date=date(2026, 5, 20),
        to_warehouse=warehouse,
        from_warehouse=warehouse,
        document_no=f"BKE-{uuid4().hex[:8]}",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code=item_code,
            source_warehouse=warehouse,
            target_warehouse=warehouse,
            qty=Decimal(qty),
            uom="UND",
            qty_in_base_uom=Decimal(qty),
            basic_rate=Decimal("10"),
            amount=Decimal(amount),
        )
    )
    database.session.commit()
    with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
        login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
        post_stock_entry(entry)
    return entry


def _seed_adjustment_scenario(app) -> tuple[str, str]:
    """Create the item, warehouse and accounts used by a posted adjustment."""
    suffix = uuid4().hex[:6].upper()
    item_code = f"BKI-{suffix}"
    warehouse = f"BKW-{suffix}"
    database.session.add(
        Item(code=item_code, name="Artículo libro GL", item_type="goods", is_stock_item=True, default_uom="UND")
    )
    database.session.add(Warehouse(code=warehouse, name="Bodega libro GL", company="cacao"))
    database.session.flush()
    inventory_account_id = database.session.execute(
        database.select(Accounts.id).filter_by(entity="cacao", code="1109")
    ).scalar_one()
    adjustment_account_id = database.session.execute(
        database.select(Accounts.id).filter_by(entity="cacao", code="5201")
    ).scalar_one()
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    for account_id in (inventory_account_id, adjustment_account_id):
        account = database.session.get(Accounts, account_id)
        account.active = True
        account.enabled = True
        account.group = False
    database.session.add(
        WarehouseCompanyAccount(
            warehouse_code=warehouse,
            company="cacao",
            inventory_account_id=inventory_account_id,
        )
    )
    defaults.inventory_adjustment_account_id = adjustment_account_id
    database.session.commit()
    return item_code, warehouse


def test_posting_multibook_creates_book_entries(entorno_contable_aislado):
    """A posted stock movement publishes one valuation per active book."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item_code, warehouse = _seed_adjustment_scenario(app)
        _post_adjustment(app, item_code, warehouse, "adjustment_positive", "5", "50")
        movements = database.session.execute(database.select(StockLedgerEntry).filter_by(item_code=item_code)).scalars().all()
        assert len(movements) == 1
        entries = (
            database.session.execute(database.select(StockLedgerBookEntry).filter_by(stock_ledger_entry_id=movements[0].id))
            .scalars()
            .all()
        )
        active_books = (
            database.session.execute(database.select(Book).filter_by(entity="cacao", status="activo")).scalars().all()
        )
        assert len(entries) == len(active_books)
        assert {entry.ledger_id for entry in entries} == {book.id for book in active_books}
        assert {entry.book_amount for entry in entries} == {Decimal("50")}
        assert all(entry.exchange_rate > 0 for entry in entries)


def test_cancellation_appends_book_countervalues(entorno_contable_aislado):
    """Cancelling a stock movement preserves its original book valuations."""
    from cacao_accounting.approval_engine import approved_execution
    from cacao_accounting.contabilidad.posting_service import cancel_document
    from cacao_accounting.internal_control_service import audit_actor

    app = entorno_contable_aislado.app
    with app.app_context():
        item_code, warehouse = _seed_adjustment_scenario(app)
        entry = _post_adjustment(app, item_code, warehouse, "adjustment_positive", "5", "50")
        original_movement = database.session.execute(
            database.select(StockLedgerEntry).filter_by(item_code=item_code)
        ).scalar_one()
        originals = (
            database.session.execute(
                database.select(StockLedgerBookEntry).filter_by(stock_ledger_entry_id=original_movement.id)
            )
            .scalars()
            .all()
        )
        snapshots = {row.id: _book_entry_snapshot(row) for row in originals}
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name), approved_execution(entry, actor.id):
            cancel_document(
                entry,
                reason="Anulación de prueba",
                actor_user_id=actor.id,
                cancellation_date=entry.posting_date,
            )
        database.session.flush()

        for row_id, snapshot in snapshots.items():
            persisted = database.session.get(StockLedgerBookEntry, row_id)
            assert persisted is not None
            assert _book_entry_snapshot(persisted) == snapshot

        reversal_movement = database.session.execute(
            database.select(StockLedgerEntry).filter_by(item_code=item_code, is_reversal=True)
        ).scalar_one()
        counters = (
            database.session.execute(
                database.select(StockLedgerBookEntry).filter_by(stock_ledger_entry_id=reversal_movement.id)
            )
            .scalars()
            .all()
        )
        assert len(counters) == len(originals)
        assert {row.book_amount for row in counters} == {-Decimal("50")}


@pytest.mark.parametrize("valuation_method", ["fifo", "moving_average"])
def test_fifo_and_moving_average_publish_book_entries(entorno_contable_aislado, valuation_method):
    """FIFO and moving average keep publishing the book valuation of each movement."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item_code, warehouse = _seed_adjustment_scenario(app)
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        entity.valuation_method = valuation_method
        database.session.commit()
        _post_adjustment(app, item_code, warehouse, "adjustment_positive", "5", "50")
        _post_adjustment(app, item_code, warehouse, "adjustment_negative", "2", "20")
        movements = (
            database.session.execute(
                database.select(StockLedgerEntry)
                .filter_by(item_code=item_code)
                .order_by(StockLedgerEntry.posting_date, StockLedgerEntry.id)
            )
            .scalars()
            .all()
        )
        assert len(movements) == 2
        for movement in movements:
            entries = (
                database.session.execute(database.select(StockLedgerBookEntry).filter_by(stock_ledger_entry_id=movement.id))
                .scalars()
                .all()
            )
            assert entries
            assert {row.book_amount for row in entries} == {movement.stock_value_difference}
