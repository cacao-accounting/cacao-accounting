# SPDX-License-Identifier: Apache-2.0
"""#1776: reintento idempotente recupera aplicaci?n recurrente pendiente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.contabilidad.recurring_journal_service import (
    RecurringJournalError,
    apply_recurring_template,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    ComprobanteContable,
    FiscalYear,
    RecurringJournalApplication,
    RecurringJournalItem,
    RecurringJournalTemplate,
    User,
    database,
)


def _seed(env, *, code: str) -> tuple[str, str, str, date]:
    with env.app.app_context():
        uid = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()
        fy = database.session.execute(database.select(FiscalYear).filter_by(entity="cacao", name="2026")).scalar_one()
        period = database.session.execute(
            database.select(AccountingPeriod).filter_by(entity="cacao", fiscal_year_id=fy.id, name="Mayo 2026")
        ).scalar_one()
        book = database.session.execute(
            database.select(Book).filter_by(entity="cacao", code="DEFAULT_BOOK")
        ).scalar_one_or_none()
        assert book is not None

        tpl = RecurringJournalTemplate(
            company="cacao",
            ledger_id=book.id,
            code=code,
            name=code,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            frequency="monthly",
            currency="NIO",
            status="approved",
            docstatus=1,
        )
        database.session.add(tpl)
        database.session.flush()
        database.session.add_all(
            [
                RecurringJournalItem(
                    template_id=tpl.id,
                    account_code="5101",
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    description="debito",
                ),
                RecurringJournalItem(
                    template_id=tpl.id,
                    account_code="1101",
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    description="credito",
                ),
            ]
        )
        database.session.commit()
        return tpl.id, fy.id, uid, period.end


def test_retry_recovers_pending_draft_application(entorno_contable_aislado):
    env = entorno_contable_aislado
    tpl_id, fy_id, uid, app_date = _seed(env, code="TPL1776OK")

    with env.app.app_context():
        app1 = apply_recurring_template(tpl_id, fy_id, "Mayo 2026", app_date, uid, company="cacao")
        assert app1.status == "pending"
        journal = database.session.get(ComprobanteContable, app1.journal_id)
        assert journal is not None
        assert journal.status == "draft"

        # Fallo parcial simulado: la aplicaci?n qued? pendiente. Reintento debe recuperar.
        app2 = apply_recurring_template(tpl_id, fy_id, "Mayo 2026", app_date, uid, company="cacao")
        assert app2.id == app1.id
        journal = database.session.get(ComprobanteContable, app2.journal_id)
        assert journal is not None
        assert journal.status == "submitted"
        refreshed = database.session.get(RecurringJournalApplication, app1.id)
        assert refreshed is not None
        assert refreshed.status == "applied"


def test_retry_pending_with_unrecoverable_journal_requires_manual(entorno_contable_aislado):
    env = entorno_contable_aislado
    tpl_id, fy_id, uid, app_date = _seed(env, code="TPL1776BAD")

    with env.app.app_context():
        app1 = apply_recurring_template(tpl_id, fy_id, "Mayo 2026", app_date, uid, company="cacao")
        journal = database.session.get(ComprobanteContable, app1.journal_id)
        assert journal is not None
        journal.status = "cancelled"
        database.session.commit()

        with pytest.raises(RecurringJournalError, match="revision manual|revisi"):
            apply_recurring_template(tpl_id, fy_id, "Mayo 2026", app_date, uid, company="cacao")
