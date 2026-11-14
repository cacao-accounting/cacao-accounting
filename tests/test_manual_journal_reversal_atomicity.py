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
    reject_journal_draft,
    submit_journal,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    ComprobanteContable,
    DocumentTransition,
    FiscalYear,
    GLEntry,
    NamingSeries,
    Sequence,
    SeriesSequenceMap,
    User,
    database,
)


def _create_submitted_journal(
    entorno_contable,
    naming_series_id: str | None = None,
    fiscal_year_id: str = "FY2026",
    year: int = 2026,
) -> tuple[str, str | None]:
    """Create a submitted source journal in a dedicated period."""
    user_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
    book_code = database.session.execute(select(Book.code).where(Book.code == "DEFAULT_BOOK")).scalar_one()
    fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
    if fiscal_year is None:
        fiscal_year = FiscalYear(
            id=fiscal_year_id,
            entity="cacao",
            name=str(year),
            year_start_date=date(year, 1, 1),
            year_end_date=date(year, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(fiscal_year)
        database.session.flush()
    source_period = (
        database.session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.entity == "cacao",
                AccountingPeriod.start == date(year, 5, 1),
                AccountingPeriod.end == date(year, 5, 31),
            )
        )
        .scalars()
        .first()
    )
    if source_period is None:
        database.session.add(
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=fiscal_year_id,
                name=f"May reversal test {uuid4().hex[:8]}",
                start=date(year, 5, 1),
                end=date(year, 5, 31),
                enabled=True,
                is_closed=False,
                status="open",
            )
        )
    reversal_period = (
        database.session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.entity == "cacao",
                AccountingPeriod.start == date(year, 6, 1),
                AccountingPeriod.end == date(year, 6, 30),
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
            start=date(year, 6, 1),
            end=date(year, 6, 30),
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
            "posting_date": f"{year}-05-15",
            "books": [book_code],
            "transaction_currency": "NIO",
            "base_currency": "NIO",
            "exchange_rate": "1",
            "naming_series_id": naming_series_id,
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


def test_invalid_reversal_request_releases_sqlite_writer(app, entorno_contable):
    """Validation failures release SQLite's immediate write reservation."""
    with app.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La reserva BEGIN IMMEDIATE solo aplica a SQLite.")
        source_id, created_reversal_period_id = _create_submitted_journal(entorno_contable)
        user_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()

        with pytest.raises(JournalValidationError, match="Debe indicar el motivo"):
            duplicate_journal_as_reversal_draft(
                source_id,
                user_id=user_id,
                reversal_date_raw=date(2026, 6, 15),
                reason="   ",
            )

        raw_connection = database.session.connection().connection.driver_connection
        assert raw_connection is not None and not raw_connection.in_transaction
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


def test_rejected_reversal_draft_can_be_retried_append_only(app, entorno_contable, authenticated_client):
    """A rejected attempt remains immutable while a later attempt can post once."""
    from cacao_accounting.reportes.services import _movement_cancellation_metadata

    with app.app_context():
        suffix = uuid4().hex[:8]
        test_year = 2090
        fiscal_year_id = f"FY-REVERSAL-{suffix}"
        naming_series = NamingSeries(
            name=f"Reversal retry test {suffix}",
            entity_type="journal_entry",
            company="cacao",
            prefix_template=f"RETRY-{suffix}-*YYYY*-*MM*-",
            is_active=True,
            is_default=False,
        )
        sequence = Sequence(
            name=f"Reversal retry sequence {suffix}", current_value=0, increment=1, padding=5, reset_policy="monthly"
        )
        database.session.add_all([naming_series, sequence])
        database.session.flush()
        database.session.add(SeriesSequenceMap(naming_series_id=naming_series.id, sequence_id=sequence.id, priority=0))
        database.session.commit()
        source_id, _created_reversal_period_id = _create_submitted_journal(
            entorno_contable, str(naming_series.id), fiscal_year_id=fiscal_year_id, year=test_year
        )
        user_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        original_entry = (
            database.session.execute(select(GLEntry).where(GLEntry.voucher_id == source_id).order_by(GLEntry.id))
            .scalars()
            .first()
        )
        first_draft = duplicate_journal_as_reversal_draft(
            source_id,
            user_id=user_id,
            reversal_date_raw=date(test_year, 6, 15),
            reason="Intento rechazado",
        )
        first_transition = database.session.execute(
            select(DocumentTransition).where(
                DocumentTransition.source_id == source_id,
                DocumentTransition.target_id == first_draft.id,
            )
        ).scalar_one()
        first_transition_snapshot = (
            first_transition.id,
            first_transition.target_id,
            first_transition.transition_type,
            first_transition.posting_date,
            first_transition.reason,
        )
        client = authenticated_client()
        source_view = client.get(f"/accounting/journal/{source_id}")
        assert source_view.status_code == 200
        assert b'data-bs-target="#reversalModal"' in source_view.data
        reject_journal_draft(str(first_draft.id), user_id=str(user_id))

        rejected_view = client.get(f"/accounting/journal/{first_draft.id}")
        assert rejected_view.status_code == 200
        assert b'data-bs-target="#reversalModal"' not in rejected_view.data

        assert original_entry is not None
        assert _movement_cancellation_metadata(original_entry)["cancellation_reason"] is None

        retry = duplicate_journal_as_reversal_draft(
            source_id,
            user_id=user_id,
            reversal_date_raw=date(test_year, 6, 15),
            reason="Intento corregido",
        )
        assert retry.document_no != first_draft.document_no
        retry_transition = database.session.execute(
            select(DocumentTransition).where(
                DocumentTransition.source_id == source_id,
                DocumentTransition.target_id == retry.id,
            )
        ).scalar_one()
        assert retry_transition.transition_type == "reversal_retry_00001"
        assert (
            first_transition.id,
            first_transition.target_id,
            first_transition.transition_type,
            first_transition.posting_date,
            first_transition.reason,
        ) == first_transition_snapshot

        submit_journal(str(retry.id), user_id=str(user_id))
        assert database.session.get(ComprobanteContable, first_draft.id).status == "rejected"
        assert database.session.get(ComprobanteContable, retry.id).status == "submitted"
        assert _movement_cancellation_metadata(original_entry)["cancellation_reason"] == "Intento corregido"
        assert (
            database.session.execute(
                select(GLEntry.id).where(
                    GLEntry.voucher_id == retry.id,
                    GLEntry.is_reversal.is_(True),
                    GLEntry.is_cancelled.is_(False),
                )
            )
            .scalars()
            .all()
        )

        with pytest.raises(JournalValidationError, match="ya tiene una reversión registrada"):
            duplicate_journal_as_reversal_draft(
                source_id,
                user_id=user_id,
                reversal_date_raw=date(test_year, 6, 15),
                reason="No duplicar la reversión contabilizada",
            )
