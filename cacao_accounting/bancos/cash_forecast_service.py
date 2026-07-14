# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio de cálculo y negocio para el Pronóstico de Flujo de Caja."""

import calendar
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from cacao_accounting.database import (
    database,
    Accounts,
    GLEntry,
    SalesInvoice,
    PurchaseInvoice,
    FiscalYear,
    CashForecast,
    CashForecastEntry,
    Entity,
)
from cacao_accounting.contabilidad.posting import _lookup_exchange_rate


def generate_periods(fiscal_year, periodicity):
    """Divide un año fiscal en períodos semanales o mensuales."""
    start = fiscal_year.year_start_date
    end = fiscal_year.year_end_date
    periods = []
    if periodicity == "monthly":
        current_start = start
        while current_start <= end:
            _, last_day = calendar.monthrange(current_start.year, current_start.month)
            current_end = date(current_start.year, current_start.month, last_day)
            if current_end > end:
                current_end = end
            periods.append(
                {
                    "name": current_start.strftime("%B %Y"),
                    "start_date": current_start,
                    "end_date": current_end,
                }
            )
            if current_start.month == 12:
                current_start = date(current_start.year + 1, 1, 1)
            else:
                current_start = date(current_start.year, current_start.month + 1, 1)
    else:
        current_start = start
        week_num = 1
        while current_start <= end:
            current_end = current_start + timedelta(days=6)
            if current_end > end:
                current_end = end
            periods.append(
                {
                    "name": f"Semana {week_num} ({current_start.strftime('%d/%m')} - {current_end.strftime('%d/%m')})",
                    "start_date": current_start,
                    "end_date": current_end,
                }
            )
            current_start = current_end + timedelta(days=1)
            week_num += 1
    return periods


def get_base_amount(amount, currency_code, company_currency, target_date):
    """Convierte un monto de moneda extranjera a la moneda de la compañía."""
    if not currency_code or currency_code == company_currency:
        return Decimal(str(amount))
    try:
        rate = _lookup_exchange_rate(currency_code, company_currency, target_date)
        if rate:
            return Decimal(str(amount)) * Decimal(str(rate))
    except (ValueError, SQLAlchemyError):
        from cacao_accounting.logs import log

        log.warning(
            "No se pudo convertir {} {} a {} usando tasa del {}, usando monto original",
            amount,
            currency_code,
            company_currency,
            target_date,
        )
    return Decimal(str(amount))


def get_cash_forecast_matrix(company, forecast_id, today_date=None):
    """Calcula la matriz de flujo de caja YTD (Real, Current, Projected) para un pronóstico."""
    if today_date is None:
        today_date = date.today()

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        return []

    fiscal_year = database.session.get(FiscalYear, forecast.fiscal_year_id)
    if not fiscal_year:
        return []

    entity = database.session.query(Entity).filter_by(code=company).first()
    company_currency = entity.currency if entity else "NIO"

    periods = generate_periods(fiscal_year, forecast.periodicity)
    if not periods:
        return []

    # Obtener cuentas de caja/banco
    cash_bank_accounts = (
        database.session.query(Accounts.id)
        .filter(
            Accounts.entity == company,
            Accounts.account_type.in_(["cash", "bank"]),
            Accounts.enabled.is_(True),
        )
        .all()
    )
    account_ids = [a[0] for a in cash_bank_accounts]

    # Saldo Inicial (antes del primer período)
    first_start = periods[0]["start_date"]
    init_balance = Decimal("0")
    if account_ids:
        bal_query = database.session.query(func.sum(GLEntry.debit - GLEntry.credit)).filter(
            GLEntry.company == company,
            GLEntry.account_id.in_(account_ids),
            GLEntry.posting_date < first_start,
            GLEntry.is_cancelled.is_(False),
            GLEntry.is_reversal.is_(False),
        )
        init_val = bal_query.scalar()
        if init_val is not None:
            init_balance = Decimal(str(init_val))

    # Obtener todas las proyecciónes manuales para este forecast
    manual_entries = database.session.query(CashForecastEntry).filter_by(forecast_id=forecast.id).all()

    # Obtener facturas pendientes (AR/AP)
    ar_invoices = (
        database.session.query(SalesInvoice)
        .filter(
            SalesInvoice.company == company,
            SalesInvoice.outstanding_amount > 0,
            SalesInvoice.docstatus == 1,
        )
        .all()
    )

    ap_invoices = (
        database.session.query(PurchaseInvoice)
        .filter(
            PurchaseInvoice.company == company,
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.docstatus == 1,
        )
        .all()
    )

    cumulative_real = init_balance
    cumulative_current = init_balance
    cumulative_projected = init_balance

    matrix = []

    for p in periods:
        start_date = p["start_date"]
        end_date = p["end_date"]

        # Determinar zona temporal
        if end_date < today_date:
            zone = "Real"
        elif start_date <= today_date <= end_date:
            zone = "Current"
        else:
            zone = "Projected"

        # 1. Movimientos Reales en este período (solo hasta hoy)
        real_inflow = Decimal("0")
        real_outflow = Decimal("0")
        real_other = Decimal("0")

        if account_ids and start_date <= today_date:
            limit_end = min(end_date, today_date)
            # Clientes (debit - credit)
            in_val = (
                database.session.query(func.sum(GLEntry.debit - GLEntry.credit))
                .filter(
                    GLEntry.company == company,
                    GLEntry.account_id.in_(account_ids),
                    GLEntry.posting_date >= start_date,
                    GLEntry.posting_date <= limit_end,
                    GLEntry.party_type == "customer",
                    GLEntry.is_cancelled.is_(False),
                    GLEntry.is_reversal.is_(False),
                )
                .scalar()
            )
            if in_val:
                real_inflow = Decimal(str(in_val))

            # Proveedores (credit - debit)
            out_val = (
                database.session.query(func.sum(GLEntry.credit - GLEntry.debit))
                .filter(
                    GLEntry.company == company,
                    GLEntry.account_id.in_(account_ids),
                    GLEntry.posting_date >= start_date,
                    GLEntry.posting_date <= limit_end,
                    GLEntry.party_type == "supplier",
                    GLEntry.is_cancelled.is_(False),
                    GLEntry.is_reversal.is_(False),
                )
                .scalar()
            )
            if out_val:
                real_outflow = Decimal(str(out_val))

            # Otros (debit - credit)
            other_val = (
                database.session.query(func.sum(GLEntry.debit - GLEntry.credit))
                .filter(
                    GLEntry.company == company,
                    GLEntry.account_id.in_(account_ids),
                    GLEntry.posting_date >= start_date,
                    GLEntry.posting_date <= limit_end,
                    or_(
                        GLEntry.party_type.is_(None),
                        ~GLEntry.party_type.in_(["customer", "supplier"]),
                    ),
                    GLEntry.is_cancelled.is_(False),
                    GLEntry.is_reversal.is_(False),
                )
                .scalar()
            )
            if other_val:
                real_other = Decimal(str(other_val))

        # 2. Proyecciones AR/AP del ERP
        proj_ar = Decimal("0")
        proj_ap = Decimal("0")

        if zone == "Current":
            # AR: incluir facturas con posting_date <= end_date
            for inv in ar_invoices:
                if inv.posting_date <= end_date:
                    amt = inv.base_outstanding_amount or inv.outstanding_amount or Decimal("0")
                    proj_ar += Decimal(str(amt))
            # AP: incluir facturas con posting_date <= end_date
            for inv in ap_invoices:
                if inv.posting_date <= end_date:
                    amt = inv.base_outstanding_amount or inv.outstanding_amount or Decimal("0")
                    proj_ap += Decimal(str(amt))
        elif zone == "Projected":
            # AR: incluir facturas en este período
            for inv in ar_invoices:
                if start_date <= inv.posting_date <= end_date:
                    amt = inv.base_outstanding_amount or inv.outstanding_amount or Decimal("0")
                    proj_ar += Decimal(str(amt))
            # AP: incluir facturas en este período
            for inv in ap_invoices:
                if start_date <= inv.posting_date <= end_date:
                    amt = inv.base_outstanding_amount or inv.outstanding_amount or Decimal("0")
                    proj_ap += Decimal(str(amt))

        # 3. Proyecciones Manuales (CashForecastEntry)
        manual_inflow = Decimal("0")
        manual_outflow = Decimal("0")

        # Se consideran sólo a partir de mañana en zona Current, o todas en zona Projected
        for entry in manual_entries:
            if start_date <= entry.estimated_date <= end_date:
                # Si es Current, sólo se consideran si estimated_date > today
                if zone == "Current" and entry.estimated_date <= today_date:
                    continue
                base_amt = get_base_amount(
                    entry.amount,
                    entry.currency,
                    company_currency,
                    entry.estimated_date,
                )
                if entry.type == "Income":
                    manual_inflow += base_amt
                else:
                    manual_outflow += base_amt

        # Actualizar saldos YTD
        if zone == "Real":
            cumulative_real += real_inflow - real_outflow + real_other
            cumulative_current = cumulative_real
            cumulative_projected = cumulative_real
        elif zone == "Current":
            real_delta = real_inflow - real_outflow + real_other
            cumulative_real += real_delta
            cumulative_current = cumulative_real + (proj_ar - proj_ap)
            cumulative_projected = cumulative_current + (manual_inflow - manual_outflow)
        else:  # Projected
            cumulative_current += proj_ar - proj_ap
            cumulative_projected += (proj_ar - proj_ap) + (manual_inflow - manual_outflow)

        matrix.append(
            {
                "period": p["name"],
                "start_date": start_date,
                "end_date": end_date,
                "zone": zone,
                "real_inflow": real_inflow,
                "real_outflow": real_outflow,
                "real_other": real_other,
                "proj_ar": proj_ar,
                "proj_ap": proj_ap,
                "manual_inflow": manual_inflow,
                "manual_outflow": manual_outflow,
                "real_balance": cumulative_real,
                "current_balance": cumulative_current,
                "projected_balance": cumulative_projected,
            }
        )

    return matrix


def get_forecast_comparison(company, base_id, compare_id, today_date=None):
    """Compara dos pronósticos de flujo de caja para identificar variaciones."""
    base_matrix = get_cash_forecast_matrix(company, base_id, today_date)
    compare_matrix = get_cash_forecast_matrix(company, compare_id, today_date)

    comparison = []
    # Match by period name
    compare_dict = {row["period"]: row for row in compare_matrix}

    for brow in base_matrix:
        period = brow["period"]
        crow = compare_dict.get(period)

        base_proj = brow["projected_balance"]
        comp_proj = crow["projected_balance"] if crow else Decimal("0")
        variance = comp_proj - base_proj

        base_manual_in = brow["manual_inflow"]
        comp_manual_in = crow["manual_inflow"] if crow else Decimal("0")
        var_manual_in = comp_manual_in - base_manual_in

        base_manual_out = brow["manual_outflow"]
        comp_manual_out = crow["manual_outflow"] if crow else Decimal("0")
        var_manual_out = comp_manual_out - base_manual_out

        comparison.append(
            {
                "period": period,
                "zone": brow["zone"],
                "base_projected": base_proj,
                "compare_projected": comp_proj,
                "variance": variance,
                "base_manual_inflow": base_manual_in,
                "compare_manual_inflow": comp_manual_in,
                "variance_manual_inflow": var_manual_in,
                "base_manual_outflow": base_manual_out,
                "compare_manual_outflow": comp_manual_out,
                "variance_manual_outflow": var_manual_out,
            }
        )

    return comparison
