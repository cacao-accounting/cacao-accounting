# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para la gestión de presupuestos."""

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, Optional

from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    Budget,
    BudgetLine,
    CostCenter,
    Entity,
    FiscalYear,
    Project,
    Unit,
    database,
)


class BudgetError(Exception):
    """Excepción base para errores de presupuesto."""

    _safe_for_display = True


class BudgetService:
    """Servicio para manejar la lógica de negocio de presupuestos."""

    def create_budget(self, data: Dict[str, Any], user_id: str) -> Budget:
        """Crea un nuevo presupuesto en estado borrador."""
        self._validate_header_data(data)

        budget = Budget(
            company=data["company"],
            ledger_id=data["ledger_id"],
            fiscal_year_id=data["fiscal_year_id"],
            budget_code=data["budget_code"],
            name=data["name"],
            description=data.get("description"),
            currency_id=data["currency_id"],
            status="draft",
            created_by=user_id,
        )
        database.session.add(budget)
        database.session.commit()
        return budget

    def update_budget(self, budget_id: str, data: Dict[str, Any], user_id: str) -> Budget:
        """Actualiza el encabezado de un presupuesto en borrador."""
        budget = database.session.get(Budget, budget_id)
        if not budget:
            raise BudgetError("Presupuesto no encontrado.")

        if budget.status != "draft":
            raise BudgetError("Solo se pueden editar presupuestos en estado borrador.")

        # No permitir cambiar compañía, libro o año fiscal si ya tiene líneas
        has_lines = database.session.query(BudgetLine).filter_by(budget_id=budget_id).first() is not None
        if has_lines and (
            data.get("company") != budget.company
            or data.get("ledger_id") != budget.ledger_id
            or data.get("fiscal_year_id") != budget.fiscal_year_id
        ):
            raise BudgetError("No se puede cambiar la compañía, libro o año fiscal si el presupuesto ya tiene líneas.")

        self._validate_header_data(data, exclude_id=budget_id)

        budget.budget_code = data.get("budget_code", budget.budget_code)
        budget.name = data.get("name", budget.name)
        budget.description = data.get("description", budget.description)
        budget.currency_id = data.get("currency_id", budget.currency_id)
        budget.modified_by = user_id
        budget.modified = datetime.now()

        database.session.commit()
        return budget

    def add_budget_line(self, budget_id: str, data: Dict[str, Any], user_id: str) -> BudgetLine:
        """Agrega una línea a un presupuesto en borrador."""
        budget = database.session.get(Budget, budget_id)
        if not budget or budget.status != "draft":
            raise BudgetError("El presupuesto no existe o no está en borrador.")

        self._validate_line_data(budget, data)

        line = BudgetLine(
            budget_id=budget_id,
            account_id=data["account_id"],
            cost_center_id=data["cost_center_id"],
            business_unit_id=data.get("business_unit_id"),
            project_id=data.get("project_id"),
            period_id=data["period_id"],
            amount=Decimal(str(data["amount"])),
            description=data.get("description"),
            created_by=user_id,
        )
        database.session.add(line)
        database.session.commit()
        return line

    def update_budget_line(self, line_id: str, data: Dict[str, Any], user_id: str) -> BudgetLine:
        """Actualiza una línea de presupuesto."""
        line = database.session.get(BudgetLine, line_id)
        if not line:
            raise BudgetError("Línea de presupuesto no encontrada.")

        budget = database.session.get(Budget, line.budget_id)
        if not budget or budget.status != "draft":
            raise BudgetError("Solo se pueden editar líneas de presupuestos en borrador.")

        self._validate_line_data(budget, data, exclude_line_id=line_id)

        line.account_id = data.get("account_id", line.account_id)
        line.cost_center_id = data.get("cost_center_id", line.cost_center_id)
        line.business_unit_id = data.get("business_unit_id", line.business_unit_id)
        line.project_id = data.get("project_id", line.project_id)
        line.period_id = data.get("period_id", line.period_id)
        line.amount = Decimal(str(data.get("amount", line.amount)))
        line.description = data.get("description", line.description)
        line.modified_by = user_id
        line.modified = datetime.now()

        database.session.commit()
        return line

    def delete_budget_line(self, line_id: str, user_id: str):
        """Elimina una línea de presupuesto."""
        line = database.session.get(BudgetLine, line_id)
        if not line:
            return

        budget = database.session.get(Budget, line.budget_id)
        if not budget or budget.status != "draft":
            raise BudgetError("Solo se pueden eliminar líneas de presupuestos en borrador.")

        database.session.delete(line)
        database.session.commit()

    def approve_budget(self, budget_id: str, user_id: str):
        """Aprueba un presupuesto."""
        budget = database.session.get(Budget, budget_id)
        if not budget or budget.status != "draft":
            raise BudgetError("El presupuesto no puede ser aprobado.")

        # Validar que tenga al menos una línea
        has_lines = database.session.query(BudgetLine).filter_by(budget_id=budget_id).first() is not None
        if not has_lines:
            raise BudgetError("No se puede aprobar un presupuesto sin líneas.")

        budget.status = "approved"
        budget.approved_by = user_id
        budget.approved_at = datetime.now()
        database.session.commit()

    def close_budget(self, budget_id: str, user_id: str):
        """Cierra un presupuesto aprobado."""
        budget = database.session.get(Budget, budget_id)
        if not budget or budget.status != "approved":
            raise BudgetError("Solo se pueden cerrar presupuestos aprobados.")

        budget.status = "closed"
        budget.closed_by = user_id
        budget.closed_at = datetime.now()
        database.session.commit()

    def _validate_header_data(self, data: Dict[str, Any], exclude_id: Optional[str] = None):
        """Valida datos del encabezado."""
        if not database.session.execute(database.select(Entity).filter_by(code=data["company"])).first():
            raise BudgetError("Compañía no válida.")

        ledger = database.session.get(Book, data["ledger_id"])
        if not ledger or ledger.entity != data["company"]:
            raise BudgetError("Libro contable no válido para la compañía.")

        fy = database.session.get(FiscalYear, data["fiscal_year_id"])
        if not fy or fy.entity != data["company"]:
            raise BudgetError("Año fiscal no válido para la compañía.")

        # Validar duplicidad de código
        query = database.session.query(Budget).filter_by(
            company=data["company"],
            ledger_id=data["ledger_id"],
            fiscal_year_id=data["fiscal_year_id"],
            budget_code=data["budget_code"],
        )
        if exclude_id:
            query = query.filter(Budget.id != exclude_id)

        if query.first():
            raise BudgetError("El código de presupuesto ya existe para este año fiscal y libro.")

    def _validate_line_data(self, budget: Budget, data: Dict[str, Any], exclude_line_id: Optional[str] = None):
        """Valida datos de una línea de presupuesto."""
        self._validate_line_account(budget, data)
        self._validate_line_cost_center(budget, data)
        self._validate_line_period(budget, data)
        self._validate_line_business_unit(budget, data)
        self._validate_line_project(budget, data)
        self._validate_line_uniqueness(budget, data, exclude_line_id)

    def _validate_line_account(self, budget: Budget, data: Dict[str, Any]) -> None:
        account = database.session.get(Accounts, data["account_id"])
        if not account or account.entity != budget.company:
            raise BudgetError("Cuenta contable no válida.")
        if account.group:
            raise BudgetError("No se puede presupuestar en una cuenta agrupadora.")

    def _validate_line_cost_center(self, budget: Budget, data: Dict[str, Any]) -> None:
        cc = database.session.get(CostCenter, data["cost_center_id"])
        if not cc or cc.entity != budget.company:
            raise BudgetError("Centro de costo no válido.")

    def _validate_line_period(self, budget: Budget, data: Dict[str, Any]) -> None:
        period = database.session.get(AccountingPeriod, data["period_id"])
        if not period or period.fiscal_year_id != budget.fiscal_year_id:
            raise BudgetError("El período no pertenece al año fiscal del presupuesto.")

    def _validate_line_business_unit(self, budget: Budget, data: Dict[str, Any]) -> None:
        unit_id = data.get("business_unit_id")
        if not unit_id:
            return
        unit = database.session.get(Unit, unit_id)
        if not unit or unit.entity != budget.company:
            raise BudgetError("Unidad de negocio no válida.")

    def _validate_line_project(self, budget: Budget, data: Dict[str, Any]) -> None:
        project_id = data.get("project_id")
        if not project_id:
            return
        project = database.session.get(Project, project_id)
        if not project or project.entity != budget.company:
            raise BudgetError("Proyecto no válido.")

    def _validate_line_uniqueness(self, budget: Budget, data: Dict[str, Any], exclude_line_id: Optional[str] = None) -> None:
        business_unit_id = data.get("business_unit_id")
        project_id = data.get("project_id")

        query = database.session.query(BudgetLine).filter(
            BudgetLine.budget_id == budget.id,
            BudgetLine.account_id == data["account_id"],
            BudgetLine.cost_center_id == data["cost_center_id"],
            BudgetLine.period_id == data["period_id"],
            (
                BudgetLine.business_unit_id.is_(None)
                if business_unit_id is None
                else BudgetLine.business_unit_id == business_unit_id
            ),
            BudgetLine.project_id.is_(None) if project_id is None else BudgetLine.project_id == project_id,
        )
        if exclude_line_id:
            query = query.filter(BudgetLine.id != exclude_line_id)

        if query.first():
            raise BudgetError("Ya existe una línea para esta combinación de dimensiones y período.")

    def get_budget_totals(self, budget_id: str) -> Dict[str, Decimal]:
        """Obtiene totales del presupuesto agrupados por período."""
        from sqlalchemy import func

        results = (
            database.session.query(BudgetLine.period_id, func.sum(BudgetLine.amount))
            .filter_by(budget_id=budget_id)
            .group_by(BudgetLine.period_id)
            .all()
        )
        return {period_id: amount for period_id, amount in results}

    def resolve_expense_account(self, item_code: str, company: str) -> Accounts | None:
        """Resuelve la cuenta de gastos para un artículo y compañía."""
        from cacao_accounting.database import ItemAccount, CompanyDefaultAccount, Accounts

        if item_code:
            item_acc = database.session.query(ItemAccount).filter_by(item_code=item_code, company=company).first()
            if item_acc and item_acc.expense_account_id:
                acc = database.session.query(Accounts).filter_by(id=item_acc.expense_account_id).first()
                if acc:
                    return acc
        defaults = database.session.query(CompanyDefaultAccount).filter_by(company=company).first()
        if defaults and defaults.default_expense:
            acc = database.session.query(Accounts).filter_by(id=defaults.default_expense).first()
            if acc:
                return acc
        return None

    def resolve_cost_center(self, item_code: str, company: str, supplier_id: str | None = None) -> CostCenter | None:
        """Resuelve el centro de costos para un artículo, compañía y proveedor opcional."""
        from cacao_accounting.database import ItemAccount, CompanyParty, CostCenter

        if item_code:
            item_acc = database.session.query(ItemAccount).filter_by(item_code=item_code, company=company).first()
            if item_acc and item_acc.cost_center_code:
                cc = database.session.query(CostCenter).filter_by(code=item_acc.cost_center_code, entity=company).first()
                if cc:
                    return cc
        if supplier_id:
            cp = database.session.query(CompanyParty).filter_by(party_id=supplier_id, company=company).first()
            if cp and cp.default_cost_center:
                cc = database.session.query(CostCenter).filter_by(code=cp.default_cost_center, entity=company).first()
                if cc:
                    return cc
        cc = database.session.query(CostCenter).filter_by(entity=company, default=True).first()
        if cc:
            return cc
        cc = database.session.query(CostCenter).filter_by(entity=company, code="MAIN").first()
        return cc

    def validate_transaction(
        self,
        company: str,
        date_val: datetime | date,
        account_id: str,
        cost_center_id: str,
        amount: Decimal,
        document_id: str,
        document_type: str,
        ledger_id: str | None = None,
    ) -> Dict[str, Any]:
        """Valida si una transacción excede el presupuesto disponible de la cuenta y centro de costo.

        Considera:
        - compañía
        - cuenta contable
        - centro de costo
        - período presupuestario
        - monto solicitado

        Retorna un diccionario indicando si excede el presupuesto, el presupuesto,
        lo comprometido, disponible, lo solicitado y el exceso.
        """
        from cacao_accounting.database import AccountingPeriod, Accounts, Book, Budget, BudgetLine, CostCenter, GLEntry

        if hasattr(date_val, "date"):
            date_val = date_val.date()  # type: ignore

        # 1. Resolve AccountingPeriod
        period = (
            database.session.query(AccountingPeriod)
            .filter(
                AccountingPeriod.entity == company,
                AccountingPeriod.start <= date_val,
                AccountingPeriod.end >= date_val,
                AccountingPeriod.enabled.is_(True),
            )
            .first()
        )

        if not period:
            return {
                "exceeded": False,
                "budget": Decimal("0"),
                "committed": Decimal("0"),
                "available": Decimal("0"),
                "requested": amount,
                "excess": Decimal("0"),
            }

        # 2. Resolve Account ID
        acc = (
            database.session.query(Accounts)
            .filter(Accounts.entity == company, (Accounts.id == account_id) | (Accounts.code == account_id))
            .first()
        )
        resolved_account_id = acc.id if acc else account_id

        # 3. Resolve Cost Center ID
        cc = (
            database.session.query(CostCenter)
            .filter(CostCenter.entity == company, (CostCenter.id == cost_center_id) | (CostCenter.code == cost_center_id))
            .first()
        )
        resolved_cost_center_id = cc.id if cc else cost_center_id

        # Resolve Ledger/Book to prevent cross-ledger summing, using the same active-book predicate as posting._active_books
        resolved_ledger_id = ledger_id
        if not resolved_ledger_id:
            from sqlalchemy import or_

            primary_book = (
                database.session.query(Book)
                .filter(
                    Book.entity == company,
                    or_(Book.status == "activo", Book.status.is_(None)),
                )
                .order_by(Book.is_primary.desc(), Book.code)
                .first()
            )
            resolved_ledger_id = primary_book.id if primary_book else None

        # 4. Resolve Approved Budgets
        budgets_query = database.session.query(Budget).filter_by(
            company=company, fiscal_year_id=period.fiscal_year_id, status="approved"
        )
        if resolved_ledger_id:
            budgets_query = budgets_query.filter_by(ledger_id=resolved_ledger_id)
        budgets = budgets_query.all()
        budget_ids = [b.id for b in budgets]

        # 5. Get Budget Amount
        budget_amount = Decimal("0")
        if budget_ids:
            lines = (
                database.session.query(BudgetLine)
                .filter(
                    BudgetLine.budget_id.in_(budget_ids),
                    BudgetLine.account_id == resolved_account_id,
                    BudgetLine.cost_center_id == resolved_cost_center_id,
                    BudgetLine.period_id == period.id,
                )
                .all()
            )
            budget_amount = sum(line.amount for line in lines)

        # 6. Calculate Committed Amount (from GLEntry actuals)
        gl_query = (
            database.session.query(GLEntry.debit, GLEntry.credit, Accounts.classification)
            .join(Accounts, GLEntry.account_id == Accounts.id)
            .filter(
                GLEntry.company == company,
                GLEntry.accounting_period_id == period.id,
                GLEntry.account_id == resolved_account_id,
                GLEntry.is_cancelled.is_(False),
            )
        )
        if resolved_ledger_id:
            gl_query = gl_query.filter(GLEntry.ledger_id == resolved_ledger_id)
        if cc:
            gl_query = gl_query.filter(GLEntry.cost_center_code == cc.code)
        actual_entries = gl_query.all()

        committed_amount = Decimal("0")
        for entry in actual_entries:
            classif = entry.classification.lower() if entry.classification else ""
            if classif in ("gastos", "activo", "expense", "asset"):
                val = entry.debit - entry.credit
            else:
                val = entry.credit - entry.debit
            committed_amount += val

        # 7. Compute results
        available_amount = budget_amount - committed_amount
        exceeded = amount > available_amount
        excess = (amount - available_amount) if exceeded else Decimal("0")

        return {
            "exceeded": exceeded,
            "budget": budget_amount,
            "committed": committed_amount,
            "available": available_amount,
            "requested": amount,
            "excess": excess,
        }
