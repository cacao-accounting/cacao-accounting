# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#925: la cancelación del ledger es monotónica (False -> True).

Una fila cancelada no se reactiva reasignando `False` ni un valor falsy como
`0`; la corrección debe ser una nueva línea append-only.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ARAPLedgerEntry,
    Accounts,
    Book,
    Currency,
    Entity,
    GLEntry,
    Item,
    Party,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)


@pytest.fixture(params=[True, False], ids=["desktop", "cloud"])
def ledger_cancellation_scenario(request):
    """Create cancelable ledger rows in both runtime modes."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": request.param,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                UOM(code="EA", name="Unidad", is_active=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        book = Book(
            entity="alpha",
            code=f"BOOK-{suffix}",
            name="Libro Alfa",
            status="activo",
            is_primary=True,
            currency="NIO",
        )
        account = Accounts(
            entity="alpha",
            code=f"1101-{suffix}",
            name="Caja",
            classification="asset",
            group=False,
            active=True,
            enabled=True,
        )
        party = Party(code=f"CLI-{suffix}", name="Cliente", is_customer=True, is_active=True)
        item = Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        warehouse = Warehouse(code=f"WH-{suffix}", name="Bodega", company="alpha")
        database.session.add_all([book, account, party, item, warehouse])
        database.session.flush()
        gl_entry = GLEntry(
            company="alpha",
            account_id=account.id,
            ledger_id=book.id,
            account_code=account.code,
            voucher_type="journal_entry",
            voucher_id=f"JE-{suffix}",
            posting_date=date(2026, 5, 10),
            debit=Decimal("100"),
            credit=Decimal("0"),
            is_cancelled=False,
            is_reversal=False,
            is_fiscal_year_closing=False,
        )
        cancelled_gl_entry = GLEntry(
            company="alpha",
            account_id=account.id,
            ledger_id=book.id,
            account_code=account.code,
            voucher_type="journal_entry",
            voucher_id=f"JE-CANCELLED-{suffix}",
            posting_date=date(2026, 5, 10),
            debit=Decimal("25"),
            credit=Decimal("0"),
            is_cancelled=True,
            is_reversal=False,
            is_fiscal_year_closing=False,
        )
        arap_entry = ARAPLedgerEntry(
            company="alpha",
            ledger_type="AR",
            party_type="customer",
            party_id=party.id,
            document_type="sales_invoice",
            document_id=f"INV-{suffix}",
            posting_date=date(2026, 5, 10),
            event_type="invoice",
            currency="NIO",
            document_amount=Decimal("100"),
            is_reversal=False,
            is_cancelled=False,
        )
        cancelled_arap_entry = ARAPLedgerEntry(
            company="alpha",
            ledger_type="AR",
            party_type="customer",
            party_id=party.id,
            document_type="sales_invoice",
            document_id=f"INV-CANCELLED-{suffix}",
            posting_date=date(2026, 5, 10),
            event_type="invoice",
            currency="NIO",
            document_amount=Decimal("25"),
            is_reversal=False,
            is_cancelled=True,
        )
        stock_entry = StockLedgerEntry(
            posting_date=date(2026, 5, 10),
            item_code=item.code,
            warehouse=warehouse.code,
            company="alpha",
            qty_change=Decimal("1"),
            voucher_type="stock_entry",
            voucher_id=f"SE-{suffix}",
            is_cancelled=False,
        )
        cancelled_stock_entry = StockLedgerEntry(
            posting_date=date(2026, 5, 10),
            item_code=item.code,
            warehouse=warehouse.code,
            company="alpha",
            qty_change=Decimal("1"),
            voucher_type="stock_entry",
            voucher_id=f"SE-CANCELLED-{suffix}",
            is_cancelled=True,
        )
        database.session.add_all(
            [gl_entry, arap_entry, stock_entry, cancelled_gl_entry, cancelled_arap_entry, cancelled_stock_entry]
        )
        database.session.commit()
        ids = {
            "gl": gl_entry.id,
            "arap": arap_entry.id,
            "stock": stock_entry.id,
            "gl_cancelled": cancelled_gl_entry.id,
            "arap_cancelled": cancelled_arap_entry.id,
            "stock_cancelled": cancelled_stock_entry.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _is_cancelled(app, model, entry_id: str) -> bool:
    """Read the persisted flag from a fresh session."""
    with app.app_context():
        entry = database.session.get(model, entry_id)
        assert entry is not None
        return bool(entry.is_cancelled)


def _try_direct_cancellation(app, model, entry_id: str) -> None:
    """Reject a tombstone mutation that bypasses the audited service."""
    with app.app_context():
        entry = database.session.get(model, entry_id)
        assert entry is not None
        entry.is_cancelled = True
        with pytest.raises(ValueError, match="servicio auditado"):
            database.session.commit()
        database.session.rollback()


@pytest.mark.parametrize("model,key", [(GLEntry, "gl"), (ARAPLedgerEntry, "arap"), (StockLedgerEntry, "stock")])
def test_direct_orm_cancellation_requires_audited_service(ledger_cancellation_scenario, model, key):
    """GL, AR/AP, and stock cannot be hidden without reversals and audit metadata."""
    app, ids = ledger_cancellation_scenario

    _try_direct_cancellation(app, model, ids[key])

    assert _is_cancelled(app, model, ids[key]) is False


@pytest.mark.parametrize("model,key", [(GLEntry, "gl"), (ARAPLedgerEntry, "arap"), (StockLedgerEntry, "stock")])
@pytest.mark.parametrize("channel", ["core", "textual"])
def test_bulk_update_cannot_cancel_ledger_evidence(ledger_cancellation_scenario, model, key, channel):
    """Core and textual SQL cannot bypass the audited cancellation service."""
    app, ids = ledger_cancellation_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "core":
                database.session.execute(database.update(model).where(model.id == ids[key]).values(is_cancelled=True))
                database.session.commit()
            else:
                database.session.execute(
                    text(f"UPDATE {model.__tablename__} SET is_cancelled = TRUE WHERE id = :entry_id"),
                    {"entry_id": ids[key]},
                )
                database.session.commit()
        database.session.rollback()

    assert _is_cancelled(app, model, ids[key]) is False


@pytest.mark.parametrize(
    "model,key",
    [(GLEntry, "gl_cancelled"), (ARAPLedgerEntry, "arap_cancelled"), (StockLedgerEntry, "stock_cancelled")],
)
@pytest.mark.parametrize("channel", ["core", "textual"])
def test_bulk_update_cannot_reactivate_cancelled_ledger_evidence(ledger_cancellation_scenario, model, key, channel):
    """Core and textual SQL cannot erase a persisted cancellation tombstone."""
    app, ids = ledger_cancellation_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "core":
                database.session.execute(database.update(model).where(model.id == ids[key]).values(is_cancelled=False))
                database.session.commit()
            else:
                database.session.execute(
                    text(f"UPDATE {model.__tablename__} SET is_cancelled = FALSE WHERE id = :entry_id"),
                    {"entry_id": ids[key]},
                )
                database.session.commit()
        database.session.rollback()

    assert _is_cancelled(app, model, ids[key]) is True


def test_every_cancellable_evidence_model_has_append_only_listeners():
    """Todo modelo con `is_cancelled` conserva los guards de actualización y borrado (#925/N16)."""
    models = sorted(
        {mapper.class_ for mapper in database.Model.registry.mappers if hasattr(mapper.class_, "is_cancelled")},
        key=lambda model: model.__name__,
    )

    assert models, "No se encontraron modelos de evidencia con is_cancelled."
    for model in models:
        assert model.__mapper__.dispatch.before_update, f"{model.__name__} no bloquea actualizaciones"
        assert model.__mapper__.dispatch.before_delete, f"{model.__name__} no bloquea borrados"
