# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2290: la conciliación no descuenta stock sin costo funcional.

La guarda de #2259 cubría salidas y transferencias. La reducción por
conciliación usaba un respaldo ``target_value / counted_qty`` que podía ser
cero cuando el bin tenía cantidad pero ningún valor ni capas consumibles,
dejando Stock Ledger y GL desalineados. Ahora se rechaza de forma atómica,
igual que en las salidas, sin bloquear el respaldo con capas parciales
valoradas.
"""

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
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    User,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 15)
ITEM_CODE = "ART01"
WAREHOUSE = "BOD01"


@pytest.fixture
def entorno_conciliacion(entorno_contable_aislado):
    """Habilita stock negativo y las cuentas de inventario y ajuste."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code=ITEM_CODE)).scalar_one()
        item.allow_negative_stock = True
        inventario = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        ajuste = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        for cuenta in (inventario, ajuste):
            cuenta.active = True
            cuenta.enabled = True
            cuenta.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=WAREHOUSE,
                company="cacao",
                inventory_account_id=inventario.id,
                is_active=True,
            )
        )
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.inventory_adjustment_account_id = ajuste.id
        database.session.commit()
        yield app, inventario.id, ajuste.id


def _seed_bin(app, *, qty: str, value: str, rate: str = "0") -> None:
    """Deja el bin con la cantidad y el valor indicados, sin capas."""
    with app.app_context():
        database.session.add(
            StockBin(
                company="cacao",
                item_code=ITEM_CODE,
                warehouse=WAREHOUSE,
                actual_qty=Decimal(qty),
                reserved_qty=Decimal("0"),
                valuation_rate=Decimal(rate),
                stock_value=Decimal(value),
            )
        )
        database.session.commit()


def _seed_partial_layer(app, *, qty: str, rate: str) -> None:
    """Agrega una capa valorada parcial, como evidencia histórica incompleta."""
    with app.app_context():
        database.session.add(
            StockValuationLayer(
                company="cacao",
                item_code=ITEM_CODE,
                warehouse=WAREHOUSE,
                qty=Decimal(qty),
                rate=Decimal(rate),
                stock_value_difference=Decimal(qty) * Decimal(rate),
                remaining_qty=Decimal(qty),
                remaining_stock_value=Decimal(qty) * Decimal(rate),
                voucher_type="stock_entry",
                voucher_id="SEED-2290-PARCIAL",
                posting_date=FECHA,
            )
        )
        database.session.commit()


def _reconciliation(app, *, counted_qty: str, target_rate: str, adjustment_account_id: str) -> str:
    """Crea un borrador de conciliación reductora contra la bodega central."""
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="stock_reconciliation",
            posting_date=FECHA,
            document_no="REC-2290",
            from_warehouse=WAREHOUSE,
            to_warehouse=WAREHOUSE,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            adjustment_account_id=adjustment_account_id,
            docstatus=0,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=ITEM_CODE,
                qty=Decimal("1"),
                uom="UND",
                qty_in_base_uom=Decimal("1"),
                counted_qty=Decimal(counted_qty),
                target_valuation_rate=Decimal(target_rate),
                target_stock_value=Decimal(counted_qty) * Decimal(target_rate),
                target_warehouse=WAREHOUSE,
            )
        )
        database.session.commit()
        return str(entry.id)


def _submit(app, entry_id: str) -> None:
    """Ejecuta el posting real con actor y aprobación."""
    with app.app_context():
        entry = database.session.get(StockEntry, entry_id)
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name), approved_execution(entry, actor.id):
            submit_document(entry)
        database.session.commit()


def _bin_snapshot(app) -> tuple[Decimal, Decimal]:
    """Devuelve cantidad y valor actuales del bin."""
    with app.app_context():
        database.session.expire_all()
        row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=ITEM_CODE, warehouse=WAREHOUSE)
        ).scalar_one()
        return Decimal(row.actual_qty), Decimal(row.stock_value)


def test_reduccion_sin_capas_ni_valor_rechaza_sin_cambios_parciales(entorno_conciliacion):
    """Un bin positivo en cero sin capas no puede reducirse a costo cero."""
    app, _inventario_id, ajuste_id = entorno_conciliacion
    _seed_bin(app, qty="10", value="0")
    entry_id = _reconciliation(app, counted_qty="4", target_rate="0", adjustment_account_id=ajuste_id)

    with pytest.raises(PostingError, match="valor funcional mayor que cero"):
        _submit(app, entry_id)
    with app.app_context():
        database.session.rollback()

    assert _bin_snapshot(app) == (Decimal("10"), Decimal("0"))
    with app.app_context():
        database.session.expire_all()
        entry = database.session.get(StockEntry, entry_id)
        assert entry.docstatus == 0
        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id)).scalars().all()
        )
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars().all()
        capas = database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=entry_id)).scalars().all()
        assert movimientos == []
        assert asientos == []
        assert capas == []


def test_reduccion_con_capas_parciales_valoradas_conserva_gl(entorno_conciliacion):
    """El respaldo con capas parciales positivas sigue conciliando cantidad y valor."""
    app, inventario_id, ajuste_id = entorno_conciliacion
    _seed_bin(app, qty="10", value="100", rate="10")
    _seed_partial_layer(app, qty="2", rate="10")
    entry_id = _reconciliation(app, counted_qty="4", target_rate="10", adjustment_account_id=ajuste_id)

    _submit(app, entry_id)

    assert _bin_snapshot(app) == (Decimal("4"), Decimal("40"))
    with app.app_context():
        database.session.expire_all()
        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id)).scalars().all()
        )
        assert len(movimientos) == 1
        assert movimientos[0].qty_change == Decimal("-6")
        assert movimientos[0].stock_value_difference == Decimal("-60")
        assert movimientos[0].qty_after_transaction == Decimal("4")

        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars().all()
        assert asientos
        libros = {row.ledger_id for row in asientos}
        assert len(libros) >= 2
        credito_inventario = sum((Decimal(row.credit) for row in asientos if row.account_id == inventario_id), Decimal("0"))
        debito_ajuste = sum((Decimal(row.debit) for row in asientos if row.account_id == ajuste_id), Decimal("0"))
        assert credito_inventario == Decimal("60") * len(libros)
        assert debito_ajuste == Decimal("60") * len(libros)
