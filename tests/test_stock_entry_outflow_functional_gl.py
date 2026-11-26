# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1879: el ajuste de solo valor lleva al GL el costo funcional del SLE."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from flask_login import login_user

from cacao_accounting.contabilidad.posting_service import (
    _get_stock_entry_line_amount,
    _movement_outflow_issue,
    post_stock_entry,
)
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    GLEntry,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerBookEntry,
    StockLedgerEntry,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)


def _configure_stock_accounts(warehouse_code: str) -> int:
    """Configure the inventory and adjustment accounts for the isolated test company."""
    inventory_account = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
    adjustment_account = database.session.execute(
        database.select(Accounts).filter_by(entity="cacao", code="5201")
    ).scalar_one()
    for account in (inventory_account, adjustment_account):
        account.active = True
        account.enabled = True
        account.group = False
    database.session.add(
        WarehouseCompanyAccount(
            warehouse_code=warehouse_code,
            company="cacao",
            inventory_account_id=inventory_account.id,
        )
    )
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    defaults.inventory_adjustment_account_id = adjustment_account.id
    database.session.commit()
    return inventory_account.id


def _post_stock_entry(app, entry: StockEntry) -> None:
    """Post a stock entry through the real service with an authenticated test user."""
    with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
        user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        login_user(user)
        post_stock_entry(entry)
    database.session.commit()


def _assert_refreshed_amount_only_line(entry_id: str, entry: StockEntry) -> None:
    """Ensure a reloaded amount-only line resolves its own functional amount."""
    database.session.expire_all()
    line = database.session.execute(
        database.select(StockEntryItem).filter_by(stock_entry_id=entry_id, qty=Decimal("0"))
    ).scalar_one()
    assert not hasattr(line, "_inventory_cost_amount")
    assert _get_stock_entry_line_amount(entry, line, "adjustment_negative") == Decimal("350")


def _assert_book_stock_matches_gl(entry_id: str, inventory_account_id: int, movement_ids: list[str]) -> None:
    """Reconcile adjustment stock and GL values and prove each book balances."""
    book_values = database.session.execute(
        database.select(StockLedgerBookEntry).where(StockLedgerBookEntry.stock_ledger_entry_id.in_(movement_ids))
    ).scalars()
    stock_by_ledger: dict[str, Decimal] = {}
    for value in book_values:
        stock_by_ledger[value.ledger_id] = stock_by_ledger.get(value.ledger_id, Decimal("0")) + Decimal(value.book_amount)

    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars()
    gl_inventory_by_ledger: dict[str, Decimal] = {}
    gl_balance_by_ledger: dict[str, list[Decimal]] = {}
    for entry in gl_entries:
        gl_balance_by_ledger.setdefault(entry.ledger_id, [Decimal("0"), Decimal("0")])
        gl_balance_by_ledger[entry.ledger_id][0] += entry.debit
        gl_balance_by_ledger[entry.ledger_id][1] += entry.credit
        if entry.account_id == inventory_account_id:
            gl_inventory_by_ledger[entry.ledger_id] = gl_inventory_by_ledger.get(entry.ledger_id, Decimal("0")) + (
                entry.debit - entry.credit
            )

    assert gl_inventory_by_ledger == stock_by_ledger
    assert gl_balance_by_ledger
    assert all(debit == credit for debit, credit in gl_balance_by_ledger.values())


def _stock_entry(purpose: str, suffix: str, warehouse_code: str, posting_date: date) -> StockEntry:
    """Build one fully specified stock entry for the integration scenario."""
    is_adjustment = purpose == "adjustment_negative"
    return StockEntry(
        purpose=purpose,
        company="cacao",
        posting_date=posting_date,
        from_warehouse=warehouse_code,
        to_warehouse=warehouse_code,
        document_no=f"{'MIX' if is_adjustment else 'OPEN'}-{suffix}",
        transaction_currency="USD" if is_adjustment else "NIO",
        base_currency="NIO",
        exchange_rate=Decimal("35") if is_adjustment else Decimal("1"),
        docstatus=1,
    )


def test_ajuste_negativo_de_solo_valor_usa_el_costo_funcional(app, entorno_contable):
    """10 USD con tasa 35 registran -350 NIO en SLE y en GL, no -10 NIO."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        uom = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
        database.session.add(uom)
        database.session.flush()
        item = Item(code=f"ART{sufijo}", name="Artículo", item_type="goods", is_stock_item=True, default_uom=uom.code)
        warehouse = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        database.session.add_all([item, warehouse])
        database.session.flush()
        database.session.add(
            StockBin(
                company="cacao",
                item_code=item.code,
                warehouse=warehouse.code,
                actual_qty=Decimal("10"),
                stock_value=Decimal("3500"),
                valuation_rate=Decimal("350"),
            )
        )
        database.session.commit()

        documento = SimpleNamespace(
            id=f"se-{sufijo}",
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("35"),
            purpose="adjustment_negative",
            from_warehouse=warehouse.code,
            voucher_type="stock_entry",
        )
        linea = SimpleNamespace(
            id=f"line-{sufijo}",
            item_code=item.code,
            source_warehouse=warehouse.code,
            target_warehouse=None,
            amount=Decimal("10"),
            valuation_rate=Decimal("0"),
            basic_rate=Decimal("0"),
            qty=Decimal("0"),
            qty_in_base_uom=Decimal("0"),
            batch_id=None,
            serial_no=None,
        )

        movimientos = _movement_outflow_issue(documento, linea, Decimal("0"))

        assert len(movimientos) == 1
        assert movimientos[0].stock_value_difference == Decimal("-350")
        assert getattr(linea, "_inventory_cost_amount", None) == Decimal("350")
        assert _get_stock_entry_line_amount(documento, linea, "adjustment_negative") == Decimal("350")


def test_posting_mixto_no_reutiliza_el_costo_fisico_en_la_linea_de_solo_valor(entorno_contable_aislado):
    """GL y SLE concilian por libro al combinar salida física y amount-only."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:6].upper()
    item_code = f"ART{suffix}"
    warehouse_code = f"W{suffix}"
    posting_date = date(2026, 5, 20)

    with app.app_context():
        database.session.add_all(
            [
                Item(code=item_code, name="Artículo multimoneda", item_type="goods", is_stock_item=True, default_uom="UND"),
                Warehouse(code=warehouse_code, name="Bodega mixta", company="cacao", is_active=True),
            ]
        )
        database.session.flush()
        inventory_account_id = _configure_stock_accounts(warehouse_code)

        opening = _stock_entry("adjustment_positive", suffix, warehouse_code, posting_date)
        database.session.add(opening)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=opening.id,
                item_code=item_code,
                source_warehouse=warehouse_code,
                target_warehouse=warehouse_code,
                qty=Decimal("5"),
                qty_in_base_uom=Decimal("5"),
                uom="UND",
                basic_rate=Decimal("700"),
                amount=Decimal("3500"),
            )
        )
        database.session.commit()
        _post_stock_entry(app, opening)

        adjustment = _stock_entry("adjustment_negative", suffix, warehouse_code, posting_date)
        database.session.add(adjustment)
        database.session.flush()
        database.session.add_all(
            [
                StockEntryItem(
                    stock_entry_id=adjustment.id,
                    item_code=item_code,
                    source_warehouse=warehouse_code,
                    target_warehouse=warehouse_code,
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    basic_rate=Decimal("700"),
                    amount=Decimal("700"),
                ),
                StockEntryItem(
                    stock_entry_id=adjustment.id,
                    item_code=item_code,
                    source_warehouse=warehouse_code,
                    target_warehouse=warehouse_code,
                    qty=Decimal("0"),
                    qty_in_base_uom=Decimal("0"),
                    uom="UND",
                    basic_rate=Decimal("0"),
                    amount=Decimal("10"),
                ),
            ]
        )
        database.session.commit()
        _post_stock_entry(app, adjustment)

        movements = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=adjustment.id)).scalars().all()
        )
        actual_movements = sorted((movement.qty_change, movement.stock_value_difference) for movement in movements)
        assert actual_movements == [
            (Decimal("-1.000000000"), Decimal("-700.0000")),
            (Decimal("0E-9"), Decimal("-350.0000")),
        ]
        _assert_refreshed_amount_only_line(adjustment.id, adjustment)
        _assert_book_stock_matches_gl(adjustment.id, inventory_account_id, [movement.id for movement in movements])
