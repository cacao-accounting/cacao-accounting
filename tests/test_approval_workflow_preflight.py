# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Business regressions for operations without approval submission routes."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event
from tempfile import gettempdir
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError


from cacao_accounting import create_app
from cacao_accounting.approval_preflight import ApprovalWorkflowRequired
from cacao_accounting.bancos.services import create_petty_cash_expense
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.fiscal_year_closing import FiscalYearClosingError, create_fiscal_year_closing_voucher
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    serialize_journal_for_form,
    submit_journal,
    update_journal_draft,
)
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    ApprovalMatrix,
    ApprovalRequest,
    Bank,
    BankAccount,
    Book,
    CacaoConfig,
    ComprobanteContable,
    CompanyDefaultAccount,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    Modules,
    NamingSeries,
    PettyCashExpense,
    User,
    UserCompanyAccess,
    database,
)

pytestmark = pytest.mark.database


@pytest.fixture
def cloud_app():
    """Create an isolated Cloud-mode database for approval policy behavior."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    database_file: Path | None = None
    if database_uri.startswith("sqlite"):
        database_file = Path(gettempdir()) / f"approval-preflight-{uuid4().hex}.sqlite"
        database_uri = f"sqlite:///{database_file.as_posix()}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()
    if database_file is not None:
        database_file.unlink(missing_ok=True)


def _create_company(company_code: str) -> None:
    """Create the company and settings used by both accounting workflows."""
    currency = f"N{company_code[1:]}"
    database.session.add(Currency(code=currency, name="Córdoba", decimals=2, active=True, default=False))
    database.session.add(
        Entity(
            code=company_code,
            name=f"Empresa {company_code}",
            company_name=f"Empresa {company_code} SA",
            tax_id=f"TAX-{company_code}",
            currency=currency,
            enabled=True,
            status="default",
        )
    )
    database.session.add_all(
        [
            CacaoConfig(key=f"approval_engine_enabled_{company_code}", value="true"),
            CacaoConfig(key=f"approval_require_different_approver_{company_code}", value="true"),
        ]
    )


def _ensure_accounting_module() -> Modules:
    """Create the shared accounting module only when test databases lack it."""
    module_query = database.select(Modules).where(Modules.module == "accounting")
    module = database.session.execute(module_query).scalar_one_or_none()
    if module is None:
        try:
            with database.session.begin_nested():
                module = Modules(module="accounting", default=False, enabled=True)
                database.session.add(module)
                database.session.flush()
        except IntegrityError:
            module = database.session.execute(
                module_query.with_for_update().execution_options(populate_existing=True)
            ).scalar_one()
    elif not module.enabled:
        pytest.skip("El módulo contable está deshabilitado en la base de datos compartida.")
    return module


def _create_fiscal_year_closing_case(company: str) -> dict[str, str]:
    """Create a closed year with a real income balance and independent approver."""
    _create_company(company)
    currency = f"N{company[1:]}"
    requester_id = f"req-{company}"
    approver_id = f"apr-{company}"
    _ensure_accounting_module()
    fiscal_year = FiscalYear(
        entity=company,
        name="FY-2025",
        year_start_date=date(2025, 1, 1),
        year_end_date=date(2025, 12, 31),
        is_closed=True,
        financial_closed=False,
    )
    database.session.add_all(
        [
            User(
                id=requester_id,
                user=requester_id,
                name="Preparador",
                password=proteger_passwd("approval-test-password"),
                classification="admin",
                active=True,
            ),
            User(
                id=approver_id,
                user=approver_id,
                name="Aprobador",
                password=proteger_passwd("approval-test-password"),
                classification="admin",
                active=True,
            ),
            fiscal_year,
        ]
    )
    database.session.flush()
    # #1828: en Cloud la clasificación admin no concede compañías por sí sola.
    database.session.add_all(
        [
            UserCompanyAccess(user_id=requester_id, company_code=company),
            UserCompanyAccess(user_id=approver_id, company_code=company),
        ]
    )

    book = Book(
        code=f"B{company[1:8]}",
        name="Libro local",
        entity=company,
        currency=currency,
        status="activo",
        is_primary=True,
    )
    income = Accounts(
        code=f"INC-{company}",
        name="Ingresos",
        entity=company,
        active=True,
        enabled=True,
        group=False,
        classification="ingreso",
        account_type="income",
    )
    retained_earnings = Accounts(
        code=f"RET-{company}",
        name="Utilidades acumuladas",
        entity=company,
        active=True,
        enabled=True,
        group=False,
        classification="patrimonio",
        account_type="equity",
    )
    period = AccountingPeriod(
        entity=company,
        fiscal_year_id=fiscal_year.id,
        name="2025-12",
        enabled=True,
        is_closed=True,
        start=date(2025, 12, 1),
        end=date(2025, 12, 31),
    )
    database.session.add_all([book, income, retained_earnings, period])
    database.session.flush()
    database.session.add_all(
        [
            CompanyDefaultAccount(company=company, retained_earnings_account_id=retained_earnings.id),
            GLEntry(
                posting_date=date(2025, 12, 31),
                company=company,
                ledger_id=book.id,
                account_id=income.id,
                account_code=income.code,
                debit=Decimal("0"),
                credit=Decimal("100"),
                account_currency=currency,
                company_currency=currency,
                exchange_rate=Decimal("1"),
                voucher_type="journal_entry",
                voucher_id=f"source-{company}",
                fiscal_year_id=fiscal_year.id,
                accounting_period_id=period.id,
                is_fiscal_year_closing=False,
                is_reversal=False,
                is_cancelled=False,
            ),
            ApprovalMatrix(
                company_id=company,
                document_type="journal_entry",
                user_id=approver_id,
                min_amount=Decimal("0"),
                approval_level=1,
                enabled=True,
            ),
        ]
    )
    database.session.commit()
    return {"company": company, "fiscal_year_id": fiscal_year.id, "requester_id": requester_id, "approver_id": approver_id}


def _create_manual_approval_case(company: str) -> tuple[dict[str, str], ComprobanteContable]:
    """Create an open-period manual journal governed by an independent approver."""
    case = _create_fiscal_year_closing_case(company)
    fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])
    period = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == case["fiscal_year_id"])
    ).scalar_one()
    assert fiscal_year is not None
    fiscal_year.is_closed = False
    period.is_closed = False
    book = database.session.execute(database.select(Book).filter_by(entity=company)).scalar_one()
    income = database.session.execute(database.select(Accounts).filter_by(code=f"INC-{company}")).scalar_one()
    retained_earnings = database.session.execute(database.select(Accounts).filter_by(code=f"RET-{company}")).scalar_one()
    currency = f"N{company[1:]}"
    journal = create_journal_draft(
        {
            "company": company,
            "posting_date": "2025-12-31",
            "books": [book.code],
            "reference": f"APPROVAL-{uuid4().hex[:8]}",
            "transaction_currency": currency,
            "base_currency": currency,
            "exchange_rate": "1",
            "lines": [
                {"order": 1, "account": retained_earnings.code, "debit": "100", "credit": ""},
                {"order": 2, "account": income.code, "debit": "", "credit": "100"},
            ],
        },
        user_id=case["requester_id"],
    )
    database.session.commit()
    return case, journal


def _request_manual_journal_approval(case: dict[str, str], journal: ComprobanteContable) -> ApprovalRequest:
    """Create the pending request and set the status assigned by the submit route."""
    from cacao_accounting.approval_engine import ApprovalEngine

    requester = database.session.get(User, case["requester_id"])
    assert requester is not None
    journal.status = "Pending Approval"
    approval_request = ApprovalEngine.request_approval(journal, actor=requester)
    assert approval_request is not None
    database.session.commit()
    return approval_request


def test_independent_approval_rejects_unsupported_postings_before_draft(cloud_app):
    """Petty cash still blocks before creating evidence when its flow is unsupported."""
    company = f"E{uuid4().hex[:8]}"
    with cloud_app.app_context():
        _create_company(company)
        database.session.commit()

        with pytest.raises(ApprovalWorkflowRequired, match="no se creó el asiento contable"):
            create_petty_cash_expense(
                company=company,
                petty_cash_id="missing-fund",
                expense_account_code="6000",
                concept="Gasto de prueba",
                amount=100,
                cost_center_code="ADMIN",
                actor_id="accountant",
            )

        assert (
            database.session.execute(
                database.select(ComprobanteContable.id).where(ComprobanteContable.entity == company)
            ).first()
            is None
        )
        assert (
            database.session.execute(database.select(PettyCashExpense.id).where(PettyCashExpense.company == company)).first()
            is None
        )
        assert database.session.execute(database.select(GLEntry.id).where(GLEntry.company == company)).first() is None


def test_fiscal_year_close_waits_for_independent_approval_and_posts_once(cloud_app):
    """The proposal, approval request and fiscal-year link follow the common workflow."""
    case = {"company": f"E{uuid4().hex[:8]}"}
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(case["company"])

        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        with pytest.raises(JournalValidationError, match="solicitud de aprobación pendiente"):
            update_journal_draft(journal.id, {}, case["requester_id"])
        repeated = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        request = database.session.execute(
            database.select(ApprovalRequest).where(ApprovalRequest.document_id == journal.id)
        ).scalar_one()
        fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])

        assert repeated.id == journal.id
        assert journal.status == "draft"
        assert request.status == "Pending Approval"
        assert request.requested_by == case["requester_id"]
        assert journal.fiscal_year_id == fiscal_year.id
        assert fiscal_year.financial_closed is False
        assert fiscal_year.closing_voucher_id is None
        assert database.session.execute(database.select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).first() is None

        from cacao_accounting.approval_engine import ApprovalEngine

        approver = database.session.get(User, case["approver_id"])
        assert approver is not None
        assert ApprovalEngine.approve(journal, approver, "Independent review") is True
        database.session.commit()

        database.session.refresh(fiscal_year)
        assert journal.status == "submitted"
        assert fiscal_year.financial_closed is True
        assert fiscal_year.closing_voucher_id == journal.id
        assert database.session.execute(database.select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).scalars().all()


def test_pending_manual_journal_posts_only_after_independent_approval(request):
    """An approved pending journal posts in the approval transaction."""
    from cacao_accounting.approval_engine import ApprovalEngine

    with request.getfixturevalue("cloud_app").app_context():
        case, journal = _create_manual_approval_case(f"E{uuid4().hex[:8]}")
        approval_request = _request_manual_journal_approval(case, journal)
        requester = database.session.get(User, case["requester_id"])
        approver = database.session.get(User, case["approver_id"])
        assert requester is not None and approver is not None

        with pytest.raises(JournalValidationError, match="Solo se puede contabilizar"):
            submit_journal(journal.id, user_id=case["requester_id"])
        database.session.rollback()
        journal = database.session.get(ComprobanteContable, journal.id)
        approval_request = database.session.get(ApprovalRequest, approval_request.id)
        assert journal is not None and approval_request is not None
        assert journal.status == "Pending Approval"
        assert approval_request.status == "Pending Approval"

        assert ApprovalEngine.approve(journal, approver, "Aprobación independiente", request=approval_request) is True
        database.session.commit()

        database.session.refresh(journal)
        database.session.refresh(approval_request)
        entries = database.session.execute(database.select(GLEntry).where(GLEntry.voucher_id == journal.id)).scalars().all()
        assert journal.status == "submitted"
        assert approval_request.status == "Approved"
        assert len(entries) == 2
        assert sum((entry.debit for entry in entries), Decimal("0")) == Decimal("100.0000")
        assert sum((entry.credit for entry in entries), Decimal("0")) == Decimal("100.0000")


def test_rejected_pending_manual_journal_returns_to_editable_draft(request):
    """Rejecting a pending manual journal unlocks correction and a new request."""
    from cacao_accounting.approval_engine import ApprovalEngine

    with request.getfixturevalue("cloud_app").app_context():
        case, journal = _create_manual_approval_case(f"E{uuid4().hex[:8]}")
        original_request = _request_manual_journal_approval(case, journal)
        approver = database.session.get(User, case["approver_id"])
        assert approver is not None

        ApprovalEngine.reject(journal, approver, "Corregir detalle", request=original_request)
        database.session.commit()

        database.session.refresh(journal)
        database.session.refresh(original_request)
        assert original_request.status == "Rejected"
        assert journal.status == "draft"
        assert database.session.execute(database.select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).first() is None

        edited_payload = serialize_journal_for_form(journal)
        edited_payload["memo"] = "Detalle corregido"
        update_journal_draft(journal.id, edited_payload, case["requester_id"])
        revised_request = ApprovalEngine.request_approval(
            journal,
            actor=database.session.get(User, case["requester_id"]),
        )
        assert revised_request is not None
        assert revised_request.id != original_request.id
        assert revised_request.status == "Pending Approval"


@pytest.mark.skipif(sys.platform == "win32", reason="La prueba de concurrencia no es fiable en Windows.")
def test_concurrent_fiscal_year_close_submissions_share_one_approval_request(cloud_app):
    """Database row locks serialize concurrent requests for the same fiscal year."""
    with cloud_app.app_context():
        if database.engine.dialect.name not in {"postgresql", "mysql"}:
            pytest.skip("La serialización por SELECT FOR UPDATE requiere PostgreSQL o MySQL.")
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")

    barrier = Barrier(2, timeout=30)

    def submit_close(_attempt: int) -> str:
        with cloud_app.app_context():
            barrier.wait(timeout=10)
            return create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"]).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        journal_ids = list(executor.map(submit_close, range(2)))

    with cloud_app.app_context():
        assert journal_ids[0] == journal_ids[1]
        assert database.session.execute(
            database.select(ComprobanteContable.id).where(
                ComprobanteContable.fiscal_year_id == case["fiscal_year_id"],
                ComprobanteContable.is_fiscal_year_closing.is_(True),
            )
        ).scalars().all() == [journal_ids[0]]
        pending_requests = (
            database.session.execute(
                database.select(ApprovalRequest.id).where(
                    ApprovalRequest.document_id == journal_ids[0], ApprovalRequest.status == "Pending Approval"
                )
            )
            .scalars()
            .all()
        )
        assert len(pending_requests) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="La prueba de concurrencia no es fiable en Windows.")
def test_reversal_submission_waits_for_fiscal_year_close_lock(cloud_app):
    """Submitting a reversal waits for the source fiscal-year row lock."""
    with cloud_app.app_context():
        if database.engine.dialect.name not in {"postgresql", "mysql"}:
            pytest.skip("La serialización por SELECT FOR UPDATE requiere PostgreSQL o MySQL.")
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])
        source_period = database.session.execute(
            database.select(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == case["fiscal_year_id"])
        ).scalar_one()
        assert fiscal_year is not None
        fiscal_year.is_closed = False
        source_period.is_closed = False
        source_period.status = "open"
        reversal_year = FiscalYear(
            entity=case["company"],
            name="FY-2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(reversal_year)
        database.session.flush()
        book = database.session.execute(database.select(Book).where(Book.entity == case["company"])).scalar_one()
        income = database.session.execute(
            database.select(Accounts).where(Accounts.entity == case["company"], Accounts.classification == "ingreso")
        ).scalar_one()
        retained_earnings = database.session.execute(
            database.select(Accounts).where(Accounts.entity == case["company"], Accounts.classification == "patrimonio")
        ).scalar_one()
        database.session.add(
            AccountingPeriod(
                entity=case["company"],
                fiscal_year_id=reversal_year.id,
                name="2026-01",
                enabled=True,
                is_closed=False,
                status="open",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
            )
        )
        database.session.execute(
            database.update(CacaoConfig)
            .where(CacaoConfig.key == f"approval_engine_enabled_{case['company']}")
            .values(value="false")
        )
        database.session.commit()

        source = create_journal_draft(
            {
                "company": case["company"],
                "posting_date": "2025-12-31",
                "books": [book.code],
                "transaction_currency": book.currency,
                "base_currency": book.currency,
                "exchange_rate": "1",
                "lines": [
                    {"order": 1, "account": retained_earnings.code, "debit": "100", "credit": ""},
                    {"order": 2, "account": income.code, "debit": "", "credit": "100"},
                ],
            },
            user_id=case["requester_id"],
            assign_identifier=False,
        )
        submit_journal(source.id, user_id=case["requester_id"])
        reversal = duplicate_journal_as_reversal_draft(
            source.id,
            user_id=case["requester_id"],
            reversal_date_raw=date(2026, 1, 15),
            reason="Reversal serialization regression",
        )
        source_fiscal_year_id = database.session.execute(
            database.select(GLEntry.fiscal_year_id).where(GLEntry.voucher_id == source.id).limit(1)
        ).scalar_one()
        database.session.execute(
            database.select(FiscalYear.id).where(FiscalYear.id == source_fiscal_year_id).with_for_update()
        ).scalar_one()
        started = Event()
        completed = Event()

        def mark_fiscal_year_lock(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            if "fiscal_year" in statement.lower() and "for update" in statement.lower():
                started.set()

        def submit_reversal() -> str:
            with cloud_app.app_context():
                submit_journal(reversal.id, user_id=case["requester_id"])
                completed.set()
                return str(reversal.id)

        event.listen(database.engine, "before_cursor_execute", mark_fiscal_year_lock)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(submit_reversal)
                assert started.wait(timeout=10)
                assert not completed.wait(timeout=0.25)
                database.session.commit()
                assert completed.wait(timeout=10)
                assert future.result(timeout=1) == reversal.id
        finally:
            event.remove(database.engine, "before_cursor_execute", mark_fiscal_year_lock)


@pytest.mark.skipif(sys.platform == "win32", reason="La prueba de concurrencia no es fiable en Windows.")
def test_mysql_repeatable_read_close_sees_reversal_committed_after_snapshot(cloud_app):
    """A close waiting on its year lock reads reversals committed after its MySQL snapshot."""
    with cloud_app.app_context():
        if database.engine.dialect.name != "mysql":
            pytest.skip("La regresión de snapshot requiere MySQL.")
        isolation = database.session.execute(text("SELECT @@transaction_isolation")).scalar_one()
        if str(isolation).replace("_", "-").upper() != "REPEATABLE-READ":
            pytest.skip("La regresión requiere el aislamiento MySQL REPEATABLE READ.")
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        original = database.session.execute(
            database.select(GLEntry).where(GLEntry.voucher_id == f"source-{case['company']}")
        ).scalar_one()
        database.session.execute(
            database.select(FiscalYear.id).where(FiscalYear.id == case["fiscal_year_id"]).with_for_update()
        ).scalar_one()
        snapshot_started = Event()
        waiting_for_year_lock = Event()

        def observe_close_lock(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            normalized = statement.lower()
            if "fiscal_year" in normalized and "for update" in normalized:
                waiting_for_year_lock.set()

        def request_close_after_snapshot() -> str:
            with cloud_app.app_context():
                database.session.execute(
                    database.select(GLEntry.id).where(GLEntry.company == case["company"]).limit(1)
                ).first()
                snapshot_started.set()
                try:
                    create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
                except FiscalYearClosingError as exc:
                    return str(exc)
                return "close created"

        event.listen(database.engine, "before_cursor_execute", observe_close_lock)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(request_close_after_snapshot)
                assert snapshot_started.wait(timeout=10)
                assert waiting_for_year_lock.wait(timeout=10)
                database.session.add(
                    GLEntry(
                        posting_date=date(2026, 1, 15),
                        company=case["company"],
                        ledger_id=original.ledger_id,
                        account_id=original.account_id,
                        account_code=original.account_code,
                        debit=Decimal("100"),
                        credit=Decimal("0"),
                        account_currency=original.account_currency,
                        company_currency=original.company_currency,
                        exchange_rate=Decimal("1"),
                        voucher_type="journal_entry",
                        voucher_id=f"rr-reversal-{case['company']}",
                        reversal_of=original.id,
                        is_reversal=True,
                        is_cancelled=False,
                    )
                )
                database.session.commit()
                assert "reversas publicadas posteriormente" in future.result(timeout=10)
        finally:
            event.remove(database.engine, "before_cursor_execute", observe_close_lock)


def test_late_cross_year_reversal_rolls_back_fiscal_close_approval(cloud_app):
    """A reversal posted while waiting for approval blocks posting atomically."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        approval_request = database.session.execute(
            database.select(ApprovalRequest).where(ApprovalRequest.document_id == journal.id)
        ).scalar_one()
        original = database.session.execute(
            database.select(GLEntry).where(GLEntry.voucher_id == f"source-{case['company']}")
        ).scalar_one()
        database.session.add(
            GLEntry(
                posting_date=date(2026, 1, 15),
                company=case["company"],
                ledger_id=original.ledger_id,
                account_id=original.account_id,
                account_code=original.account_code,
                debit=Decimal("100"),
                credit=Decimal("0"),
                account_currency=original.account_currency,
                company_currency=original.company_currency,
                exchange_rate=Decimal("1"),
                voucher_type="journal_entry",
                voucher_id=f"reversal-{case['company']}",
                reversal_of=original.id,
                is_reversal=True,
                is_cancelled=False,
            )
        )
        database.session.commit()

        from cacao_accounting.approval_engine import ApprovalEngine

        approver = database.session.get(User, case["approver_id"])
        assert approver is not None
        with pytest.raises(ValueError, match="reversas publicadas posteriormente"):
            ApprovalEngine.approve(journal, approver, "Revisión independiente")
        database.session.rollback()

        database.session.refresh(approval_request)
        fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])
        assert approval_request.status == "Pending Approval"
        assert journal.status == "draft"
        assert fiscal_year.financial_closed is False
        assert fiscal_year.closing_voucher_id is None
        assert database.session.execute(database.select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).first() is None

        with pytest.raises(FiscalYearClosingError, match="reversas publicadas posteriormente"):
            create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])


def test_rejected_fiscal_close_can_be_resubmitted_without_duplicate_draft(cloud_app):
    """A rejected proposal leaves no close and retry reuses its matching draft."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        original_request = database.session.execute(
            database.select(ApprovalRequest).where(ApprovalRequest.document_id == journal.id)
        ).scalar_one()

        from cacao_accounting.approval_engine import ApprovalEngine

        approver = database.session.get(User, case["approver_id"])
        assert approver is not None
        ApprovalEngine.reject(journal, approver, "Revisar saldos")
        database.session.commit()
        fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])
        assert original_request.status == "Rejected"
        assert fiscal_year.financial_closed is False
        assert fiscal_year.closing_voucher_id is None
        assert database.session.execute(database.select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).first() is None

        retry = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        requests = (
            database.session.execute(
                database.select(ApprovalRequest)
                .where(ApprovalRequest.document_id == journal.id)
                .order_by(ApprovalRequest.created_at, ApprovalRequest.id)
            )
            .scalars()
            .all()
        )
        assert retry.id == journal.id
        assert len(requests) == 2
        assert {request.status for request in requests} == {"Rejected", "Pending Approval"}
        assert ApprovalEngine.approve(journal, approver, "Revisión independiente tras reintento") is True
        database.session.commit()
        database.session.refresh(fiscal_year)
        assert fiscal_year.financial_closed is True
        assert fiscal_year.closing_voucher_id == journal.id


def test_rejected_fiscal_close_with_edited_amount_is_not_resubmitted(cloud_app):
    """A rejected close edited away from calculated balances cannot be approved."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        request = database.session.execute(
            database.select(ApprovalRequest).where(ApprovalRequest.document_id == journal.id)
        ).scalar_one()

        from cacao_accounting.approval_engine import ApprovalEngine

        approver = database.session.get(User, case["approver_id"])
        assert approver is not None
        ApprovalEngine.reject(journal, approver, "Revisar saldos")
        database.session.commit()

        edited = serialize_journal_for_form(journal)
        edited["lines"][0]["debit"] = "90"
        edited["lines"][1]["credit"] = "90"
        update_journal_draft(journal.id, edited, case["requester_id"])

        with pytest.raises(FiscalYearClosingError, match="no coincide con los saldos calculados"):
            create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])

        database.session.refresh(request)
        assert request.status == "Rejected"
        assert (
            database.session.execute(
                database.select(ApprovalRequest.id).where(
                    ApprovalRequest.document_id == journal.id,
                    ApprovalRequest.status == "Pending Approval",
                )
            ).first()
            is None
        )


def test_rejected_fiscal_close_with_edited_bank_account_is_not_resubmitted(cloud_app):
    """A rejected close cannot be resubmitted with an unrelated bank association."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        request = database.session.execute(
            database.select(ApprovalRequest).where(ApprovalRequest.document_id == journal.id)
        ).scalar_one()
        retained_earnings = database.session.execute(
            database.select(Accounts).where(
                Accounts.entity == case["company"],
                Accounts.classification == "patrimonio",
            )
        ).scalar_one()
        bank = Bank(name=f"Banco {case['company']}")
        database.session.add(bank)
        database.session.flush()
        bank_account = BankAccount(
            bank_id=bank.id,
            company=case["company"],
            account_name="Cuenta de prueba",
            account_no=f"BANK-{case['company']}",
            currency=f"N{case['company'][1:]}",
            gl_account_id=retained_earnings.id,
            is_active=True,
        )
        database.session.add(bank_account)
        database.session.flush()

        from cacao_accounting.approval_engine import ApprovalEngine

        approver = database.session.get(User, case["approver_id"])
        assert approver is not None
        ApprovalEngine.reject(journal, approver, "Revisar asociación bancaria")
        database.session.commit()

        edited = serialize_journal_for_form(journal)
        edited["lines"][0]["bank_account"] = bank_account.id
        update_journal_draft(journal.id, edited, case["requester_id"])

        with pytest.raises(FiscalYearClosingError, match="no coincide con los saldos calculados"):
            create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])

        database.session.refresh(request)
        assert request.status == "Rejected"
        assert (
            database.session.execute(
                database.select(ApprovalRequest.id).where(
                    ApprovalRequest.document_id == journal.id,
                    ApprovalRequest.status == "Pending Approval",
                )
            ).first()
            is None
        )


def test_rejected_fiscal_close_with_edited_naming_series_is_not_resubmitted(cloud_app):
    """A rejected close with a different numbering series cannot be resubmitted."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        request = database.session.execute(
            database.select(ApprovalRequest).where(ApprovalRequest.document_id == journal.id)
        ).scalar_one()
        alternate_series = NamingSeries(
            name=f"Alternate close {case['company']}",
            entity_type="journal_entry",
            company=case["company"],
            prefix_template=f"ALT-{case['company']}-*YYYY*-",
            is_active=True,
            is_default=False,
        )
        database.session.add(alternate_series)
        database.session.flush()

        from cacao_accounting.approval_engine import ApprovalEngine

        approver = database.session.get(User, case["approver_id"])
        assert approver is not None
        ApprovalEngine.reject(journal, approver, "Revisar numeración")
        database.session.commit()

        edited = serialize_journal_for_form(journal)
        edited["naming_series_id"] = alternate_series.id
        update_journal_draft(journal.id, edited, case["requester_id"])

        with pytest.raises(FiscalYearClosingError, match="no coincide con los saldos calculados"):
            create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])

        database.session.refresh(request)
        assert request.status == "Rejected"
        assert (
            database.session.execute(
                database.select(ApprovalRequest.id).where(
                    ApprovalRequest.document_id == journal.id,
                    ApprovalRequest.status == "Pending Approval",
                )
            ).first()
            is None
        )


def test_fiscal_year_close_posts_directly_when_approval_engine_is_disabled(cloud_app):
    """The existing direct close path remains atomic when Cloud approvals are off."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        database.session.execute(
            database.update(CacaoConfig)
            .where(CacaoConfig.key == f"approval_engine_enabled_{case['company']}")
            .values(value="false")
        )
        database.session.commit()

        journal = create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])
        assert journal.status == "submitted"
        assert fiscal_year.financial_closed is True
        assert fiscal_year.closing_voucher_id == journal.id
        assert (
            database.session.execute(
                database.select(ApprovalRequest.id).where(ApprovalRequest.document_id == journal.id)
            ).first()
            is None
        )


def test_missing_independent_approval_rule_rolls_back_new_closing_draft(cloud_app):
    """A required independent route without a matching rule creates no evidence."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")
        database.session.execute(database.delete(ApprovalMatrix).where(ApprovalMatrix.company_id == case["company"]))
        database.session.commit()

        with pytest.raises(FiscalYearClosingError, match="no se creó el asiento contable"):
            create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])

        assert (
            database.session.execute(
                database.select(ComprobanteContable.id).where(ComprobanteContable.fiscal_year_id == case["fiscal_year_id"])
            ).first()
            is None
        )
        assert (
            database.session.execute(
                database.select(ApprovalRequest.id).where(ApprovalRequest.company_id == case["company"])
            ).first()
            is None
        )


def test_approval_request_failure_rolls_back_closing_draft(cloud_app):
    """Database failure while linking approval leaves no closing evidence."""
    with cloud_app.app_context():
        case = _create_fiscal_year_closing_case(f"E{uuid4().hex[:8]}")

        def fail_approval_insert(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT INTO APPROVAL_REQUEST"):
                raise IntegrityError(statement, parameters, RuntimeError("simulated approval write failure"))

        event.listen(database.engine, "before_cursor_execute", fail_approval_insert)
        try:
            with pytest.raises(IntegrityError):
                create_fiscal_year_closing_voucher(case["company"], case["fiscal_year_id"], case["requester_id"])
        finally:
            event.remove(database.engine, "before_cursor_execute", fail_approval_insert)

        assert (
            database.session.execute(
                database.select(ComprobanteContable.id).where(ComprobanteContable.fiscal_year_id == case["fiscal_year_id"])
            ).first()
            is None
        )
        assert (
            database.session.execute(
                database.select(ApprovalRequest.id).where(ApprovalRequest.company_id == case["company"])
            ).first()
            is None
        )
        fiscal_year = database.session.get(FiscalYear, case["fiscal_year_id"])
        assert fiscal_year.financial_closed is False
        assert fiscal_year.closing_voucher_id is None


def test_petty_cash_only_uses_preflight_when_independent_review_is_enabled(cloud_app):
    """An inactive approval engine retains the ordinary direct validation path."""
    company = f"E{uuid4().hex[:8]}"
    with cloud_app.app_context():
        _create_company(company)
        database.session.execute(
            database.update(CacaoConfig).where(CacaoConfig.key == f"approval_engine_enabled_{company}").values(value="false")
        )
        database.session.commit()

        with pytest.raises(ValueError, match="La caja chica seleccionada no existe"):
            create_petty_cash_expense(
                company=company,
                petty_cash_id="missing-fund",
                expense_account_code="6000",
                concept="Gasto de prueba",
                amount=100,
                cost_center_code="ADMIN",
                actor_id="accountant",
            )

        assert (
            database.session.execute(
                database.select(ComprobanteContable.id).where(ComprobanteContable.entity == company)
            ).first()
            is None
        )
