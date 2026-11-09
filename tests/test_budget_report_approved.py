# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El comparativo Real vs Presupuesto solo consume presupuestos aprobados.

Escenario de negocio: el selector de la UI ofrece presupuestos aprobados, pero
un POST manipulado puede enviar el ID de un borrador. El servicio debe validar
el estado en servidor y no devolver líneas de un presupuesto no aprobado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.budget_report_service import BudgetReportService
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    Budget,
    BudgetLine,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
    Modules,
    User,
    UserCompanyAccess,
    database,
)

FECHA = date(2026, 1, 1)
CONTRASENA = "reporte-presupuesto-2026"


@pytest.fixture
def presupuestos_reporte():
    """Dos presupuestos con línea: uno borrador y otro aprobado."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="admin", company_code="cacao"),
            ]
        )
        database.session.flush()
        libro = Book(
            entity="cacao",
            code="LOCAL",
            name="Principal",
            status="activo",
            currency="NIO",
            default=True,
            is_primary=True,
        )
        anio = FiscalYear(
            entity="cacao",
            name="2026",
            year_start_date=FECHA,
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        cuenta = Accounts(
            code="5.01.01.001",
            name="Gastos",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="expense",
        )
        centro = CostCenter(
            code="CC-1",
            name="Centro",
            entity="cacao",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([libro, anio, cuenta, centro])
        database.session.flush()
        periodo = AccountingPeriod(
            entity="cacao",
            fiscal_year_id=anio.id,
            name="2026-01",
            start=FECHA,
            end=date(2026, 1, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(periodo)
        database.session.flush()
        presupuestos = {}
        for estado in ("draft", "approved"):
            presupuesto = Budget(
                company="cacao",
                ledger_id=libro.id,
                fiscal_year_id=anio.id,
                budget_code=f"B-{estado}",
                name=f"Presupuesto {estado}",
                currency_id="NIO",
                status=estado,
            )
            database.session.add(presupuesto)
            database.session.flush()
            database.session.add(
                BudgetLine(
                    budget_id=presupuesto.id,
                    account_id=cuenta.id,
                    cost_center_id=centro.id,
                    period_id=periodo.id,
                    amount=Decimal("100"),
                )
            )
            presupuestos[estado] = presupuesto.id
        database.session.commit()
        ids = {
            "draft": presupuestos["draft"],
            "approved": presupuestos["approved"],
            "libro": libro.id,
            "anio": anio.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _reporte(application, ids, estado: str):
    with application.app_context():
        return BudgetReportService().get_real_vs_budget_report(
            {
                "company": "cacao",
                "ledger_id": ids["libro"],
                "fiscal_year_id": ids["anio"],
                "budget_id": ids[estado],
                "granularity": "month",
            }
        )


def test_reporte_ignora_presupuesto_en_borrador(presupuestos_reporte):
    """Un ID de borrador no devuelve líneas del presupuesto."""
    application, ids = presupuestos_reporte

    reporte = _reporte(application, ids, "draft")

    assert reporte.rows == []
    assert reporte.totals == {}


def test_reporte_incluye_presupuesto_aprobado(presupuestos_reporte):
    """Control positivo: el presupuesto aprobado sí genera filas."""
    application, ids = presupuestos_reporte

    reporte = _reporte(application, ids, "approved")

    assert reporte.rows
    assert reporte.totals


def test_reporte_renderiza_la_etiqueta_de_variacion(presupuestos_reporte):
    """La etiqueta «Var %» no se interpreta como formato gettext."""
    application, ids = presupuestos_reporte
    client = application.test_client()
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200

    response = client.get(
        "/accounting/presupuestos/report/real-vs-budget",
        query_string={
            "company": "cacao",
            "ledger_id": ids["libro"],
            "fiscal_year_id": ids["anio"],
            "budget_id": ids["approved"],
        },
    )

    assert response.status_code == 200
    assert "Var %" in response.get_data(as_text=True)
