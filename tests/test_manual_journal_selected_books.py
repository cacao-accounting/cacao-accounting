# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Manual journals preserve the accounting books selected by the user."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    submit_journal,
    update_journal_draft,
)
from cacao_accounting.database import Book, GLEntry, User, database


def _journal_payload(book_codes: list[str] | None) -> dict[str, object]:
    """Build a balanced, local-currency manual voucher for both test paths."""
    reference = f"SELECTED-BOOKS-{uuid4().hex[:8]}"
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": book_codes,
        "reference": reference,
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }


def test_manual_journal_posts_only_selected_books_after_update(app, entorno_contable):
    """Create, edit, and post retain a one-book selection with two active books."""
    del entorno_contable
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        primary = database.session.execute(select(Book).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        secondary = database.session.execute(select(Book).where(Book.code == "NIIF")).scalar_one()
        payload = _journal_payload([primary.code])

        journal = create_journal_draft(payload, user_id=actor_id, assign_identifier=False)
        journal = update_journal_draft(journal.id, payload, user_id=actor_id)
        assert json.loads(journal.book_codes) == [primary.code]

        submit_journal(journal.id, user_id=actor_id)
        entries = database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal.id)).scalars().all()

        assert primary.status == "activo"
        assert secondary.status == "activo"
        assert len(entries) == 2
        assert {entry.ledger_id for entry in entries} == {primary.id}


def test_manual_journal_without_subset_still_posts_all_active_books(app, entorno_contable):
    """An omitted/empty selection keeps the established all-active-books path."""
    del entorno_contable
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        active_ids = set(
            database.session.execute(select(Book.id).where(Book.entity == "cacao", Book.status == "activo")).scalars().all()
        )
        journal = create_journal_draft(_journal_payload(None), user_id=actor_id, assign_identifier=False)

        submit_journal(journal.id, user_id=actor_id)
        entries = database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal.id)).scalars().all()

        assert len(entries) == 2 * len(active_ids)
        assert {entry.ledger_id for entry in entries} == active_ids


def test_manual_journal_rejects_a_selected_inactive_book(app, entorno_contable):
    """A draft cannot persist a selector that posting would silently drop."""
    del entorno_contable
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        secondary = database.session.execute(select(Book).where(Book.code == "NIIF")).scalar_one()
        secondary.status = "suspendido"
        database.session.flush()

        with pytest.raises(JournalValidationError, match="Libro contable no válido"):
            create_journal_draft(_journal_payload([secondary.code]), user_id=actor_id, assign_identifier=False)

        database.session.rollback()
        assert database.session.get(Book, secondary.id).status == "activo"
