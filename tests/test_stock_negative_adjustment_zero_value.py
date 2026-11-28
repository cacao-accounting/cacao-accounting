# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2259: un ajuste negativo sin valoración no deja stock sin efecto contable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import PostingError, submit_document
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    GLEntry,
    Item,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor


def test_ajuste_negativo_sin_valoracion_no_genera_stock_sin_gl(entorno_contable_aislado) -> None:
    """Sin capas ni tasa de respaldo, el consumo a costo cero se rechaza antes de persistir."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        item.allow_negative_stock = True
        inventario = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        ajuste = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        for cuenta in (inventario, ajuste):
            cuenta.active = True
            cuenta.enabled = True
            cuenta.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code="BOD01",
                company="cacao",
                inventory_account_id=inventario.id,
            )
        )
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.inventory_adjustment_account_id = ajuste.id

        entrada = StockEntry(
            purpose="adjustment_negative",
            company="cacao",
            posting_date=date(2026, 5, 20),
            from_warehouse="BOD01",
            to_warehouse="BOD01",
            document_no="ADJNEG-CERO",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(entrada)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entrada.id,
                item_code=item.code,
                source_warehouse="BOD01",
                target_warehouse="BOD01",
                qty=Decimal("2"),
                uom="UND",
                qty_in_base_uom=Decimal("2"),
                basic_rate=Decimal("0"),
                amount=Decimal("0"),
            )
        )
        database.session.commit()
        entrada_id = entrada.id
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        with pytest.raises(PostingError, match="valor funcional mayor que cero"):
            with audit_actor(actor.id, actor.name), approved_execution(entrada, actor.id):
                submit_document(entrada)
        database.session.rollback()

        database.session.expire_all()
        recargada = database.session.get(StockEntry, entrada_id)
        assert recargada is not None
        assert recargada.docstatus == 0
        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entrada_id)).scalars().all()
        )
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada_id)).scalars().all()
        assert movimientos == []
        assert asientos == []
        assert database.session.execute(database.select(Warehouse).filter_by(code="BOD01")).scalar_one() is not None
