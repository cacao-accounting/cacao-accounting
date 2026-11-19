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

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ARAPLedgerEntry,
    Accounts,
    Book,
    Currency,
    Entity,
    GLEntry,
    Party,
    database,
)


@pytest.fixture
def ledger_cancellation_scenario():
    """Create one GL row and one AR/AP row that can be cancelled."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
        database.session.add_all([book, account, party])
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
        database.session.add_all([gl_entry, arap_entry])
        database.session.commit()
        ids = {"gl": gl_entry.id, "arap": arap_entry.id}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _cancel(app, model, entry_id: str) -> None:
    """Apply the legitimate False -> True transition and persist it."""
    with app.app_context():
        entry = database.session.get(model, entry_id)
        assert entry is not None
        entry.is_cancelled = True
        database.session.commit()


def _is_cancelled(app, model, entry_id: str) -> bool:
    """Read the persisted flag from a fresh session."""
    with app.app_context():
        entry = database.session.get(model, entry_id)
        assert entry is not None
        return bool(entry.is_cancelled)


def _try_reactivation(app, model, entry_id: str, value) -> None:
    """Attempt a reverse transition and roll back after the guard raises."""
    with app.app_context():
        entry = database.session.get(model, entry_id)
        assert entry is not None
        entry.is_cancelled = value
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()


def test_cancellation_is_allowed_and_persisted_for_gl(ledger_cancellation_scenario):
    """The legitimate cancellation keeps working."""
    app, ids = ledger_cancellation_scenario

    _cancel(app, GLEntry, ids["gl"])

    assert _is_cancelled(app, GLEntry, ids["gl"]) is True


@pytest.mark.parametrize("value", [False, 0])
def test_reactivating_a_cancelled_gl_entry_is_rejected(ledger_cancellation_scenario, value):
    """False and 0 cannot lift the GL cancellation."""
    app, ids = ledger_cancellation_scenario
    _cancel(app, GLEntry, ids["gl"])

    _try_reactivation(app, GLEntry, ids["gl"], value)

    assert _is_cancelled(app, GLEntry, ids["gl"]) is True


@pytest.mark.parametrize("value", [False, 0])
def test_reactivating_a_cancelled_ar_ap_entry_is_rejected(ledger_cancellation_scenario, value):
    """The AR/AP subledger applies the same monotonic rule."""
    app, ids = ledger_cancellation_scenario
    _cancel(app, ARAPLedgerEntry, ids["arap"])

    _try_reactivation(app, ARAPLedgerEntry, ids["arap"], value)

    assert _is_cancelled(app, ARAPLedgerEntry, ids["arap"]) is True


def test_core_bulk_cancellation_is_rejected(ledger_cancellation_scenario):
    """A Core UPDATE cannot cancel evidence without the audited path."""
    app, ids = ledger_cancellation_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            database.session.execute(database.update(GLEntry).where(GLEntry.id == ids["gl"]).values(is_cancelled=True))
            database.session.commit()
        database.session.rollback()

    assert _is_cancelled(app, GLEntry, ids["gl"]) is False


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
