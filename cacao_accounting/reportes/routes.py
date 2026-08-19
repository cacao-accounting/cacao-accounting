"""Reportes operativos de subledgers, aging, Kardex y reconciliaciones."""

from __future__ import annotations


from dataclasses import replace

from datetime import date


from typing import cast

from flask import Blueprint, render_template, request

from flask_login import login_required


from cacao_accounting.decorators import exige_acceso_compania, modulo_activo, verifica_acceso

from cacao_accounting.reportes.services import (
    AgingFilters,
    BankingFilters,
    FinancialReportFilters,
    KardexFilters,
    ReconciliationFilters,
    SubledgerFilters,
    get_account_movement_detail,
    get_account_summary_report,
    get_aging_report,
    get_ar_ap_subledger,
    get_batch_report,
    get_bank_balance_summary,
    get_bank_movement_detail,
    get_balance_sheet_report,
    get_gross_margin,
    get_income_statement_report,
    get_inventory_existence,
    get_inventory_valuation,
    get_kardex,
    get_purchases_by_item,
    get_purchases_by_supplier,
    get_reconciliation_report,
    get_reconciliation_matrix,
    get_sales_by_customer,
    get_sales_by_item,
    get_serial_report,
    get_stock_balance,
    get_trial_balance_report,
)

from cacao_accounting.version import APPNAME

from cacao_accounting.reportes.helpers import (
    _resolve_view_context,
    _resolve_company,
    _default_ledger_for_company,
    _default_period_for_company,
    _date_arg,
    _financial_filters,
    _should_run_financial_report,
    _empty_financial_report,
    _render_financial_report,
    _render_operational_framework,
    _operational_filters,
    _render_operational_report,
    _operational_context_summary,
)

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value

else:

    def _(value: str) -> str:
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):
            return value


reportes = Blueprint("reportes", __name__, template_folder="templates")

REPORT_TABLE_HTML = "reportes/report_table.html"

_COLUMN_LABELS = {
    "posting_date": "Posting Date",
    "accounting_period": "Period",
    "document_no": "Voucher",
    "voucher_type": "Type",
    "account_code": "Account",
    "account_name": "Account Name",
    "account_type": "Account Type",
    "classification": "Section",
    "debit": "Debit",
    "credit": "Credit",
    "running_balance": "Final Balance",
    "currency": "Currency",
    "ledger": "Ledger",
    "company": "Company",
    "opening_balance": "Opening Balance",
    "ending_balance": "Final Balance",
    "cost_center": "Cost Center",
    "unit": "Unit",
    "project": "Project",
    "party_type": "Party Type",
    "party_id": "Party",
    "created_by": "User",
    "created": "Creation Date",
    "created_at": "Creation Date",
    "movement_count": "Movements",
    "first_movement": "First Movement",
    "last_movement": "Last Movement",
    "line_comment": "Reference",
    "reference_type": "Reference Type",
    "is_reversal": "Is Reversal",
    "reversal_of": "Reversal Of",
    "status": "Status",
    "voucher_status": "Status",
    "section": "Section",
    "amount": "Amount",
    "bank_account": "Bank Account",
    "party_name": "Party",
    "payment_type": "Payment Type",
    "incoming_amount": "Incoming Amount",
    "outgoing_amount": "Outgoing Amount",
    "receipts_amount": "Receipts",
    "payments_amount": "Payments",
    "account_no": "Account Number",
    "item_name": "Item Name",
    "balance_qty": "Balance Qty",
    "incoming_qty": "Incoming Qty",
    "outgoing_qty": "Outgoing Qty",
    "value_change": "Value Change",
    "original_amount": "Original Amount",
    "paid_amount": "Paid Amount",
    "outstanding_amount": "Outstanding Amount",
    "days": "Days",
    "bucket": "Bucket",
    "remarks": "Remarks",
}

_MONEY_COLUMNS = {
    "debit",
    "credit",
    "difference",
    "opening_balance",
    "ending_balance",
    "running_balance",
    "amount",
    "assets",
    "liabilities",
    "equity",
    "period_profit",
    "income",
    "cost",
    "expense",
    "gross_profit",
    "net_profit",
    "incoming_amount",
    "outgoing_amount",
    "receipts_amount",
    "payments_amount",
    "original_amount",
    "paid_amount",
    "outstanding_amount",
    "value_change",
    "stock_value",
    "remaining_stock_value",
}

_RIGHT_ALIGN_COLUMNS = _MONEY_COLUMNS | {"level", "incoming_qty", "outgoing_qty", "balance_qty", "actual_qty", "days"}

_ALWAYS_VISIBLE_COLUMNS = {
    "debit",
    "credit",
    "difference",
    "account_code",
    "account_name",
    "section",
    "amount",
    "opening_balance",
    "ending_balance",
}

_EMPTY_CELL_VALUE = "—"

_FINANCIAL_FILTER_FIELDS = (
    "company",
    "ledger",
    "accounting_period",
    "voucher_number",
    "account_code",
    "account_from",
    "account_to",
    "cost_center_code",
    "unit_code",
    "project_code",
    "party_type",
    "party_id",
    "voucher_type",
    "status",
    "show_cancellations",
    "include_running_balance",
    "page_size",
    "sort_by",
    "sort_dir",
    "group_by",
)


@reportes.route("/reports/account-summary")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def account_summary():
    """Resumen de movimientos por cuenta (Sábana analítica)."""
    filters, selected_view, saved_views = _resolve_view_context("account-summary", _financial_filters())
    report = get_account_summary_report(filters) if _should_run_financial_report() else _empty_financial_report()
    return _render_financial_report(
        "account-summary",
        _("Resumen de Movimiento por Cuenta"),
        report,
        filters,
        selected_view,
        saved_views,
    )


@reportes.route("/reports/account-movement")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def account_movement():
    """Report account movement detail."""
    filters, selected_view, saved_views = _resolve_view_context("account-movement", _financial_filters())
    report = get_account_movement_detail(filters) if _should_run_financial_report() else _empty_financial_report()
    if request.args.get("export") in {"csv", "xlsx"}:
        export_report = get_account_movement_detail(cast(FinancialReportFilters, replace(filters, export_all=True, page=1)))
        return _render_financial_report(
            "account-movement",
            _("Detalle de Movimiento Contable"),
            export_report,
            filters,
            selected_view,
            saved_views,
        )
    return _render_financial_report(
        "account-movement",
        _("Detalle de Movimiento Contable"),
        report,
        filters,
        selected_view,
        saved_views,
    )


@reportes.route("/reports/trial-balance")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def trial_balance():
    """Report trial balance."""
    filters, selected_view, saved_views = _resolve_view_context("trial-balance", _financial_filters())
    report = get_trial_balance_report(filters) if _should_run_financial_report() else _empty_financial_report()
    return _render_financial_report(
        "trial-balance",
        _("Balanza de Comprobación"),
        report,
        filters,
        selected_view,
        saved_views,
    )


@reportes.route("/reports/income-statement")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def income_statement():
    """Report income statement."""
    filters, selected_view, saved_views = _resolve_view_context("income-statement", _financial_filters())
    report = get_income_statement_report(filters) if _should_run_financial_report() else _empty_financial_report()
    return _render_financial_report(
        "income-statement",
        _("Estado de Resultado"),
        report,
        filters,
        selected_view,
        saved_views,
    )


@reportes.route("/reports/balance-sheet")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def balance_sheet():
    """Report balance sheet."""
    filters, selected_view, saved_views = _resolve_view_context("balance-sheet", _financial_filters())
    report = get_balance_sheet_report(filters) if _should_run_financial_report() else _empty_financial_report()
    return _render_financial_report(
        "balance-sheet",
        _("Balance General"),
        report,
        filters,
        selected_view,
        saved_views,
    )


@reportes.route("/reports/subledger")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def subledger():
    """Report AR/AP subledger by document."""
    company = _resolve_company(request.args.get("company", "cacao"))
    exige_acceso_compania("accounting", company, "consultar")
    party_type = request.args.get("party_type", "customer")
    report = get_ar_ap_subledger(
        SubledgerFilters(
            company=company,
            party_type=party_type,
            party_id=request.args.get("party_id") or None,
            as_of_date=_date_arg("as_of_date"),
        )
    )
    return render_template(
        REPORT_TABLE_HTML,
        titulo="Subledger AR/AP - " + APPNAME,
        report_title="Subledger AR/AP",
        rows=report.rows,
        totals=report.totals,
    )


@reportes.route("/reports/aging")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def aging():
    """Report AR/AP aging."""
    company = _resolve_company(request.args.get("company", "cacao"))
    exige_acceso_compania("accounting", company, "consultar")
    party_type = request.args.get("party_type", "customer")
    report = get_aging_report(
        AgingFilters(
            company=company,
            party_type=party_type,
            party_id=request.args.get("party_id") or None,
            as_of_date=_date_arg("as_of_date") or date.today(),
        )
    )
    return render_template(
        REPORT_TABLE_HTML,
        titulo="Aging AR/AP - " + APPNAME,
        report_title="Aging AR/AP",
        rows=report.rows,
        totals=report.totals,
    )


@reportes.route("/reports/kardex")
@login_required
@modulo_activo("inventory")
def kardex():
    """Report inventory kardex."""
    company = _resolve_company(request.args.get("company", "cacao"))
    filters = KardexFilters(
        company=company,
        item_code=request.args.get("item_code") or None,
        warehouse=request.args.get("warehouse") or None,
        date_from=_date_arg("date_from"),
        date_to=_date_arg("date_to"),
    )
    report = get_kardex(filters)
    return _render_operational_framework(
        "kardex",
        _("Kardex"),
        report,
        module_home_endpoint="inventario.inventario_",
        module_home_label=_("Inventario"),
        filter_mode="kardex",
        filter_state={
            "company": company,
            "item_code": filters.item_code or "",
            "warehouse": filters.warehouse or "",
            "date_from": filters.date_from.isoformat() if filters.date_from else "",
            "date_to": filters.date_to.isoformat() if filters.date_to else "",
        },
        context_summary=_operational_context_summary(
            report,
            company=company,
            date_from=filters.date_from.isoformat() if filters.date_from else None,
            date_to=filters.date_to.isoformat() if filters.date_to else None,
        ),
    )


@reportes.route("/reports/inventory-existence")
@login_required
@modulo_activo("inventory")
def inventory_existence():
    """Genera reporte de existencias a una fecha clave."""
    company = _resolve_company(request.args.get("company", "cacao"))
    as_of_date = _date_arg("as_of_date")
    filters = KardexFilters(
        company=company,
        item_code=request.args.get("item_code") or None,
        warehouse=request.args.get("warehouse") or None,
        date_to=as_of_date,
    )
    report = get_inventory_existence(filters)
    return _render_operational_framework(
        "inventory-existence",
        _("Existencia de Inventario"),
        report,
        module_home_endpoint="inventario.inventario_",
        module_home_label=_("Inventario"),
        filter_mode="inventory_existence",
        filter_state={
            "company": company,
            "item_code": filters.item_code or "",
            "warehouse": filters.warehouse or "",
            "as_of_date": as_of_date.isoformat() if as_of_date else "",
        },
        context_summary=_operational_context_summary(
            report,
            company=company,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
        ),
    )


@reportes.route("/reports/reconciliations")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def reconciliations():
    """Report reconciliations."""
    company = _resolve_company(request.args.get("company", "cacao"))
    exige_acceso_compania("accounting", company, "consultar")
    report = get_reconciliation_report(
        company=company,
        as_of_date=_date_arg("as_of_date"),
    )
    return render_template(
        REPORT_TABLE_HTML,
        titulo="Reconciliaciones - " + APPNAME,
        report_title="Reconciliaciones",
        rows=report.rows,
        totals=report.totals,
    )


@reportes.route("/reports/reconciliation-matrix")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def reconciliation_matrix():
    """Reconcilia AR, AP, inventario, bancos e impuestos contra GL."""
    company = _resolve_company(request.args.get("company", "cacao"))
    period = request.args.get("accounting_period") or _default_period_for_company(company)
    report = get_reconciliation_matrix(
        ReconciliationFilters(
            company=company,
            ledger=request.args.get("ledger") or _default_ledger_for_company(company),
            accounting_period=period,
            as_of_date=_date_arg("as_of_date"),
            currency=request.args.get("currency") or None,
        )
    )
    return _render_operational_framework(
        "reconciliation-matrix",
        _("Matriz de Reconciliación Subledger ↔ GL"),
        report,
        module_home_endpoint="reportes.trial_balance",
        module_home_label=_("Balanza de Comprobación"),
        filter_mode="reconciliation_matrix",
        filter_state={
            "company": company,
            "ledger": request.args.get("ledger") or "",
            "accounting_period": period or "",
            "as_of_date": request.args.get("as_of_date") or "",
            "currency": request.args.get("currency") or "",
        },
        context_summary=_operational_context_summary(
            report, company=company, ledger=report.ledger_currency or "—", period=period
        ),
    )


@reportes.route("/reports/bank-movement")
@login_required
@modulo_activo(("cash", "banking"))
def bank_movement():
    """Genera reporte de detalle de movimiento bancario."""
    company = _resolve_company(request.args.get("company", "cacao"))
    filters = BankingFilters(
        company=company,
        bank_account_id=request.args.get("bank_account_id") or None,
        date_from=_date_arg("date_from"),
        date_to=_date_arg("date_to"),
    )
    report = get_bank_movement_detail(filters)
    return _render_operational_framework(
        "bank-movement",
        _("Detalle de Movimiento Bancario"),
        report,
        module_home_endpoint="bancos.bancos_",
        module_home_label=_("Bancos"),
        filter_mode="bank_movement",
        filter_state={
            "company": company,
            "bank_account_id": filters.bank_account_id or "",
            "date_from": filters.date_from.isoformat() if filters.date_from else "",
            "date_to": filters.date_to.isoformat() if filters.date_to else "",
        },
        context_summary=_operational_context_summary(
            report,
            company=company,
            date_from=filters.date_from.isoformat() if filters.date_from else None,
            date_to=filters.date_to.isoformat() if filters.date_to else None,
        ),
    )


@reportes.route("/reports/bank-balance-summary")
@login_required
@modulo_activo(("cash", "banking"))
def bank_balance_summary():
    """Genera reporte de resumen de saldos bancarios."""
    company = _resolve_company(request.args.get("company", "cacao"))
    filters = BankingFilters(
        company=company,
        bank_account_id=request.args.get("bank_account_id") or None,
        as_of_date=_date_arg("as_of_date"),
    )
    report = get_bank_balance_summary(filters)
    return _render_operational_framework(
        "bank-balance-summary",
        _("Resumen de Saldos Bancarios"),
        report,
        module_home_endpoint="bancos.bancos_",
        module_home_label=_("Bancos"),
        filter_mode="bank_balance_summary",
        filter_state={
            "company": company,
            "bank_account_id": filters.bank_account_id or "",
            "as_of_date": filters.as_of_date.isoformat() if filters.as_of_date else "",
        },
        context_summary=_operational_context_summary(
            report,
            company=company,
            as_of_date=filters.as_of_date.isoformat() if filters.as_of_date else None,
        ),
    )


@reportes.route("/reports/accounts-payable")
@login_required
@modulo_activo("purchases")
def accounts_payable():
    """Genera reporte de cuentas por pagar por proveedor a fecha clave."""
    company = _resolve_company(request.args.get("company", "cacao"))
    as_of_date = _date_arg("as_of_date")
    party_id = request.args.get("party_id") or None
    report = get_ar_ap_subledger(
        SubledgerFilters(
            company=company,
            party_type="supplier",
            party_id=party_id,
            as_of_date=as_of_date,
            include_returns=False,
        )
    )
    return _render_operational_framework(
        "accounts-payable",
        _("Cuentas por Pagar"),
        report,
        module_home_endpoint="compras.compras_",
        module_home_label=_("Compras"),
        filter_mode="accounts_payable",
        filter_state={
            "company": company,
            "party_id": party_id or "",
            "as_of_date": as_of_date.isoformat() if as_of_date else "",
        },
        context_summary=_operational_context_summary(
            report,
            company=company,
            party_type=_("Proveedor"),
            as_of_date=as_of_date.isoformat() if as_of_date else None,
        ),
    )


@reportes.route("/reports/ap-aging")
@login_required
@modulo_activo("purchases")
def ap_aging():
    """Genera aging de cuentas por pagar."""
    company = _resolve_company(request.args.get("company", "cacao"))
    as_of_date = _date_arg("as_of_date") or date.today()
    party_id = request.args.get("party_id") or None
    report = get_aging_report(
        AgingFilters(
            company=company,
            party_type="supplier",
            party_id=party_id,
            as_of_date=as_of_date,
            include_returns=False,
        )
    )
    return _render_operational_framework(
        "ap-aging",
        _("Aging de Cuentas por Pagar"),
        report,
        module_home_endpoint="compras.compras_",
        module_home_label=_("Compras"),
        filter_mode="ap_aging",
        filter_state={"company": company, "party_id": party_id or "", "as_of_date": as_of_date.isoformat()},
        context_summary=_operational_context_summary(
            report, company=company, party_type=_("Proveedor"), as_of_date=as_of_date.isoformat()
        ),
    )


@reportes.route("/reports/accounts-receivable")
@login_required
@modulo_activo("sales")
def accounts_receivable():
    """Genera reporte de cuentas por cobrar por cliente a fecha clave."""
    company = _resolve_company(request.args.get("company", "cacao"))
    as_of_date = _date_arg("as_of_date")
    party_id = request.args.get("party_id") or None
    report = get_ar_ap_subledger(
        SubledgerFilters(company=company, party_type="customer", party_id=party_id, as_of_date=as_of_date)
    )
    return _render_operational_framework(
        "accounts-receivable",
        _("Cuentas por Cobrar"),
        report,
        module_home_endpoint="ventas.ventas_",
        module_home_label=_("Ventas"),
        filter_mode="accounts_receivable",
        filter_state={
            "company": company,
            "party_id": party_id or "",
            "as_of_date": as_of_date.isoformat() if as_of_date else "",
        },
        context_summary=_operational_context_summary(
            report,
            company=company,
            party_type=_("Cliente"),
            as_of_date=as_of_date.isoformat() if as_of_date else None,
        ),
    )


@reportes.route("/reports/ar-aging")
@login_required
@modulo_activo("sales")
def ar_aging():
    """Genera aging de cuentas por cobrar."""
    company = _resolve_company(request.args.get("company", "cacao"))
    as_of_date = _date_arg("as_of_date") or date.today()
    party_id = request.args.get("party_id") or None
    report = get_aging_report(AgingFilters(company=company, party_type="customer", party_id=party_id, as_of_date=as_of_date))
    return _render_operational_framework(
        "ar-aging",
        _("Aging de Cuentas por Cobrar"),
        report,
        module_home_endpoint="ventas.ventas_",
        module_home_label=_("Ventas"),
        filter_mode="ar_aging",
        filter_state={"company": company, "party_id": party_id or "", "as_of_date": as_of_date.isoformat()},
        context_summary=_operational_context_summary(
            report, company=company, party_type=_("Cliente"), as_of_date=as_of_date.isoformat()
        ),
    )


@reportes.route("/reports/purchases-by-supplier")
@login_required
@modulo_activo("purchases")
def purchases_by_supplier():
    """Genera reporte de compras agrupadas por proveedor."""
    return _render_operational_report("Compras por Proveedor", get_purchases_by_supplier(_operational_filters()))


@reportes.route("/reports/purchases-by-item")
@login_required
@modulo_activo("purchases")
def purchases_by_item():
    """Genera reporte de compras agrupadas por articulo."""
    return _render_operational_report("Compras por Item", get_purchases_by_item(_operational_filters()))


@reportes.route("/reports/sales-by-customer")
@login_required
@modulo_activo("sales")
def sales_by_customer():
    """Genera reporte de ventas agrupadas por cliente."""
    return _render_operational_report("Ventas por Cliente", get_sales_by_customer(_operational_filters()))


@reportes.route("/reports/sales-by-item")
@login_required
@modulo_activo("sales")
def sales_by_item():
    """Genera reporte de ventas agrupadas por articulo."""
    return _render_operational_report("Ventas por Item", get_sales_by_item(_operational_filters()))


@reportes.route("/reports/gross-margin")
@login_required
@modulo_activo("sales")
def gross_margin():
    """Genera reporte de margen bruto por ventas."""
    return _render_operational_report("Margen Bruto", get_gross_margin(_operational_filters()))


@reportes.route("/reports/stock-balance")
@login_required
@modulo_activo("inventory")
def stock_balance():
    """Genera reporte de balance de stock por articulo y bodega."""
    return _render_operational_report("Stock Balance", get_stock_balance(_operational_filters()))


@reportes.route("/reports/inventory-valuation")
@login_required
@modulo_activo("inventory")
def inventory_valuation():
    """Genera reporte de valoracion del inventario."""
    return _render_operational_report("Valoracion de Inventario", get_inventory_valuation(_operational_filters()))


@reportes.route("/reports/batches")
@login_required
@modulo_activo("inventory")
def batches():
    """Genera reporte de lotes de inventario."""
    return _render_operational_report("Lotes", get_batch_report(_operational_filters()))


@reportes.route("/reports/serials")
@login_required
@modulo_activo("inventory")
def serials():
    """Genera reporte de numeros de serie de inventario."""
    return _render_operational_report("Seriales", get_serial_report(_operational_filters()))
