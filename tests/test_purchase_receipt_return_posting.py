# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#759: una devolución física posteada conserva la valoración original.

La recepción original deja una capa histórica. La devolución aprobada debe
agregar capas compensatorias y movimientos de Stock Ledger/GL sin reescribir
la capa original ni su valoración por libro.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import post_purchase_receipt
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyDefaultAccount,
    GLEntry,
    Item,
    Party,
    PurchaseReceipt,
    PurchaseReceiptItem,
    StockLedgerBookEntry,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

ITEM_CODE = "ART01"
WAREHOUSE_CODE = "BOD01"
UOM_CODE = "UND"
SUPPLIER_CODE = "PRV001"


def _seed_bridge_and_warehouse_account(entorno) -> None:
    """Ensure the purchase bridge and warehouse inventory accounts are mapped."""
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    bridge_account = database.session.execute(
        database.select(Accounts).filter_by(entity="cacao", code="2103")
    ).scalar_one_or_none()
    if bridge_account is None:
        bridge_account = Accounts(
            entity="cacao",
            code="2103",
            name="Puente de compras",
            classification="liability",
            account_type="bridge",
        )
        database.session.add(bridge_account)
        database.session.flush()
    inventory_account = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
    defaults.bridge_account_id = bridge_account.id
    mapping = database.session.execute(
        database.select(WarehouseCompanyAccount).filter_by(warehouse_code=WAREHOUSE_CODE, company="cacao")
    ).scalar_one_or_none()
    if mapping is None:
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=WAREHOUSE_CODE,
                company="cacao",
                inventory_account_id=inventory_account.id,
            )
        )
    else:
        mapping.inventory_account_id = inventory_account.id
    database.session.commit()


def _receipt(*, is_return: bool, reversal_of: str | None, qty: str, amount: str) -> PurchaseReceipt:
    """Persist one approved purchase receipt or physical return."""
    supplier = database.session.execute(database.select(Party).filter_by(code=SUPPLIER_CODE)).scalar_one()
    item = database.session.execute(database.select(Item).filter_by(code=ITEM_CODE)).scalar_one()
    uom = database.session.execute(database.select(UOM).filter_by(code=UOM_CODE)).scalar_one()
    warehouse = database.session.execute(
        database.select(Warehouse).filter_by(code=WAREHOUSE_CODE, company="cacao")
    ).scalar_one()
    suffix = uuid4().hex[:8]
    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 10) if not is_return else date(2026, 5, 20),
        docstatus=1,
        document_no=f"{'PRT' if is_return else 'PRC'}-{suffix}",
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        is_return=is_return,
        reversal_of=reversal_of,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        total=Decimal(amount),
        base_total=Decimal(amount),
        grand_total=Decimal(amount),
    )
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal(qty),
            qty_in_base_uom=Decimal(qty),
            uom=uom.code,
            rate=Decimal("10"),
            amount=Decimal(amount),
            base_amount=Decimal(amount),
            warehouse=warehouse.code,
        )
    )
    database.session.commit()
    return receipt


def _post(receipt: PurchaseReceipt, actor: User) -> None:
    """Post a receipt or return through the authorized service scope."""
    with audit_actor(actor.id, actor.name), approved_execution(receipt, actor.id):
        post_purchase_receipt(receipt)
    database.session.commit()


def _layer_snapshot(layer: StockValuationLayer) -> dict[str, object]:
    """Capture the historical layer values that must remain unchanged."""
    return {
        "qty": layer.qty,
        "rate": layer.rate,
        "stock_value_difference": layer.stock_value_difference,
        "remaining_qty": layer.remaining_qty,
        "remaining_stock_value": layer.remaining_stock_value,
        "source_layer_id": layer.source_layer_id,
        "voucher_id": layer.voucher_id,
    }


def test_posted_purchase_return_preserves_layer_and_reconciles_ledgers(entorno_contable_aislado):
    """A posted physical return adds compensating evidence and keeps history intact."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _seed_bridge_and_warehouse_account(entorno_contable_aislado)
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        original = _receipt(is_return=False, reversal_of=None, qty="10", amount="100")
        _post(original, actor)

        original_layer = database.session.execute(
            database.select(StockValuationLayer).filter_by(voucher_type="purchase_receipt", voucher_id=original.id, qty=10)
        ).scalar_one()
        original_layer_values = _layer_snapshot(original_layer)
        original_movement = database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="purchase_receipt", voucher_id=original.id)
        ).scalar_one()
        original_movement_values = {
            "qty_change": original_movement.qty_change,
            "qty_after_transaction": original_movement.qty_after_transaction,
            "valuation_rate": original_movement.valuation_rate,
            "stock_value_difference": original_movement.stock_value_difference,
            "stock_value": original_movement.stock_value,
            "is_cancelled": original_movement.is_cancelled,
            "voucher_id": original_movement.voucher_id,
        }
        original_book_values = (
            database.session.execute(
                database.select(StockLedgerBookEntry).filter_by(stock_ledger_entry_id=original_movement.id)
            )
            .scalars()
            .all()
        )
        original_book_snapshots = {
            row.id: {
                "book_amount": row.book_amount,
                "exchange_rate": row.exchange_rate,
                "ledger_id": row.ledger_id,
            }
            for row in original_book_values
        }
        original_gl = database.session.execute(database.select(GLEntry).filter_by(voucher_id=original.id)).scalars().all()
        assert original_gl
        assert sum(entry.debit for entry in original_gl) == sum(entry.credit for entry in original_gl)
        original_gl_snapshots = {
            entry.id: {
                "account_id": entry.account_id,
                "ledger_id": entry.ledger_id,
                "debit": entry.debit,
                "credit": entry.credit,
            }
            for entry in original_gl
        }

        returned = _receipt(
            is_return=True,
            reversal_of=original.id,
            qty="4",
            amount="40",
        )
        _post(returned, actor)

        database.session.expire_all()
        preserved_layer = database.session.get(StockValuationLayer, original_layer.id)
        assert preserved_layer is not None
        assert _layer_snapshot(preserved_layer) == original_layer_values

        return_layers = (
            database.session.execute(
                database.select(StockValuationLayer).filter_by(voucher_type="purchase_receipt", voucher_id=returned.id)
            )
            .scalars()
            .all()
        )
        assert len(return_layers) == 1
        return_layer = return_layers[0]
        assert return_layer.qty == Decimal("-4")
        assert return_layer.rate == Decimal("10")
        assert return_layer.stock_value_difference == Decimal("-40")
        assert return_layer.source_layer_id == original_layer.id

        return_movement = database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="purchase_receipt", voucher_id=returned.id)
        ).scalar_one()
        assert return_movement.qty_change == Decimal("-4")
        assert return_movement.stock_value_difference == Decimal("-40")

        original_movement_after = database.session.get(StockLedgerEntry, original_movement.id)
        assert original_movement_after is not None
        assert {
            "qty_change": original_movement_after.qty_change,
            "qty_after_transaction": original_movement_after.qty_after_transaction,
            "valuation_rate": original_movement_after.valuation_rate,
            "stock_value_difference": original_movement_after.stock_value_difference,
            "stock_value": original_movement_after.stock_value,
            "is_cancelled": original_movement_after.is_cancelled,
            "voucher_id": original_movement_after.voucher_id,
        } == original_movement_values

        for row_id, snapshot in original_book_snapshots.items():
            row = database.session.get(StockLedgerBookEntry, row_id)
            assert row is not None
            assert row.book_amount == snapshot["book_amount"]
            assert row.exchange_rate == snapshot["exchange_rate"]
            assert row.ledger_id == snapshot["ledger_id"]

        for entry_id, snapshot in original_gl_snapshots.items():
            entry = database.session.get(GLEntry, entry_id)
            assert entry is not None
            assert entry.account_id == snapshot["account_id"]
            assert entry.ledger_id == snapshot["ledger_id"]
            assert entry.debit == snapshot["debit"]
            assert entry.credit == snapshot["credit"]

        active_books = (
            database.session.execute(database.select(Book).filter_by(entity="cacao", status="activo")).scalars().all()
        )
        assert len(active_books) >= 2
        active_ledger_ids = {book.id for book in active_books}

        return_book_entries = (
            database.session.execute(database.select(StockLedgerBookEntry).filter_by(stock_ledger_entry_id=return_movement.id))
            .scalars()
            .all()
        )
        assert len(return_book_entries) == len(active_books)
        assert {row.ledger_id for row in return_book_entries} == active_ledger_ids
        assert {row.book_amount for row in return_book_entries} == {Decimal("-40")}

        return_gl = database.session.execute(database.select(GLEntry).filter_by(voucher_id=returned.id)).scalars().all()
        assert return_gl
        by_book: dict[str, tuple[Decimal, Decimal]] = {}
        for entry in return_gl:
            debit, credit = by_book.get(entry.ledger_id, (Decimal("0"), Decimal("0")))
            by_book[entry.ledger_id] = (debit + Decimal(entry.debit), credit + Decimal(entry.credit))
        assert set(by_book) == active_ledger_ids
        assert all(debit == credit == Decimal("40") for debit, credit in by_book.values())

        assert sum(layer.qty for layer in (preserved_layer, return_layer)) == Decimal("6")
        assert sum(layer.stock_value_difference for layer in (preserved_layer, return_layer)) == Decimal("60")
