# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1819: un comprobante sin entradas GL no puede pasar a estado enviado."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JOURNAL_STATUS_DRAFT,
    JournalValidationError,
    create_journal_draft,
    submit_journal,
)
from cacao_accounting.database import Book, ComprobanteContable, ComprobanteContableDetalle, GLEntry, User, database


def _journal_payload(books: list[str] | None, line_book: str | None = None) -> dict[str, object]:
    """Construye un comprobante balanceado en moneda local para las dos pruebas."""
    line = {"account": "1101", "debit": "100", "credit": ""}
    counterpart = {"account": "4101", "debit": "", "credit": "100"}
    if line_book:
        line["book"] = line_book
        counterpart["book"] = line_book
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": books,
        "reference": f"NO-GL-{uuid4().hex[:8]}",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [{**line, "order": 1}, {**counterpart, "order": 2}],
    }


def _assert_not_posted(journal_id: str) -> None:
    """Verifica que el comprobante sigue en borrador y sin evidencia GL."""
    database.session.expire_all()
    stored = database.session.get(ComprobanteContable, journal_id)
    assert stored is not None
    assert stored.status == JOURNAL_STATUS_DRAFT
    entries = database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all()
    assert entries == []


def test_journal_rejects_a_book_deactivated_after_draft(app, entorno_contable):
    """Desactivar el libro de las líneas entre alta y submit bloquea la contabilización."""
    del entorno_contable
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        primary = database.session.execute(select(Book).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        secondary = database.session.execute(select(Book).where(Book.code == "NIIF")).scalar_one()
        journal = create_journal_draft(
            _journal_payload([primary.code, secondary.code], secondary.code),
            user_id=actor_id,
            assign_identifier=False,
        )

        secondary.status = "suspendido"
        database.session.flush()

        with pytest.raises(JournalValidationError, match="Libro contable no válido"):
            submit_journal(journal.id, user_id=actor_id)

        _assert_not_posted(journal.id)
        database.session.rollback()


def test_journal_with_stale_inactive_line_book_is_never_submitted(app, entorno_contable):
    """Un registro con líneas huérfanas de libros activos nunca queda submitted sin GL."""
    del entorno_contable
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        primary = database.session.execute(select(Book).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        secondary = database.session.execute(select(Book).where(Book.code == "NIIF")).scalar_one()
        journal = create_journal_draft(_journal_payload([primary.code]), user_id=actor_id, assign_identifier=False)

        # Simula un registro legacy/importado cuyas líneas conservan un libro dado de baja.
        lines = (
            database.session.execute(
                select(ComprobanteContableDetalle).where(ComprobanteContableDetalle.transaction_id == journal.id)
            )
            .scalars()
            .all()
        )
        for line in lines:
            line.book = secondary.code
        secondary.status = "suspendido"
        database.session.flush()

        with pytest.raises(JournalValidationError, match="no generó ninguna entrada"):
            submit_journal(journal.id, user_id=actor_id)

        _assert_not_posted(journal.id)
        database.session.rollback()
