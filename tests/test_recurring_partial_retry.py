# SPDX-License-Identifier: Apache-2.0
"""#1776: un fallo parcial recurrente debe ser recuperable por reintento."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.contabilidad.recurring_journal_service import (
    apply_recurring_template,
    approve_recurring_template,
    create_recurring_template,
)
from cacao_accounting.contabilidad.services import _apply_recurring_templates
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    ComprobanteContable,
    GLEntry,
    RecurringJournalApplication,
    RecurringJournalItem,
    User,
    database,
)


def _mk_template(code: str, admin: str) -> str:
    cargo = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
    abono = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
    t = create_recurring_template(
        data={
            "code": code,
            "name": code,
            "company": "cacao",
            "ledger_id": None,
            "books": ["DEFAULT_BOOK"],
            "naming_series_id": None,
            "description": "#1776",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "frequency": "monthly",
            "currency": None,
        },
        items=[
            {"account_code": str(cargo.code), "debit": 50, "credit": 0},
            {"account_code": str(abono.code), "debit": 0, "credit": 50},
        ],
        user_id=admin,
    )
    approve_recurring_template(t.id, admin)
    return t.id


def test_partial_recurring_retry_is_idempotent(entorno_contable_aislado):
    uid = uuid4().hex[:6].upper()
    period_id = f"P1776{uid}"
    with entorno_contable_aislado.app.app_context():
        admin = str(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one().id)
        period = AccountingPeriod(
            id=period_id,
            entity="cacao",
            fiscal_year_id="FY2026",
            name=f"1776-{uid}",
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.commit()

        ok_id = _mk_template(f"OK{uid}", admin)
        bad_id = _mk_template(f"BAD{uid}", admin)
        # make bad template fail validation during apply by removing items
        for item in database.session.execute(database.select(RecurringJournalItem).filter_by(template_id=bad_id)).scalars():
            database.session.delete(item)
        database.session.commit()

        success, errors = _apply_recurring_templates(
            [ok_id, bad_id], "FY2026", period.name, date(2026, 6, 30), admin, company="cacao"
        )
        assert success == 1
        assert errors

        apps = list(
            database.session.execute(
                database.select(RecurringJournalApplication).filter_by(accounting_period_id=period.id)
            ).scalars()
        )
        assert len(apps) == 1
        first = apps[0]
        assert first.status == "applied"
        assert first.journal_id is not None
        journal = database.session.get(ComprobanteContable, first.journal_id)
        assert journal is not None and journal.status == "submitted"
        entries = list(
            database.session.execute(
                database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=journal.id, is_cancelled=False)
            )
            .scalars()
            .all()
        )
        assert len(entries) == 2
        assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries) == Decimal("50")

        # El reintento devuelve la misma aplicación sin duplicar comprobante ni GL.
        second = apply_recurring_template(ok_id, "FY2026", period.name, date(2026, 6, 30), admin, company="cacao")
        assert second.id == first.id
        apps2 = list(
            database.session.execute(database.select(RecurringJournalApplication).filter_by(accounting_period_id=period.id))
            .scalars()
            .all()
        )
        assert len(apps2) == 1
        persisted_entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=journal.id, is_cancelled=False)
            )
            .scalars()
            .all()
        )
        assert persisted_entries == entries
