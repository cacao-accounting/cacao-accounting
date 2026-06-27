# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
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
        from cacao_accounting.database import AccountingPeriod, Book, Entity, Modules, User, database

        database.create_all()
        report_user = User(user="report-user", name="Report User", classification="admin", active=True)
        report_user.password = b"x"
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
                Modules(module="accounting", default=True, enabled=True),
                Modules(module="banking", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
                report_user,
                Book(
                    entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, default=True, currency="NIO"
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="2026-05",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                ),
            ]
        )
        database.session.commit()
        yield app


def test_get_bank_movement_detail_supports_bank_filter(app_ctx):
    from cacao_accounting.database import Bank, BankAccount, BankTransaction, PaymentEntry, database
    from cacao_accounting.reportes.services import BankingFilters, get_bank_movement_detail

    bank = Bank(name="Banco Central")
    database.session.add(bank)
    database.session.flush()
    account_a = BankAccount(bank_id=bank.id, company="cacao", account_name="Cuenta Operativa", currency="NIO")
    account_b = BankAccount(bank_id=bank.id, company="cacao", account_name="Cuenta Transfer", currency="NIO")
    database.session.add_all([account_a, account_b])
    database.session.flush()
    database.session.add_all(
        [
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 5, 2),
                payment_type="receive",
                bank_account_id=account_a.id,
                received_amount=Decimal("100.00"),
                currency="NIO",
                docstatus=1,
            ),
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 5, 3),
                payment_type="pay",
                bank_account_id=account_a.id,
                paid_amount=Decimal("40.00"),
                currency="NIO",
                docstatus=1,
            ),
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 5, 4),
                payment_type="internal_transfer",
                bank_account_id=account_a.id,
                target_bank_account_id=account_b.id,
                paid_amount=Decimal("25.00"),
                received_amount=Decimal("25.00"),
                currency="NIO",
                docstatus=1,
            ),
            BankTransaction(
                bank_account_id=account_a.id,
                posting_date=date(2026, 5, 5),
                deposit=Decimal("10.00"),
                reference_number="ST-001",
            ),
        ]
    )
    database.session.commit()

    report = get_bank_movement_detail(
        BankingFilters(company="cacao", bank_account_id=account_a.id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    )

    assert [row.values["payment_type"] for row in report.rows] == ["receive", "pay", "internal_transfer", "statement"]
    assert report.totals["incoming_amount"] == Decimal("110.00")
    assert report.totals["outgoing_amount"] == Decimal("65.00")
    assert report.totals["running_balance"] == Decimal("45.00")


def test_get_inventory_existence_uses_as_of_date(app_ctx):
    from cacao_accounting.database import Item, StockLedgerEntry, UOM, Warehouse, database
    from cacao_accounting.reportes.services import KardexFilters, get_inventory_existence

    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(code="ITEM-EX", name="Item Existencia", item_type="goods", is_stock_item=True, default_uom="EA"),
            Warehouse(code="WH-EX", name="Bodega Existencia", company="cacao"),
        ]
    )
    database.session.add_all(
        [
            StockLedgerEntry(
                posting_date=date(2026, 5, 1),
                item_code="ITEM-EX",
                warehouse="WH-EX",
                company="cacao",
                qty_change=Decimal("10"),
                qty_after_transaction=Decimal("10"),
                valuation_rate=Decimal("10"),
                stock_value_difference=Decimal("100"),
                stock_value=Decimal("100"),
                voucher_type="stock_entry",
                voucher_id="STE-1",
            ),
            StockLedgerEntry(
                posting_date=date(2026, 5, 3),
                item_code="ITEM-EX",
                warehouse="WH-EX",
                company="cacao",
                qty_change=Decimal("-4"),
                qty_after_transaction=Decimal("6"),
                valuation_rate=Decimal("10"),
                stock_value_difference=Decimal("-40"),
                stock_value=Decimal("60"),
                voucher_type="stock_entry",
                voucher_id="STE-2",
            ),
            StockLedgerEntry(
                posting_date=date(2026, 5, 10),
                item_code="ITEM-EX",
                warehouse="WH-EX",
                company="cacao",
                qty_change=Decimal("2"),
                qty_after_transaction=Decimal("8"),
                valuation_rate=Decimal("10"),
                stock_value_difference=Decimal("20"),
                stock_value=Decimal("80"),
                voucher_type="stock_entry",
                voucher_id="STE-3",
            ),
        ]
    )
    database.session.commit()

    report = get_inventory_existence(
        KardexFilters(company="cacao", item_code="ITEM-EX", warehouse="WH-EX", date_to=date(2026, 5, 5))
    )

    assert len(report.rows) == 1
    row = report.rows[0].values
    assert row["item_name"] == "Item Existencia"
    assert row["balance_qty"] == Decimal("6")
    assert row["stock_value"] == Decimal("60")


def test_operational_report_routes_render_without_breaking_financial_reports(app_ctx):
    from cacao_accounting.database import User, database

    user = database.session.execute(database.select(User).filter_by(user="report-user")).scalar_one()
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True

    banking_response = client.get("/reports/bank-movement?company=cacao")
    banking_html = banking_response.get_data(as_text=True)
    assert banking_response.status_code == 200
    assert 'doctype: "bank_account"' in banking_html
    assert "Detalle de Movimiento Bancario" in banking_html

    accounting_response = client.get("/reports/account-movement?company=cacao&ledger=FISC&accounting_period=2026-05")
    accounting_html = accounting_response.get_data(as_text=True)
    assert accounting_response.status_code == 200
    assert 'doctype: "book"' in accounting_html
    assert 'doctype: "bank_account"' not in accounting_html
