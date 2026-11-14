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
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


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


def test_app_startup_fails_if_monthly_close_guard_cannot_be_installed(tmp_path, monkeypatch):
    """Startup must not continue without the persistent monthly-close uniqueness guard."""
    from cacao_accounting.database import helpers as database_helpers

    def fail_to_install_guard():
        raise SQLAlchemyError("unique index creation failed")

    monkeypatch.setattr(database_helpers, "_ensure_monthly_close_run_unique_constraint", fail_to_install_guard)

    with pytest.raises(SQLAlchemyError, match="unique index creation failed"):
        create_app(
            {
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'startup-guard.sqlite'}",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "TESTING": True,
                "SECRET_KEY": "monthly-close-startup-guard-test",
            }
        )


@pytest.fixture
def monthly_close_scenario(tmp_path, request):
    """Provide an accountant, an open period, and a dedicated database engine."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    isolation_level = getattr(request, "param", None)
    if database_uri.startswith("sqlite"):
        if isolation_level:
            pytest.skip("La regresión REPEATABLE READ requiere PostgreSQL.")
        database_uri = f"sqlite:///{tmp_path / 'monthly-close.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    elif isolation_level and not database_uri.startswith("postgresql"):
        pytest.skip("La regresión REPEATABLE READ requiere PostgreSQL.")

    settings = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    }
    if isolation_level:
        settings["SQLALCHEMY_ENGINE_OPTIONS"] = {
            **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
            "isolation_level": isolation_level,
        }
    app = create_app(settings)
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


@pytest.mark.skipif(
    not str(configuracion["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite"),
    reason="La prueba de actualización de esquema usa una base SQLite local aislada.",
)
def test_legacy_monthly_close_table_gets_unique_index(monthly_close_scenario):
    """Existing schemas gain a unique index without requiring table recreation."""
    from sqlalchemy import inspect

    from cacao_accounting.database.helpers import _ensure_monthly_close_run_unique_constraint

    app, _company, _period_id, _user_id, _endpoint = monthly_close_scenario
    with app.app_context():
        database.session.remove()
        with database.engine.begin() as connection:
            connection.execute(text("DROP TABLE period_close_check"))
            connection.execute(text("DROP TABLE period_close_run"))
            connection.execute(
                text("CREATE TABLE period_close_run (company VARCHAR(10) NOT NULL, period_id VARCHAR(26) NOT NULL)")
            )

        barrier = Barrier(2)

        def install_guard():
            with app.app_context():
                barrier.wait(timeout=10)
                _ensure_monthly_close_run_unique_constraint()

        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(lambda _: install_guard(), range(2)))

        unique_indexes = [
            index
            for index in inspect(database.engine).get_indexes("period_close_run")
            if index["name"] == "uq_period_close_run_company_period" and index["unique"]
        ]
        assert len(unique_indexes) == 1

        with pytest.raises(IntegrityError):
            with database.engine.begin() as connection:
                connection.execute(text("INSERT INTO period_close_run (company, period_id) VALUES ('cacao', 'P2026-05')"))
                connection.execute(text("INSERT INTO period_close_run (company, period_id) VALUES ('cacao', 'P2026-05')"))


@pytest.mark.skipif(
    not str(configuracion["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite"),
    reason="La prueba del índice homónimo usa una base SQLite local aislada.",
)
def test_legacy_monthly_close_wrong_named_index_fails_closed(monthly_close_scenario):
    """An index with the expected name but wrong columns must not satisfy the guard."""
    from cacao_accounting.database.helpers import _ensure_monthly_close_run_unique_constraint

    app, _company, _period_id, _user_id, _endpoint = monthly_close_scenario
    with app.app_context():
        database.session.remove()
        with database.engine.begin() as connection:
            connection.execute(text("DROP TABLE period_close_check"))
            connection.execute(text("DROP TABLE period_close_run"))
            connection.execute(
                text("CREATE TABLE period_close_run (company VARCHAR(10) NOT NULL, period_id VARCHAR(26) NOT NULL)")
            )
            connection.execute(text("CREATE INDEX uq_period_close_run_company_period ON period_close_run (company)"))

        with pytest.raises(RuntimeError, match="no protege company y period_id"):
            _ensure_monthly_close_run_unique_constraint()


@pytest.mark.skipif(
    not str(configuracion["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite"),
    reason="La prueba de actualización de esquema usa una base SQLite local aislada.",
)
def test_legacy_duplicate_monthly_close_runs_block_unique_index_without_rewriting_rows(monthly_close_scenario):
    """Ambiguous old runs are preserved and prevent automatic constraint creation."""
    from sqlalchemy import inspect

    from cacao_accounting.database.helpers import _ensure_monthly_close_run_unique_constraint

    app, _company, _period_id, _user_id, _endpoint = monthly_close_scenario
    with app.app_context():
        database.session.remove()
        with database.engine.begin() as connection:
            connection.execute(text("DROP TABLE period_close_check"))
            connection.execute(text("DROP TABLE period_close_run"))
            connection.execute(
                text("CREATE TABLE period_close_run (company VARCHAR(10) NOT NULL, period_id VARCHAR(26) NOT NULL)")
            )
            connection.execute(
                text(
                    "INSERT INTO period_close_run (company, period_id) " "VALUES ('cacao', 'P2026-05'), ('cacao', 'P2026-05')"
                )
            )

        with pytest.raises(RuntimeError, match="varias corridas"):
            _ensure_monthly_close_run_unique_constraint()

        with database.engine.connect() as connection:
            row_count = connection.execute(text("SELECT COUNT(*) FROM period_close_run")).scalar_one()
        unique_indexes = [
            index
            for index in inspect(database.engine).get_indexes("period_close_run")
            if index["name"] == "uq_period_close_run_company_period" and index["unique"]
        ]
        assert row_count == 2
        assert unique_indexes == []


@pytest.mark.parametrize("monthly_close_scenario", [None, "REPEATABLE READ"], indirect=True)
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
