# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para el reporte Real versus Presupuesto."""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from sqlalchemy import func

from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Budget,
    BudgetLine,
    GLEntry,
    CostCenter,
    Unit,
    Project,
    database,
)
from cacao_accounting.reportes.services import ReportRow, PaginatedReport


class BudgetReportService:
    """Servicio para el reporte comparativo Real vs Presupuesto."""

    def get_real_vs_budget_report(self, filters: Dict[str, Any]) -> PaginatedReport:
        """Genera el reporte Real vs Presupuesto integrando con la infraestructura de reportes."""
        company = filters.get("company")
        budget_id = filters.get("budget_id")
        ledger_id = filters.get("ledger_id")
        fiscal_year_id = filters.get("fiscal_year_id")
        granularity = filters.get("granularity", "month")

        period_from_id = filters.get("period_from_id")
        period_to_id = filters.get("period_to_id")
        account_from = filters.get("account_from")
        account_to = filters.get("account_to")
        cost_center_id = filters.get("cost_center_id")
        business_unit_id = filters.get("business_unit_id")
        project_id = filters.get("project_id")

        budget = database.session.get(Budget, budget_id)
        if not budget:
            return self._empty_report()
        if not self._validate_budget_access(budget, company, ledger_id, fiscal_year_id):
            return self._empty_report()

        cc_map, u_map, p_map, cc_names, u_names, p_names = self._build_dimension_maps(company)
        cost_center_id = self._translate_cc_filter(cost_center_id, cc_map)
        business_unit_id = self._translate_bu_filter(business_unit_id, u_map)
        project_id = self._translate_project_filter(project_id, p_map)

        all_periods = self._get_all_periods(fiscal_year_id)
        period_range_ids = self._get_period_range_ids(all_periods, period_from_id, period_to_id)

        budget_lines = self._get_budget_lines(budget_id, period_range_ids, cost_center_id, business_unit_id, project_id)
        actual_entries = self._get_actual_gl_entries(
            company, ledger_id, period_range_ids, account_from, account_to
        )

        account_info = {a.id: a for a in database.session.query(Accounts).filter_by(entity=company).all()}
        period_to_group = self._build_period_to_group(all_periods, granularity)

        data_map = self._populate_data_map(
            budget_lines, actual_entries, period_to_group,
            cost_center_id, business_unit_id, project_id,
            cc_map, u_map, p_map
        )

        rows, total_budget, total_actual = self._build_report_rows(
            data_map, account_info, cc_names, u_names, p_names, filters
        )

        rows.sort(key=lambda x: (x.values["period_group"], x.values["account_code"]))
        columns = ["period_group", "account_code", "account_name", "cost_center",
                   "business_unit", "project", "budget", "actual", "variance", "variance_pct"]

        return PaginatedReport(
            rows=rows,
            totals={"budget": total_budget, "actual": total_actual, "variance": total_actual - total_budget},
            columns=columns,
            ledger_currency=budget.currency_id,
        )

    def _empty_report(self) -> PaginatedReport:
        """Return an empty report structure."""
        return PaginatedReport(rows=[], totals={}, columns=[], ledger_currency=None)

    def _validate_budget_access(
        self, budget: Budget, company: Optional[str],
        ledger_id: Optional[str], fiscal_year_id: Optional[str]
    ) -> bool:
        """Validate budget belongs to requested company/ledger/fiscal_year."""
        if company and budget.company != company:
            return False
        if ledger_id and budget.ledger_id != ledger_id:
            return False
        if fiscal_year_id and budget.fiscal_year_id != fiscal_year_id:
            return False
        return True

    def _build_dimension_maps(self, company: str) -> Tuple[
        Dict[str, str], Dict[str, str], Dict[str, str],
        Dict[str, str], Dict[str, str], Dict[str, str]
    ]:
        """Build code→ID and ID→name maps for dimensions."""
        cc_objs = database.session.query(CostCenter).filter_by(entity=company).all()
        u_objs = database.session.query(Unit).filter_by(entity=company).all()
        p_objs = database.session.query(Project).filter_by(entity=company).all()
        cc_map = {c.code: c.id for c in cc_objs}
        u_map = {u.code: u.id for u in u_objs}
        p_map = {p.code: p.id for p in p_objs}
        cc_names = {c.id: c.name for c in cc_objs}
        u_names = {u.id: u.name for u in u_objs}
        p_names = {p.id: p.name for p in p_objs}
        return cc_map, u_map, p_map, cc_names, u_names, p_names

    def _translate_cc_filter(self, cost_center_id: Optional[str], cc_map: Dict[str, str]) -> Optional[str]:
        """Translate cost center code to ID if needed."""
        if cost_center_id and cost_center_id not in set(cc_map.values()):
            return cc_map.get(cost_center_id, cost_center_id)
        return cost_center_id

    def _translate_bu_filter(self, business_unit_id: Optional[str], u_map: Dict[str, str]) -> Optional[str]:
        """Translate business unit code to ID if needed."""
        if business_unit_id and business_unit_id not in set(u_map.values()):
            return u_map.get(business_unit_id, business_unit_id)
        return business_unit_id

    def _translate_project_filter(self, project_id: Optional[str], p_map: Dict[str, str]) -> Optional[str]:
        """Translate project code to ID if needed."""
        if project_id and project_id not in set(p_map.values()):
            return p_map.get(project_id, project_id)
        return project_id

    def _get_all_periods(self, fiscal_year_id: str) -> List[AccountingPeriod]:
        """Get all periods for a fiscal year ordered by start date."""
        return (
            database.session.query(AccountingPeriod)
            .filter_by(fiscal_year_id=fiscal_year_id)
            .order_by(AccountingPeriod.start)
            .all()
        )

    def _get_period_range_ids(
        self, all_periods: List[AccountingPeriod],
        period_from_id: Optional[str], period_to_id: Optional[str]
    ) -> List[str]:
        """Build list of period IDs within the requested range."""
        if not (period_from_id and period_to_id):
            return [p.id for p in all_periods]
        start_p = database.session.get(AccountingPeriod, period_from_id)
        end_p = database.session.get(AccountingPeriod, period_to_id)
        if not (start_p and end_p):
            return [p.id for p in all_periods]
        return [
            p.id for p in all_periods
            if p.start >= start_p.start and p.end <= end_p.end
        ]

    def _get_budget_lines(
        self,
        budget_id: str,
        period_range_ids: List[str],
        cost_center_id: Optional[str],
        business_unit_id: Optional[str],
        project_id: Optional[str],
    ) -> List[Any]:
        """Query budget lines with filters."""
        query = database.session.query(
            BudgetLine.account_id,
            BudgetLine.cost_center_id,
            BudgetLine.business_unit_id,
            BudgetLine.project_id,
            BudgetLine.period_id,
            BudgetLine.amount,
        ).filter(BudgetLine.budget_id == budget_id, BudgetLine.period_id.in_(period_range_ids))
        if cost_center_id:
            query = query.filter(BudgetLine.cost_center_id == cost_center_id)
        if business_unit_id:
            query = query.filter(BudgetLine.business_unit_id == business_unit_id)
        if project_id:
            query = query.filter(BudgetLine.project_id == project_id)
        return query.all()

    def _get_actual_gl_entries(
        self,
        company: str,
        ledger_id: str,
        period_range_ids: List[str],
        account_from: Optional[str],
        account_to: Optional[str],
    ) -> List[Any]:
        """Query GL entries for actual amounts."""
        g_query = (
            database.session.query(
                GLEntry.account_id,
                GLEntry.account_code,
                GLEntry.cost_center_code,
                GLEntry.unit_code,
                GLEntry.project_code,
                GLEntry.accounting_period_id,
                Accounts.classification,
                func.sum(GLEntry.debit).label("debit"),
                func.sum(GLEntry.credit).label("credit"),
            )
            .join(Accounts, GLEntry.account_id == Accounts.id)
            .filter(
                GLEntry.company == company,
                GLEntry.ledger_id == ledger_id,
                GLEntry.accounting_period_id.in_(period_range_ids),
                GLEntry.is_cancelled.is_(False),
            )
        )
        if account_from:
            g_query = g_query.filter(GLEntry.account_code >= account_from)
        if account_to:
            g_query = g_query.filter(GLEntry.account_code <= account_to)
        return g_query.group_by(
            GLEntry.account_id,
            GLEntry.account_code,
            GLEntry.cost_center_code,
            GLEntry.unit_code,
            GLEntry.project_code,
            GLEntry.accounting_period_id,
            Accounts.classification,
        ).all()

    def _build_period_to_group(self, all_periods: List[AccountingPeriod], granularity: str) -> Dict[str, str]:
        """Build mapping from period_id to group name based on granularity."""
        groupings = self._get_period_groupings(all_periods, granularity)
        period_to_group = {}
        for g_name, p_ids in groupings.items():
            for p_id in p_ids:
                period_to_group[p_id] = g_name
        return period_to_group

    def _populate_data_map(
        self,
        budget_lines: List[Any],
        actual_entries: List[Any],
        period_to_group: Dict[str, str],
        cost_center_id: Optional[str],
        business_unit_id: Optional[str],
        project_id: Optional[str],
        cc_map: Dict[str, str],
        u_map: Dict[str, str],
        p_map: Dict[str, str],
    ) -> Dict[tuple, Dict[str, Decimal]]:
        """Populate the data map with budget and actual amounts."""
        data_map: Dict[tuple, Dict[str, Decimal]] = {}
        for bl in budget_lines:
            bl_group = period_to_group.get(bl.period_id)
            if not bl_group:
                continue
            key = (bl.account_id, bl.cost_center_id, bl.business_unit_id, bl.project_id, bl_group)
            if key not in data_map:
                data_map[key] = {"budget": Decimal("0"), "actual": Decimal("0")}
            data_map[key]["budget"] += bl.amount

        for ae in actual_entries:
            ae_group = period_to_group.get(ae.accounting_period_id)
            if not ae_group:
                continue
            c_id = cc_map.get(ae.cost_center_code)
            if cost_center_id and c_id != cost_center_id:
                continue
            bu_id = u_map.get(ae.unit_code)
            if business_unit_id and bu_id != business_unit_id:
                continue
            pr_id = p_map.get(ae.project_code)
            if project_id and pr_id != project_id:
                continue
            key = (ae.account_id, c_id, bu_id, pr_id, ae_group)
            if key not in data_map:
                data_map[key] = {"budget": Decimal("0"), "actual": Decimal("0")}
            classif = ae.classification.lower() if ae.classification else ""
            if classif in ("gastos", "activo", "expense", "asset"):
                amount = ae.debit - ae.credit
            else:
                amount = ae.credit - ae.debit
            data_map[key]["actual"] += amount
        return data_map

    def _build_report_rows(
        self,
        data_map: Dict[tuple, Dict[str, Decimal]],
        account_info: Dict[str, Any],
        cc_names: Dict[str, str],
        u_names: Dict[str, str],
        p_names: Dict[str, str],
        filters: Dict[str, Any],
    ) -> Tuple[List[ReportRow], Decimal, Decimal]:
        """Build report rows from data map."""
        rows = []
        total_budget = Decimal("0")
        total_actual = Decimal("0")
        for key, values in data_map.items():
            acc_id, cc_id, u_id, proj_id, g_name = key
            acc = account_info.get(acc_id)
            budget_val = values["budget"]
            actual_val = values["actual"]
            variance = actual_val - budget_val
            if filters.get("only_variance") and variance == 0:
                continue
            total_budget += budget_val
            total_actual += actual_val
            rows.append(
                ReportRow(
                    values={
                        "period_group": g_name,
                        "account_code": acc.code if acc else "",
                        "account_name": acc.name if acc else "",
                        "cost_center": cc_names.get(cc_id, ""),
                        "business_unit": u_names.get(u_id, ""),
                        "project": p_names.get(proj_id, ""),
                        "budget": budget_val,
                        "actual": actual_val,
                        "variance": variance,
                        "variance_pct": (variance / budget_val * 100) if budget_val != 0 else None,
                    }
                )
            )
        return rows, total_budget, total_actual

    def _get_period_groupings(self, periods: List[AccountingPeriod], granularity: str) -> Dict[str, List[str]]:
        """Agrupa periodos por la granularidad seleccionada."""
        groupings = defaultdict(list)
        for p in periods:
            if granularity == "year":
                key = str(p.start.year)
            elif granularity == "semester":
                key = f"{p.start.year} S{1 if p.start.month <= 6 else 2}"
            elif granularity == "quarter":
                key = f"{p.start.year} Q{(p.start.month - 1) // 3 + 1}"
            else:  # month
                key = p.name
            groupings[key].append(p.id)
        return dict(groupings)
