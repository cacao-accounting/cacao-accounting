# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El estado de resultados clasifica costos de bienes y servicios.

Escenario de negocio (issue #2191): los catálogos base registraban la cuenta de
costo de ventas con ``rubro=Expense`` y ``account_type=cost_of_goods_sold``.
El estado de resultados decidía la sección solo por ``classification``, por lo
que el costo terminaba en gastos operativos, la utilidad bruta era igual a los
ingresos y el margen bruto quedaba inflado. La corrección usa la clasificación
normalizada y reconoce los tipos de cuenta de costo de bienes y de servicios,
sin reescribir cuentas ni asientos históricos.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.budget_report_service import BudgetReportService
from cacao_accounting.contabilidad.budget_service import BudgetService
from cacao_accounting.database import AccountingPeriod, Accounts, Book, FiscalYear, GLEntry, database
from cacao_accounting.api.dashboard import _accounting_monthly_result, _income_expense_balances
from cacao_accounting.reportes.analytics import get_kpi_snapshot, metric_value
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    OperationalReportFilters,
    get_gross_margin,
    get_income_statement_report,
    normalize_account_classification,
)

CATALOG_DIRECTORY = Path(__file__).resolve().parents[1] / "cacao_accounting" / "contabilidad" / "ctas" / "catalogos"
VOUCHER_PREFIX = "IS-COST-2191"
POSTING_DATE = date(2091, 5, 20)
PERIOD_ID = "P2191-05"
FISCAL_YEAR_ID = "FY2191"
COMPANY = "cacao"


def _read_catalog(filename: str) -> dict[str, dict[str, str]]:
    """Carga un catálogo CSV indexado por código de cuenta."""
    with (CATALOG_DIRECTORY / filename).open(encoding="utf-8", newline="") as handle:
        return {row["codigo"]: row for row in csv.DictReader(handle)}


def _post_entries(app, scenario: dict, entries: list[tuple[str, str, str, str]]) -> None:
    """Publica asientos de prueba en el libro y período del escenario."""
    with app.app_context():
        for suffix, account_code, debit, credit in entries:
            account = database.session.execute(
                select(Accounts).where(Accounts.entity == COMPANY, Accounts.code == account_code)
            ).scalar_one()
            database.session.add(
                GLEntry(
                    company=COMPANY,
                    ledger_id=scenario["book_id"],
                    account_id=account.id,
                    account_code=account.code,
                    account_currency="NIO",
                    company_currency="NIO",
                    exchange_rate=Decimal("1"),
                    posting_date=POSTING_DATE,
                    debit=Decimal(debit),
                    credit=Decimal(credit),
                    voucher_type="journal_entry",
                    voucher_id=f"{VOUCHER_PREFIX}-{suffix}",
                    fiscal_year_id=FISCAL_YEAR_ID,
                    accounting_period_id=PERIOD_ID,
                )
            )
        database.session.commit()


@pytest.fixture
def cost_accounts(app, entorno_contable):
    """Crea cuentas de ingreso, costo y gasto con clasificaciones heterogéneas."""
    definitions = {
        "cogs": ("9901", "Costo de bienes vendidos", "expense", "cost_of_goods_sold"),
        "service": ("9902", "Costo de servicios", "expense", "cost_of_service"),
        "expense": ("9903", "Gastos operativos", "expense", "expense"),
        "classified_cost": ("9904", "Costo clasificado sin tipo", "cost", None),
        "income": ("9905", "Ingresos por servicios", "income", "income"),
        "unknown_cost": ("9906", "Costo legado sin clasificación", "legacy-value", "cost_of_service"),
        "unclassified_cost": ("9907", "Costo legado sin rubro", None, "cost_of_goods_sold"),
    }
    with app.app_context():
        for code, name, classification, account_type in definitions.values():
            existing = database.session.execute(
                select(Accounts).where(Accounts.entity == COMPANY, Accounts.code == code)
            ).scalar_one_or_none()
            if existing is None:
                database.session.add(
                    Accounts(
                        entity=COMPANY,
                        code=code,
                        name=name,
                        classification=classification,
                        account_type=account_type,
                        group=False,
                        active=True,
                        enabled=True,
                    )
                )
        database.session.commit()
        fiscal_year = database.session.get(FiscalYear, FISCAL_YEAR_ID)
        if fiscal_year is None:
            database.session.add(
                FiscalYear(
                    id=FISCAL_YEAR_ID,
                    entity=COMPANY,
                    name="2091",
                    year_start_date=date(2091, 1, 1),
                    year_end_date=date(2091, 12, 31),
                    is_closed=False,
                )
            )
            database.session.flush()
        period = database.session.get(AccountingPeriod, PERIOD_ID)
        if period is None:
            database.session.add(
                AccountingPeriod(
                    id=PERIOD_ID,
                    entity=COMPANY,
                    fiscal_year_id=FISCAL_YEAR_ID,
                    name="Mayo 2091 costos",
                    start=date(2091, 5, 1),
                    end=date(2091, 5, 31),
                    status="open",
                    enabled=True,
                    is_closed=False,
                )
            )
        book_id = database.session.execute(select(Book.id).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        database.session.commit()

    scenario = {
        "book_id": book_id,
        "codes": {key: values[0] for key, values in definitions.items()},
    }
    yield scenario

    with app.app_context():
        database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id.like(f"{VOUCHER_PREFIX}%")))
        database.session.execute(
            database.delete(Accounts).where(Accounts.entity == COMPANY, Accounts.code.in_(list(scenario["codes"].values())))
        )
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.id == PERIOD_ID))
        database.session.execute(database.delete(FiscalYear).where(FiscalYear.id == FISCAL_YEAR_ID))
        database.session.commit()


@pytest.fixture
def reference_cost_case(app, cost_accounts):
    """Publica el caso de referencia: ingreso 1000, costo 400 y gasto 100."""
    _post_entries(
        app,
        cost_accounts,
        [
            ("income", cost_accounts["codes"]["income"], "0", "1000"),
            ("cogs", cost_accounts["codes"]["cogs"], "250", "0"),
            ("service", cost_accounts["codes"]["service"], "150", "0"),
            ("expense", cost_accounts["codes"]["expense"], "100", "0"),
        ],
    )
    return cost_accounts


def _income_statement_filters() -> FinancialReportFilters:
    return FinancialReportFilters(company=COMPANY, ledger="DEFAULT_BOOK", accounting_period=PERIOD_ID)


def test_base_catalogs_mark_cost_of_goods_sold_as_cost():
    """Los catálogos base español e inglés presentan el costo en su sección."""
    for filename in ("base_es.csv", "base_en.csv"):
        rows = _read_catalog(filename)
        assert rows["51.01"]["rubro"] == "Cost", filename
        assert rows["51.01"]["account_type"] == "cost_of_goods_sold", filename
        # Los gastos operativos conservan su clasificación.
        assert rows["52.02.037"]["rubro"] == "Expense", filename


def test_niif_and_us_gaap_service_costs_are_classified_as_cost():
    """Los catálogos NIIF Pymes y US GAAP mantienen costos de bienes y servicios."""
    niif = _read_catalog("niif_pymes_es.csv")
    assert niif["51.01.01"]["rubro"] == "Cost"
    assert niif["51.01.01"]["account_type"] == "cost_of_goods_sold"
    assert niif["51.01.03"]["rubro"] == "Cost"
    assert niif["51.01.03"]["account_type"] == ""
    assert niif["52.01.01"]["rubro"] == "Cost"

    us_gaap = _read_catalog("us_gaap.csv")
    assert us_gaap["510100"]["rubro"] == "Cost"
    assert us_gaap["510100"]["account_type"] == "cost_of_goods_sold"
    assert us_gaap["520100"]["rubro"] == "Cost"
    assert us_gaap["610100"]["rubro"] == "Expense"


@pytest.mark.parametrize("filename", ("base_es.csv", "base_en.csv", "niif_pymes_es.csv", "us_gaap.csv"))
def test_catalog_classifications_resolve_without_contradictions(filename):
    """Cada fila del catálogo conserva su rubro al normalizarse."""
    for row in _read_catalog(filename).values():
        resolved = normalize_account_classification(row["rubro"], row["account_type"])
        if row["rubro"] == "Cost" or row["account_type"] in {"cost_of_goods_sold", "cost_of_service"}:
            assert resolved == "cost", row
        elif row["rubro"] == "Expense":
            assert resolved == "expense", row


@pytest.mark.parametrize(
    ("classification", "account_type", "expected"),
    [
        ("Expense", "cost_of_goods_sold", "cost"),
        ("Expense", "cost_of_service", "cost"),
        ("Cost", None, "cost"),
        ("costos", None, "costo"),
        ("Expense", "expense", "expense"),
        ("Income", None, "income"),
        (None, None, ""),
    ],
)
def test_normalize_account_classification_prefers_cost_account_type(classification, account_type, expected):
    """El tipo de costo prevalece y la clasificación normalizada es el respaldo."""
    assert normalize_account_classification(classification, account_type) == expected


def test_income_statement_computes_gross_and_net_profit(reference_cost_case, app):
    """Ingreso 1000, costo 400 y gasto 100 producen utilidad bruta 600 y neta 500."""
    with app.app_context():
        report = get_income_statement_report(_income_statement_filters())

    assert report.totals["income"] == Decimal("1000")
    assert report.totals["cost"] == Decimal("400")
    assert report.totals["expense"] == Decimal("100")
    assert report.totals["gross_profit"] == Decimal("600")
    assert report.totals["net_profit"] == Decimal("500")
    assert report.totals.get("unclassified_accounts", 0) == 0

    by_code = {row.values["account_code"]: row.values for row in report.rows if row.values.get("account_code")}
    assert by_code[reference_cost_case["codes"]["cogs"]]["section"] == "cost"
    assert by_code[reference_cost_case["codes"]["cogs"]]["amount"] == Decimal("250")
    assert by_code[reference_cost_case["codes"]["service"]]["section"] == "cost"
    assert by_code[reference_cost_case["codes"]["service"]]["amount"] == Decimal("150")
    assert by_code[reference_cost_case["codes"]["expense"]]["section"] == "expense"


def test_income_statement_recognizes_cost_classification_without_account_type(cost_accounts, app):
    """Una cuenta con clasificación Cost y sin tipo de cuenta sigue siendo costo."""
    _post_entries(
        app,
        cost_accounts,
        [
            ("income-only", cost_accounts["codes"]["income"], "0", "500"),
            ("classified-cost", cost_accounts["codes"]["classified_cost"], "120", "0"),
        ],
    )
    with app.app_context():
        report = get_income_statement_report(_income_statement_filters())

    assert report.totals["cost"] == Decimal("120")
    assert report.totals["gross_profit"] == Decimal("380")
    assert report.totals["net_profit"] == Decimal("380")


def test_gross_margin_and_kpis_share_the_cost_classification(reference_cost_case, app):
    """El margen bruto y los KPIs usan la misma sección de costos que el reporte."""
    filters = OperationalReportFilters(company=COMPANY, date_from=POSTING_DATE, date_to=POSTING_DATE)
    with app.app_context():
        margin_report = get_gross_margin(filters)
        snapshot = get_kpi_snapshot(COMPANY, POSTING_DATE, POSTING_DATE)
        income_metric = metric_value(COMPANY, "income", POSTING_DATE, POSTING_DATE)
        expenses_metric = metric_value(COMPANY, "expenses", POSTING_DATE, POSTING_DATE)
        gross_margin_metric = metric_value(COMPANY, "gross_margin", POSTING_DATE, POSTING_DATE)

    assert margin_report.totals["income"] == Decimal("1000")
    assert margin_report.totals["cogs"] == Decimal("400")
    assert margin_report.totals["gross_margin"] == Decimal("600")
    assert income_metric == Decimal("1000")
    assert expenses_metric == Decimal("100")
    assert gross_margin_metric == Decimal("600")
    assert snapshot["metrics"]["cost"] == Decimal("400")
    assert snapshot["metrics"]["expenses"] == Decimal("100")
    assert snapshot["metrics"]["gross_margin"] == Decimal("600")
    assert snapshot["metrics"]["net_income"] == Decimal("500")

    with app.app_context():
        dashboard_balances = _income_expense_balances(COMPANY, POSTING_DATE, POSTING_DATE)
        monthly_result = _accounting_monthly_result(COMPANY, POSTING_DATE, POSTING_DATE)
    assert dashboard_balances == {"income": Decimal("1000"), "expenses": Decimal("500")}
    assert len(monthly_result) == 1
    assert monthly_result[0]["month"] == 5
    # `_accounting_monthly_result` serializa importes como texto decimal exacto;
    # la escala del GL es de ocho decimales, no de cuatro.
    assert Decimal(monthly_result[0]["income"]) == Decimal("1000")
    assert Decimal(monthly_result[0]["expenses"]) == Decimal("500")


def test_dashboard_keeps_typed_cost_with_missing_or_unknown_classification(cost_accounts, app):
    """Dashboard SQL includes cost account types even when classification is unusable."""
    _post_entries(
        app,
        cost_accounts,
        [
            ("unknown-income", cost_accounts["codes"]["income"], "0", "100"),
            ("unknown-cost", cost_accounts["codes"]["unknown_cost"], "20", "0"),
            ("unclassified-cost", cost_accounts["codes"]["unclassified_cost"], "30", "0"),
        ],
    )
    with app.app_context():
        balances = _income_expense_balances(COMPANY, POSTING_DATE, POSTING_DATE)
        monthly_result = _accounting_monthly_result(COMPANY, POSTING_DATE, POSTING_DATE)
        income_statement = get_income_statement_report(_income_statement_filters())

    assert balances == {"income": Decimal("100"), "expenses": Decimal("50")}
    assert len(monthly_result) == 1
    assert monthly_result[0]["month"] == 5
    assert Decimal(monthly_result[0]["income"]) == Decimal("100")
    assert Decimal(monthly_result[0]["expenses"]) == Decimal("50")
    assert income_statement.totals["cost"] == Decimal("50")


def test_monthly_result_preserves_eight_decimal_precision(cost_accounts, app):
    """El dashboard serializa importes de ocho decimales sin redondearlos."""
    _post_entries(
        app,
        cost_accounts,
        [
            ("precision-income", cost_accounts["codes"]["income"], "0", "0.00000001"),
            ("precision-cost", cost_accounts["codes"]["cogs"], "0.00000001", "0"),
        ],
    )
    with app.app_context():
        monthly_result = _accounting_monthly_result(COMPANY, POSTING_DATE, POSTING_DATE)
    assert len(monthly_result) == 1
    assert monthly_result[0]["month"] == 5
    # La notación científica es válida mientras el valor sea exacto y no se
    # haya redondeado a la escala anterior de cuatro decimales.
    assert Decimal(monthly_result[0]["income"]) == Decimal("0.00000001")
    assert Decimal(monthly_result[0]["expenses"]) == Decimal("0.00000001")


def test_budget_committed_amount_keeps_cost_accounts_debit_positive(reference_cost_case, app):
    """El compromiso presupuestal de una cuenta de costo no invierte su signo."""
    with app.app_context():
        account = database.session.execute(
            select(Accounts).where(Accounts.entity == COMPANY, Accounts.code == reference_cost_case["codes"]["cogs"])
        ).scalar_one()
        committed = BudgetService._compute_committed_amount(
            company=COMPANY,
            period_id=PERIOD_ID,
            resolved_account_id=account.id,
            resolved_ledger_id=reference_cost_case["book_id"],
            cost_center_code=None,
        )
    assert committed == Decimal("250")


def test_budget_actual_amount_uses_normalized_cost_classification():
    """El real versus presupuesto reconoce el tipo de costo y conserva el debe."""
    service = BudgetReportService()
    assert service._actual_amount("Cost", None, Decimal("250"), Decimal("0")) == Decimal("250")
    assert service._actual_amount("Expense", "cost_of_service", Decimal("150"), Decimal("0")) == Decimal("150")
    assert service._actual_amount("Expense", "expense", Decimal("100"), Decimal("0")) == Decimal("100")
    assert service._actual_amount("Income", None, Decimal("0"), Decimal("1000")) == Decimal("1000")


def test_budget_actual_query_returns_account_type(reference_cost_case, app):
    """La consulta de reales conserva el tipo de cuenta que decide el signo."""
    with app.app_context():
        rows = BudgetReportService()._get_actual_gl_entries(
            COMPANY,
            reference_cost_case["book_id"],
            [PERIOD_ID],
            reference_cost_case["codes"]["cogs"],
            reference_cost_case["codes"]["cogs"],
        )
    assert len(rows) == 1
    assert rows[0].account_type == "cost_of_goods_sold"
    assert rows[0].debit == Decimal("250")
