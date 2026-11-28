# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2342: conciliación real de inventario bajo controles internos Cloud.

La regresión publica una conciliación con diferencia usando el posting real
(sin sustituir ``post_document_to_gl``), verifica snapshots, Stock Ledger,
valuación y GL, y comprueba que las líneas quedan bloqueadas. También cubre
un fallo de posting con rollback y reintento.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import PostingError, submit_document
from cacao_accounting.database import (
    Accounts,
    GLEntry,
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


@pytest.fixture
def entorno_cloud(entorno_contable_aislado):
    """Entorno aislado con controles internos Cloud activos y cuentas de stock."""
    app = entorno_contable_aislado.app
    app.config["MODO_ESCRITORIO"] = False
    app.config["INTERNAL_CONTROLS_ENFORCE"] = True
    with app.app_context():
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
                is_active=True,
            )
        )
        database.session.commit()
        yield entorno_contable_aislado, inventario.id, ajuste.id


def _seed_stock() -> None:
    """Deja 10 unidades a costo 10 en la bodega central y su capa FIFO."""
    database.session.add(
        StockBin(
            company="cacao",
            item_code="ART01",
            warehouse="BOD01",
            actual_qty=Decimal("10"),
            reserved_qty=Decimal("0"),
            valuation_rate=Decimal("10"),
            stock_value=Decimal("100"),
        )
    )
    database.session.add(
        StockValuationLayer(
            company="cacao",
            item_code="ART01",
            warehouse="BOD01",
            qty=Decimal("10"),
            rate=Decimal("10"),
            remaining_qty=Decimal("10"),
            remaining_stock_value=Decimal("100"),
            voucher_type="stock_entry",
            voucher_id="SEED-2342",
            posting_date=FECHA,
        )
    )
    database.session.commit()


def _reconciliation(adjustment_account_id: str, target_value: str = "80") -> tuple[str, str]:
    """Crea un borrador de conciliación con diferencia de cantidad real."""
    entry = StockEntry(
        company="cacao",
        purpose="stock_reconciliation",
        posting_date=FECHA,
        document_no="REC-2342",
        from_warehouse="BOD01",
        to_warehouse="BOD01",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        adjustment_account_id=adjustment_account_id,
        docstatus=0,
    )
    database.session.add(entry)
    database.session.flush()
    line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ART01",
        qty=Decimal("2"),
        uom="UND",
        qty_in_base_uom=Decimal("2"),
        counted_qty=Decimal("8"),
        target_valuation_rate=Decimal("10"),
        target_stock_value=Decimal(target_value),
        target_warehouse="BOD01",
    )
    database.session.add(line)
    database.session.commit()
    return str(entry.id), str(line.id)


def _submit(entry_id: str) -> None:
    """Ejecuta el servicio real de posting con actor y aprobación."""
    entry = database.session.get(StockEntry, entry_id)
    actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    with audit_actor(actor.id, actor.name), approved_execution(entry, actor.id):
        submit_document(entry)
    database.session.commit()


def test_conciliacion_real_bajo_controles_cloud(entorno_cloud):
    """La diferencia se refleja en snapshot, bin, SLE y GL, y bloquea la línea."""
    entorno, inventario_id, ajuste_id = entorno_cloud
    app = entorno.app
    with app.app_context():
        _seed_stock()
        entry_id, line_id = _reconciliation(ajuste_id)

        _submit(entry_id)

        database.session.expire_all()
        entry = database.session.get(StockEntry, entry_id)
        line = database.session.get(StockEntryItem, line_id)
        assert entry.docstatus == 1
        assert line.current_qty == Decimal("10")
        assert line.counted_qty == Decimal("8")
        assert line.qty_difference == Decimal("-2")
        assert line.qty == Decimal("2")
        assert line.current_stock_value == Decimal("100")
        assert line.target_stock_value == Decimal("80")
        assert line.stock_value_difference == Decimal("-20")

        bin_actual = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ART01", warehouse="BOD01")
        ).scalar_one()
        assert bin_actual.actual_qty == Decimal("8")
        assert bin_actual.stock_value == Decimal("80")

        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id)).scalars().all()
        )
        assert len(movimientos) == 1
        assert movimientos[0].qty_change == Decimal("-2")
        assert movimientos[0].qty_after_transaction == Decimal("8")
        assert movimientos[0].stock_value_difference == Decimal("-20")

        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars().all()
        assert asientos
        por_libro: dict[str, tuple[Decimal, Decimal]] = {}
        for row in asientos:
            debit, credit = por_libro.get(row.ledger_id, (Decimal("0"), Decimal("0")))
            por_libro[row.ledger_id] = (debit + Decimal(row.debit), credit + Decimal(row.credit))
        assert len(por_libro) >= 2
        assert all(debit == Decimal("20") and credit == Decimal("20") for debit, credit in por_libro.values())
        assert sum((Decimal(row.credit) for row in asientos if row.account_id == inventario_id), Decimal("0")) == (
            Decimal("20") * len(por_libro)
        )
        assert sum((Decimal(row.debit) for row in asientos if row.account_id == ajuste_id), Decimal("0")) == (
            Decimal("20") * len(por_libro)
        )

        line.counted_qty = Decimal("9")
        with pytest.raises(ValueError, match="inmutables"):
            database.session.flush()
        database.session.rollback()


def test_fallo_de_posting_revierte_y_permite_reintentar(entorno_cloud):
    """Un objetivo incoherente no deja evidencia y el mismo borrador se corrige."""
    entorno, _inventario_id, ajuste_id = entorno_cloud
    app = entorno.app
    with app.app_context():
        _seed_stock()
        entry_id, line_id = _reconciliation(ajuste_id, target_value="90")

        with pytest.raises(PostingError, match="no coincide"):
            _submit(entry_id)
        database.session.rollback()

        database.session.expire_all()
        entry = database.session.get(StockEntry, entry_id)
        line = database.session.get(StockEntryItem, line_id)
        assert entry.docstatus == 0
        assert database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id)).scalars().all() == []
        assert database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars().all() == []
        bin_actual = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ART01", warehouse="BOD01")
        ).scalar_one()
        assert bin_actual.actual_qty == Decimal("10")

        line.target_stock_value = Decimal("80")
        database.session.commit()
        _submit(entry_id)

        database.session.expire_all()
        entry = database.session.get(StockEntry, entry_id)
        bin_actual = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ART01", warehouse="BOD01")
        ).scalar_one()
        assert entry.docstatus == 1
        assert bin_actual.actual_qty == Decimal("8")
        assert (
            len(database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id)).scalars().all())
            == 1
        )
        assert database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry_id)).scalars().all()
