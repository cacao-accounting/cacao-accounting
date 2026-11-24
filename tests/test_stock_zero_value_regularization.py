# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1873: valor sin existencias y regularización de residuos de inventario."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting.contabilidad.posting_service import PostingError, post_stock_entry
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    Entity,
    GLEntry,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)

FECHA = date(2026, 5, 15)


def _escenario(app, *, qty: str, stock_value: str, layer_value: str) -> tuple[str, str]:
    """Crea item, bodega, cuenta de inventario y bin con la valoración indicada."""
    sufijo = uuid4().hex[:6]
    codigo_item = f"R{sufijo}"
    codigo_bodega = f"RW{sufijo}"
    with app.app_context():
        database.session.add(
            Item(code=codigo_item, name="Artículo residuo", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code=codigo_bodega, name="Bodega residuo", company="cacao", is_active=True))
        database.session.flush()
        inventario = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        ajuste = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        for cuenta in (inventario, ajuste):
            cuenta.active = True
            cuenta.enabled = True
            cuenta.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=codigo_bodega,
                company="cacao",
                inventory_account_id=inventario.id,
            )
        )
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.inventory_adjustment_account_id = ajuste.id
        database.session.add(
            StockBin(
                company="cacao",
                item_code=codigo_item,
                warehouse=codigo_bodega,
                actual_qty=Decimal(qty),
                stock_value=Decimal(stock_value),
                valuation_rate=Decimal(stock_value) / Decimal(qty) if Decimal(qty) else Decimal("0"),
            )
        )
        if Decimal(layer_value) != 0:
            database.session.add(
                StockValuationLayer(
                    item_code=codigo_item,
                    warehouse=codigo_bodega,
                    company="cacao",
                    qty=Decimal(qty),
                    rate=Decimal(layer_value) / Decimal(qty) if Decimal(qty) else Decimal("0"),
                    stock_value_difference=Decimal(layer_value),
                    remaining_qty=Decimal(qty),
                    remaining_stock_value=Decimal(layer_value),
                    voucher_type="seed",
                    voucher_id=f"seed-{sufijo}",
                    posting_date=FECHA,
                )
            )
        database.session.commit()
    return codigo_item, codigo_bodega


def _entrada(codigo_item: str, codigo_bodega: str, purpose: str, qty: str, amount: str) -> StockEntry:
    """Crea un StockEntry aprobado con una línea."""
    entrada = StockEntry(
        purpose=purpose,
        company="cacao",
        posting_date=FECHA,
        to_warehouse=codigo_bodega,
        from_warehouse=codigo_bodega,
        document_no=f"REG-{uuid4().hex[:8]}",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
    )
    database.session.add(entrada)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entrada.id,
            item_code=codigo_item,
            source_warehouse=codigo_bodega,
            target_warehouse=codigo_bodega,
            qty=Decimal(qty),
            uom="UND",
            qty_in_base_uom=Decimal(qty),
            basic_rate=Decimal("10"),
            amount=Decimal(amount),
        )
    )
    database.session.commit()
    return entrada


def _postear(app, entrada: StockEntry) -> None:
    with app.test_request_context(f"/inventory/stock-entry/{entrada.id}"):
        login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
        post_stock_entry(entrada)


def test_ajuste_de_solo_valor_sin_stock_se_rechaza(entorno_contable_aislado):
    app = entorno_contable_aislado.app
    """No se puede crear valor en una bodega sin existencias."""
    codigo_item, codigo_bodega = _escenario(app, qty="0", stock_value="0", layer_value="0")
    with app.app_context():
        entrada = _entrada(codigo_item, codigo_bodega, "adjustment_positive", "0", "50")
        with pytest.raises(PostingError, match="sin existencias positivas"):
            _postear(app, entrada)
        database.session.rollback()
        assert database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada.id)).scalars().all() == []


def test_ajuste_de_solo_valor_con_stock_actualiza_bin_y_gl(entorno_contable_aislado):
    app = entorno_contable_aislado.app
    """El ajuste de solo valor es válido cuando hay existencias."""
    codigo_item, codigo_bodega = _escenario(app, qty="10", stock_value="100", layer_value="100")
    with app.app_context():
        entrada = _entrada(codigo_item, codigo_bodega, "adjustment_positive", "0", "20")
        _postear(app, entrada)
        database.session.commit()
        bin_actual = database.session.execute(
            database.select(StockBin).filter_by(item_code=codigo_item, warehouse=codigo_bodega)
        ).scalar_one()
        assert bin_actual.actual_qty == Decimal("10")
        assert bin_actual.stock_value == Decimal("120")
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada.id)).scalars().all()
        assert sum((a.debit for a in asientos), Decimal("0")) == sum((a.credit for a in asientos), Decimal("0"))


def test_agotamiento_con_residuo_regulariza_bin_sle_svl_y_gl(entorno_contable_aislado):
    """Al llegar a cero, el residuo se compensa en todos los ledgers."""
    app = entorno_contable_aislado.app
    with app.app_context():
        entidad = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        entidad.valuation_method = "fifo"
        database.session.commit()
    codigo_item, codigo_bodega = _escenario(app, qty="1", stock_value="10.0001", layer_value="10.0000")
    with app.app_context():
        entrada = _entrada(codigo_item, codigo_bodega, "adjustment_negative", "1", "10")
        _postear(app, entrada)
        database.session.commit()

        bin_final = database.session.execute(
            database.select(StockBin).filter_by(item_code=codigo_item, warehouse=codigo_bodega)
        ).scalar_one()
        assert bin_final.actual_qty == Decimal("0")
        assert bin_final.stock_value == Decimal("0")

        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entrada.id)).scalars().all()
        )
        assert len(movimientos) == 2
        residuo = [movimiento for movimiento in movimientos if movimiento.qty_change == 0]
        assert len(residuo) == 1
        assert residuo[0].stock_value_difference == Decimal("-0.0001")
        assert residuo[0].stock_value == Decimal("0")

        capas_residuo = (
            database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=entrada.id, qty=Decimal("0")))
            .scalars()
            .all()
        )
        assert len(capas_residuo) == 1
        assert capas_residuo[0].stock_value_difference == Decimal("-0.0001")
        assert capas_residuo[0].remaining_stock_value == Decimal("0")

        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada.id)).scalars().all()
        por_libro: dict[str, list[Decimal]] = {}
        for asiento in asientos:
            por_libro.setdefault(asiento.ledger_id, [Decimal("0"), Decimal("0")])
            por_libro[asiento.ledger_id][0] += asiento.debit
            por_libro[asiento.ledger_id][1] += asiento.credit
        assert len(por_libro) == 2
        for ledger, (debito, credito) in por_libro.items():
            assert debito == credito
            inventario_credito = sum(
                (asiento.credit for asiento in asientos if asiento.ledger_id == ledger and asiento.account_code == "1109"),
                Decimal("0"),
            )
            assert inventario_credito == Decimal("10.0001")


def test_agotamiento_exacto_no_genera_residuo(entorno_contable_aislado):
    app = entorno_contable_aislado.app
    """Sin diferencia de valor no se crea una regularización extra."""
    codigo_item, codigo_bodega = _escenario(app, qty="1", stock_value="10", layer_value="10")
    with app.app_context():
        entrada = _entrada(codigo_item, codigo_bodega, "adjustment_negative", "1", "10")
        _postear(app, entrada)
        database.session.commit()
        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entrada.id)).scalars().all()
        )
        assert len(movimientos) == 1
        assert movimientos[0].qty_change == Decimal("-1")
        assert (
            database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=entrada.id, qty=Decimal("0")))
            .scalars()
            .all()
            == []
        )
