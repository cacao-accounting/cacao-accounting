# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Trazabilidad GL de reversas manuales (#1167, #1709)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    list_journal_lines,
    serialize_journal_for_form,
    submit_journal,
    update_journal_draft,
)
from cacao_accounting.contabilidad.posting_service import PostingError, post_comprobante_contable
from cacao_accounting.database import AccountingPeriod, Book, CostCenter, ExchangeRate, GLEntry, User, database
from cacao_accounting.internal_control_service import audit_actor


def test_reversion_manual_enlaza_cada_linea_gl_de_origen(app, entorno_contable):
    """La reversa multilibro conserva vínculo por línea, incluso con cuentas repetidas."""
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        database.session.add(CostCenter(code="MAIN", name="Principal", entity="cacao", active=True, enabled=True))
        database.session.add(CostCenter(code="ALT", name="Alternativo", entity="cacao", active=True, enabled=True))
        database.session.add(
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id="FY2026",
                name="Junio 2026",
                start=date(2026, 6, 1),
                end=date(2026, 6, 30),
                enabled=True,
                is_closed=False,
                status="open",
            )
        )
        niif_book = database.session.execute(select(Book).where(Book.code == "NIIF")).scalar_one()
        niif_book.currency = "USD"
        database.session.add_all(
            [
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("37.50"), date=date(2026, 6, 1)),
                ExchangeRate(origin="NIO", destination="USD", rate=Decimal("1") / Decimal("37.50"), date=date(2026, 6, 1)),
            ]
        )
        database.session.commit()

        journal = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-15",
                "books": ["DEFAULT_BOOK", "NIIF"],
                "transaction_currency": "USD",
                "base_currency": "NIO",
                "lines": [
                    {
                        "order": 1,
                        "account": "5101",
                        "debit": "60",
                        "credit": "",
                        "cost_center": "MAIN",
                        "economic_line_id": "client-controlled-id",
                    },
                    {"order": 2, "account": "5101", "debit": "40", "credit": "", "cost_center": "MAIN"},
                    {"order": 3, "account": "1101", "debit": "", "credit": "100"},
                ],
            },
            user_id=actor_id,
            assign_identifier=False,
        )
        submit_journal(journal.id, user_id=actor_id)
        original_id = journal.id
        original_entries = list(
            database.session.execute(
                select(GLEntry).where(
                    GLEntry.voucher_type == "journal_entry",
                    GLEntry.voucher_id == original_id,
                    GLEntry.is_cancelled.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert len(original_entries) == 6
        primary_book_id = database.session.execute(select(Book.id).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        primary_source = next(entry for entry in original_entries if entry.ledger_id == primary_book_id)
        assert primary_source.exchange_rate == Decimal("36.50")
        assert all(entry.economic_line_id != "client-controlled-id" for entry in original_entries)
        originals_by_line = {(entry.ledger_id, entry.economic_line_id): entry for entry in original_entries}
        assert len(originals_by_line) == len(original_entries)

        reversal = duplicate_journal_as_reversal_draft(
            original_id,
            user_id=actor_id,
            reversal_date_raw=date(2026, 6, 15),
            reason="Corrección del registro original",
        )
        edited_payload = serialize_journal_for_form(reversal)
        edited_payload["lines"] = edited_payload["lines"][:-1]
        with pytest.raises(JournalValidationError, match="cantidad de líneas"):
            update_journal_draft(reversal.id, edited_payload, actor_id)

        edited_payload = serialize_journal_for_form(reversal)
        edited_payload["lines"][0]["order"] = 99
        with pytest.raises(JournalValidationError, match="identidad de las líneas"):
            update_journal_draft(reversal.id, edited_payload, actor_id)

        valid_payload = serialize_journal_for_form(reversal)
        invalid_amount_payload = deepcopy(valid_payload)
        invalid_amount_payload["lines"][0]["credit"] = "61"
        invalid_amount_payload["lines"][2]["debit"] = "101"
        reversal = update_journal_draft(reversal.id, invalid_amount_payload, actor_id)
        with pytest.raises(JournalValidationError, match="no coincide con su línea GL de origen"):
            submit_journal(reversal.id, user_id=actor_id)
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == reversal.id)).scalar_one_or_none() is None
        )

        invalid_book_payload = deepcopy(valid_payload)
        for line in invalid_book_payload["lines"]:
            line["book"] = "DEFAULT_BOOK"
        reversal = update_journal_draft(reversal.id, invalid_book_payload, actor_id)
        with pytest.raises(JournalValidationError, match="cada libro contable"):
            submit_journal(reversal.id, user_id=actor_id)
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == reversal.id)).scalar_one_or_none() is None
        )

        invalid_account_payload = deepcopy(valid_payload)
        invalid_account_payload["lines"][0]["account"] = "1101"
        reversal = update_journal_draft(reversal.id, invalid_account_payload, actor_id)
        with pytest.raises(JournalValidationError, match="no coincide con su línea GL de origen"):
            submit_journal(reversal.id, user_id=actor_id)
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == reversal.id)).scalar_one_or_none() is None
        )

        invalid_dimension_payload = deepcopy(valid_payload)
        invalid_dimension_payload["lines"][0]["cost_center"] = "ALT"
        reversal = update_journal_draft(reversal.id, invalid_dimension_payload, actor_id)
        with pytest.raises(JournalValidationError, match="no coincide con su línea GL de origen"):
            submit_journal(reversal.id, user_id=actor_id)
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == reversal.id)).scalar_one_or_none() is None
        )

        reversal = update_journal_draft(reversal.id, valid_payload, actor_id)
        submit_journal(reversal.id, user_id=actor_id)

        reversal_entries = list(
            database.session.execute(
                select(GLEntry).where(
                    GLEntry.voucher_type == "journal_entry",
                    GLEntry.voucher_id == reversal.id,
                    GLEntry.is_cancelled.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert len(reversal_entries) == len(original_entries)
        assert all(entry.is_reversal for entry in reversal_entries)
        assert len({entry.reversal_of for entry in reversal_entries}) == len(original_entries)
        for entry in reversal_entries:
            source = originals_by_line[(entry.ledger_id, entry.economic_line_id)]
            assert entry.reversal_of == source.id
            assert entry.account_id == source.account_id
            assert entry.debit == source.credit
            assert entry.credit == source.debit
            assert entry.exchange_rate == source.exchange_rate
        assert sum((entry.debit - entry.credit for entry in reversal_entries), Decimal("0")) == Decimal("0")
        with audit_actor(actor_id, "Administrador"):
            with pytest.raises(PostingError):
                post_comprobante_contable(reversal)
        invalid_reversal = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-06-20",
                "books": ["DEFAULT_BOOK", "NIIF"],
                "transaction_currency": "NIO",
                "lines": [
                    {"order": 1, "account": "5101", "debit": "60", "credit": "", "cost_center": "MAIN"},
                    {"order": 2, "account": "5101", "debit": "40", "credit": "", "cost_center": "MAIN"},
                    {"order": 3, "account": "1101", "debit": "", "credit": "100"},
                ],
            },
            user_id=actor_id,
            assign_identifier=False,
        )
        invalid_reversal.document_no = "INVALID-REVERSAL-GL"
        invalid_reversal.reversal_of = original_id
        database.session.commit()

        with pytest.raises(JournalValidationError, match="no conserva su identidad contable de origen"):
            submit_journal(invalid_reversal.id, user_id=actor_id)
        for index, line in enumerate(list_journal_lines(invalid_reversal.id)):
            line.economic_line_id = f"missing-source-{index}"
        database.session.commit()
        with pytest.raises(JournalValidationError, match="línea GL de origen única"):
            submit_journal(invalid_reversal.id, user_id=actor_id)
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == invalid_reversal.id)).scalar_one_or_none()
            is None
        )


def test_asiento_manual_sin_periodo_no_se_contabiliza(app, entorno_contable):
    """A balanced journal outside configured periods remains a draft without GL rows."""
    with app.app_context():
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()
        journal = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2027-01-15",
                "books": ["DEFAULT_BOOK"],
                "transaction_currency": "NIO",
                "lines": [
                    {"order": 1, "account": "5101", "debit": "100", "credit": "", "cost_center": "MAIN"},
                    {"order": 2, "account": "1101", "debit": "", "credit": "100"},
                ],
            },
            user_id=actor_id,
            assign_identifier=False,
        )

        with pytest.raises(JournalValidationError, match="No existe un periodo contable configurado"):
            submit_journal(journal.id, user_id=actor_id)

        database.session.refresh(journal)
        assert journal.status == "draft"
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).scalar_one_or_none() is None
        )
