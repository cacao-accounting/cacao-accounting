# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión para consumo de inventario cuyo comprobante ya fue anulado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask_login import login_user

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.cancellation_service import (
    _stock_consumption_is_active,
    active_cancellation_dependencies,
)
from cacao_accounting.contabilidad.posting_service import cancel_document, post_stock_entry
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    Entity,
    Item,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor


def _post_adjustment(app, item_code: str, warehouse_code: str, movement: tuple[str, str, str]) -> StockEntry:
    """Persist and post one stock adjustment against the test inventory bin."""
    purpose, qty, amount = movement
    document = StockEntry(
        purpose=purpose,
        company="cacao",
        posting_date=date(2026, 5, 20),
        to_warehouse=warehouse_code,
        from_warehouse=warehouse_code,
        document_no=f"{purpose}-{uuid4().hex[:8]}",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
    )
    database.session.add(document)
    database.session.flush()
    quantity = Decimal(qty)
    database.session.add(
        StockEntryItem(
            stock_entry_id=document.id,
            item_code=item_code,
            source_warehouse=warehouse_code,
            target_warehouse=warehouse_code,
            qty=quantity,
            uom="UND",
            qty_in_base_uom=quantity,
            basic_rate=Decimal("10"),
            amount=Decimal(amount),
        )
    )
    database.session.commit()
    with app.test_request_context(f"/inventory/stock-entry/{document.id}"):
        login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
        post_stock_entry(document)
    database.session.commit()
    return document


def _prepare_inventory_accounts(item_code: str, warehouse_code: str) -> None:
    """Create the item, warehouse, and adjustment accounts needed by the postings."""
    database.session.add(
        Item(code=item_code, name="Artículo de cancelación", item_type="goods", is_stock_item=True, default_uom="UND")
    )
    database.session.add(Warehouse(code=warehouse_code, name="Bodega de cancelación", company="cacao"))
    database.session.flush()
    entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
    entity.valuation_method = "fifo"
    inventory_account = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
    adjustment_account = database.session.execute(
        database.select(Accounts).filter_by(entity="cacao", code="5201")
    ).scalar_one()
    for account in (inventory_account, adjustment_account):
        account.active = True
        account.enabled = True
        account.group = False
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    defaults.inventory_adjustment_account_id = adjustment_account.id
    database.session.add(
        WarehouseCompanyAccount(
            warehouse_code=warehouse_code,
            company="cacao",
            inventory_account_id=inventory_account.id,
        )
    )
    database.session.commit()


def test_cancelar_origen_permite_consumo_cuyo_voucher_ya_fue_anulado(entorno_contable_aislado) -> None:
    """El consumo aprobado bloquea; tras su anulación, el origen puede anularse."""
    app = entorno_contable_aislado.app
    item_code = f"CANCEL-{uuid4().hex[:8].upper()}"
    warehouse_code = f"CANW-{uuid4().hex[:8].upper()}"
    with app.app_context():
        _prepare_inventory_accounts(item_code, warehouse_code)

        source = _post_adjustment(app, item_code, warehouse_code, ("adjustment_positive", "5", "50"))
        consumer = _post_adjustment(app, item_code, warehouse_code, ("adjustment_negative", "2", "20"))
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        dependencies = active_cancellation_dependencies(source, "stock_entry", source.id)
        assert [(dependency.kind, dependency.identifier) for dependency in dependencies] == [
            ("consumo de inventario", consumer.id)
        ]

        with audit_actor(actor.id, actor.name), approved_execution(consumer, actor.id):
            cancel_document(
                consumer,
                reason="Anular consumo",
                actor_user_id=actor.id,
                cancellation_date=consumer.posting_date,
            )
        database.session.commit()

        consumer_layers = (
            database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=consumer.id)).scalars().all()
        )
        assert sum((layer.qty for layer in consumer_layers), Decimal("0")) == Decimal("0")
        assert database.session.get(StockEntry, consumer.id).docstatus == 2

        with audit_actor(actor.id, actor.name), approved_execution(source, actor.id):
            cancel_document(
                source,
                reason="Anular origen tras anular consumo",
                actor_user_id=actor.id,
                cancellation_date=source.posting_date,
            )
        database.session.commit()

        assert database.session.get(StockEntry, source.id).docstatus == 2
        assert database.session.get(StockEntry, consumer.id).docstatus == 2
        source_layers = (
            database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=source.id)).scalars().all()
        )
        assert sum((layer.qty for layer in source_layers), Decimal("0")) == Decimal("0")
        source_movements = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=source.id)).scalars().all()
        )
        assert len(source_movements) == 2
        assert sum((movement.qty_change for movement in source_movements), Decimal("0")) == Decimal("0")


def test_consumer_sin_tipo_o_documento_resoluble_bloquea_por_seguridad(entorno_contable_aislado) -> None:
    """No se libera evidencia de consumo si su documento de origen es desconocido o falta."""
    with entorno_contable_aislado.app.app_context():
        assert _stock_consumption_is_active("unknown_voucher", "missing-consumer") is True
        assert _stock_consumption_is_active("stock_entry", "missing-consumer") is True
