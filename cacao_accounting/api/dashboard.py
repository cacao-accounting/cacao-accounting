# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""API para el dashboard ejecutivo de la aplicación."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import extract, func

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    BankAccount,
    BankTransaction,
    CompanyParty,
    Entity,
    GLEntry,
    Item,
    Party,
    PaymentEntry,
    PurchaseInvoice,
    PurchaseOrder,
    SalesInvoice,
    StockBin,
    StockLedgerEntry,
    Warehouse,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.modulos import (
    MODULE_ACCOUNTING,
    MODULE_BANKS,
    MODULE_INVENTORY,
    MODULE_PURCHASES,
    MODULE_SALES,
)

dashboard_api = Blueprint("dashboard_api", __name__)

INCOME_CLASSIFICATIONS = {"Income", "Ingresos"}
EXPENSE_CLASSIFICATIONS = {"Expense", "Gastos"}


@dashboard_api.route("/api/dashboard/data")
@login_required
def get_dashboard_data():
    """Devuelve los datos necesarios para renderizar el dashboard modular."""
    company_id = request.args.get("company")
    period_id = request.args.get("period")

    if not company_id:
        return jsonify({"error": "Se requiere el parámetro 'company'"}), 400

    company = database.session.get(Entity, company_id)
    if company is None:
        return jsonify({"error": "Compañía no encontrada"}), 404

    if not user_can_access_company(current_user, company):
        return jsonify({"error": "No tiene acceso a la compañía seleccionada"}), 403

    period = _resolve_period(period_id, company)
    if period_id and period is None:
        return jsonify({"error": "Periodo contable no encontrado para la compañía"}), 404

    start_date = period.start if period else None
    end_date = period.end if period else None
    sections = _dashboard_sections(company, start_date, end_date)

    return jsonify(
        {
            "company": {
                "id": company.id,
                "code": company.code,
                "name": company.name or company.company_name,
                "currency": company.currency,
            },
            "period": _period_payload(period),
            "sections": sections,
        }
    )


def user_can_access_company(user: Any, company: Entity | None) -> bool:
    """Valida acceso temporal del usuario a una compañía."""
    if company is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "active", False) is not True:
        return False
    return getattr(company, "enabled", None) is not False


def _resolve_period(period_id: str | None, company: Entity) -> AccountingPeriod | None:
    """Devuelve el periodo solicitado si pertenece a la compañía."""
    if not period_id:
        return None
    return database.session.query(AccountingPeriod).filter_by(id=period_id, entity=company.code).one_or_none()


def _period_payload(period: AccountingPeriod | None) -> dict[str, Any] | None:
    """Serializa el periodo activo del dashboard."""
    if period is None:
        return None
    return {
        "id": period.id,
        "name": period.name,
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
    }


def _dashboard_sections(
    company: Entity,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, dict[str, Any]]:
    """Construye las secciones uniformes del dashboard."""
    company_code = str(company.code)
    currency = str(company.currency or "USD")
    return {
        "accounting": _section_or_hidden(
            MODULE_ACCOUNTING,
            "Contabilidad",
            "Resumen financiero del periodo seleccionado.",
            lambda: get_accounting_data(company_code, currency, start_date, end_date),
        ),
        "banks": _section_or_hidden(
            MODULE_BANKS,
            "Bancos",
            "Saldos, conciliaciones y pagos en proceso.",
            lambda: get_banks_data(company_code, currency, start_date, end_date),
        ),
        "purchases": _section_or_hidden(
            MODULE_PURCHASES,
            "Compras",
            "Facturas, órdenes abiertas y cuentas por pagar.",
            lambda: get_purchases_data(company_code, currency, start_date, end_date),
        ),
        "inventory": _section_or_hidden(
            MODULE_INVENTORY,
            "Inventario",
            "Existencias, bodegas y movimientos recientes.",
            lambda: get_inventory_data(company_code, currency, start_date, end_date),
        ),
        "sales": _section_or_hidden(
            MODULE_SALES,
            "Ventas",
            "Facturación, cobranza y comportamiento comercial.",
            lambda: get_sales_data(company_code, currency, start_date, end_date),
        ),
    }


def _section_or_hidden(
    module_name: str,
    title: str,
    subtitle: str,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Devuelve una sección visible o una sección oculta uniforme."""
    if not _has_module_access(module_name):
        return _hidden_section(title, subtitle)
    section = loader()
    section["visible"] = True
    section["title"] = title
    section["subtitle"] = subtitle
    section["badge"] = ""
    return section


def _has_module_access(module_name: str) -> bool:
    """Indica si el usuario actual puede consultar un módulo."""
    module_id = obtener_id_modulo_por_nombre(module_name)
    return Permisos(modulo=module_id, usuario=current_user.id).autorizado


def _hidden_section(title: str, subtitle: str) -> dict[str, Any]:
    """Representa una sección sin permisos sin exponer datos."""
    return {
        "visible": False,
        "title": title,
        "subtitle": subtitle,
        "badge": "Oculto por permisos",
        "kpis": {},
        "charts": {},
        "tables": {},
        "actions": [],
        "empty_state": "No tiene permisos para ver esta sección.",
    }


def get_accounting_data(
    company: str,
    currency: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    """Obtiene métricas contables desde el GL."""
    balances = _income_expense_balances(company, start_date, end_date)
    income = balances["income"]
    expenses = balances["expenses"]
    profit = income - expenses
    pending_vouchers = _count_model(PaymentEntry, company, docstatus=0)
    journal_entries = _gl_query(company, start_date, end_date).count()

    return {
        "kpis": {
            "income": _money_kpi("Ingresos", income, currency),
            "expenses": _money_kpi("Gastos", expenses, currency),
            "profit": _money_kpi("Utilidad", profit, currency),
            "pending_vouchers": _count_kpi("Pendientes", pending_vouchers),
        },
        "charts": {"monthly_result": _accounting_monthly_result(company, start_date, end_date)},
        "tables": {
            "summary": [
                {"label": "Ingresos", "amount": income, "currency": currency},
                {"label": "Gastos", "amount": expenses, "currency": currency},
                {"label": "Utilidad", "amount": profit, "currency": currency},
                {"label": "Asientos del periodo", "amount": journal_entries, "currency": ""},
            ]
        },
        "actions": [
            {"label": "Nuevo comprobante", "url": "/accounting/journal/new"},
            {"label": "Estado de resultados", "url": "/reports/income-statement"},
            {"label": "Balance general", "url": "/reports/balance-sheet"},
        ],
        "empty_state": "No hay movimientos contables en el periodo seleccionado.",
    }


def get_banks_data(
    company: str,
    currency: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    """Obtiene saldos bancarios, conciliaciones y pagos pendientes."""
    accounts = database.session.query(BankAccount).filter_by(company=company, is_active=True).all()
    balances = _bank_balances(company, accounts)
    account_ids = [account.id for account in accounts]
    unreconciled = _bank_transactions_query(account_ids, start_date, end_date).filter_by(is_reconciled=False).count()
    pending_payments = _document_query(PaymentEntry, company, start_date, end_date).filter_by(docstatus=0).count()
    total_balance = sum(balances.values())

    return {
        "kpis": {
            "balance": _money_kpi("Saldo bancario", total_balance, currency),
            "accounts": _count_kpi("Cuentas activas", len(accounts)),
            "unreconciled": _count_kpi("Sin conciliar", unreconciled),
            "pending_payments": _count_kpi("Pagos pendientes", pending_payments),
        },
        "charts": {},
        "tables": {
            "account_balances": [
                {
                    "name": account.account_name,
                    "account_no": account.account_no,
                    "balance": balances.get(account.gl_account_id, 0),
                    "currency": account.currency or currency,
                }
                for account in accounts
            ],
            "recent_movements": _recent_bank_movements(account_ids, start_date, end_date, currency),
        },
        "actions": [
            {"label": "Nuevo pago", "url": "/cash_management/payment/new"},
            {"label": "Conciliar bancos", "url": "/cash_management/bank-reconciliation"},
            {"label": "Resumen bancario", "url": "/reports/bank-balance-summary"},
        ],
        "empty_state": "No hay cuentas bancarias activas para esta compañía.",
    }


def get_purchases_data(
    company: str,
    currency: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    """Obtiene métricas de compras y cuentas por pagar."""
    invoices = _document_query(PurchaseInvoice, company, start_date, end_date).filter_by(docstatus=1)
    total = _sum_query(invoices, func.coalesce(PurchaseInvoice.base_grand_total, PurchaseInvoice.grand_total))
    outstanding = _sum_document_field(PurchaseInvoice, company, "base_outstanding_amount", "outstanding_amount")
    open_orders = database.session.query(PurchaseOrder).filter_by(company=company, docstatus=1).count()
    suppliers = _active_parties(company, "supplier")

    return {
        "kpis": {
            "total": _money_kpi("Compras", total, currency),
            "outstanding": _money_kpi("Por pagar", outstanding, currency),
            "open_orders": _count_kpi("Órdenes abiertas", open_orders),
            "suppliers": _count_kpi("Proveedores activos", suppliers),
        },
        "charts": {},
        "tables": {
            "recent_invoices": _recent_purchase_invoices(company, start_date, end_date, currency),
            "payables": _payable_invoices(company, currency),
        },
        "actions": [
            {"label": "Nueva factura", "url": "/buying/purchase-invoice/new"},
            {"label": "Nueva orden", "url": "/buying/purchase-order/new"},
            {"label": "Cuentas por pagar", "url": "/reports/accounts-payable"},
        ],
        "empty_state": "No hay compras en el periodo seleccionado.",
    }


def get_inventory_data(
    company: str,
    currency: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    """Obtiene métricas de inventario basadas en StockBin y StockLedgerEntry."""
    bins = database.session.query(StockBin).filter_by(company=company)
    inventory_value = float(bins.with_entities(func.sum(StockBin.stock_value)).scalar() or 0)
    active_warehouses = database.session.query(Warehouse).filter_by(company=company, is_active=True).count()
    stocked_items = bins.filter(StockBin.actual_qty != 0).count()
    movements = _stock_movements_query(company, start_date, end_date).count()

    return {
        "kpis": {
            "value": _money_kpi("Valor inventario", inventory_value, currency),
            "warehouses": _count_kpi("Bodegas activas", active_warehouses),
            "stocked_items": _count_kpi("Ítems con existencia", stocked_items),
            "movements": _count_kpi("Movimientos", movements),
        },
        "charts": {},
        "tables": {
            "lowest_stock_items": _lowest_stock_items(company),
            "recent_movements": _recent_stock_movements(company, start_date, end_date),
        },
        "actions": [
            {"label": "Movimiento", "url": "/inventory/stock-entry/new"},
            {"label": "Conciliación", "url": "/inventory/stock-entry/reconciliation/new"},
            {"label": "Valuación", "url": "/reports/inventory-valuation"},
        ],
        "empty_state": "No hay existencias o movimientos de inventario.",
    }


def get_sales_data(
    company: str,
    currency: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    """Obtiene métricas de ventas, cobranza y clientes."""
    invoices = _document_query(SalesInvoice, company, start_date, end_date).filter_by(docstatus=1)
    sales_total = _sum_query(invoices, func.coalesce(SalesInvoice.base_grand_total, SalesInvoice.grand_total))
    receivables = _sum_document_field(SalesInvoice, company, "base_outstanding_amount", "outstanding_amount")
    invoice_count = invoices.count()
    customers = _active_parties(company, "customer")

    return {
        "kpis": {
            "sales": _money_kpi("Ventas", sales_total, currency),
            "receivables": _money_kpi("Por cobrar", receivables, currency),
            "invoices": _count_kpi("Facturas emitidas", invoice_count),
            "customers": _count_kpi("Clientes activos", customers),
        },
        "charts": {"trend": _sales_trend(company, start_date, end_date)},
        "tables": {
            "top_customers": _top_customers(company, start_date, end_date, currency),
            "recent_invoices": _recent_sales_invoices(company, start_date, end_date, currency),
        },
        "actions": [
            {"label": "Nueva factura", "url": "/sales/sales-invoice/new"},
            {"label": "Nueva orden", "url": "/sales/sales-order/new"},
            {"label": "Cuentas por cobrar", "url": "/reports/accounts-receivable"},
        ],
        "empty_state": "No hay ventas en el periodo seleccionado.",
    }


def _gl_query(company: str, start_date: date | None, end_date: date | None):
    """Crea query base de GL filtrada por compañía y fechas."""
    query = database.session.query(GLEntry).filter_by(company=company)
    if start_date and end_date:
        query = query.filter(GLEntry.posting_date >= start_date, GLEntry.posting_date <= end_date)
    return query


def _document_query(model: Any, company: str, start_date: date | None, end_date: date | None):
    """Crea query base de documento filtrada por compañía y fechas."""
    query = database.session.query(model).filter_by(company=company)
    if start_date and end_date:
        query = query.filter(model.posting_date >= start_date, model.posting_date <= end_date)
    return query


def _stock_movements_query(company: str, start_date: date | None, end_date: date | None):
    """Crea query base de movimientos de inventario."""
    query = database.session.query(StockLedgerEntry).filter_by(company=company, is_cancelled=False)
    if start_date and end_date:
        query = query.filter(StockLedgerEntry.posting_date >= start_date, StockLedgerEntry.posting_date <= end_date)
    return query


def _income_expense_balances(
    company: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, float]:
    """Calcula ingresos y gastos por clasificación de cuenta."""
    query = (
        database.session.query(Accounts.classification, func.sum(GLEntry.debit - GLEntry.credit).label("balance"))
        .join(GLEntry, Accounts.id == GLEntry.account_id)
        .filter(GLEntry.company == company, Accounts.entity == company)
        .filter(Accounts.classification.in_(INCOME_CLASSIFICATIONS | EXPENSE_CLASSIFICATIONS))
    )
    if start_date and end_date:
        query = query.filter(GLEntry.posting_date >= start_date, GLEntry.posting_date <= end_date)
    results = query.group_by(Accounts.classification).all()
    income = Decimal("0")
    expenses = Decimal("0")
    for result in results:
        balance = Decimal(result.balance or 0)
        if result.classification in INCOME_CLASSIFICATIONS:
            income += abs(balance)
        elif result.classification in EXPENSE_CLASSIFICATIONS:
            expenses += balance
    return {"income": float(income), "expenses": float(expenses)}


def _accounting_monthly_result(
    company: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, float | int]]:
    """Devuelve ingresos y gastos agrupados por mes."""
    query = (
        database.session.query(
            extract("month", GLEntry.posting_date).label("month"),
            Accounts.classification,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        )
        .join(Accounts, Accounts.id == GLEntry.account_id)
        .filter(GLEntry.company == company, Accounts.entity == company)
        .filter(Accounts.classification.in_(INCOME_CLASSIFICATIONS | EXPENSE_CLASSIFICATIONS))
    )
    if start_date and end_date:
        query = query.filter(GLEntry.posting_date >= start_date, GLEntry.posting_date <= end_date)
    rows = query.group_by("month", Accounts.classification).order_by("month").all()
    months: dict[int, dict[str, float | int]] = {}
    for row in rows:
        month = int(row.month)
        payload = months.setdefault(month, {"month": month, "income": 0.0, "expenses": 0.0})
        balance = float(row.balance or 0)
        if row.classification in INCOME_CLASSIFICATIONS:
            payload["income"] = float(payload["income"]) + abs(balance)
        elif row.classification in EXPENSE_CLASSIFICATIONS:
            payload["expenses"] = float(payload["expenses"]) + balance
    return list(months.values())


def _bank_balances(company: str, accounts: list[BankAccount]) -> dict[str | None, float]:
    """Obtiene saldos de GL por cuenta bancaria."""
    gl_account_ids = [account.gl_account_id for account in accounts if account.gl_account_id]
    if not gl_account_ids:
        return {}
    results = (
        database.session.query(GLEntry.account_id, func.sum(GLEntry.debit - GLEntry.credit))
        .filter(GLEntry.account_id.in_(gl_account_ids), GLEntry.company == company)
        .group_by(GLEntry.account_id)
        .all()
    )
    return {row[0]: float(row[1] or 0) for row in results}


def _bank_transactions_query(
    account_ids: list[str],
    start_date: date | None,
    end_date: date | None,
):
    """Crea query de transacciones bancarias filtrada por cuentas y fechas."""
    query = database.session.query(BankTransaction)
    if not account_ids:
        return query.filter(BankTransaction.id == "__none__")
    query = query.filter(BankTransaction.bank_account_id.in_(account_ids))
    if start_date and end_date:
        query = query.filter(BankTransaction.posting_date >= start_date, BankTransaction.posting_date <= end_date)
    return query


def _recent_bank_movements(
    account_ids: list[str],
    start_date: date | None,
    end_date: date | None,
    currency: str,
) -> list[dict[str, Any]]:
    """Devuelve movimientos bancarios recientes."""
    rows = _bank_transactions_query(account_ids, start_date, end_date).order_by(BankTransaction.posting_date.desc()).limit(5)
    return [
        {
            "date": row.posting_date.isoformat(),
            "description": row.description or row.reference_number or "Movimiento bancario",
            "amount": float((row.deposit or 0) - (row.withdrawal or 0)),
            "currency": currency,
            "status": "Conciliado" if row.is_reconciled else "Pendiente",
        }
        for row in rows
    ]


def _recent_purchase_invoices(
    company: str,
    start_date: date | None,
    end_date: date | None,
    currency: str,
) -> list[dict[str, Any]]:
    """Devuelve facturas de compra recientes."""
    rows = (
        _document_query(PurchaseInvoice, company, start_date, end_date)
        .filter_by(docstatus=1)
        .order_by(PurchaseInvoice.posting_date.desc())
        .limit(5)
    )
    return [_purchase_invoice_payload(row, currency) for row in rows]


def _payable_invoices(company: str, currency: str) -> list[dict[str, Any]]:
    """Devuelve facturas por pagar."""
    rows = (
        database.session.query(PurchaseInvoice)
        .filter_by(company=company, docstatus=1)
        .filter(func.coalesce(PurchaseInvoice.base_outstanding_amount, PurchaseInvoice.outstanding_amount, 0) > 0)
        .order_by(PurchaseInvoice.posting_date.desc())
        .limit(5)
    )
    return [_purchase_invoice_payload(row, currency) for row in rows]


def _purchase_invoice_payload(invoice: PurchaseInvoice, currency: str) -> dict[str, Any]:
    """Serializa una factura de compra para tablas del dashboard."""
    return {
        "date": invoice.posting_date.isoformat() if invoice.posting_date else "",
        "document_no": invoice.document_no or invoice.id,
        "party": invoice.supplier_name or "Proveedor",
        "total": _numeric(invoice.base_grand_total or invoice.grand_total),
        "outstanding": _numeric(invoice.base_outstanding_amount or invoice.outstanding_amount),
        "currency": currency,
    }


def _lowest_stock_items(company: str) -> list[dict[str, Any]]:
    """Devuelve ítems con menor existencia actual por bodega."""
    rows = (
        database.session.query(StockBin, Item.name.label("item_name"), Warehouse.name.label("warehouse_name"))
        .join(Item, Item.code == StockBin.item_code)
        .join(Warehouse, Warehouse.code == StockBin.warehouse)
        .filter(StockBin.company == company, Warehouse.company == company)
        .order_by(StockBin.actual_qty.asc())
        .limit(5)
    )
    return [
        {
            "item_code": stock_bin.item_code,
            "item_name": item_name,
            "warehouse": warehouse_name,
            "current_qty": _numeric(stock_bin.actual_qty),
            "stock_value": _numeric(stock_bin.stock_value),
        }
        for stock_bin, item_name, warehouse_name in rows
    ]


def _recent_stock_movements(
    company: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    """Devuelve movimientos recientes de inventario."""
    rows = _stock_movements_query(company, start_date, end_date).order_by(StockLedgerEntry.posting_date.desc()).limit(5)
    return [
        {
            "date": row.posting_date.isoformat(),
            "item_code": row.item_code,
            "warehouse": row.warehouse,
            "qty_change": _numeric(row.qty_change),
            "voucher_type": row.voucher_type,
        }
        for row in rows
    ]


def _sales_trend(
    company: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, float | int]]:
    """Devuelve tendencia mensual de ventas."""
    query = (
        _document_query(SalesInvoice, company, start_date, end_date)
        .filter_by(docstatus=1)
        .with_entities(
            extract("month", SalesInvoice.posting_date).label("month"),
            func.sum(func.coalesce(SalesInvoice.base_grand_total, SalesInvoice.grand_total)).label("total"),
        )
        .group_by("month")
        .order_by("month")
    )
    return [{"month": int(row.month), "total": _numeric(row.total)} for row in query]


def _top_customers(
    company: str,
    start_date: date | None,
    end_date: date | None,
    currency: str,
) -> list[dict[str, Any]]:
    """Devuelve mejores clientes por ventas."""
    query = (
        _document_query(SalesInvoice, company, start_date, end_date)
        .filter_by(docstatus=1)
        .with_entities(
            SalesInvoice.customer_name,
            func.sum(func.coalesce(SalesInvoice.base_grand_total, SalesInvoice.grand_total)).label("total"),
        )
        .group_by(SalesInvoice.customer_name)
        .order_by(func.sum(func.coalesce(SalesInvoice.base_grand_total, SalesInvoice.grand_total)).desc())
        .limit(5)
    )
    return [{"name": row.customer_name or "Cliente", "total": _numeric(row.total), "currency": currency} for row in query]


def _recent_sales_invoices(
    company: str,
    start_date: date | None,
    end_date: date | None,
    currency: str,
) -> list[dict[str, Any]]:
    """Devuelve facturas de venta recientes."""
    rows = (
        _document_query(SalesInvoice, company, start_date, end_date)
        .filter_by(docstatus=1)
        .order_by(SalesInvoice.posting_date.desc())
        .limit(5)
    )
    return [
        {
            "date": row.posting_date.isoformat() if row.posting_date else "",
            "document_no": row.document_no or row.id,
            "party": row.customer_name or "Cliente",
            "total": _numeric(row.base_grand_total or row.grand_total),
            "outstanding": _numeric(row.base_outstanding_amount or row.outstanding_amount),
            "currency": currency,
        }
        for row in rows
    ]


def _active_parties(company: str, role: str) -> int:
    """Cuenta terceros activos en una compañía."""
    party_filter = Party.is_customer.is_(True) if role == "customer" else Party.is_supplier.is_(True)
    return (
        database.session.query(CompanyParty)
        .join(Party, Party.id == CompanyParty.party_id)
        .filter(CompanyParty.company == company)
        .filter(CompanyParty.is_active.is_(True))
        .filter(party_filter, Party.is_active.is_(True))
        .count()
    )


def _sum_document_field(model: Any, company: str, base_field: str, fallback_field: str) -> float:
    """Suma un campo monetario con fallback en documentos aprobados."""
    expression = func.coalesce(getattr(model, base_field), getattr(model, fallback_field))
    return _numeric(database.session.query(func.sum(expression)).filter_by(company=company, docstatus=1).scalar())


def _sum_query(query: Any, expression: Any) -> float:
    """Suma una expresión sobre un query existente."""
    return _numeric(query.with_entities(func.sum(expression)).scalar())


def _count_model(model: Any, company: str, docstatus: int) -> int:
    """Cuenta documentos por compañía y estado."""
    return database.session.query(model).filter_by(company=company, docstatus=docstatus).count()


def _money_kpi(label: str, value: float, currency: str) -> dict[str, Any]:
    """Crea un KPI monetario."""
    return {"label": label, "value": value, "format": "money", "currency": currency}


def _count_kpi(label: str, value: int) -> dict[str, Any]:
    """Crea un KPI numérico."""
    return {"label": label, "value": value, "format": "count"}


def _numeric(value: Any) -> float:
    """Convierte valores numéricos de SQLAlchemy a float."""
    return float(value or 0)
