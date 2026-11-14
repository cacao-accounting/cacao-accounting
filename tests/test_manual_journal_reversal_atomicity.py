# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La reversión manual no deja borradores huérfanos ante conflictos."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    list_journal_lines,
    submit_journal,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    ComprobanteContable,
    DocumentTransition,
    FiscalYear,
    GLEntry,
    User,
    database,
)


def _create_submitted_journal(entorno_contable) -> tuple[str, str | None]:
    """Create a submitted source journal in a dedicated period."""
    user_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
    book_code = database.session.execute(select(Book.code).where(Book.code == "DEFAULT_BOOK")).scalar_one()
    fiscal_year_id = database.session.execute(select(FiscalYear.id).where(FiscalYear.entity == "cacao")).scalar_one()
    reversal_period = (
        database.session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.entity == "cacao",
                AccountingPeriod.start == date(2026, 6, 1),
                AccountingPeriod.end == date(2026, 6, 30),
            )
        )
        .scalars()
        .first()
    )
    created_reversal_period_id = None
    if reversal_period is None:
        reversal_period = AccountingPeriod(
            entity="cacao",
            fiscal_year_id=fiscal_year_id,
            name=f"June reversal test {uuid4().hex[:8]}",
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
            enabled=True,
            is_closed=False,
            status="open",
        )
        database.session.add(reversal_period)
        database.session.flush()
        created_reversal_period_id = str(reversal_period.id)
    database.session.commit()
    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-15",
            "books": [book_code],
            "transaction_currency": "NIO",
            "base_currency": "NIO",
            "exchange_rate": "1",
            "lines": [
                {"order": 1, "account": "1101", "debit": "25", "credit": ""},
                {"order": 2, "account": "1102", "debit": "", "credit": "25"},
            ],
        },
        user_id=user_id,
        assign_identifier=False,
    )
    submit_journal(journal.id, user_id=user_id)
    return str(journal.id), created_reversal_period_id


def test_reversal_transition_conflict_rolls_back_the_draft(app, entorno_contable, monkeypatch):
    """A failed unique transition insert rolls back its reversal journal and lines."""
    with app.app_context():
        source_id, created_reversal_period_id = _create_submitted_journal(entorno_contable)
        user_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        reversal_period_id = database.session.execute(
            select(AccountingPeriod.id)
            .where(
                AccountingPeriod.entity == "cacao",
                AccountingPeriod.start == date(2026, 6, 1),
                AccountingPeriod.end == date(2026, 6, 30),
            )
            .order_by(AccountingPeriod.id)
        ).scalar_one()

        def add_conflicting_transition(reversed_draft):
            """Make the database enforce the source's unique reversal transition."""
            database.session.add(
                DocumentTransition(
                    source_type="journal_entry",
                    source_id=source_id,
                    target_type="journal_entry",
                    target_id=reversed_draft.id,
                    transition_type="reversal",
                    company="cacao",
                    posting_date=date(2026, 6, 15),
                    accounting_period_id=reversal_period_id,
                    actor_user_id=user_id,
                    reason="Concurrent reversal",
                )
            )
            database.session.flush()

        from cacao_accounting.contabilidad import journal_service

        monkeypatch.setattr(journal_service, "log_reversal_draft_created", add_conflicting_transition)
        with pytest.raises(DBAPIError):
            duplicate_journal_as_reversal_draft(
                source_id,
                user_id=user_id,
                reversal_date_raw=date(2026, 6, 15),
                reason="Rollback on competing transition",
            )

        orphaned_draft = database.session.execute(
            select(ComprobanteContable.id).where(ComprobanteContable.reversal_of == source_id)
        ).scalar_one_or_none()
        transition_id = database.session.execute(
            select(DocumentTransition.id).where(
                DocumentTransition.source_type == "journal_entry",
                DocumentTransition.source_id == source_id,
                DocumentTransition.transition_type == "reversal",
            )
        ).scalar_one_or_none()

        assert orphaned_draft is None
        assert transition_id is None
        if created_reversal_period_id:
            database.session.delete(database.session.get(AccountingPeriod, created_reversal_period_id))
            database.session.commit()


def test_submit_rejects_orphaned_reversal_draft(app, entorno_contable):
    """A legacy reversal draft without its source transition cannot reach the GL."""
    with app.app_context():
        source_id, created_reversal_period_id = _create_submitted_journal(entorno_contable)
        user_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        book_code = database.session.execute(select(Book.code).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        orphaned_draft = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-06-15",
                "books": [book_code],
                "transaction_currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {"order": 1, "account": "1102", "debit": "25", "credit": ""},
                    {"order": 2, "account": "1101", "debit": "", "credit": "25"},
                ],
            },
            user_id=user_id,
            assign_identifier=False,
            source_economic_line_ids=[str(line.economic_line_id or line.id) for line in list_journal_lines(source_id)],
        )
        orphaned_draft.reversal_of = source_id
        database.session.commit()

        with pytest.raises(JournalValidationError, match="no tiene una transición válida"):
            submit_journal(orphaned_draft.id, user_id=user_id)

        persisted_draft = database.session.get(ComprobanteContable, orphaned_draft.id)
        gl_entry_id = database.session.execute(
            select(GLEntry.id).where(GLEntry.voucher_id == orphaned_draft.id)
        ).scalar_one_or_none()
        assert persisted_draft is not None and persisted_draft.status == "draft"
        assert gl_entry_id is None
        if created_reversal_period_id:
            database.session.delete(database.session.get(AccountingPeriod, created_reversal_period_id))
            database.session.commit()
