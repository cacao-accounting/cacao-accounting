# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""A monthly close period can be opened only once under concurrent requests."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event, current_thread
from uuid import uuid4

import pytest
from flask import url_for


from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import routes as accounting_routes
from cacao_accounting.contabilidad import services as accounting_services
from cacao_accounting.contabilidad.services import PeriodCloseError
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    FiscalYear,
    Modules,
    PeriodCloseRun,
    Roles,
    RolesUser,
    User,
    database,
)


pytestmark = pytest.mark.database


@pytest.fixture
def monthly_close_scenario(tmp_path):
    """Provide an accountant, an open period, and a dedicated database engine."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'monthly-close.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        suffix = uuid4().hex[:7].upper()
        currency = Currency(code=f"M{suffix}", name="Moneda de cierre", decimals=2, active=True, default=False)
        company = Entity(
            code=f"C{suffix}",
            name=f"Empresa cierre {suffix}",
            company_name=f"Empresa cierre {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency.code,
            enabled=True,
            status="default",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        fiscal_year = FiscalYear(
            entity=company.code,
            name=f"FY-{suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        database.session.add(fiscal_year)
        database.session.flush()
        period = AccountingPeriod(
            entity=company.code,
            fiscal_year_id=fiscal_year.id,
            name="Mayo 2026",
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
            enabled=True,
            is_closed=False,
        )
        user = User(
            user=f"close-{suffix}",
            name="Responsable de cierre",
            password=b"business-test",
            classification="admin",
            active=True,
            company=company.code,
        )
        database.session.add_all([period, user])
        module = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="accounting", default=True, enabled=True))
        elif module.enabled is not True:
            pytest.skip("El módulo de contabilidad debe estar activo en la base de pruebas.")

        admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one_or_none()
        if admin_role is None:
            admin_role = Roles(name="admin", note="Administrator")
            database.session.add(admin_role)
        database.session.flush()
        database.session.add(RolesUser(user_id=user.id, role_id=admin_role.id, active=True))
        company_code = company.code
        database.session.commit()
        period_id = period.id
        user_id = user.id
        with app.test_request_context():
            endpoint = url_for("contabilidad.nuevo_cierre_mensual")

    yield app, company_code, period_id, user_id, endpoint

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_concurrent_monthly_close_requests_share_one_period_run(monthly_close_scenario, monkeypatch):
    """Parallel close requests resolve to the same open run for one period."""
    app, company, period_id, user_id, endpoint = monthly_close_scenario
    after_authorization = Barrier(2)
    original_create = accounting_routes.create_monthly_close_run

    def synchronize_after_authorization(company_code: str, selected_period_id: str):
        after_authorization.wait(timeout=10)
        return original_create(company_code, selected_period_id)

    monkeypatch.setattr(accounting_routes, "create_monthly_close_run", synchronize_after_authorization)

    def request_close() -> tuple[int, str | None]:
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        response = client.post(endpoint, data={"period_id": period_id}, follow_redirects=False)
        return response.status_code, response.headers.get("Location")

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: request_close(), range(2)))

    with app.app_context():
        runs = (
            database.session.execute(database.select(PeriodCloseRun).filter_by(company=company, period_id=period_id))
            .scalars()
            .all()
        )
        period = database.session.get(AccountingPeriod, period_id)
        assert len(runs) == 1
        assert runs[0].run_status == "open"
        assert period is not None and period.is_closed is False
        assert [status for status, _ in responses] == [302, 302]
        assert responses[0][1] == responses[1][1]


def test_closed_period_rejects_monthly_close_creation(monthly_close_scenario):
    """A closed accounting period cannot acquire a new open close run."""
    app, company, period_id, user_id, endpoint = monthly_close_scenario
    with app.app_context():
        period = database.session.get(AccountingPeriod, period_id)
        assert period is not None
        period.is_closed = True
        database.session.commit()

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.post(endpoint, data={"period_id": period_id}, follow_redirects=False)

    with app.app_context():
        runs = (
            database.session.execute(database.select(PeriodCloseRun).filter_by(company=company, period_id=period_id))
            .scalars()
            .all()
        )
        assert runs == []
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/period-close/monthly")
        with client.session_transaction() as session:
            flashes = session.get("_flashes", [])
        assert any("periodo ya se encuentra cerrado" in message for _, message in flashes)


def test_monthly_close_retry_and_finalization_use_the_same_lock_order(monthly_close_scenario, monkeypatch):
    """A retry and finalization cannot deadlock by taking period/run locks in reverse order."""
    app, company, period_id, user_id, endpoint = monthly_close_scenario
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    initial_response = client.post(endpoint, data={"period_id": period_id}, follow_redirects=False)
    assert initial_response.status_code == 302

    with app.app_context():
        close_run = database.session.execute(
            database.select(PeriodCloseRun).filter_by(company=company, period_id=period_id)
        ).scalar_one()
        close_run_id = close_run.id
        database.session.commit()

    creator_has_period = Event()
    release_creator = Event()
    finalizer_attempted_period = Event()
    original_lock_period = accounting_services._lock_monthly_close_period

    def coordinate_period_lock(company_code: str, selected_period_id: str):
        worker_name = current_thread().name
        if worker_name.endswith("_0"):
            period = original_lock_period(company_code, selected_period_id)
            creator_has_period.set()
            assert release_creator.wait(timeout=10)
            return period
        finalizer_attempted_period.set()
        return original_lock_period(company_code, selected_period_id)

    monkeypatch.setattr(accounting_services, "_lock_monthly_close_period", coordinate_period_lock)

    def retry_creation() -> str:
        with app.app_context():
            try:
                close_run, created = accounting_services.create_monthly_close_run(company, period_id)
                database.session.commit()
                assert created is False
                return close_run.id
            finally:
                database.session.remove()

    def finalize_existing_run() -> str:
        with app.app_context():
            try:
                accounting_services.finalize_monthly_close(close_run_id, str(user_id))
                return "closed"
            except PeriodCloseError:
                database.session.rollback()
                return "validation_failed"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="monthly-close") as workers:
        creator = workers.submit(retry_creation)
        assert creator_has_period.wait(timeout=10)
        finalizer = workers.submit(finalize_existing_run)
        assert finalizer_attempted_period.wait(timeout=10)
        release_creator.set()
        assert creator.result(timeout=10) == close_run_id
        assert finalizer.result(timeout=10) in {"closed", "validation_failed"}

    with app.app_context():
        runs = (
            database.session.execute(database.select(PeriodCloseRun).filter_by(company=company, period_id=period_id))
            .scalars()
            .all()
        )
        assert len(runs) == 1
