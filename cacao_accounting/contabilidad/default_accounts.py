# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios para cuentas predeterminadas y tipos de cuenta."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import Accounts, CompanyDefaultAccount, database


class DefaultAccountError(ValueError):
    """Error de configuracion de cuentas predeterminadas."""


@dataclass(frozen=True)
class DefaultAccountDefinition:
    """Define una cuenta predeterminada requerida por el sistema."""

    field: str
    label: str
    allowed_account_types: tuple[str, ...]


DEFAULT_ACCOUNT_DEFINITIONS: tuple[DefaultAccountDefinition, ...] = (
    DefaultAccountDefinition("default_cash", "Cuenta de efectivo por defecto", ("cash",)),
    DefaultAccountDefinition("default_bank", "Cuenta bancaria por defecto", ("bank",)),
    DefaultAccountDefinition("default_receivable", "Cuenta por cobrar por defecto", ("receivable",)),
    DefaultAccountDefinition("default_payable", "Cuenta por pagar por defecto", ("payable",)),
    DefaultAccountDefinition("default_income", "Cuenta de ingresos por defecto", ("income",)),
    DefaultAccountDefinition("default_expense", "Cuenta de gastos por defecto", ("expense",)),
    DefaultAccountDefinition("default_inventory", "Cuenta de inventario por defecto", ("inventory",)),
    DefaultAccountDefinition("default_cogs", "Cuenta de costo de ventas por defecto", ("cost_of_goods_sold", "expense")),
    DefaultAccountDefinition(
        "inventory_adjustment_account_id",
        "Cuenta de ajustes de inventario",
        ("inventory_adjustment", "expense"),
    ),
    DefaultAccountDefinition("bridge_account_id", "Cuenta puente de compras", ("bridge",)),
    DefaultAccountDefinition(
        "customer_advance_account_id",
        "Cuenta de anticipos de clientes",
        ("customer_advance", "liability"),
    ),
    DefaultAccountDefinition(
        "supplier_advance_account_id",
        "Cuenta de anticipos a proveedores",
        ("supplier_advance", "asset"),
    ),
    DefaultAccountDefinition(
        "bank_difference_account_id",
        "Cuenta de diferencias bancarias",
        ("bank_difference", "expense", "income"),
    ),
    DefaultAccountDefinition("default_sales_tax_account_id", "Cuenta de impuesto de ventas", ("tax",)),
    DefaultAccountDefinition("default_purchase_tax_account_id", "Cuenta de impuesto de compras", ("tax",)),
    DefaultAccountDefinition("default_rounding_account_id", "Cuenta de redondeo", ("rounding", "expense")),
    DefaultAccountDefinition("exchange_gain_account_id", "Cuenta de ganancia cambiaria", ("exchange_gain", "income")),
    DefaultAccountDefinition("exchange_loss_account_id", "Cuenta de perdida cambiaria", ("exchange_loss", "expense")),
    DefaultAccountDefinition(
        "unrealized_exchange_gain_account_id",
        "Cuenta de ganancia cambiaria no realizada",
        ("unrealized_exchange_gain", "income"),
    ),
    DefaultAccountDefinition(
        "unrealized_exchange_loss_account_id",
        "Cuenta de perdida cambiaria no realizada",
        ("unrealized_exchange_loss", "expense"),
    ),
    DefaultAccountDefinition("deferred_income_account_id", "Cuenta de ingresos diferidos", ("deferred_income",)),
    DefaultAccountDefinition("deferred_expense_account_id", "Cuenta de gastos diferidos", ("deferred_expense",)),
    DefaultAccountDefinition("payment_discount_account_id", "Cuenta de descuentos de pago", ("payment_discount", "expense")),
    DefaultAccountDefinition(
        "period_profit_loss_account_id",
        "Cuenta de ganancias y perdidas del periodo",
        ("period_profit_loss",),
    ),
    DefaultAccountDefinition(
        "retained_earnings_account_id",
        "Cuenta de ganancias y perdidas acumuladas",
        ("retained_earnings",),
    ),
)

DEFAULT_ACCOUNT_FIELDS: tuple[str, ...] = tuple(item.field for item in DEFAULT_ACCOUNT_DEFINITIONS)
DEFAULT_ACCOUNT_DEFINITION_BY_FIELD = {item.field: item for item in DEFAULT_ACCOUNT_DEFINITIONS}

SPECIAL_ACCOUNT_TYPES: frozenset[str] = frozenset(
    {
        "bank",
        "cash",
        "receivable",
        "payable",
        "inventory",
        "tax",
        "bridge",
        "cost_of_goods_sold",
        "inventory_adjustment",
        "customer_advance",
        "supplier_advance",
        "bank_difference",
        "rounding",
        "exchange_gain",
        "exchange_loss",
        "unrealized_exchange_gain",
        "unrealized_exchange_loss",
        "deferred_income",
        "deferred_expense",
        "payment_discount",
        "period_profit_loss",
        "retained_earnings",
        "asset",
        "liability",
        "equity",
        "income",
        "expense",
    }
)

ACCOUNT_TYPE_ALLOWED_VOUCHERS: dict[str, frozenset[str]] = {
    "bank": frozenset({"payment_entry", "bank_transaction"}),
    "cash": frozenset({"payment_entry", "bank_transaction"}),
    "receivable": frozenset({"sales_invoice", "payment_entry"}),
    "payable": frozenset({"purchase_invoice", "payment_entry"}),
    "inventory": frozenset({"purchase_receipt", "delivery_note", "stock_entry"}),
    "tax": frozenset({"sales_invoice", "purchase_invoice"}),
    "bridge": frozenset({"purchase_receipt", "purchase_invoice", "stock_entry"}),
    "cost_of_goods_sold": frozenset({"delivery_note"}),
    "inventory_adjustment": frozenset({"stock_entry"}),
    "customer_advance": frozenset({"payment_entry"}),
    "supplier_advance": frozenset({"payment_entry"}),
    "bank_difference": frozenset({"bank_transaction", "journal_entry"}),
    "rounding": frozenset({"sales_invoice", "purchase_invoice", "payment_entry"}),
    "exchange_gain": frozenset({"exchange_revaluation", "journal_entry"}),
    "exchange_loss": frozenset({"exchange_revaluation", "journal_entry"}),
    "unrealized_exchange_gain": frozenset({"exchange_revaluation"}),
    "unrealized_exchange_loss": frozenset({"exchange_revaluation"}),
    "deferred_income": frozenset({"sales_invoice", "journal_entry"}),
    "deferred_expense": frozenset({"purchase_invoice", "journal_entry"}),
    "payment_discount": frozenset({"payment_entry"}),
    "period_profit_loss": frozenset({"period_close_run"}),
    "retained_earnings": frozenset({"period_close_run"}),
}

MANUAL_BLOCKED_ACCOUNT_TYPES: frozenset[str] = frozenset(
    {
        "inventory",
    }
)


def default_account_json_path(catalog_file: str | Path) -> Path:
    """Devuelve la ruta del JSON de mapping que acompana a un catalogo CSV."""
    path = Path(catalog_file)
    return path.with_suffix(".json")


def catalog_has_default_mapping(catalog_file: str | Path) -> bool:
    """Indica si un catalogo tiene mapping JSON companero."""
    return default_account_json_path(catalog_file).is_file()


def load_catalog_default_mapping(catalog_file: str | Path) -> dict[str, str]:
    """Carga y valida el mapping de cuentas predeterminadas de un catalogo."""
    mapping_path = default_account_json_path(catalog_file)
    if not mapping_path.is_file():
        raise DefaultAccountError(f"El catalogo {Path(catalog_file).name} no tiene mapping JSON de cuentas.")
    raw = json.loads(mapping_path.read_text(encoding="utf-8"))
    default_accounts = raw.get("default_accounts")
    if not isinstance(default_accounts, dict):
        raise DefaultAccountError("El mapping JSON debe contener el objeto default_accounts.")
    missing = [field for field in DEFAULT_ACCOUNT_FIELDS if not default_accounts.get(field)]
    if missing:
        raise DefaultAccountError("Faltan cuentas predeterminadas en el mapping: " + ", ".join(missing))
    return {field: str(default_accounts[field]) for field in DEFAULT_ACCOUNT_FIELDS}


def account_label(account: Accounts | None) -> str:
    """Etiqueta compacta para selects y paneles."""
    if not account:
        return ""
    return f"{account.code} - {account.name}"


def get_company_default_accounts(company: str) -> CompanyDefaultAccount | None:
    """Obtiene la configuracion de cuentas predeterminadas de una compania."""
    return database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalar_one_or_none()


def _account_by_code(company: str, code: str) -> Accounts | None:
    return database.session.execute(select(Accounts).filter_by(entity=company, code=code)).scalar_one_or_none()


def _account_by_id(account_id: str) -> Accounts | None:
    return database.session.get(Accounts, account_id)


def validate_default_account_assignment(company: str, field: str, account_id: str | None) -> None:
    """Valida que una cuenta pueda asignarse a un campo predeterminado."""
    if not account_id:
        return
    definition = DEFAULT_ACCOUNT_DEFINITION_BY_FIELD[field]
    account = _account_by_id(account_id)
    if not account or account.entity != company:
        raise DefaultAccountError("La cuenta seleccionada no existe para la compania.")
    account_type = (account.account_type or "").strip()
    if account_type and account_type not in definition.allowed_account_types:
        allowed = ", ".join(definition.allowed_account_types)
        raise DefaultAccountError(f"La cuenta {account.code} debe ser de tipo: {allowed}.")


def upsert_company_default_accounts(company: str, values: dict[str, str | None]) -> CompanyDefaultAccount:
    """Crea o actualiza la configuracion de cuentas predeterminadas."""
    config = get_company_default_accounts(company)
    if config is None:
        config = CompanyDefaultAccount(company=company)
        database.session.add(config)
    for field in DEFAULT_ACCOUNT_FIELDS:
        value = values.get(field) or None
        validate_default_account_assignment(company, field, value)
        setattr(config, field, value)
    return config


def apply_catalog_default_mapping(company: str, catalog_file: str | Path) -> CompanyDefaultAccount:
    """Aplica el mapping JSON de un catalogo a una compania."""
    code_mapping = load_catalog_default_mapping(catalog_file)
    values: dict[str, str | None] = {}
    for field, account_code in code_mapping.items():
        account = _account_by_code(company, account_code)
        if not account:
            raise DefaultAccountError(f"La cuenta {account_code} no existe en la compania {company}.")
        values[field] = account.id
    return upsert_company_default_accounts(company, values)


def validate_gl_account_usage(account_id: str, voucher_type: str | None) -> None:
    """Valida restricciones estrictas de uso por tipo de cuenta."""
    account = _account_by_id(account_id)
    if not account:
        raise DefaultAccountError("La cuenta contable configurada no existe.")
    account_type = (account.account_type or "").strip()
    if not account_type:
        return
    is_manual_voucher = voucher_type == "journal_entry"
    if is_manual_voucher and account_type in MANUAL_BLOCKED_ACCOUNT_TYPES:
        raise DefaultAccountError(f"La cuenta {account.code} de tipo {account_type} no permite afectacion manual.")
    if is_manual_voucher:
        return
    allowed_vouchers = ACCOUNT_TYPE_ALLOWED_VOUCHERS.get(account_type)
    if allowed_vouchers and voucher_type not in allowed_vouchers:
        raise DefaultAccountError(
            f"La cuenta {account.code} de tipo {account_type} no puede afectarse desde {voucher_type or 'este origen'}."
        )


def accounts_for_company(company: str) -> list[Accounts]:
    """Lista cuentas activas de detalle para seleccion de defaults."""
    return list(
        database.session.execute(
            select(Accounts).filter_by(entity=company).where(Accounts.group.is_(False)).order_by(Accounts.code)
        ).scalars()
    )


def default_account_rows(config: CompanyDefaultAccount | None) -> list[dict[str, Any]]:
    """Construye filas de presentacion para la UI de cuentas predeterminadas."""
    rows: list[dict[str, Any]] = []
    for definition in DEFAULT_ACCOUNT_DEFINITIONS:
        account = _account_by_id(getattr(config, definition.field)) if config and getattr(config, definition.field) else None
        rows.append(
            {
                "field": definition.field,
                "label": definition.label,
                "allowed_account_types": definition.allowed_account_types,
                "account": account,
            }
        )
    return rows
