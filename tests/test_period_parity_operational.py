# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de paridad de períodos en reportes operativos (Bancos e Inventario)."

Cubre el criterio de la estrategia de pruebas del issue: al menos un reporte de
Bancos e Inventario resuelve exactamente la ventana del período contable,
incluyendo primer y último día y excluyendo lo anterior y posterior.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def op_app():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "testing",
        }
    )
    with app.app_context():
        from cacao_accounting.database import (
            AccountingPeriod,
            Bank,
            BankAccount,
            Book,
            Entity,
            Item,
            Modules,
            UOM,
            User,
            Warehouse,
            database,
        )

        database.create_all()
        user = User(user="op-user", name="Op User", classification="admin", active=True)
        user.password = b"x"
        bank = Bank(name="Banco Central")
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="banking", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                user,
                Book(
                    entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, default=True, currency="NIO"
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
                bank,
                UOM(code="EA", name="Each"),
                Item(code="ITEM-1", name="Item Uno", item_type="goods", is_stock_item=True, default_uom="EA"),
                Warehouse(code="WH-1", name="Bodega 1", company="cacao"),
            ]
        )
        database.session.flush()
        database.session.add(BankAccount(bank_id=bank.id, company="cacao", account_name="Operativa", currency="NIO"))
        database.session.commit()
        yield app


def _seed_bank(op_app) -> None:
    from cacao_accounting.database import BankAccount, PaymentEntry, database

    account = database.session.execute(database.select(BankAccount).where(BankAccount.company == "cacao")).scalar_one()
    database.session.add_all(
        [
            PaymentEntry(
                company="cacao",
                posting_date=date(2025, 12, 31),
                payment_type="receive",
                bank_account_id=account.id,
                received_amount=Decimal("10"),
                currency="NIO",
                docstatus=1,
            ),
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 1, 1),
                payment_type="receive",
                bank_account_id=account.id,
                received_amount=Decimal("20"),
                currency="NIO",
                docstatus=1,
            ),
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 1, 31),
                payment_type="pay",
                bank_account_id=account.id,
                paid_amount=Decimal("5"),
                currency="NIO",
                docstatus=1,
            ),
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 2, 1),
                payment_type="receive",
                bank_account_id=account.id,
                received_amount=Decimal("30"),
                currency="NIO",
                docstatus=1,
            ),
        ]
    )
    database.session.commit()


def _bank_dates(period_from: str, period_to: str) -> set[date]:
    from cacao_accounting.database import AccountingPeriod, BankAccount, database
    from cacao_accounting.reportes.services import BankingFilters, get_bank_movement_detail

    from_id = (
        database.session.execute(database.select(AccountingPeriod).where(AccountingPeriod.name == period_from)).scalar_one().id
    )
    to_id = (
        database.session.execute(database.select(AccountingPeriod).where(AccountingPeriod.name == period_to)).scalar_one().id
    )
    account_id = database.session.execute(database.select(BankAccount).where(BankAccount.company == "cacao")).scalar_one().id
    report = get_bank_movement_detail(
        BankingFilters(company="cacao", bank_account_id=account_id, period_from=str(from_id), period_to=str(to_id))
    )
    dates: set[date] = set()
    for row in report.rows:
        value = row.values.get("posting_date")
        if isinstance(value, date):
            dates.add(value)
    return dates


def _seed_inventory(op_app) -> None:
    from cacao_accounting.database import StockLedgerEntry, database

    database.session.add_all(
        [
            StockLedgerEntry(
                posting_date=date(2025, 12, 31),
                item_code="ITEM-1",
                warehouse="WH-1",
                company="cacao",
                qty_change=Decimal("1"),
                qty_after_transaction=Decimal("1"),
                valuation_rate=Decimal("1"),
                stock_value_difference=Decimal("1"),
                stock_value=Decimal("1"),
                voucher_type="stock_entry",
                voucher_id="STE-0",
            ),
            StockLedgerEntry(
                posting_date=date(2026, 1, 1),
                item_code="ITEM-1",
                warehouse="WH-1",
                company="cacao",
                qty_change=Decimal("2"),
                qty_after_transaction=Decimal("3"),
                valuation_rate=Decimal("1"),
                stock_value_difference=Decimal("2"),
                stock_value=Decimal("3"),
                voucher_type="stock_entry",
                voucher_id="STE-1",
            ),
            StockLedgerEntry(
                posting_date=date(2026, 1, 31),
                item_code="ITEM-1",
                warehouse="WH-1",
                company="cacao",
                qty_change=Decimal("3"),
                qty_after_transaction=Decimal("6"),
                valuation_rate=Decimal("1"),
                stock_value_difference=Decimal("3"),
                stock_value=Decimal("6"),
                voucher_type="stock_entry",
                voucher_id="STE-2",
            ),
            StockLedgerEntry(
                posting_date=date(2026, 2, 1),
                item_code="ITEM-1",
                warehouse="WH-1",
                company="cacao",
                qty_change=Decimal("4"),
                qty_after_transaction=Decimal("10"),
                valuation_rate=Decimal("1"),
                stock_value_difference=Decimal("4"),
                stock_value=Decimal("10"),
                voucher_type="stock_entry",
                voucher_id="STE-3",
            ),
        ]
    )
    database.session.commit()


def _inventory_dates(period_from: str, period_to: str) -> set[date]:
    from cacao_accounting.database import AccountingPeriod, database
    from cacao_accounting.reportes.services import KardexFilters, get_kardex

    from_id = (
        database.session.execute(database.select(AccountingPeriod).where(AccountingPeriod.name == period_from)).scalar_one().id
    )
    to_id = (
        database.session.execute(database.select(AccountingPeriod).where(AccountingPeriod.name == period_to)).scalar_one().id
    )
    report = get_kardex(KardexFilters(company="cacao", period_from=str(from_id), period_to=str(to_id)))
    dates: set[date] = set()
    for row in report.rows:
        value = row.values.get("posting_date")
        if isinstance(value, date):
            dates.add(value)
    return dates


def test_bank_movement_period_inclusive(op_app) -> None:
    """El detalle bancario acota el período: primer y último día dentro; antes/después fuera."""
    _seed_bank(op_app)
    dates = _bank_dates("01-2026", "01-2026")
    assert date(2026, 1, 1) in dates
    assert date(2026, 1, 31) in dates
    assert date(2025, 12, 31) not in dates
    assert date(2026, 2, 1) not in dates


def test_kardex_period_inclusive(op_app) -> None:
    """El Kardex acota el período: primer y último día dentro; antes/después fuera."""
    _seed_inventory(op_app)
    dates = _inventory_dates("01-2026", "01-2026")
    assert date(2026, 1, 1) in dates
    assert date(2026, 1, 31) in dates
    assert date(2025, 12, 31) not in dates
    assert date(2026, 2, 1) not in dates
