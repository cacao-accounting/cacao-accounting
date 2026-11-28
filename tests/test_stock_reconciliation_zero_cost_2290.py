# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2290: la reducción de conciliación siempre consume evidencia valorada.

La guarda de #2259/#2290 rechaza un respaldo sin valor funcional. Antes de
aceptarla como defensa, estas pruebas recorren los flujos reales de posting:
cada movimiento de cantidad crea una capa de valuación, por lo que el neto de
capas coincide con el bin y una reducción no supera la evidencia disponible.
El estado "bin positivo, sin capas valoradas" solo puede venir de evidencia
histórica inconsistente, no de los flujos actuales.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import _consume_stock_valuation_layers, submit_document
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    GLEntry,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
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
    """Configura cuentas de inventario y ajuste sobre el escenario aislado."""
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


def _movimiento(app, *, purpose: str, qty: str, rate: str, document_no: str) -> str:
    """Crea un StockEntry de recepción o salida y lo contabiliza con el flujo real."""
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose=purpose,
            posting_date=FECHA,
            document_no=document_no,
            from_warehouse=WAREHOUSE,
            to_warehouse=WAREHOUSE,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=ITEM_CODE,
                qty=Decimal(qty),
                qty_in_base_uom=Decimal(qty),
                uom="UND",
                basic_rate=Decimal(rate),
                valuation_rate=Decimal(rate),
                amount=Decimal(qty) * Decimal(rate),
                source_warehouse=WAREHOUSE,
                target_warehouse=WAREHOUSE,
            )
        )
        database.session.commit()
        _submit(app, entry.id)
        return str(entry.id)


def _conciliacion(app, *, counted_qty: str, target_rate: str, adjustment_account_id: str) -> str:
    """Crea y contabiliza una conciliación reductora contra la bodega central."""
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="stock_reconciliation",
            posting_date=FECHA,
            document_no=f"REC-2290-{counted_qty}-{target_rate}",
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
        _submit(app, entry.id)
        return str(entry.id)


def _submit(app, entry_id: str) -> None:
    """Ejecuta el posting real con actor y aprobación."""
    with app.app_context():
        entry = database.session.get(StockEntry, entry_id)
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name), approved_execution(entry, actor.id):
            submit_document(entry)
        database.session.commit()


def _evidencia(app) -> tuple[tuple[Decimal, Decimal], list[tuple[str, Decimal, Decimal, str | None]]]:
    """Devuelve el bin y las capas del artículo/bodega."""
    with app.app_context():
        database.session.expire_all()
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=ITEM_CODE, warehouse=WAREHOUSE)
        ).scalar_one()
        capas = (
            database.session.execute(
                database.select(StockValuationLayer)
                .filter_by(company="cacao", item_code=ITEM_CODE, warehouse=WAREHOUSE)
                .order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
            )
            .scalars()
            .all()
        )
        return (
            (Decimal(bin_row.actual_qty), Decimal(bin_row.stock_value)),
            [(str(capa.id), Decimal(capa.qty), Decimal(capa.stock_value_difference), capa.source_layer_id) for capa in capas],
        )


def _cuadra(bin_row: tuple[Decimal, Decimal], capas: list[tuple[str, Decimal, Decimal, str | None]]) -> None:
    """El neto de capas debe reproducir cantidad y valor del bin."""
    qty = sum((capa[1] for capa in capas), Decimal("0"))
    valor = sum((capa[2] for capa in capas), Decimal("0"))
    assert bin_row == (qty, valor)


def test_stock_valorado_cuadra_y_la_reduccion_consume_capas(entorno_conciliacion):
    """Recepción, salida y conciliación dejan capas que cubren toda reducción."""
    app, _inventario_id, ajuste_id = entorno_conciliacion
    _movimiento(app, purpose="material_receipt", qty="10", rate="10", document_no="REC-2290-VAL")
    _movimiento(app, purpose="material_issue", qty="4", rate="10", document_no="ISS-2290-VAL")

    entrada_id = _conciliacion(app, counted_qty="4", target_rate="10", adjustment_account_id=ajuste_id)

    bin_row, capas = _evidencia(app)
    assert bin_row == (Decimal("4"), Decimal("40"))
    _cuadra(bin_row, capas)
    with app.app_context():
        cost, rate, _source, _composicion = _consume_stock_valuation_layers(
            company="cacao", item_code=ITEM_CODE, warehouse=WAREHOUSE, quantity=Decimal("4")
        )
        assert cost == Decimal("40")
        assert rate == Decimal("10")
    with app.app_context():
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada_id)).scalars().all()
        libros = {row.ledger_id for row in asientos}
        assert libros
        assert all(
            sum((Decimal(row.credit) for row in asientos if row.ledger_id == libro), Decimal("0")) == Decimal("20")
            for libro in libros
        )


def test_stock_en_cero_solo_reduce_con_capas_de_evidencia(entorno_conciliacion):
    """La conciliación puede dejar stock sin valor, pero con capas que lo respaldan."""
    app, _inventario_id, ajuste_id = entorno_conciliacion
    _conciliacion(app, counted_qty="10", target_rate="0", adjustment_account_id=ajuste_id)

    bin_row, capas = _evidencia(app)
    assert bin_row == (Decimal("10"), Decimal("0"))
    _cuadra(bin_row, capas)

    _conciliacion(app, counted_qty="4", target_rate="0", adjustment_account_id=ajuste_id)

    bin_row, capas = _evidencia(app)
    assert bin_row == (Decimal("4"), Decimal("0"))
    _cuadra(bin_row, capas)
    with app.app_context():
        cost, _rate, _source, _composicion = _consume_stock_valuation_layers(
            company="cacao", item_code=ITEM_CODE, warehouse=WAREHOUSE, quantity=Decimal("4")
        )
        assert cost == Decimal("0")
