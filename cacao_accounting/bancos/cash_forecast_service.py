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
from cacao_accounting.ledger_queries import primary_ledger_id

_EPOCH_DATE = date(1900, 1, 1)


def _generate_monthly_periods(start: date, end: date) -> list[dict]:
    """Genera períodos mensuales dentro de un rango de fechas."""
    periods: list[dict] = []
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
    return periods


def _generate_weekly_periods(start: date, end: date) -> list[dict]:
    """Genera períodos semanales dentro de un rango de fechas."""
    periods: list[dict] = []
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


def generate_periods(fiscal_year, periodicity):
    """Divide un año fiscal en períodos semanales o mensuales."""
    start = fiscal_year.year_start_date
    end = fiscal_year.year_end_date
    if periodicity == "monthly":
        return _generate_monthly_periods(start, end)
    return _generate_weekly_periods(start, end)


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


def _resolve_company_currency(company: str) -> str:
    """Resuelve la moneda base de una compañía."""
    entity = database.session.query(Entity).filter_by(code=company).first()
    return entity.currency if entity else "NIO"


def _get_cash_bank_account_ids(company: str) -> list[str]:
    """Obtiene los IDs de cuentas de efectivo y banco activas de una compañía."""
    rows = (
        database.session.query(Accounts.id)
        .filter(
            Accounts.entity == company,
            Accounts.account_type.in_(["cash", "bank"]),
            Accounts.enabled.is_(True),
        )
        .all()
    )
    return [a[0] for a in rows]


def _compute_initial_balance(company: str, account_ids: list[str], first_start: date) -> Decimal:
    """Calcula el saldo inicial de efectivo/banco antes del primer período."""
    if not account_ids:
        return Decimal("0")
    init_val = database.session.query(func.sum(GLEntry.debit - GLEntry.credit)).filter(
        GLEntry.company == company,
        GLEntry.account_id.in_(account_ids),
        GLEntry.posting_date < first_start,
        GLEntry.is_cancelled.is_(False),
        GLEntry.is_reversal.is_(False),
    )
    ledger_id = primary_ledger_id(company)
    if ledger_id:
        init_val = init_val.filter(GLEntry.ledger_id == ledger_id)
    init_val = init_val.scalar()
    return Decimal(str(init_val)) if init_val is not None else Decimal("0")


def _query_gl_sum(
    company: str,
    account_ids: list[str],
    start_date: date,
    limit_end: date,
    party_type_filter: str | None = None,
    exclude_party_types: bool = False,
    use_debit_credit: bool = True,
) -> Decimal:
    """Consulta la suma de GLEntry para un filtro de party_type dado."""
    base_filters = [
        GLEntry.company == company,
        GLEntry.account_id.in_(account_ids),
        GLEntry.posting_date >= start_date,
        GLEntry.posting_date <= limit_end,
        GLEntry.is_cancelled.is_(False),
        GLEntry.is_reversal.is_(False),
    ]
    ledger_id = primary_ledger_id(company)
    if ledger_id:
        base_filters.append(GLEntry.ledger_id == ledger_id)
    if party_type_filter:
        base_filters.append(GLEntry.party_type == party_type_filter)
    elif exclude_party_types:
        base_filters.append(or_(GLEntry.party_type.is_(None), ~GLEntry.party_type.in_(["customer", "supplier"])))
    expr = func.sum(GLEntry.debit - GLEntry.credit) if use_debit_credit else func.sum(GLEntry.credit - GLEntry.debit)
    val = database.session.query(expr).filter(*base_filters).scalar()
    return Decimal(str(val)) if val else Decimal("0")


def _compute_real_movements(
    company: str, account_ids: list[str], start_date: date, limit_end: date
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula flujos reales (ingreso, egreso, otros) para un período."""
    if not account_ids:
        return Decimal("0"), Decimal("0"), Decimal("0")
    real_inflow = _query_gl_sum(company, account_ids, start_date, limit_end, party_type_filter="customer")
    real_outflow = _query_gl_sum(
        company, account_ids, start_date, limit_end, party_type_filter="supplier", use_debit_credit=False
    )
    real_other = _query_gl_sum(company, account_ids, start_date, limit_end, exclude_party_types=True)
    return real_inflow, real_outflow, real_other


def _sum_invoice_amount(invoices: list, start_date: date, end_date: date) -> Decimal:
    """Suma montos pendientes de facturas dentro de un rango de fechas."""
    total = Decimal("0")
    for inv in invoices:
        if start_date <= inv.posting_date <= end_date:
            amt = inv.base_outstanding_amount or inv.outstanding_amount or Decimal("0")
            total += Decimal(str(amt))
    return total


def _compute_ar_ap_projections(
    zone: str,
    ar_invoices: list,
    ap_invoices: list,
    start_date: date,
    end_date: date,
) -> tuple[Decimal, Decimal]:
    """Calcula proyecciones AR/AP según la zona temporal."""
    if zone == "Current":
        ar_total = _sum_invoice_amount(ar_invoices, _EPOCH_DATE, end_date)
        ap_total = _sum_invoice_amount(ap_invoices, _EPOCH_DATE, end_date)
        return ar_total, ap_total
    if zone == "Projected":
        return _sum_invoice_amount(ar_invoices, start_date, end_date), _sum_invoice_amount(ap_invoices, start_date, end_date)
    return Decimal("0"), Decimal("0")


def _compute_manual_projections(
    manual_entries: list,
    start_date: date,
    end_date: date,
    zone: str,
    today_date: date,
    company_currency: str,
) -> tuple[Decimal, Decimal]:
    """Calcula proyecciones manuales de ingreso y egreso para un período."""
    manual_inflow = Decimal("0")
    manual_outflow = Decimal("0")
    for entry in manual_entries:
        if not (start_date <= entry.estimated_date <= end_date):
            continue
        if zone == "Current" and entry.estimated_date <= today_date:
            continue
        base_amt = get_base_amount(entry.amount, entry.currency, company_currency, entry.estimated_date)
        if entry.type == "Income":
            manual_inflow += base_amt
        else:
            manual_outflow += base_amt
    return manual_inflow, manual_outflow


def _update_cumulatives(
    zone: str,
    real_inflow: Decimal,
    real_outflow: Decimal,
    real_other: Decimal,
    proj_ar: Decimal,
    proj_ap: Decimal,
    manual_inflow: Decimal,
    manual_outflow: Decimal,
    cumulatives: dict,
) -> None:
    """Actualiza los saldos acumulados YTD según la zona temporal."""
    real_delta = real_inflow - real_outflow + real_other
    if zone == "Real":
        cumulatives["real"] += real_delta
        cumulatives["current"] = cumulatives["real"]
        cumulatives["projected"] = cumulatives["real"]
    elif zone == "Current":
        cumulatives["real"] += real_delta
        cumulatives["current"] = cumulatives["real"] + (proj_ar - proj_ap)
        cumulatives["projected"] = cumulatives["current"] + (manual_inflow - manual_outflow)
    else:
        cumulatives["current"] += proj_ar - proj_ap
        cumulatives["projected"] += (proj_ar - proj_ap) + (manual_inflow - manual_outflow)


def _determine_zone(start_date: date, end_date: date, today_date: date) -> str:
    """Determina la zona temporal de un período."""
    if end_date < today_date:
        return "Real"
    if start_date <= today_date <= end_date:
        return "Current"
    return "Projected"


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

    company_currency = _resolve_company_currency(company)
    periods = generate_periods(fiscal_year, forecast.periodicity)
    if not periods:
        return []

    account_ids = _get_cash_bank_account_ids(company)
    init_balance = _compute_initial_balance(company, account_ids, periods[0]["start_date"])
    manual_entries = database.session.query(CashForecastEntry).filter_by(forecast_id=forecast.id).all()
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

    cumulatives: dict[str, Decimal] = {"real": init_balance, "current": init_balance, "projected": init_balance}
    matrix = []

    for p in periods:
        start_date = p["start_date"]
        end_date = p["end_date"]
        zone = _determine_zone(start_date, end_date, today_date)

        real_inflow, real_outflow, real_other = Decimal("0"), Decimal("0"), Decimal("0")
        if account_ids and start_date <= today_date:
            limit_end = min(end_date, today_date)
            real_inflow, real_outflow, real_other = _compute_real_movements(company, account_ids, start_date, limit_end)

        proj_ar, proj_ap = _compute_ar_ap_projections(zone, ar_invoices, ap_invoices, start_date, end_date)
        manual_inflow, manual_outflow = _compute_manual_projections(
            manual_entries, start_date, end_date, zone, today_date, company_currency
        )

        _update_cumulatives(
            zone,
            real_inflow,
            real_outflow,
            real_other,
            proj_ar,
            proj_ap,
            manual_inflow,
            manual_outflow,
            cumulatives,
        )

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
                "real_balance": cumulatives["real"],
                "current_balance": cumulatives["current"],
                "projected_balance": cumulatives["projected"],
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
