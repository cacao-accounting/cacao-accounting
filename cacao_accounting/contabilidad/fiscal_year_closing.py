# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para el cierre contable de año fiscal."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from cacao_accounting.contabilidad.journal_service import create_journal_draft
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    ComprobanteContable,
    FiscalYear,
    GLEntry,
    database,
)


class FiscalYearClosingError(ValueError):
    """Error en el proceso de cierre de año fiscal."""


def calculate_closing_balances(company: str, fiscal_year: FiscalYear) -> list[dict[str, Any]]:
    """Calcula los saldos de cierre para cuentas de ingresos, costos y gastos."""
    # Filtrar entradas por compañia y rango de fechas del año fiscal
    # Excluir registros de cierre previos si los hubiera (is_fiscal_year_closing=False)
    query = (
        select(
            GLEntry.account_id,
            GLEntry.account_code,
            GLEntry.cost_center_code,
            GLEntry.unit_code,
            GLEntry.project_code,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        )
        .join(Accounts, Accounts.id == GLEntry.account_id)
        .where(
            GLEntry.company == company,
            GLEntry.posting_date >= fiscal_year.year_start_date,
            GLEntry.posting_date <= fiscal_year.year_end_date,
            GLEntry.is_fiscal_year_closing.is_(False),
            GLEntry.is_cancelled.is_(False),
            Accounts.classification.in_(["ingreso", "costo", "gasto", "income", "cost", "expense"]),
        )
        .group_by(
            GLEntry.account_id,
            GLEntry.account_code,
            GLEntry.cost_center_code,
            GLEntry.unit_code,
            GLEntry.project_code,
        )
    )

    results = database.session.execute(query).all()
    balances = []
    for row in results:
        if row.balance != 0:
            balances.append(
                {
                    "account_id": row.account_id,
                    "account_code": row.account_code,
                    "cost_center": row.cost_center_code,
                    "unit": row.unit_code,
                    "project": row.project_code,
                    "balance": row.balance,
                }
            )
    return balances


def create_fiscal_year_closing_voucher(company: str, fiscal_year_id: str, user_id: str) -> ComprobanteContable:
    """Ejecuta el proceso de cierre de año fiscal."""
    fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
    if not fiscal_year:
        raise FiscalYearClosingError("Año fiscal no encontrado.")

    if fiscal_year.entity != company:
        raise FiscalYearClosingError("La compañía no coincide con la entidad del año fiscal.")

    if not fiscal_year.is_closed:
        raise FiscalYearClosingError("El año fiscal debe estar cerrado administrativamente antes del cierre contable.")
    if fiscal_year.financial_closed:
        raise FiscalYearClosingError("El año fiscal ya tiene un cierre contable realizado.")

    balances = calculate_closing_balances(company, fiscal_year)
    if not balances:
        raise FiscalYearClosingError("No hay movimientos en cuentas de resultados para cerrar en este año fiscal.")

    defaults = (
        database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()
    )
    if not defaults or not defaults.retained_earnings_account_id:
        raise FiscalYearClosingError("No se ha definido la cuenta de utilidades acumuladas en la configuración.")

    retained_earnings_account = database.session.get(Accounts, defaults.retained_earnings_account_id)
    if not retained_earnings_account:
        raise FiscalYearClosingError("La cuenta de utilidades acumuladas configurada no existe.")

    lines = []
    total_net_balance = Decimal("0")
    order = 1

    for b in balances:
        balance = Decimal(str(b["balance"]))
        # Para cerrar la cuenta: si saldo es deudor (positivo), acreditamos. Si es acreedor (negativo), debitamos.
        debit = Decimal("0")
        credit = Decimal("0")
        if balance > 0:
            credit = balance
        else:
            debit = abs(balance)

        lines.append(
            {
                "order": order,
                "account": b["account_code"],
                "cost_center": b["cost_center"],
                "unit": b["unit"],
                "project": b["project"],
                "debit": str(debit) if debit > 0 else "",
                "credit": str(credit) if credit > 0 else "",
                "remarks": f"Cierre año fiscal {fiscal_year.name}",
            }
        )
        total_net_balance += balance
        order += 1

    # Contrapartida a utilidades acumuladas
    debit_re = Decimal("0")
    credit_re = Decimal("0")
    if total_net_balance > 0:
        debit_re = total_net_balance
    else:
        credit_re = abs(total_net_balance)

    lines.append(
        {
            "order": order,
            "account": retained_earnings_account.code,
            "debit": str(debit_re) if debit_re > 0 else "",
            "credit": str(credit_re) if credit_re > 0 else "",
            "remarks": f"Resultado neto año fiscal {fiscal_year.name}",
        }
    )

    payload = {
        "company": company,
        "posting_date": fiscal_year.year_end_date.isoformat(),
        "reference": f"CIERRE-{fiscal_year.name}",
        "memo": f"Cierre contable automático del año fiscal {fiscal_year.name}",
        "is_closing": True,
        "is_fiscal_year_closing": True,
        "fiscal_year_id": fiscal_year.id,
        "lines": lines,
    }

    journal = create_journal_draft(payload, user_id=user_id)
    # Ya no ejecutamos submit_journal aqui para permitir el estado de borrador
    return journal


def reverse_fiscal_year_closing(fiscal_year_id: str, user_id: str) -> None:
    """Revierte el cierre contable de un año fiscal."""
    fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
    if not fiscal_year:
        raise FiscalYearClosingError("Año fiscal no encontrado.")
    if not fiscal_year.financial_closed or not fiscal_year.closing_voucher_id:
        raise FiscalYearClosingError("El año fiscal no tiene un cierre contable que revertir.")

    journal = database.session.get(ComprobanteContable, fiscal_year.closing_voucher_id)
    if not journal:
        # Si el comprobante no existe por alguna razon, permitimos resetear la bandera
        fiscal_year.financial_closed = False
        fiscal_year.closing_voucher_id = None
        database.session.add(fiscal_year)
        database.session.commit()
        return

    # Anular el comprobante. Esto disparará el hook en journal_service para actualizar el año fiscal.
    from cacao_accounting.contabilidad.journal_service import cancel_submitted_journal
    cancel_submitted_journal(journal.id, user_id=user_id)
