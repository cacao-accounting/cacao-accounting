# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""R2R budget entry keeps one authorized amount per dimension combination."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest


from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import budget_import_service as budget_import_module
from cacao_accounting.contabilidad.budget_import_service import BudgetImportService
from cacao_accounting.contabilidad.budget_service import BudgetError, BudgetService
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    BudgetImport,
    BudgetLine,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
    database,
)


pytestmark = pytest.mark.database


@pytest.fixture
def budget_scenario(tmp_path):
    """Provide a real budget with a financial year, account, center, and open period."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'budget-integrity.sqlite'}"
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
        currency = Currency(code=f"C{suffix}", name="Moneda presupuestaria", decimals=2, active=True, default=False)
        company = Entity(
            code=f"B{suffix}",
            name=f"Empresa presupuestaria {suffix}",
            company_name=f"Empresa presupuestaria {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency.code,
            enabled=True,
            status="default",
        )
        database.session.add_all([currency, company])
        database.session.flush()

        ledger = Book(
            entity=company.code,
            code=f"L{suffix}",
            name="Libro fiscal",
            currency=currency.code,
            status="activo",
            is_primary=True,
        )
        year = FiscalYear(
            entity=company.code,
            name=f"FY-{suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        account = Accounts(
            entity=company.code,
            code=f"5{suffix}",
            name="Gastos de operación",
            classification="expense",
            account_type="expense",
            group=False,
            active=True,
            enabled=True,
        )
        center = CostCenter(
            entity=company.code,
            code="OPS",
            name="Operaciones",
            active=True,
            enabled=True,
            default=True,
            group=False,
        )
        database.session.add_all([ledger, year, account, center])
        database.session.flush()
        period = AccountingPeriod(
            entity=company.code,
            fiscal_year_id=year.id,
            name="Marzo 2026",
            start=date(2026, 3, 1),
            end=date(2026, 3, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.commit()

        budget = BudgetService().create_budget(
            {
                "company": company.code,
                "ledger_id": ledger.id,
                "fiscal_year_id": year.id,
                "budget_code": f"OPEX-{suffix}",
                "name": "Gastos operativos 2026",
                "currency_id": currency.code,
            },
            user_id=None,
        )
        scenario = {
            "app": app,
            "company": company.code,
            "account_id": account.id,
            "account_code": account.code,
            "center_id": center.id,
            "center_code": center.code,
            "period_id": period.id,
            "budget_id": budget.id,
            "budget_code": budget.budget_code,
            "ledger_id": ledger.id,
            "currency_code": currency.code,
            "import_service": BudgetImportService(),
        }

    yield scenario

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _budget_line_data(scenario, amount: str) -> dict[str, str | None]:
    """Build the expense authorization dimensions from the business scenario."""
    return {
        "account_id": scenario["account_id"],
        "cost_center_id": scenario["center_id"],
        "business_unit_id": None,
        "project_id": None,
        "period_id": scenario["period_id"],
        "amount": amount,
        "description": "Servicios de operación de marzo",
    }


def test_concurrent_expense_authorizations_cannot_duplicate_a_budget_combination(budget_scenario):
    """Two users cannot double the same cost authorization by submitting together."""
    app = budget_scenario["app"]
    start = Barrier(2)

    def add_authorization(amount: str) -> str:
        with app.app_context():
            try:
                start.wait(timeout=10)
                BudgetService().add_budget_line(
                    budget_scenario["budget_id"], _budget_line_data(budget_scenario, amount), user_id=None
                )
                return "created"
            except BudgetError:
                database.session.rollback()
                return "duplicate"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(add_authorization, ("100.00", "100.00")))

    with app.app_context():
        lines = database.session.query(BudgetLine).filter_by(budget_id=budget_scenario["budget_id"]).all()
        assert sorted(outcomes) == ["created", "duplicate"]
        assert len(lines) == 1
        assert lines[0].amount == Decimal("100.0000")


def test_import_confirmation_rejects_a_stale_expense_preview_atomically(budget_scenario):
    """An expense approved after preview must make a conflicting import fail as a whole."""
    scenario = budget_scenario
    app = scenario["app"]
    csv_content = (
        f"Cuenta,Centro de Costo,Marzo 2026,Total\n" f"{scenario['account_code']},{scenario['center_code']},250.00,250.00\n"
    ).encode("utf-8")

    with app.app_context():
        batch = scenario["import_service"].validate_import(
            scenario["budget_id"], "gastos-marzo.csv", csv_content, user_id=None
        )
        assert batch.status == "validated"
        assert batch.rows_inserted == 1

        BudgetService().add_budget_line(scenario["budget_id"], _budget_line_data(scenario, "300.00"), user_id=None)

        with pytest.raises(BudgetError, match="Ya existe una línea"):
            scenario["import_service"].insert_lines(batch.id, user_id=None)

        lines = database.session.query(BudgetLine).filter_by(budget_id=scenario["budget_id"]).all()
        imported_batch = database.session.get(BudgetImport, batch.id)
        assert [(line.amount, line.business_unit_id, line.project_id) for line in lines] == [(Decimal("300.0000"), None, None)]
        assert imported_batch is not None
        assert imported_batch.status == "failed"


def test_two_confirmations_of_the_same_expense_import_keep_imported_status(budget_scenario, monkeypatch):
    """Retrying an already imported expense preview cannot downgrade its status."""
    scenario = budget_scenario
    app = scenario["app"]
    csv_content = (
        f"Cuenta,Centro de Costo,Marzo 2026,Total\n" f"{scenario['account_code']},{scenario['center_code']},250.00,250.00\n"
    ).encode("utf-8")

    with app.app_context():
        batch = scenario["import_service"].validate_import(
            scenario["budget_id"], "gastos-marzo.csv", csv_content, user_id=None
        )
        import_id = batch.id

    after_validated_read = Barrier(2)
    original_lock = budget_import_module._lock_budget_for_line_write

    def wait_for_both_validated_reads(budget_id):
        after_validated_read.wait(timeout=10)
        return original_lock(budget_id)

    monkeypatch.setattr(budget_import_module, "_lock_budget_for_line_write", wait_for_both_validated_reads)

    def confirm_import() -> str:
        with app.app_context():
            try:
                scenario["import_service"].insert_lines(import_id, user_id=None)
                return "imported"
            except BudgetError:
                database.session.rollback()
                return "already processed"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: confirm_import(), range(2)))

    with app.app_context():
        batch = database.session.get(BudgetImport, import_id)
        lines = database.session.query(BudgetLine).filter_by(budget_id=scenario["budget_id"]).all()
        assert sorted(outcomes) == ["already processed", "imported"]
        assert batch is not None and batch.status == "imported"
        assert [(line.amount, line.business_unit_id, line.project_id) for line in lines] == [(Decimal("250.0000"), None, None)]
