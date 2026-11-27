# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos\u00e9 Moreno Reyes

"""Manual journal lines must reference existing active currencies."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
from cacao_accounting.database import ComprobanteContable, Currency, User, database


def _payload(line_currency: str = "USD") -> dict[str, object]:
    """Build a balanced journal with one foreign-currency line."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": ["DEFAULT_BOOK"],
        "reference": f"LINE-CURRENCY-{uuid4().hex[:8]}",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": "", "currency": line_currency},
            {"order": 2, "account": "4101", "debit": "", "credit": "3650", "currency": "NIO"},
        ],
    }


def _admin_id() -> str:
    """Return the seeded administrator identity."""
    return str(database.session.execute(select(User.id).where(User.user == "admin")).scalar_one())


def test_manual_journal_rejects_inactive_line_currency_without_persisting(app, entorno_contable):
    """An inactive line currency is rejected before a draft is persisted."""
    del entorno_contable
    with app.app_context():
        usd = database.session.execute(select(Currency).where(Currency.code == "USD")).scalar_one()
        previous_active = usd.active
        usd.active = False
        database.session.flush()
        payload = _payload()
        try:
            with pytest.raises(JournalValidationError, match="moneda de la l\u00ednea est\u00e1 inactiva"):
                create_journal_draft(payload, user_id=_admin_id(), assign_identifier=False)
            assert (
                database.session.execute(
                    select(ComprobanteContable).where(ComprobanteContable.reference == payload["reference"])
                ).scalar_one_or_none()
                is None
            )
        finally:
            usd.active = previous_active
            database.session.flush()


def test_manual_journal_rejects_unknown_line_currency(app, entorno_contable):
    """A line currency absent from the catalog is rejected before rate lookup."""
    del entorno_contable
    with app.app_context():
        assert database.session.execute(select(Currency).where(Currency.code == "ZZZ")).scalar_one_or_none() is None
        with pytest.raises(JournalValidationError, match="moneda de la l\u00ednea no existe"):
            create_journal_draft(_payload("ZZZ"), user_id=_admin_id(), assign_identifier=False)
