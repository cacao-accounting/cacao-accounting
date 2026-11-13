# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Casos R2R de revaluación cambiaria sobre exposiciones bancarias."""

from __future__ import annotations

import calendar
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.audit_chain import verify_audit_trail_chain
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationError, ExchangeRevaluationService
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    AuditTrail,
    Bank,
    BankAccount,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    ExchangeRate,
    ExchangeRevaluation,
    FiscalYear,
    GLEntry,
    Modules,
    User,
    database,
)


@pytest.fixture
def business_app(tmp_path):
    """Crea una aplicación real con una base aislada en el motor configurado."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'business.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base de pruebas dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _seed_bank_exposure(company: str) -> tuple[str, int, int, str]:
    """Record a USD bank balance and its closing-rate scenario for one company."""
    occupied_rates = set(
        database.session.execute(
            database.select(ExchangeRate.origin, ExchangeRate.destination, ExchangeRate.date).where(
                ExchangeRate.origin.in_(["NIO", "USD"]), ExchangeRate.destination.in_(["NIO", "USD"])
            )
        ).all()
    )
    candidate_periods = [(year, month) for year in range(2001, 2027) for month in range(2, 12)]
    offset = int(company[1:], 16) % len(candidate_periods)
    period_options = candidate_periods[offset:] + candidate_periods[:offset]
    closing_year, closing_month = next(
        (year, month)
        for year, month in period_options
        if ("USD", "NIO", date(year, month - 1, 1)) not in occupied_rates
        and ("USD", "NIO", date(year, month - 1, calendar.monthrange(year, month - 1)[1])) not in occupied_rates
        and ("USD", "NIO", date(year, month, 1)) not in occupied_rates
        and ("USD", "NIO", date(year, month, calendar.monthrange(year, month)[1])) not in occupied_rates
        and ("NIO", "USD", date(year, month - 1, 1)) not in occupied_rates
        and ("NIO", "USD", date(year, month - 1, calendar.monthrange(year, month - 1)[1])) not in occupied_rates
        and ("NIO", "USD", date(year, month, 1)) not in occupied_rates
        and ("NIO", "USD", date(year, month, calendar.monthrange(year, month)[1])) not in occupied_rates
    )
    prior_start = date(closing_year, closing_month - 1, 1)
    prior_end = date(closing_year, closing_month - 1, calendar.monthrange(closing_year, closing_month - 1)[1])
    period_start = date(closing_year, closing_month, 1)
    period_end = date(closing_year, closing_month, calendar.monthrange(closing_year, closing_month)[1])
    following_start = date(closing_year, closing_month + 1, 1)
    following_end = date(closing_year, closing_month + 1, calendar.monthrange(closing_year, closing_month + 1)[1])
    existing_currencies = set(
        database.session.execute(database.select(Currency.code).where(Currency.code.in_(["NIO", "USD"]))).scalars()
    )
    if "NIO" not in existing_currencies:
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    if "USD" not in existing_currencies:
        database.session.add(Currency(code="USD", name="Dólar", decimals=2, active=True))
    if database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one_or_none() is None:
        database.session.add(Modules(module="accounting", default=False, enabled=True))
    database.session.flush()
    database.session.add(
        Entity(
            code=company,
            name=f"Empresa de prueba R2R {company}",
            company_name=f"Empresa de prueba R2R {company} SA",
            tax_id=f"TAX-{company}",
            currency="NIO",
            enabled=True,
            status="default",
        )
    )
    database.session.flush()
    user = User(
        user=f"qa-{company}",
        name="Responsable de contabilidad",
        password=b"business-test",
        classification="admin",
        active=True,
        company=company,
    )
    database.session.add(user)

    ledger = Book(
        entity=company,
        code=f"L{company[1:]}",
        name=f"Libro principal {company}",
        status="activo",
        currency="NIO",
        default=True,
        is_primary=True,
    )
    bank_account_gl = Accounts(
        code="1.01.02.001",
        name="Banco en dólares",
        entity=company,
        group=False,
        active=True,
        enabled=True,
        account_type="bank",
    )
    gain_account = Accounts(
        code="4.01.01.001",
        name="Ganancia cambiaria no realizada",
        entity=company,
        group=False,
        active=True,
        enabled=True,
        account_type="income",
    )
    loss_account = Accounts(
        code="5.01.02.001",
        name="Pérdida cambiaria no realizada",
        entity=company,
        group=False,
        active=True,
        enabled=True,
        account_type="expense",
    )
    fiscal_year = FiscalYear(
        entity=company,
        name=str(closing_year),
        year_start_date=date(closing_year, 1, 1),
        year_end_date=date(closing_year, 12, 31),
        is_closed=False,
    )
    bank = Bank(name=f"Banco {company}", is_active=True)
    database.session.add_all([ledger, bank_account_gl, gain_account, loss_account, fiscal_year, bank])
    database.session.flush()

    prior_period = AccountingPeriod(
        entity=company,
        fiscal_year_id=fiscal_year.id,
        name="Cierre previo de septiembre",
        start=prior_start,
        end=prior_end,
        enabled=True,
        is_closed=False,
    )
    period = AccountingPeriod(
        entity=company,
        fiscal_year_id=fiscal_year.id,
        name="Cierre de octubre",
        start=period_start,
        end=period_end,
        enabled=True,
        is_closed=False,
    )
    following_period = AccountingPeriod(
        entity=company,
        fiscal_year_id=fiscal_year.id,
        name="Período siguiente",
        start=following_start,
        end=following_end,
        enabled=True,
        is_closed=False,
    )
    bank_account = BankAccount(
        company=company,
        bank_id=bank.id,
        account_name="Cuenta operativa USD",
        account_no=f"USD-{company}",
        gl_account_id=bank_account_gl.id,
        currency="USD",
        is_active=True,
    )
    database.session.add_all(
        [
            prior_period,
            period,
            following_period,
            bank_account,
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.00"), date=prior_start),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.30"), date=prior_end),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.30"), date=period_start),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.60"), date=period_end),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal(1) / Decimal("36.00"), date=prior_start),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal(1) / Decimal("36.30"), date=prior_end),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal(1) / Decimal("36.30"), date=period_start),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal(1) / Decimal("36.60"), date=period_end),
            CompanyDefaultAccount(
                company=company,
                default_bank=bank_account_gl.id,
                default_expense=loss_account.id,
                default_income=gain_account.id,
                unrealized_exchange_gain_account_id=gain_account.id,
                unrealized_exchange_loss_account_id=loss_account.id,
            ),
        ]
    )
    database.session.flush()
    database.session.add(
        GLEntry(
            company=company,
            ledger_id=ledger.id,
            account_id=bank_account_gl.id,
            bank_account_id=bank_account.id,
            voucher_type="bank_transfer",
            voucher_id=f"OPEN-{company}",
            posting_date=prior_start,
            debit=Decimal("3600"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("100"),
            credit_in_account_currency=Decimal("0"),
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36.00"),
        )
    )
    database.session.commit()
    return company, closing_year, closing_month, prior_period.id, period.id, following_period.id, following_start


def test_concurrent_revaluations_preserve_one_active_period_result(business_app):
    """Exercise month-end revaluation, prior-period reversal, and competing voids."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, year, month, prior_period_id, period_id, following_period_id, following_start = _seed_bank_exposure(company)
        database_dialect = database.engine.dialect.name
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        prior_run = ExchangeRevaluationService().run(company=company, period_id=prior_period_id, user_id=actor_id)
        prior_run_id = str(prior_run.id)

    start_together = Barrier(2)

    def close_month() -> str | None:
        with business_app.app_context():
            database.session.get(AccountingPeriod, period_id)
            start_together.wait(timeout=10)
            try:
                run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
            except ExchangeRevaluationError as error:
                if "revalorización está ejecutándose" not in str(error):
                    raise
                return None
            return str(run.id)

    with ThreadPoolExecutor(max_workers=2) as workers:
        run_ids = list(workers.map(lambda _index: close_month(), range(2)))
    if None in run_ids:
        run_ids = [run_id for run_id in run_ids if run_id is not None]
        with business_app.app_context():
            retry = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
            run_ids.append(str(retry.id))

    with business_app.app_context():
        runs = list(
            database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company, year=year, month=month))
            .scalars()
            .all()
        )
        prior_run = database.session.get(ExchangeRevaluation, prior_run_id)
        assert prior_run is not None and prior_run.status == "voided"
        assert len(run_ids) == 2
        assert len(runs) == 2
        assert {run.status for run in runs} == {"posted", "voided"}

        previous_period_lines = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    voucher_type="exchange_revaluation",
                    voucher_id=prior_run_id,
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(previous_period_lines) == 2
        assert all(line.is_cancelled for line in previous_period_lines)
        assert sum(line.debit for line in previous_period_lines) == Decimal("30.0000")
        assert sum(line.credit for line in previous_period_lines) == Decimal("30.0000")
        prior_reversals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    voucher_type="exchange_revaluation",
                    voucher_id=prior_run_id,
                    is_reversal=True,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(prior_reversals) == 2
        for reversal in prior_reversals:
            original = next(line for line in previous_period_lines if line.id == reversal.reversal_of)
            assert (reversal.debit, reversal.credit) == (original.credit, original.debit)
        voided_run = next(run for run in runs if run.status == "voided")
        original_lines = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    voucher_type="exchange_revaluation",
                    voucher_id=voided_run.id,
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        active_lines = list(
            database.session.execute(
                database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation", is_cancelled=False)
            )
            .scalars()
            .all()
        )
        assert len(original_lines) == 2
        assert all(line.is_cancelled for line in original_lines)
        assert len(active_lines) == 6
        assert sum(line.is_reversal for line in active_lines) == 4
        posted_run_id = next(run.id for run in runs if run.status == "posted")

    if database_dialect == "sqlite":
        with business_app.app_context():
            period = database.session.get(AccountingPeriod, following_period_id)
            assert period is not None
            period.is_closed = True
            database.session.commit()
        with business_app.app_context():
            with pytest.raises(ExchangeRevaluationError, match="periodo cerrado"):
                ExchangeRevaluationService().void(run_id=posted_run_id, reversal_date=following_start)
    else:
        period_read = Event()
        continue_void = Event()

        def void_after_period_read() -> str:
            with business_app.app_context():
                database.session.get(AccountingPeriod, following_period_id)
                period_read.set()
                assert continue_void.wait(timeout=10)
                with pytest.raises(ExchangeRevaluationError, match="periodo cerrado") as error:
                    ExchangeRevaluationService().void(run_id=posted_run_id, reversal_date=following_start)
                return str(error.value)

        with ThreadPoolExecutor(max_workers=1) as workers:
            pending_void = workers.submit(void_after_period_read)
            assert period_read.wait(timeout=10)
            with business_app.app_context():
                period = database.session.get(AccountingPeriod, following_period_id)
                assert period is not None
                period.is_closed = True
                database.session.commit()
            continue_void.set()
            assert "periodo cerrado" in pending_void.result(timeout=10)

    with business_app.app_context():
        posted_run = database.session.get(ExchangeRevaluation, posted_run_id)
        assert posted_run is not None and posted_run.status == "posted"
        posted_lines = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=posted_run_id,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(posted_lines) == 2
        assert all(not line.is_reversal for line in posted_lines)
        assert sum(line.debit for line in posted_lines) == Decimal("60.0000")
        assert sum(line.credit for line in posted_lines) == Decimal("60.0000")

    void_together = Barrier(2)

    def void_month() -> bool:
        with business_app.app_context():
            database.session.get(AccountingPeriod, period_id)
            void_together.wait(timeout=10)
            try:
                ExchangeRevaluationService().void(run_id=posted_run_id, user_id=actor_id)
                return True
            except ExchangeRevaluationError as error:
                assert "Solo se puede anular" in str(error) or "Otra anulación de revalorización está en curso" in str(error)
                return False

    with ThreadPoolExecutor(max_workers=2) as workers:
        void_results = list(workers.map(lambda _index: void_month(), range(2)))

    with business_app.app_context():
        posted_run = database.session.get(ExchangeRevaluation, posted_run_id)
        assert posted_run is not None and posted_run.status == "voided"
        assert sum(void_results) == 1
        all_originals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        all_reversals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    is_reversal=True,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(all_originals) == 6
        assert all(line.is_cancelled for line in all_originals)
        assert len(all_reversals) == 6
        originals_by_id = {line.id: line for line in all_originals}
        for reversal in all_reversals:
            original = originals_by_id[reversal.reversal_of]
            assert (reversal.debit, reversal.credit) == (original.credit, original.debit)
        audit_rows = list(
            database.session.execute(
                database.select(AuditTrail).where(AuditTrail.document_id.in_([prior_run_id, *[str(run.id) for run in runs]]))
            )
            .scalars()
            .all()
        )
        assert len(audit_rows) >= 5
        assert all(row.payload_hash and row.hash_version for row in audit_rows)
        assert verify_audit_trail_chain() == []

        # The mutable head must reveal missing append-only evidence even when
        # every audit row has disappeared from the same database snapshot.
        evidence_removal = database.session.begin_nested()
        database.session.execute(database.delete(AuditTrail))
        database.session.flush()
        assert verify_audit_trail_chain() == [{"row": "main", "finding": "head_pointer_mismatch"}]
        evidence_removal.rollback()
