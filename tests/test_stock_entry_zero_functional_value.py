# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1891: una entrada de stock no puede tener valor funcional cero."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _movement_inflow_receipt,
    submit_document,
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
from cacao_accounting.internal_control_service import audit_actor


def test_recepcion_con_valor_funcional_cero_se_rechaza(app, entorno_contable):
    """100 unidades de 0.0001 USD con tasa 0.1 redondean a cero y se rechazan."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        uom = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
        database.session.add(uom)
        database.session.commit()
        item = Item(
            code=f"ART{sufijo}",
            name="Artículo",
            item_type="goods",
            is_stock_item=True,
            default_uom=uom.code,
        )
        warehouse = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        database.session.add_all([item, warehouse])
        database.session.flush()
        database.session.add(
            StockBin(
                company="cacao",
                item_code=item.code,
                warehouse=warehouse.code,
                actual_qty=Decimal("10"),
                stock_value=Decimal("10"),
                valuation_rate=Decimal("1"),
            )
        )
        database.session.commit()

        documento = SimpleNamespace(
            id=f"se-{sufijo}",
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("0.1"),
            purpose="adjustment_positive",
            to_warehouse=warehouse.code,
            voucher_type="stock_entry",
        )
        linea = SimpleNamespace(
            id=f"line-{sufijo}",
            item_code=item.code,
            target_warehouse=warehouse.code,
            source_warehouse=None,
            amount=Decimal("0.0001"),
            valuation_rate=Decimal("0.0001"),
            basic_rate=Decimal("0.0001"),
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            batch_id=None,
            serial_no=None,
        )

        with pytest.raises(PostingError, match="valor funcional mayor que cero"):
            _movement_inflow_receipt(documento, linea, "adjustment_positive", Decimal("1"))


def test_posting_con_valor_funcional_cero_no_deja_evidencia_parcial(app, entorno_contable):
    """El submit falla, revierte docstatus y no crea GL, SLE ni valoración."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        artefacto = f"Z{sufijo}"
        bodega_codigo = f"ZW{sufijo}"
        database.session.add(
            Item(code=artefacto, name="Artículo cero", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code=bodega_codigo, name="Bodega cero", company="cacao", is_active=True))
        database.session.flush()
        inventario = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        ajuste = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        for cuenta in (inventario, ajuste):
            cuenta.active = True
            cuenta.enabled = True
            cuenta.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=bodega_codigo,
                company="cacao",
                inventory_account_id=inventario.id,
            )
        )
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.inventory_adjustment_account_id = ajuste.id

        entrada = StockEntry(
            purpose="adjustment_positive",
            company="cacao",
            posting_date=date(2026, 5, 15),
            to_warehouse=bodega_codigo,
            from_warehouse=bodega_codigo,
            document_no=f"ZCERO-{sufijo}",
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("0.1"),
            docstatus=0,
        )
        database.session.add(entrada)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entrada.id,
                item_code=artefacto,
                source_warehouse=bodega_codigo,
                target_warehouse=bodega_codigo,
                qty=Decimal("1"),
                uom="UND",
                qty_in_base_uom=Decimal("1"),
                basic_rate=Decimal("0.0001"),
                amount=Decimal("0.0001"),
            )
        )
        database.session.commit()
        entrada_id = entrada.id
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        with pytest.raises(PostingError, match="valor funcional mayor que cero"):
            with audit_actor(actor.id, actor.name), approved_execution(entrada, actor.id):
                submit_document(entrada)
        database.session.rollback()

        recargada = database.session.get(StockEntry, entrada_id)
        assert recargada is not None
        assert recargada.docstatus == 0
        assert (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entrada_id)).scalars().all() == []
        )
        assert database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada_id)).scalars().all() == []
        assert (
            database.session.execute(
                database.select(StockLedgerBookEntry).where(
                    StockLedgerBookEntry.stock_ledger_entry_id.in_(
                        database.select(StockLedgerEntry.id).where(StockLedgerEntry.voucher_id == entrada_id)
                    )
                )
            )
            .scalars()
            .all()
            == []
        )
        bin_cero = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=artefacto, warehouse=bodega_codigo)
        ).scalar_one_or_none()
        assert bin_cero is None
