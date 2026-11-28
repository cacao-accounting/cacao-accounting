# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio de cálculo y negocio para el Pronóstico de Flujo de Caja."""

import calendar
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, tuple_
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
    CompanyParty,
    Currency,
    Entity,
    PaymentTerms,
)
from cacao_accounting.cancellation_scope import effective_gl_scope
from cacao_accounting.contabilidad.posting import _lookup_exchange_rate
from cacao_accounting.document_flow.payment import compute_outstanding_amount
from cacao_accounting.ledger_queries import primary_ledger_id
from cacao_accounting.numbers import coerce_decimal


from cacao_accounting.i18n import _

_EPOCH_DATE = date(1900, 1, 1)
CASH_FORECAST_PERIODICITIES = frozenset({"weekly", "monthly"})


class CashForecastConversionError(ValueError):
    """Indica que una proyección no puede convertirse de forma segura."""


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


def _fiscal_year_range(forecast: CashForecast) -> tuple[date, date]:
    """Devuelve el rango del año fiscal asociado al pronóstico."""
    fiscal_year = database.session.get(FiscalYear, forecast.fiscal_year_id)
    if fiscal_year is None:
        raise ValueError(_("El pronóstico no tiene un año fiscal asociado."))
    return fiscal_year.year_start_date, fiscal_year.year_end_date


def validate_forecast_entry_date(forecast: CashForecast, estimated_date: date) -> None:
    """Exige que una proyección manual caiga dentro de su año fiscal.

    Regla aprobada (#2185): el pronóstico rechaza fechas fuera del rango de
    su año fiscal en alta, edición e importación; las proyecciones históricas
    externas se reportan con ``out_of_range_forecast_entries`` sin
    modificarlas, en cumplimiento del principio append-only.
    """
    start, end = _fiscal_year_range(forecast)
    if not start <= estimated_date <= end:
        raise ValueError(
            _("La fecha estimada debe estar dentro del año fiscal (%(start)s a %(end)s).")
            % {"start": start.isoformat(), "end": end.isoformat()}
        )


def out_of_range_forecast_entries(forecast: CashForecast) -> list[CashForecastEntry]:
    """Reporta proyecciones históricas fuera del año fiscal sin modificarlas."""
    start, end = _fiscal_year_range(forecast)
    return list(
        database.session.execute(
            database.select(CashForecastEntry).where(
                CashForecastEntry.forecast_id == forecast.id,
                (CashForecastEntry.estimated_date < start) | (CashForecastEntry.estimated_date > end),
            )
        )
        .scalars()
        .all()
    )


def generate_periods(fiscal_year, periodicity):
    """Divide un año fiscal en períodos semanales o mensuales."""
    if periodicity not in CASH_FORECAST_PERIODICITIES:
        raise ValueError(_("La periodicidad debe ser semanal o mensual."))
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
        if rate is not None and Decimal(str(rate)) > 0:
            return Decimal(str(amount)) * Decimal(str(rate))
    except (ValueError, SQLAlchemyError):
        pass
    raise CashForecastConversionError(
        _("No existe tipo de cambio para %(currency_code)s -> %(company_currency)s en %(target_date)s.")
        % {"currency_code": currency_code, "company_currency": company_currency, "target_date": target_date}
    )


def _resolve_company_currency(company: str) -> str:
    """Resuelve la moneda funcional configurada de una compañía.

    No asume NIO: sin moneda (o con una moneda inactiva) el pronóstico debe
    detenerse en lugar de presentar saldos convertidos a una moneda inventada
    (#1324).
    """
    entity = database.session.query(Entity).filter_by(code=company).first()
    currency = str(getattr(entity, "currency", None) or "").strip() if entity else ""
    if not currency:
        raise CashForecastConversionError(_("La compañía requiere una moneda funcional configurada."))
    currency_row = database.session.query(Currency).filter_by(code=currency).first()
    if currency_row is None or not currency_row.active:
        raise CashForecastConversionError(_("La moneda funcional de la compañía no esta activa."))
    return currency


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
        *effective_gl_scope(),
    )
    ledger_id = primary_ledger_id(company)
    if ledger_id:
        init_val = init_val.filter(GLEntry.ledger_id == ledger_id)
    init_val = init_val.scalar()
    return Decimal(str(init_val)) if init_val is not None else Decimal("0")


def _compute_real_movements(
    company: str, account_ids: list[str], start_date: date, limit_end: date
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula flujos reales clasificando el tercero en la contrapartida del voucher.

    Las líneas de banco/caja no llevan ``party_type`` porque esa dimensión pertenece
    a la cuenta AR/AP. La clasificación se hace por voucher para no perder los
    cobros y pagos que sí tienen un tercero en otra línea del asiento.
    """
    if not account_ids:
        return Decimal("0"), Decimal("0"), Decimal("0")

    filters = [
        GLEntry.company == company,
        GLEntry.account_id.in_(account_ids),
        GLEntry.posting_date >= start_date,
        GLEntry.posting_date <= limit_end,
        *effective_gl_scope(),
    ]
    ledger_id = primary_ledger_id(company)
    if ledger_id:
        filters.append(GLEntry.ledger_id == ledger_id)
    cash_entries = database.session.query(GLEntry).filter(*filters).all()
    if not cash_entries:
        return Decimal("0"), Decimal("0"), Decimal("0")

    voucher_keys = {(entry.voucher_type, entry.voucher_id) for entry in cash_entries}
    counterpart_filters = [
        GLEntry.company == company,
        *effective_gl_scope(),
        tuple_(GLEntry.voucher_type, GLEntry.voucher_id).in_(voucher_keys),
    ]
    if ledger_id:
        counterpart_filters.append(GLEntry.ledger_id == ledger_id)
    related_entries = database.session.query(GLEntry).filter(*counterpart_filters).all()
    party_types_by_voucher: dict[tuple[str, str], set[str]] = {}
    for entry in related_entries:
        party_type = (entry.party_type or "").strip().lower()
        if party_type in {"customer", "supplier"}:
            party_types_by_voucher.setdefault((entry.voucher_type, entry.voucher_id), set()).add(party_type)

    real_inflow = Decimal("0")
    real_outflow = Decimal("0")
    real_other = Decimal("0")
    for entry in cash_entries:
        delta = Decimal(str(entry.debit or 0)) - Decimal(str(entry.credit or 0))
        party_types = party_types_by_voucher.get((entry.voucher_type, entry.voucher_id), set())
        if party_types in ({"customer"}, {"supplier"}):
            if delta >= 0:
                real_inflow += delta
            else:
                real_outflow -= delta
        else:
            real_other += delta
    return real_inflow, real_outflow, real_other


def _invoice_forecast_amount(
    invoice,
    company_currency: str,
    flow_date: date,
    excluded: list[dict] | None = None,
) -> tuple[Decimal, Decimal] | None:
    """Resolve an invoice balance from its canonical subledger state."""
    try:
        outstanding = compute_outstanding_amount(invoice)
        return outstanding, _forecast_base_amount(outstanding, invoice, company_currency, flow_date)
    except CashForecastConversionError as exc:
        # An incomplete document must not make every other cash-flow projection
        # unavailable. Se conserva la exclusión para que la matriz la informe
        # en lugar de parecer completa (#1325).
        if excluded is not None:
            try:
                outstanding = compute_outstanding_amount(invoice)
            except Exception:  # pragma: no cover - diagnóstico best-effort
                outstanding = Decimal("0")
            excluded.append(
                {
                    "id": getattr(invoice, "id", ""),
                    "document_no": getattr(invoice, "document_no", None),
                    "document_type": getattr(invoice, "document_type", None),
                    "amount": outstanding,
                    "currency": getattr(invoice, "transaction_currency", None),
                    "date": flow_date,
                    "reason": str(exc),
                }
            )
        return None


def _sum_invoice_amount(
    invoices: list,
    start_date: date,
    end_date: date,
    company_currency: str = "NIO",
    due_dates: dict[str, date] | None = None,
    excluded: list[dict] | None = None,
) -> Decimal:
    """Suma saldos pendientes usando la fecha de vencimiento del documento."""
    total = Decimal("0")
    for invoice in invoices:
        flow_date = (
            getattr(invoice, "due_date", None) or (due_dates or {}).get(invoice.id) or getattr(invoice, "posting_date", None)
        )
        if flow_date is None:
            continue
        if not start_date <= flow_date <= end_date:
            continue
        forecast = _invoice_forecast_amount(invoice, company_currency, flow_date, excluded=excluded)
        if forecast is None:
            continue
        outstanding, amount = forecast
        if outstanding <= 0:
            continue
        if getattr(invoice, "is_return", False):
            amount = -Decimal(str(amount))
        total += Decimal(str(amount))
    return total


def _load_invoice_due_dates(company: str, invoices: list) -> dict[str, date]:
    """Deriva vencimientos por factura usando los términos activos del tercero."""
    party_ids = {
        party_id
        for invoice in invoices
        if (party_id := getattr(invoice, "customer_id", None) or getattr(invoice, "supplier_id", None))
    }
    if not party_ids:
        return {}

    due_days_by_party: dict[str, int | None] = dict(
        database.session.execute(
            database.select(CompanyParty.party_id, PaymentTerms.due_days)
            .join(PaymentTerms, PaymentTerms.id == CompanyParty.payment_terms_id, isouter=True)
            .where(
                CompanyParty.company == company,
                CompanyParty.is_active.is_(True),
                CompanyParty.party_id.in_(party_ids),
            )
        ).all()
    )
    due_dates: dict[str, date] = {}
    for invoice in invoices:
        if getattr(invoice, "due_date", None) or not invoice.posting_date:
            continue
        party_id = getattr(invoice, "customer_id", None) or getattr(invoice, "supplier_id", None)
        due_dates[invoice.id] = invoice.posting_date + timedelta(days=due_days_by_party.get(party_id, 0) or 0)
    return due_dates


def _forecast_base_amount(outstanding: Decimal, invoice, company_currency: str, flow_date: date) -> Decimal:
    """Convert a canonical outstanding amount to company currency for forecast use."""
    transaction_currency = getattr(invoice, "transaction_currency", None)
    if not transaction_currency:
        raise CashForecastConversionError(
            _(
                "El documento no tiene moneda transaccional explícita; "
                "no se puede convertir al pronóstico de %(company_currency)s en %(flow_date)s."
            )
            % {"company_currency": company_currency, "flow_date": flow_date}
        )
    if transaction_currency == company_currency:
        return outstanding
    raw_exchange_rate = getattr(invoice, "exchange_rate", None)
    if raw_exchange_rate is None or Decimal(str(raw_exchange_rate)) <= 0:
        raise CashForecastConversionError(
            _("No existe tipo de cambio para %(transaction_currency)s -> %(company_currency)s en %(flow_date)s.")
            % {
                "transaction_currency": transaction_currency,
                "company_currency": company_currency,
                "flow_date": flow_date,
            }
        )
    return outstanding * Decimal(str(raw_exchange_rate))


def _compute_ar_ap_projections(
    zone: str,
    ar_invoices: list,
    ap_invoices: list,
    start_date: date,
    end_date: date,
    company_currency: str,
    due_dates: dict[str, date],
    excluded: list[dict] | None = None,
) -> tuple[Decimal, Decimal]:
    """Calcula proyecciones AR/AP según la zona temporal."""
    if zone == "Current":
        ar_total = _sum_invoice_amount(ar_invoices, _EPOCH_DATE, end_date, company_currency, due_dates, excluded)
        ap_total = _sum_invoice_amount(ap_invoices, _EPOCH_DATE, end_date, company_currency, due_dates, excluded)
        return ar_total, ap_total
    if zone == "Projected":
        return (
            _sum_invoice_amount(ar_invoices, start_date, end_date, company_currency, due_dates, excluded),
            _sum_invoice_amount(ap_invoices, start_date, end_date, company_currency, due_dates, excluded),
        )
    return Decimal("0"), Decimal("0")


def _compute_manual_projections(
    manual_entries: list,
    start_date: date,
    end_date: date,
    zone: str,
    today_date: date,
    company_currency: str,
) -> tuple[Decimal, Decimal, list[dict]]:
    """Calcula proyecciones manuales de ingreso y egreso para un período."""
    manual_inflow = Decimal("0")
    manual_outflow = Decimal("0")
    incomplete_entries = []
    for entry in manual_entries:
        if not start_date <= entry.estimated_date <= end_date:
            continue
        try:
            amount = coerce_decimal(entry.amount, "monto", positive=True)
        except ValueError:
            continue
        if zone == "Current" and entry.estimated_date <= today_date:
            continue
        try:
            base_amt = coerce_decimal(
                get_base_amount(amount, entry.currency, company_currency, entry.estimated_date),
                "monto convertido",
                positive=True,
            )
        except CashForecastConversionError:
            incomplete_entries.append(
                {
                    "id": entry.id,
                    "concept": entry.concept,
                    "type": entry.type,
                    "amount": amount,
                    "currency": entry.currency,
                    "estimated_date": entry.estimated_date,
                }
            )
            continue
        except ValueError:
            continue
        if entry.type == "Income":
            manual_inflow += base_amt
        else:
            manual_outflow += base_amt
    return manual_inflow, manual_outflow, incomplete_entries


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
    if forecast.company != company:
        raise ValueError(_("El pronóstico no pertenece a la compañía solicitada."))

    fiscal_year = database.session.get(FiscalYear, forecast.fiscal_year_id)
    if not fiscal_year or fiscal_year.entity != company:
        raise ValueError(_("El año fiscal no pertenece a la compañía del pronóstico."))

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
            SalesInvoice.docstatus == 1,
        )
        .all()
    )
    ap_invoices = (
        database.session.query(PurchaseInvoice)
        .filter(
            PurchaseInvoice.company == company,
            PurchaseInvoice.docstatus == 1,
        )
        .all()
    )
    invoice_due_dates = _load_invoice_due_dates(company, [*ar_invoices, *ap_invoices])

    cumulatives: dict[str, Decimal] = {"real": init_balance, "current": init_balance, "projected": init_balance}
    matrix = []

    for p in periods:
        start_date = p["start_date"]
        end_date = p["end_date"]
        zone = _determine_zone(start_date, end_date, today_date)
        excluded_invoices: list[dict] = []

        real_inflow, real_outflow, real_other = Decimal("0"), Decimal("0"), Decimal("0")
        if account_ids and start_date <= today_date:
            limit_end = min(end_date, today_date)
            real_inflow, real_outflow, real_other = _compute_real_movements(company, account_ids, start_date, limit_end)

        proj_ar, proj_ap = _compute_ar_ap_projections(
            zone,
            ar_invoices,
            ap_invoices,
            start_date,
            end_date,
            company_currency,
            invoice_due_dates,
            excluded_invoices,
        )
        manual_inflow, manual_outflow, incomplete_manual_entries = _compute_manual_projections(
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
                "incomplete_manual_entries": incomplete_manual_entries,
                "incomplete_invoice_entries": excluded_invoices,
                "is_incomplete": bool(incomplete_manual_entries or excluded_invoices),
                "real_balance": cumulatives["real"],
                "current_balance": cumulatives["current"],
                "projected_balance": cumulatives["projected"],
            }
        )

    return matrix


def get_forecast_comparison(company, base_id, compare_id, today_date=None):
    """Compara dos pronósticos de flujo de caja para identificar variaciones."""
    base_forecast = database.session.get(CashForecast, base_id)
    compare_forecast = database.session.get(CashForecast, compare_id)
    if not base_forecast or not compare_forecast:
        return []
    if base_forecast.company != company or compare_forecast.company != company:
        raise ValueError(_("Los pronósticos comparados deben pertenecer a la compañía solicitada."))
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
