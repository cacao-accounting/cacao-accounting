# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Casos R2R de revaluación cambiaria sobre exposiciones bancarias."""

from __future__ import annotations

import importlib
from typing import Any

import calendar
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


from cacao_accounting import create_app
from cacao_accounting.audit_chain import verify_audit_trail_chain
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationError, ExchangeRevaluationService
from cacao_accounting.contabilidad.fiscal_year_closing import (
    FiscalYearClosingError,
    _cross_year_reversal_pairs,
    calculate_closing_balances,
    create_fiscal_year_closing_voucher,
)
from cacao_accounting.document_identifiers import IdentifierConfigurationError
from cacao_accounting.contabilidad.services import _resolve_period_from_date
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    AuditTrail,
    Bank,
    BankAccount,
    Book,
    CashFlowAccountMapping,
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
from cacao_accounting.reportes.cash_flow import get_cash_flow_statement
from cacao_accounting.reportes.services import FinancialReportFilters

pytestmark = pytest.mark.database


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


def _pg_isolated_url() -> Any:
    """Crea URL de base PostgreSQL aislada preservando credenciales (Refs: #1910)."""
    raw = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("Este escenario requiere PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    nombre = f"cnc_{uuid4().hex[:10]}"
    admin_engine = create_engine(url.set(database="postgres"))
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    finally:
        admin_engine.dispose()
    return url.set(database=nombre)


def _drop_pg_isolated_url(url_aislada: Any) -> None:
    nombre = url_aislada.database
    admin_engine = create_engine(url_aislada.set(database="postgres"))
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname = '{nombre}' AND pid <> pg_backend_pid()"
                )
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture
def pg_business_app():
    """App PostgreSQL aislada con credenciales preservadas (Refs: #1910)."""
    url_aislada = _pg_isolated_url()
    application = None
    try:
        application = create_app(
            {
                **configuracion,
                # Regresi?n #1910: str(URL) redacta password; render_as_string lo conserva.
                "SQLALCHEMY_DATABASE_URI": url_aislada.render_as_string(hide_password=False),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": True,
            }
        )
        with application.app_context():
            database.create_all()
        yield application
    finally:
        if application is not None:
            with application.app_context():
                database.session.remove()
                database.engine.dispose()
        _drop_pg_isolated_url(url_aislada)


def _seed_bank_exposure(company: str) -> tuple[str, int, int, str, str, str, date]:
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


def test_revaluation_rejects_disabled_period_without_creating_run(business_app):
    """A disabled accounting period cannot create a run or GL evidence."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, _year, _month, _prior_id, period_id, _following_id, _following_start = _seed_bank_exposure(company)
        period = database.session.get(AccountingPeriod, period_id)
        assert period is not None
        period.enabled = False
        database.session.commit()

        with pytest.raises(ExchangeRevaluationError, match="periodo cerrado o inexistente"):
            ExchangeRevaluationService().run(company=company, period_id=period_id)

        assert database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company)).scalars().all() == []
        assert (
            database.session.execute(database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation"))
            .scalars()
            .all()
            == []
        )


def test_revaluation_form_does_not_choose_between_overlapping_periods(business_app):
    """Year/month form resolution rejects ambiguous accounting periods."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, year, month, _prior_id, period_id, _following_id, _following_start = _seed_bank_exposure(company)
        period = database.session.get(AccountingPeriod, period_id)
        assert period is not None
        database.session.add(
            AccountingPeriod(
                entity=company,
                fiscal_year_id=period.fiscal_year_id,
                name=f"Duplicado {period.name}",
                start=period.start,
                end=period.end,
                enabled=True,
                is_closed=False,
                status="open",
            )
        )
        database.session.flush()

        assert _resolve_period_from_date(company, str(year), str(month)) == ("", "")
        with pytest.raises(ExchangeRevaluationError, match="más de un periodo contable"):
            ExchangeRevaluationService().run(company=company, year=year, month=month)


def test_revaluation_void_rejects_disabled_period_without_reversal(business_app):
    """A posted run remains intact when its reversal period is disabled."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, _year, _month, _prior_id, period_id, _following_id, _following_start = _seed_bank_exposure(company)
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
        run_id = str(run.id)
        period = database.session.get(AccountingPeriod, period_id)
        assert period is not None
        period.enabled = False
        database.session.commit()

        with pytest.raises(ExchangeRevaluationError, match="periodo cerrado o inexistente"):
            ExchangeRevaluationService().void(run_id=run_id)

        assert database.session.get(ExchangeRevaluation, run_id).status == "posted"
        entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                )
            )
            .scalars()
            .all()
        )
        assert entries
        assert all(not entry.is_reversal for entry in entries)


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


def test_two_concurrent_runs_leave_one_active_adjustment(business_app, monkeypatch):
    """La segunda corrida concurrente no puede postear otro ajuste activo.

    La primera corrida conserva la reserva del periodo mientras la segunda
    intenta adquirirla. En SQLite la reserva rechaza de inmediato a la segunda;
    en los motores con ``FOR UPDATE`` la bloquea desde la resolución del periodo,
    antes de llegar a ``_lock_period_for_run``, así que la prueba observa la
    entrada de la segunda invocación en esa resolución. Cuando la primera
    confirma, la segunda relee la corrida previa. No hay reintento que normalice
    el resultado: la prueba observa que ambas invocaciones respetan la
    serialización.
    """
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, year, month, _prior_id, period_id, _following_id, _following_start = _seed_bank_exposure(company)
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        database_dialect = database.engine.dialect.name

    first_holds_lock = Event()
    release_first = Event()
    second_resolves_period = Event()
    second_rejected = Event()
    lock_calls = 0
    resolve_calls = 0
    real_resolve = ExchangeRevaluationService._resolve_period
    real_lock = ExchangeRevaluationService._lock_period_for_run
    real_reserve = ExchangeRevaluationService._reserve_sqlite_writer
    real_create_journal = ExchangeRevaluationService._create_journal

    def observe_resolve(self, company, year, month, period_id):
        nonlocal resolve_calls
        resolve_calls += 1
        if resolve_calls == 2:
            second_resolves_period.set()
        return real_resolve(self, company, year, month, period_id)

    def observe_lock(self, period):
        nonlocal lock_calls
        lock_calls += 1
        return real_lock(self, period)

    def observe_reserve(self, message):
        try:
            return real_reserve(self, message)
        except ExchangeRevaluationError:
            if lock_calls == 2:
                second_rejected.set()
            raise

    def pause_first(self, run, user_id, *, reversal=False, posting_date=None):
        if not first_holds_lock.is_set():
            first_holds_lock.set()
            assert release_first.wait(timeout=10)
        return real_create_journal(self, run, user_id, reversal=reversal, posting_date=posting_date)

    monkeypatch.setattr(ExchangeRevaluationService, "_resolve_period", observe_resolve)
    monkeypatch.setattr(ExchangeRevaluationService, "_lock_period_for_run", observe_lock)
    monkeypatch.setattr(ExchangeRevaluationService, "_reserve_sqlite_writer", observe_reserve)
    monkeypatch.setattr(ExchangeRevaluationService, "_create_journal", pause_first)

    def execute_once() -> tuple[str, str]:
        with business_app.app_context():
            try:
                run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
                return ("posted", str(run.id))
            except ExchangeRevaluationError as error:
                return ("rejected", str(error))
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(execute_once)
        assert first_holds_lock.wait(timeout=10)
        second = workers.submit(execute_once)
        if database_dialect == "sqlite":
            assert second_rejected.wait(timeout=10)
        else:
            assert second_resolves_period.wait(timeout=10)
        release_first.set()
        first_result = first.result(timeout=10)
        second_result = second.result(timeout=10)

    if database_dialect == "sqlite":
        assert first_result[0] == "posted"
        assert second_result[0] == "rejected"
        assert "Otra revalorización está ejecutándose" in second_result[1]
        posted_id = first_result[1]
        expected_statuses = {"posted"}
    else:
        assert first_result[0] == "posted"
        assert second_result[0] == "posted"
        posted_id = second_result[1]
        expected_statuses = {"posted", "voided"}

    with business_app.app_context():
        runs = list(
            database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company, year=year, month=month))
            .scalars()
            .all()
        )
        posted_runs = [run for run in runs if run.status == "posted"]
        assert {run.status for run in runs} == expected_statuses
        assert len(posted_runs) == 1
        assert posted_runs[0].id == posted_id
        assert len({run.journal_entry_id for run in posted_runs}) == 1

        entries = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                )
            )
            .scalars()
            .all()
        )
        active_originals = [entry for entry in entries if not entry.is_cancelled and not entry.is_reversal]
        assert {entry.voucher_id for entry in active_originals} == {posted_id}


def test_historical_rerun_respects_scope_and_closed_periods(business_app):
    """La reejecución histórica solo revierte corridas abiertas del ejercicio.

    La política documentada en #2120 exige revocar la corrida futura del mismo
    ejercicio, sin tocar períodos cerrados ni corridas de otros ejercicios.
    """
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, year, _month, prior_id, period_id, following_id, _following_start = _seed_bank_exposure(company)
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        service = ExchangeRevaluationService()

        prior_run = service.run(company=company, period_id=prior_id, user_id=actor_id)
        prior_run_id = str(prior_run.id)
        closed_period = database.session.get(AccountingPeriod, prior_id)
        assert closed_period is not None
        closed_period.is_closed = True
        database.session.commit()

        later_run = service.run(company=company, period_id=following_id, user_id=actor_id)
        later_run_id = str(later_run.id)

        other_year = FiscalYear(
            entity=company,
            name=str(year + 1),
            year_start_date=date(year + 1, 1, 1),
            year_end_date=date(year + 1, 12, 31),
            is_closed=False,
        )
        database.session.add(other_year)
        database.session.flush()
        foreign_run = ExchangeRevaluation(
            company=company,
            status="posted",
            docstatus=1,
            run_date=date(year + 1, 3, 31),
            month=3,
            year=year + 1,
            currency="NIO",
            document_no=f"OTRO-{company}",
        )
        database.session.add(foreign_run)
        database.session.flush()
        foreign_run_id = str(foreign_run.id)
        database.session.commit()

        rerun = service.run(company=company, period_id=period_id, user_id=actor_id)
        rerun_id = str(rerun.id)

        statuses = dict(
            database.session.execute(
                database.select(ExchangeRevaluation.id, ExchangeRevaluation.status).where(
                    ExchangeRevaluation.id.in_([prior_run_id, later_run_id, foreign_run_id, rerun_id])
                )
            ).all()
        )
        assert statuses[prior_run_id] == "posted"
        assert statuses[foreign_run_id] == "posted"
        assert statuses[later_run_id] == "voided"
        assert statuses[rerun_id] == "posted"

        entries = list(
            database.session.execute(database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation"))
            .scalars()
            .all()
        )
        assert any(not entry.is_cancelled for entry in entries if entry.voucher_id == prior_run_id)
        assert all(entry.is_cancelled for entry in entries if entry.voucher_id == later_run_id and not entry.is_reversal)
        assert any(entry.is_reversal and not entry.is_cancelled for entry in entries if entry.voucher_id == later_run_id)


def test_auto_reversal_fails_closed_when_run_period_is_unresolvable(business_app, monkeypatch):
    """No se anula evidencia si la fecha no resuelve un periodo contable único."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, _year, _month, period_id, _following_id, _next_id, _next_start = _seed_bank_exposure(company)
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)

        def unresolved_period(_company: str, _run_date: date) -> AccountingPeriod:
            raise IdentifierConfigurationError("La fecha corresponde a más de un periodo contable.")

        revaluation_module = importlib.import_module("cacao_accounting.contabilidad.exchange_revaluation_service")
        monkeypatch.setattr(revaluation_module, "resolve_accounting_period", unresolved_period)

        with pytest.raises(ExchangeRevaluationError, match="más de un periodo"):
            ExchangeRevaluationService()._void_outstanding_run(run, actor_id, run.run_date)

        assert run.status == "posted"


def test_cierre_fiscal_incluye_reversa_fx_interperiodo_real(business_app):
    """El cierre del año de reversión incluye FX y el año origen detecta el par futuro."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, year, _month, _prior_period_id, period_id, following_period_id, following_start = _seed_bank_exposure(
            company
        )
        fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(entity=company)).scalar_one()
        original_period = database.session.get(AccountingPeriod, period_id)
        following_period = database.session.get(AccountingPeriod, following_period_id)
        assert original_period is not None and following_period is not None
        fiscal_year.year_end_date = original_period.end
        following_year = FiscalYear(
            entity=company,
            name=f"{year}-following",
            year_start_date=following_start,
            year_end_date=following_period.end,
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(following_year)
        database.session.flush()
        following_period.fiscal_year_id = following_year.id
        for code in ("4.01.01.001", "5.01.02.001"):
            account = database.session.execute(database.select(Accounts).filter_by(entity=company, code=code)).scalar_one()
            account.classification = "income" if code.startswith("4.") else "expense"
        database.session.flush()
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        ledger_id = database.session.execute(database.select(Book.id).filter_by(entity=company)).scalar_one()
        database.session.commit()

        run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
        run_id = str(run.id)
        originals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        assert originals
        assert any(entry.account_code in {"4.01.01.001", "5.01.02.001"} for entry in originals)

        ExchangeRevaluationService().void(
            run_id=run_id,
            user_id=actor_id,
            reason="Reversa entre ejercicios para el cierre fiscal",
            reversal_date=following_start,
        )
        reversals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_reversal=True,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert reversals
        assert all(entry.posting_date == following_start for entry in reversals)
        assert all(entry.accounting_period_id == following_period_id for entry in reversals)

        prior_balances = calculate_closing_balances(company, fiscal_year, ledger_id=ledger_id)
        next_balances = calculate_closing_balances(company, following_year, ledger_id=ledger_id)
        assert {entry.account_code for entry in originals if entry.account_code.startswith(("4.", "5."))} <= {
            row["account_code"] for row in prior_balances
        }
        pnl_reversals = [entry for entry in reversals if entry.account_code.startswith(("4.", "5."))]
        assert pnl_reversals
        next_by_account = {row["account_code"]: row["balance"] for row in next_balances}
        assert all(next_by_account.get(entry.account_code) == entry.debit - entry.credit for entry in pnl_reversals)

        assert _cross_year_reversal_pairs(company, fiscal_year)
        fiscal_year.is_closed = True
        prior_periods = database.session.execute(
            database.select(AccountingPeriod).filter_by(fiscal_year_id=fiscal_year.id)
        ).scalars()
        for period in prior_periods:
            period.is_closed = True
        database.session.commit()
        with pytest.raises(FiscalYearClosingError, match="reversas publicadas posteriormente"):
            create_fiscal_year_closing_voucher(company, fiscal_year.id, actor_id)


def test_rerunning_the_same_period_leaves_one_active_adjustment(business_app):
    """Una segunda corrida anula la anterior y deja un solo ajuste activo."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, year, month, _prior_id, period_id, _following_id, _following_start = _seed_bank_exposure(company)
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        first = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
        first_id = str(first.id)
        second = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
        second_id = str(second.id)

        runs = list(
            database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company, year=year, month=month))
            .scalars()
            .all()
        )
        posted_runs = [run for run in runs if run.status == "posted"]
        assert len(posted_runs) == 1
        assert posted_runs[0].id == second_id
        assert database.session.get(ExchangeRevaluation, first_id).status == "voided"

        entries = list(
            database.session.execute(database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation"))
            .scalars()
            .all()
        )
        active_originals = [entry for entry in entries if not entry.is_cancelled and not entry.is_reversal]
        assert {entry.voucher_id for entry in active_originals} == {second_id}


def test_efe_conserva_apertura_tras_reversion_interperiodo(business_app):
    """#2265: una reversa real en el periodo siguiente no reescribe el corte previo."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, _year, _month, _opening_period_id, period_id, following_period_id, following_start = _seed_bank_exposure(
            company
        )
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        ledger_code = database.session.execute(database.select(Book.code).filter_by(entity=company)).scalar_one()
        bank_gl = database.session.execute(
            database.select(Accounts).filter_by(entity=company, code="1.01.02.001")
        ).scalar_one()
        for code, classification in (("4.01.01.001", "income"), ("5.01.02.001", "expense")):
            account = database.session.execute(database.select(Accounts).filter_by(entity=company, code=code)).scalar_one()
            account.classification = classification
        database.session.add(CashFlowAccountMapping(company=company, account_id=bank_gl.id, flow_section="cash"))
        database.session.commit()

        run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
        run_id = str(run.id)
        original_entries = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        assert original_entries and all(not entry.is_cancelled for entry in original_entries)
        bank_delta = sum(
            (entry.debit - entry.credit for entry in original_entries if entry.account_id == bank_gl.id),
            Decimal("0"),
        )
        assert bank_delta != Decimal("0")
        opening_entry = database.session.execute(
            database.select(GLEntry).filter_by(company=company, voucher_id=f"OPEN-{company}")
        ).scalar_one()
        opening_amount = Decimal(str(opening_entry.debit - opening_entry.credit))
        cut_before_reversal = opening_amount + bank_delta

        original_filters = FinancialReportFilters(
            company=company,
            ledger=ledger_code,
            accounting_period=period_id,
        )
        following_filters = FinancialReportFilters(
            company=company,
            ledger=ledger_code,
            accounting_period=following_period_id,
        )
        original_before = get_cash_flow_statement(original_filters).totals
        following_before = get_cash_flow_statement(following_filters).totals
        assert original_before["cash_closing"] == cut_before_reversal
        assert following_before["cash_opening"] == cut_before_reversal
        assert following_before["cash_closing"] == cut_before_reversal
        assert following_before["net_change_cash"] == Decimal("0")

        service = ExchangeRevaluationService()
        service.void(run_id=run_id, user_id=actor_id, reason="Reversa interperiodo del EFE", reversal_date=following_start)

        reversed_entries = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_reversal=True,
                )
            )
            .scalars()
            .all()
        )
        assert len(reversed_entries) == len(original_entries)
        assert all(entry.is_cancelled for entry in original_entries)
        assert all(entry.accounting_period_id == following_period_id for entry in reversed_entries)

        original_after = get_cash_flow_statement(original_filters).totals
        following_after = get_cash_flow_statement(following_filters).totals
        # El corte histórico y la apertura del periodo siguiente son inmutables.
        assert original_after["cash_closing"] == cut_before_reversal
        assert following_after["cash_opening"] == cut_before_reversal
        assert following_after["net_change_cash"] == -bank_delta
        assert following_after["cash_closing"] == opening_amount
        assert following_after["difference"] == Decimal("0")


def test_void_rechaza_reversa_en_fecha_anterior(business_app):
    """#2265: una reversa no puede adelantar el efecto de la revaluación."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, _year, _month, _opening_period_id, period_id, _following_period_id, following_start = _seed_bank_exposure(
            company
        )
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        bank_gl = database.session.execute(
            database.select(Accounts).filter_by(entity=company, code="1.01.02.001")
        ).scalar_one()
        for code, classification in (("4.01.01.001", "income"), ("5.01.02.001", "expense")):
            account = database.session.execute(database.select(Accounts).filter_by(entity=company, code=code)).scalar_one()
            account.classification = classification
        database.session.add(CashFlowAccountMapping(company=company, account_id=bank_gl.id, flow_section="cash"))
        database.session.commit()

        run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=actor_id)
        originales = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=str(run.id),
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        assert originales
        ids_originales = {entry.id for entry in originales}
        ledger_code = database.session.execute(database.select(Book.code).filter_by(entity=company)).scalar_one()
        filtros = FinancialReportFilters(company=company, ledger=ledger_code, accounting_period=period_id)
        cierre_antes = get_cash_flow_statement(filtros).totals["cash_closing"]

        fecha_adelantada = following_start - timedelta(days=5)
        with pytest.raises(ExchangeRevaluationError, match="fecha de reversión debe ser igual o posterior"):
            ExchangeRevaluationService().void(run_id=str(run.id), user_id=actor_id, reversal_date=fecha_adelantada)

        reversas = list(
            database.session.execute(
                database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation", is_reversal=True)
            )
            .scalars()
            .all()
        )
        assert not reversas
        corrida = database.session.get(ExchangeRevaluation, run.id)
        assert corrida.status == "posted"
        assert corrida.docstatus == 1
        activos = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company, voucher_type="exchange_revaluation", voucher_id=str(run.id), is_cancelled=False
                )
            )
            .scalars()
            .all()
        )
        assert {entry.id for entry in activos} == ids_originales
        assert get_cash_flow_statement(filtros).totals["cash_closing"] == cierre_antes


def test_pg_isolated_url_preserves_credentials():
    """Regresi?n #1910: str(URL) redacta password; render_as_string(hide_password=False) la conserva."""
    raw = "postgresql+pg8000://cacao:super-secret@127.0.0.1:5432/cacao"
    url = make_url(raw)
    assert "super-secret" not in str(url)
    assert "super-secret" in url.render_as_string(hide_password=False)


@pytest.mark.database
def test_concurrent_revaluation_void_pg_isolated_url(pg_business_app):
    """#1910/#1653: anulaci?n concurrente en PostgreSQL deja un solo reverso."""
    company = f"R{uuid4().hex[:9]}"
    with pg_business_app.app_context():
        company, year, month, _prior_id, period_id, _following_id, _following_start = _seed_bank_exposure(company)
        actor_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        run = ExchangeRevaluationService().run(company=company, year=year, month=month, period_id=period_id, user_id=actor_id)
        run_id = str(run.id)

    start_together = Barrier(2)

    def void_run() -> str:
        with pg_business_app.app_context():
            start_together.wait(timeout=10)
            try:
                ExchangeRevaluationService().void(run_id=run_id, user_id=actor_id, reason="anulacion concurrente")
                return "ok"
            except ExchangeRevaluationError as exc:
                return f"err:{exc}"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _i: void_run(), range(2)))

    assert results.count("ok") == 1, results
    assert any(r.startswith("err:") for r in results), results

    with pg_business_app.app_context():
        corrida = database.session.get(ExchangeRevaluation, run_id)
        assert corrida is not None and corrida.status == "voided"
        originals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company, voucher_type="exchange_revaluation", voucher_id=run_id, is_reversal=False
                )
            )
            .scalars()
            .all()
        )
        reversals = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_reversal=True,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(originals) == 2
        assert all(line.is_cancelled for line in originals)
        assert len(reversals) == 2
