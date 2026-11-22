# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1785: el reporte Real vs Presupuesto solo expone presupuestos aprobados.

Un presupuesto en borrador debe devolver el reporte vacío, incluso si se
invoca con su id; uno aprobado conserva su estructura y sus cifras. La
regresión cubre ambos estados con datos reales de línea presupuestaria.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.budget_report_service import BudgetReportService
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    Budget,
    BudgetLine,
    CostCenter,
    FiscalYear,
    User,
    database,
)


@pytest.fixture
def presupuestos(app, entorno_contable):
    """Crea un presupuesto en borrador y otro aprobado, con una línea cada uno."""
    sufijo = uuid4().hex[:6].upper()
    with app.app_context():
        centro = CostCenter(
            entity="cacao",
            code=f"CC{sufijo}",
            name=f"Centro {sufijo}",
            active=True,
            enabled=True,
        )
        database.session.add(centro)
        database.session.flush()
        book_id = database.session.execute(database.select(Book.id).filter_by(code="DEFAULT_BOOK")).scalar_one()
        fiscal_id = database.session.execute(database.select(FiscalYear.id).filter_by(id="FY2026")).scalar_one()
        period_id = database.session.execute(database.select(AccountingPeriod.id).filter_by(id="P2026-05")).scalar_one()
        admin_id = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        comunes = {
            "company": "cacao",
            "ledger_id": book_id,
            "fiscal_year_id": fiscal_id,
            "currency_id": "NIO",
            "name": f"Presupuesto {sufijo}",
        }
        borrador = Budget(budget_code=f"BOR-{sufijo}", status="draft", **comunes)
        aprobado = Budget(
            budget_code=f"APR-{sufijo}",
            status="approved",
            approved_by=admin_id,
            approved_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            **comunes,
        )
        database.session.add_all([borrador, aprobado])
        database.session.flush()
        for presupuesto in (borrador, aprobado):
            database.session.add(
                BudgetLine(
                    budget_id=presupuesto.id,
                    account_id=cuenta.id,
                    cost_center_id=centro.id,
                    period_id=period_id,
                    amount=Decimal("1200"),
                    description=f"Línea {presupuesto.status}",
                )
            )
        database.session.commit()
        return {
            "borrador": borrador.id,
            "aprobado": aprobado.id,
            "ledger": book_id,
            "fiscal": fiscal_id,
        }


def _filtros(presupuesto_id: str, datos: dict[str, str]) -> dict[str, str]:
    """Filtros completos para resolver un presupuesto concreto."""
    return {
        "company": "cacao",
        "budget_id": presupuesto_id,
        "ledger_id": datos["ledger"],
        "fiscal_year_id": datos["fiscal"],
        "period_from_id": "P2026-05",
        "period_to_id": "P2026-05",
        "granularity": "month",
    }


def test_presupuesto_en_borrador_devuelve_reporte_vacio(app, entorno_contable, presupuestos):
    """Aunque el id exista, un presupuesto no aprobado no expone cifras."""
    with app.app_context():
        reporte = BudgetReportService().get_real_vs_budget_report(_filtros(presupuestos["borrador"], presupuestos))

    assert reporte.rows == []
    assert reporte.columns == []
    assert reporte.totals == {}


def test_presupuesto_aprobado_expone_estructura_y_cifras(app, entorno_contable, presupuestos):
    """El presupuesto aprobado sí construye el reporte con su moneda y línea."""
    with app.app_context():
        reporte = BudgetReportService().get_real_vs_budget_report(_filtros(presupuestos["aprobado"], presupuestos))

    assert reporte.columns
    assert reporte.ledger_currency == "NIO"
    assert reporte.rows
    assert any(row.values["account_code"] == "5201" for row in reporte.rows)
    assert reporte.totals["budget"] == Decimal("1200.0000")
