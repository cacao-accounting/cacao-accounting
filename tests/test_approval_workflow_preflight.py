# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Business regressions for operations without approval submission routes."""

from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest


from cacao_accounting import create_app
from cacao_accounting.approval_preflight import ApprovalWorkflowRequired
from cacao_accounting.bancos.services import create_petty_cash_expense
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.fiscal_year_closing import FiscalYearClosingError, create_fiscal_year_closing_voucher
from cacao_accounting.database import (
    CacaoConfig,
    ComprobanteContable,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    PettyCashExpense,
    database,
)


pytestmark = pytest.mark.database


@pytest.fixture
def cloud_app(tmp_path):
    """Create an isolated Cloud-mode database for approval policy behavior."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'approval-preflight.sqlite'}"
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


def test_independent_approval_rejects_unsupported_postings_before_draft(cloud_app):
    """Fiscal close and petty cash do not persist journals when review is required."""
    company = f"E{uuid4().hex[:8]}"
    with cloud_app.app_context():
        _create_company(company)
        fiscal_year = FiscalYear(
            entity=company,
            name="FY-2025",
            year_start_date=date(2025, 1, 1),
            year_end_date=date(2025, 12, 31),
            is_closed=True,
            financial_closed=False,
        )
        database.session.add(fiscal_year)
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

        with pytest.raises(FiscalYearClosingError, match="no se creó el asiento contable"):
            create_fiscal_year_closing_voucher(company, fiscal_year.id, user_id="accountant")

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
