# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones de reversiones interperíodo de comprobantes (issues #763 y #764)."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con períodos abiertos consecutivos para reversiones."""
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
        from cacao_accounting.database import AccountingPeriod, Book, Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                User(id="user-1", user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Book(entity="cacao", code="DEFAULT_BOOK", name="Default", status="activo", is_primary=True, currency="NIO"),
                AccountingPeriod(
                    entity="cacao",
                    name="2026-05",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="2026-06",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 6, 1),
                    end=date(2026, 6, 30),
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="2026-07",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 7, 1),
                    end=date(2026, 7, 31),
                ),
            ]
        )
        database.session.commit()
        yield app


def _seed_submitted_journal() -> object:
    """Crea un comprobante contabilizado con saldo balanceado en mayo."""
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-GRD", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-GRD", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-08",
            "memo": "Comprobante con reversión interperíodo",
            "lines": [
                {"account": debit.id, "debit": "80.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "80.00"},
            ],
        },
        user_id="user-1",
    )
    submit_journal(journal.id)
    return journal


def test_duplicate_journal_reversal_rejected_on_second_attempt(app_ctx):
    """La segunda reversión del mismo comprobante lanza un error de negocio, no un IntegrityError."""
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        duplicate_journal_as_reversal_draft,
    )
    from cacao_accounting.database import ComprobanteContable, DocumentTransition, database

    journal = _seed_submitted_journal()
    first = duplicate_journal_as_reversal_draft(
        journal.id, user_id="user-1", reversal_date_raw="2026-06-08", reason="Primera reversión"
    )
    assert first.id is not None

    transitions = (
        database.session.execute(
            database.select(DocumentTransition).filter_by(
                source_type="journal_entry",
                source_id=journal.id,
                transition_type="reversal",
            )
        )
        .scalars()
        .all()
    )
    assert len(transitions) == 1

    with pytest.raises(JournalValidationError, match="ya tiene una reversión"):
        duplicate_journal_as_reversal_draft(
            journal.id, user_id="user-1", reversal_date_raw="2026-07-08", reason="Reversión duplicada"
        )

    refreshed = database.session.get(ComprobanteContable, journal.id)
    assert refreshed.status == "submitted"
    remaining = (
        database.session.execute(
            database.select(DocumentTransition).filter_by(
                source_type="journal_entry",
                source_id=journal.id,
                transition_type="reversal",
            )
        )
        .scalars()
        .all()
    )
    assert len(remaining) == 1


def test_route_revert_same_journal_twice_returns_business_message(app_ctx):
    """El flujo HTTP de reversión no regresa 500 al intentar revertir dos veces."""
    from cacao_accounting.database import ComprobanteContable, User, database

    journal = _seed_submitted_journal()
    user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True

    first = client.post(
        f"/accounting/journal/{journal.id}/revert",
        data={"reversal_date": "2026-06-08", "reason": "Primera reversión"},
        follow_redirects=False,
    )
    assert first.status_code == 302
    assert "/accounting/journal/edit/" in first.headers.get("Location", "")

    second = client.post(
        f"/accounting/journal/{journal.id}/revert",
        data={"reversal_date": "2026-07-08", "reason": "Reversión duplicada"},
        follow_redirects=True,
    )
    html = second.get_data(as_text=True)
    assert second.status_code == 200
    assert "ya tiene una reversión" in html

    drafts = (
        database.session.execute(database.select(ComprobanteContable).filter(ComprobanteContable.memo.like("Reversión de%")))
        .scalars()
        .all()
    )
    assert len(drafts) == 1


def test_journal_with_reversal_transition_cannot_be_cancelled(app_ctx):
    """Un comprobante con reversión interperíodo registrada no puede anularse."""
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        cancel_submitted_journal,
        duplicate_journal_as_reversal_draft,
    )
    from cacao_accounting.database import ComprobanteContable, database

    journal = _seed_submitted_journal()
    duplicate_journal_as_reversal_draft(
        journal.id, user_id="user-1", reversal_date_raw="2026-06-08", reason="Reversión en curso"
    )

    with pytest.raises(JournalValidationError, match="reversion"):
        cancel_submitted_journal(journal.id, user_id="user-1", reason="Intento de anulación")

    refreshed = database.session.get(ComprobanteContable, journal.id)
    assert refreshed.status == "submitted"
