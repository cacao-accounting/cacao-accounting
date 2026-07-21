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

    def _resolve_descendant_ids(self, entity_id: str | None, model_class: type, include_descendants: bool) -> list[str]:
        """Resuelve IDs de descendientes jerarquicos si aplica."""
        if not entity_id:
            return []
        ids = [entity_id]
        if include_descendants:
            node = database.session.get(model_class, entity_id)
            if node:
                ids = [node.id] + [d.id for d in node.descendants]
        return ids

    def get_real_vs_budget_report(self, filters: Dict[str, Any]) -> PaginatedReport:
        """Genera el reporte Real vs Presupuesto integrando con la infraestructura de reportes."""
        company: Optional[str] = filters.get("company")
        budget_id: Optional[str] = filters.get("budget_id")
        ledger_id: Optional[str] = filters.get("ledger_id")
        fiscal_year_id: Optional[str] = filters.get("fiscal_year_id")
        granularity: str = filters.get("granularity") or "month"

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
        if not company or not fiscal_year_id or not ledger_id or not budget_id:
            return self._empty_report()
        if not self._validate_budget_access(budget, company, ledger_id, fiscal_year_id):
            return self._empty_report()

        cc_map, u_map, p_map, cc_names, u_names, p_names = self._build_dimension_maps(company)
        cost_center_id = self._translate_cc_filter(cost_center_id, cc_map)
        business_unit_id = self._translate_bu_filter(business_unit_id, u_map)
        project_id = self._translate_project_filter(project_id, p_map)

        all_periods = self._get_all_periods(fiscal_year_id)
        period_range_ids = self._get_period_range_ids(all_periods, period_from_id, period_to_id)

        include_descendants = filters.get("include_descendants") == "true" or filters.get("include_descendants") is True
        from cacao_accounting.database import Unit as DBUnit, Project as DBProject

        bu_ids = self._resolve_descendant_ids(business_unit_id, DBUnit, include_descendants)
        p_ids = self._resolve_descendant_ids(project_id, DBProject, include_descendants)

        budget_lines = self._get_budget_lines(
            budget_id, period_range_ids, cost_center_id, business_unit_id, project_id, bu_ids=bu_ids, p_ids=p_ids
        )
        actual_entries = self._get_actual_gl_entries(company, ledger_id, period_range_ids, account_from, account_to)

        account_info = {a.id: a for a in database.session.query(Accounts).filter_by(entity=company).all()}
        period_to_group = self._build_period_to_group(all_periods, granularity)

        data_map = self._populate_data_map(
            budget_lines,
            actual_entries,
            period_to_group,
            cost_center_id,
            business_unit_id,
            project_id,
            cc_map,
            u_map,
            p_map,
            bu_ids=bu_ids,
            p_ids=p_ids,
        )

        rows, total_budget, total_actual = self._build_report_rows(data_map, account_info, cc_names, u_names, p_names, filters)

        rows.sort(key=lambda x: (x.values["period_group"], x.values["account_code"]))
        columns = [
            "period_group",
            "account_code",
            "account_name",
            "cost_center",
            "business_unit",
            "project",
            "budget",
            "actual",
            "variance",
            "variance_pct",
        ]

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
        self, budget: Budget, company: Optional[str], ledger_id: Optional[str], fiscal_year_id: Optional[str]
    ) -> bool:
        """Validate budget belongs to requested company/ledger/fiscal_year."""
        if company and budget.company != company:
            return False
        if ledger_id and budget.ledger_id != ledger_id:
            return False
        if fiscal_year_id and budget.fiscal_year_id != fiscal_year_id:
            return False
        return True

    def _build_dimension_maps(
        self, company: str
    ) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]:
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
        self, all_periods: List[AccountingPeriod], period_from_id: Optional[str], period_to_id: Optional[str]
    ) -> List[str]:
        """Build list of period IDs within the requested range."""
        if not (period_from_id and period_to_id):
            return [p.id for p in all_periods]
        start_p = database.session.get(AccountingPeriod, period_from_id)
        end_p = database.session.get(AccountingPeriod, period_to_id)
        if not (start_p and end_p):
            return [p.id for p in all_periods]
        return [p.id for p in all_periods if p.start >= start_p.start and p.end <= end_p.end]

    def _get_budget_lines(
        self,
        budget_id: str,
        period_range_ids: List[str],
        cost_center_id: Optional[str],
        business_unit_id: Optional[str],
        project_id: Optional[str],
        bu_ids: Optional[List[str]] = None,
        p_ids: Optional[List[str]] = None,
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
        if bu_ids:
            query = query.filter(BudgetLine.business_unit_id.in_(bu_ids))
        elif business_unit_id:
            query = query.filter(BudgetLine.business_unit_id == business_unit_id)
        if p_ids:
            query = query.filter(BudgetLine.project_id.in_(p_ids))
        elif project_id:
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
        bu_ids: Optional[List[str]] = None,
        p_ids: Optional[List[str]] = None,
    ) -> Dict[tuple, Dict[str, Decimal]]:
        """Populate the data map with budget and actual amounts."""
        data_map: Dict[tuple, Dict[str, Decimal]] = {}
        for bl in budget_lines:
            self._add_budget_amount(data_map, bl, period_to_group)

        for ae in actual_entries:
            self._add_actual_amount(
                data_map,
                ae,
                period_to_group,
                cost_center_id,
                business_unit_id,
                project_id,
                cc_map,
                u_map,
                p_map,
                bu_ids=bu_ids,
                p_ids=p_ids,
            )
        return data_map

    def _ensure_bucket(self, data_map: Dict[tuple, Dict[str, Decimal]], key: tuple) -> None:
        """Create a budget/actual bucket when it does not exist yet."""
        if key not in data_map:
            data_map[key] = {"budget": Decimal("0"), "actual": Decimal("0")}

    def _add_budget_amount(
        self, data_map: Dict[tuple, Dict[str, Decimal]], budget_line: Any, period_to_group: Dict[str, str]
    ) -> None:
        """Accumulate the budget amount for a grouped budget line."""
        budget_group = period_to_group.get(budget_line.period_id)
        if not budget_group:
            return
        key = (
            budget_line.account_id,
            budget_line.cost_center_id,
            budget_line.business_unit_id,
            budget_line.project_id,
            budget_group,
        )
        self._ensure_bucket(data_map, key)
        data_map[key]["budget"] += budget_line.amount

    def _actual_amount(self, classification: Any, debit: Any, credit: Any) -> Decimal:
        """Return the signed amount for a GL entry based on account classification."""
        classif = classification.lower() if classification else ""
        if classif in ("gastos", "activo", "expense", "asset"):
            return debit - credit
        return credit - debit

    def _actual_dimensions(
        self,
        actual_entry: Any,
        cc_map: Dict[str, str],
        u_map: Dict[str, str],
        p_map: Dict[str, str],
    ) -> tuple[str | None, str | None, str | None]:
        """Translate actual entry dimension codes to IDs."""
        return (
            cc_map.get(actual_entry.cost_center_code),
            u_map.get(actual_entry.unit_code),
            p_map.get(actual_entry.project_code),
        )

    def _actual_matches_filters(
        self,
        cost_center_id: Optional[str],
        business_unit_id: Optional[str],
        project_id: Optional[str],
        actual_cost_center_id: str | None,
        actual_business_unit_id: str | None,
        actual_project_id: str | None,
        bu_ids: Optional[List[str]] = None,
        p_ids: Optional[List[str]] = None,
    ) -> bool:
        """Check whether an actual entry matches the requested dimension filters."""
        if cost_center_id and actual_cost_center_id != cost_center_id:
            return False
        if bu_ids:
            if actual_business_unit_id not in bu_ids:
                return False
        elif business_unit_id and actual_business_unit_id != business_unit_id:
            return False
        if p_ids:
            if actual_project_id not in p_ids:
                return False
        elif project_id and actual_project_id != project_id:
            return False
        return True

    def _add_actual_amount(
        self,
        data_map: Dict[tuple, Dict[str, Decimal]],
        actual_entry: Any,
        period_to_group: Dict[str, str],
        cost_center_id: Optional[str],
        business_unit_id: Optional[str],
        project_id: Optional[str],
        cc_map: Dict[str, str],
        u_map: Dict[str, str],
        p_map: Dict[str, str],
        bu_ids: Optional[List[str]] = None,
        p_ids: Optional[List[str]] = None,
    ) -> None:
        """Accumulate the actual amount for a GL entry."""
        actual_group = period_to_group.get(actual_entry.accounting_period_id)
        if not actual_group:
            return
        actual_cost_center_id, actual_business_unit_id, actual_project_id = self._actual_dimensions(
            actual_entry, cc_map, u_map, p_map
        )
        if not self._actual_matches_filters(
            cost_center_id,
            business_unit_id,
            project_id,
            actual_cost_center_id,
            actual_business_unit_id,
            actual_project_id,
            bu_ids=bu_ids,
            p_ids=p_ids,
        ):
            return
        key = (
            actual_entry.account_id,
            actual_cost_center_id,
            actual_business_unit_id,
            actual_project_id,
            actual_group,
        )
        self._ensure_bucket(data_map, key)
        data_map[key]["actual"] += self._actual_amount(actual_entry.classification, actual_entry.debit, actual_entry.credit)

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
