# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Concurrent manual reversal requests create one draft and one transition."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    submit_journal,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    ComprobanteContable,
    Currency,
    DocumentTransition,
    Entity,
    FiscalYear,
    Modules,
    User,
    database,
)

pytestmark = pytest.mark.database


@pytest.fixture
def concurrent_reversal_scenario(tmp_path):
    """Create an isolated company and posted journal for concurrent callers."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'journal-reversal-concurrency.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6].upper()
    company_code = f"J{suffix}"
    book_code = f"B{suffix}"
    user_id = f"U{suffix}"
    debit_account = f"CASH{suffix}"
    credit_account = f"BANK{suffix}"

    with app.app_context():
        database.create_all()
        nio_currency = database.session.execute(select(Currency.code).where(Currency.code == "NIO")).scalar_one_or_none()
        if nio_currency is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        accounting_module = database.session.execute(
            select(Modules).where(Modules.module == "accounting")
        ).scalar_one_or_none()
        if accounting_module is None:
            database.session.add(Modules(module="accounting", default=True, enabled=True))
        else:
            accounting_module.enabled = True

        database.session.flush()
        company = Entity(
            code=company_code,
            name=f"Reversal {suffix}",
            company_name=f"Reversal {suffix} SA",
            tax_id=f"REV-{suffix}",
            currency="NIO",
            enabled=True,
            status="activo",
        )
        database.session.add(company)
        database.session.flush()
        book = Book(
            entity=company_code,
            code=book_code,
            name=f"Book {suffix}",
            status="activo",
            is_primary=True,
            currency="NIO",
        )
        fiscal_year = FiscalYear(
            entity=company_code,
            name=f"FY {suffix}",
            year_start_date=date(2027, 1, 1),
            year_end_date=date(2027, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        user = User(
            id=user_id,
            user=user_id,
            name="Accounting administrator",
            password=b"unused",
            classification="admin",
            active=True,
            company=company_code,
        )
        database.session.add_all([book, fiscal_year, user])
        database.session.flush()
        source_period = AccountingPeriod(
            entity=company_code,
            fiscal_year_id=fiscal_year.id,
            name=f"January {suffix}",
            status="open",
            enabled=True,
            is_closed=False,
            start=date(2027, 1, 1),
            end=date(2027, 1, 31),
        )
        reversal_period = AccountingPeriod(
            entity=company_code,
            fiscal_year_id=fiscal_year.id,
            name=f"February {suffix}",
            status="open",
            enabled=True,
            is_closed=False,
            start=date(2027, 2, 1),
            end=date(2027, 2, 28),
        )
        database.session.add_all(
            [
                source_period,
                reversal_period,
                Accounts(
                    entity=company_code,
                    code=debit_account,
                    name="Cash",
                    group=False,
                    active=True,
                    enabled=True,
                    classification="asset",
                    account_type="cash",
                ),
                Accounts(
                    entity=company_code,
                    code=credit_account,
                    name="Bank",
                    group=False,
                    active=True,
                    enabled=True,
                    classification="asset",
                    account_type="bank",
                ),
            ]
        )
        database.session.commit()
        journal = create_journal_draft(
            {
                "company": company_code,
                "posting_date": "2027-01-15",
                "books": [book_code],
                "transaction_currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {"order": 1, "account": debit_account, "debit": "25", "credit": ""},
                    {"order": 2, "account": credit_account, "debit": "", "credit": "25"},
                ],
            },
            user_id=user_id,
            assign_identifier=False,
        )
        submit_journal(journal.id, user_id=user_id)
        seed = {"source_id": str(journal.id), "user_id": user_id}

    yield app, seed

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_concurrent_reversal_requests_create_one_draft_and_transition(concurrent_reversal_scenario):
    """Source locking and the unique transition prevent duplicate posted intent."""
    app, seed = concurrent_reversal_scenario
    request_barrier = Barrier(2)

    def create_reversal():
        with app.app_context():
            database.session.remove()
            request_barrier.wait(timeout=10)
            try:
                draft = duplicate_journal_as_reversal_draft(
                    seed["source_id"],
                    user_id=seed["user_id"],
                    reversal_date_raw=date(2027, 2, 15),
                    reason="Concurrent reversal request",
                )
                return "created", str(draft.id)
            except JournalValidationError:
                return "rejected", "already reversed"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _index: create_reversal(), range(2)))

    assert [status for status, _detail in outcomes].count("created") == 1
    assert [status for status, _detail in outcomes].count("rejected") == 1

    with app.app_context():
        transition = database.session.execute(
            select(DocumentTransition).where(
                DocumentTransition.source_type == "journal_entry",
                DocumentTransition.source_id == seed["source_id"],
                DocumentTransition.transition_type == "reversal",
            )
        ).scalar_one()
        reversal_drafts = (
            database.session.execute(select(ComprobanteContable).where(ComprobanteContable.reversal_of == seed["source_id"]))
            .scalars()
            .all()
        )

    assert len(reversal_drafts) == 1
    assert transition.target_id == reversal_drafts[0].id
