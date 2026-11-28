# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos\u00e9 Moreno Reyes

"""Manual journal balance validation uses historical line exchange rates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.api.line_import import _validate_complete_journal_import
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    submit_journal,
)
from cacao_accounting.database import Currency, ExchangeRate, GLEntry, User, database


def _payload(credit_currency: str = "NIO") -> dict[str, object]:
    """Build a mixed-currency journal dated after the seeded historical rate."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": ["DEFAULT_BOOK"],
        "reference": "HISTORICAL-LINE-RATE",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": "", "currency": "USD"},
            {"order": 2, "account": "4101", "debit": "", "credit": "3650", "currency": credit_currency},
        ],
    }


def _admin_id() -> str:
    """Return the seeded administrator identity."""
    return str(database.session.execute(select(User.id).where(User.user == "admin")).scalar_one())


def test_manual_journal_balances_with_historical_rate_for_line(app, entorno_contable):
    """A missing line rate is resolved from the historical exchange-rate table."""
    del entorno_contable
    with app.app_context():
        historical_rate = (
            database.session.execute(
                select(ExchangeRate)
                .where(
                    ExchangeRate.origin == "USD",
                    ExchangeRate.destination == "NIO",
                    ExchangeRate.date <= date(2026, 5, 15),
                )
                .order_by(ExchangeRate.date.desc())
            )
            .scalars()
            .first()
        )
        assert historical_rate is not None
        assert historical_rate.rate == Decimal("36.50")
        actor_id = _admin_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        assert journal.status == "draft"

        submit_journal(journal.id, user_id=actor_id)
        entries = database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal.id)).scalars().all()

        assert len(entries) == 2
        assert sum((entry.debit for entry in entries), Decimal("0")) == Decimal("3650")
        assert sum((entry.credit for entry in entries), Decimal("0")) == Decimal("3650")


def test_manual_journal_rejects_missing_historical_conversion(app, entorno_contable):
    """An unavailable conversion blocks the draft instead of assuming rate one."""
    del entorno_contable
    with app.app_context():
        database.session.add(Currency(code="EUT", name="Test euro", decimals=2, active=True))
        database.session.flush()
        try:
            with pytest.raises(JournalValidationError, match="tipo de cambio registrado"):
                create_journal_draft(_payload("EUT"), user_id=_admin_id(), assign_identifier=False)
        finally:
            database.session.rollback()


def test_line_import_validation_uses_the_journal_posting_date(app, entorno_contable):
    """The API validation path resolves line rates with the draft date too."""
    del entorno_contable
    errors: list[dict[str, object]] = []
    context: dict[str, object] = {
        "company_id": "cacao",
        "posting_date": "2026-05-15",
        "books": ["DEFAULT_BOOK"],
        "transaction_currency": "NIO",
        "exchange_rate": "",
        "existing_lines": [],
    }
    rows = [
        {"account": "1101", "debit": "100", "credit": "", "currency": "USD"},
        {"account": "4101", "debit": "", "credit": "3650", "currency": "NIO"},
    ]

    with app.app_context():
        _validate_complete_journal_import(context, rows, "cacao", errors)

    assert errors == []
