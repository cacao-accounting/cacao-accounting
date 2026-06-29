# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para la gestión de presupuestos."""

from datetime import datetime
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
        account = database.session.get(Accounts, data["account_id"])
        if not account or account.entity != budget.company:
            raise BudgetError("Cuenta contable no válida.")
        if account.group:
            raise BudgetError("No se puede presupuestar en una cuenta agrupadora.")

        cc = database.session.get(CostCenter, data["cost_center_id"])
        if not cc or cc.entity != budget.company:
            raise BudgetError("Centro de costo no válido.")

        period = database.session.get(AccountingPeriod, data["period_id"])
        if not period or period.fiscal_year_id != budget.fiscal_year_id:
            raise BudgetError("El período no pertenece al año fiscal del presupuesto.")

        if data.get("business_unit_id"):
            unit = database.session.get(Unit, data["business_unit_id"])
            if not unit or unit.entity != budget.company:
                raise BudgetError("Unidad de negocio no válida.")

        if data.get("project_id"):
            project = database.session.get(Project, data["project_id"])
            if not project or project.entity != budget.company:
                raise BudgetError("Proyecto no válido.")

        # Validar duplicados (NULL-safe)
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
