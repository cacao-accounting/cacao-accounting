# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1488: el lote de importación pertenece al presupuesto autorizado.

La ruta autoriza el presupuesto de la URL; el servicio debe rechazar un lote
validado de otro presupuesto antes de insertar líneas o cambiar su estado.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
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
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def cross_budget_scenario():
    """Create two companies with their own budget and a validated batch for beta."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    def seed(company: str, label: str) -> dict[str, str]:
        entity = Entity(
            code=company,
            name=label,
            company_name=f"Compañía {label} {suffix}",
            tax_id=f"TAX-{label}-{suffix}",
            currency=currency.code,
            enabled=True,
            status="default" if label == "Alfa" else None,
        )
        database.session.add(entity)
        database.session.flush()
        ledger = Book(
            entity=company,
            code=f"L{label}{suffix}"[:10],
            name=f"Libro {label}",
            currency=currency.code,
            status="activo",
            is_primary=True,
        )
        year = FiscalYear(
            entity=company,
            name=f"FY-{label}-{suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        account = Accounts(
            entity=company,
            code=f"5{label}{suffix}"[:20],
            name="Gastos de operación",
            classification="expense",
            account_type="expense",
            group=False,
            active=True,
            enabled=True,
        )
        center = CostCenter(
            entity=company,
            code=f"OPS-{label}-{suffix}"[:20],
            name="Operaciones",
            active=True,
            enabled=True,
            default=True,
            group=False,
        )
        database.session.add_all([ledger, year, account, center])
        database.session.flush()
        period = AccountingPeriod(
            entity=company,
            fiscal_year_id=year.id,
            name=f"Marzo {label} 2026",
            start=date(2026, 3, 1),
            end=date(2026, 3, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.commit()
        budget = BudgetService().create_budget(
            {
                "company": company,
                "ledger_id": ledger.id,
                "fiscal_year_id": year.id,
                "budget_code": f"OPEX-{label}-{suffix}"[:50],
                "name": f"Gastos operativos {label}",
                "currency_id": currency.code,
            },
            user_id=None,
        )
        return {
            "company": company,
            "account_code": account.code,
            "center_code": center.code,
            "period": period.name,
            "budget_id": budget.id,
        }

    with app.app_context():
        database.create_all()
        suffix_currency = f"C{suffix}"[:10]
        currency = Currency(code=suffix_currency, name="Moneda presupuestaria", decimals=2, active=True, default=True)
        database.session.add(currency)
        database.session.flush()
        alpha = seed(f"A{suffix}"[:10], "Alfa")
        beta = seed(f"B{suffix}"[:10], "Beta")
        csv_content = (
            f"Cuenta,Centro de Costo,{beta['period']},Total\n" f"{beta['account_code']},{beta['center_code']},250.00,250.00\n"
        ).encode("utf-8")
        batch = BudgetImportService().validate_import(beta["budget_id"], "gastos-beta.csv", csv_content, user_id=None)
        alpha_company = alpha["company"]
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                User(
                    id=f"importer-{suffix}",
                    user=f"importer-{suffix}",
                    name="Importador",
                    password=b"unused",
                    active=True,
                    company=alpha_company,
                ),
            ]
        )
        database.session.flush()
        accounting_module = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        accounting_role = Roles(name=f"budget-import-{suffix}", note="Importación de presupuestos")
        database.session.add(accounting_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=accounting_role.id, module_id=accounting_module, access=True, view=True, import_=True),
                RolesUser(user_id=f"importer-{suffix}", role_id=accounting_role.id, active=True),
                UserCompanyAccess(user_id=f"importer-{suffix}", company_code=alpha_company),
            ]
        )
        database.session.commit()
        ids = {
            "importer": f"importer-{suffix}",
            "alpha_budget": alpha["budget_id"],
            "beta_budget": beta["budget_id"],
            "batch": batch.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _budget_lines(app, budget_id: str) -> int:
    """Count persisted lines for one budget."""
    with app.app_context():
        return len(database.session.execute(database.select(BudgetLine).filter_by(budget_id=budget_id)).scalars().all())


def _batch_status(app, batch_id: str) -> str:
    """Read the persisted status of one import batch."""
    with app.app_context():
        batch = database.session.get(BudgetImport, batch_id)
        assert batch is not None
        return batch.status


def test_service_rejects_a_batch_from_another_budget(cross_budget_scenario):
    """A validated batch cannot be imported through an unrelated budget id."""
    app, ids = cross_budget_scenario

    with app.app_context():
        service = BudgetImportService()
        with pytest.raises(BudgetError):
            service.insert_lines(ids["batch"], user_id=None, budget_id=ids["alpha_budget"])
        database.session.rollback()

    assert _batch_status(app, ids["batch"]) == "validated"
    assert _budget_lines(app, ids["alpha_budget"]) == 0
    assert _budget_lines(app, ids["beta_budget"]) == 0


def test_service_imports_the_batch_for_its_own_budget(cross_budget_scenario):
    """The owning budget keeps the normal import path."""
    app, ids = cross_budget_scenario

    with app.app_context():
        BudgetImportService().insert_lines(ids["batch"], user_id=None, budget_id=ids["beta_budget"])

    assert _batch_status(app, ids["batch"]) == "imported"
    assert _budget_lines(app, ids["beta_budget"]) == 1
    assert _budget_lines(app, ids["alpha_budget"]) == 0


def test_route_rejects_a_batch_owned_by_another_company(cross_budget_scenario):
    """The HTTP import of budget A cannot consume a validated batch of B."""
    app, ids = cross_budget_scenario
    client = _authenticated_client(app, ids["importer"])

    response = client.post(
        f"/accounting/presupuestos/{ids['alpha_budget']}/import",
        data={"import_id": ids["batch"]},
    )

    assert response.status_code == 200
    assert "no pertenece al presupuesto" in response.get_data(as_text=True)
    assert _batch_status(app, ids["batch"]) == "validated"
    assert _budget_lines(app, ids["alpha_budget"]) == 0
    assert _budget_lines(app, ids["beta_budget"]) == 0
