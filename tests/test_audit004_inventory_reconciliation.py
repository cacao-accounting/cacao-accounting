# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Suite AUDIT-004 (issue #279): reconciliacion inventario fisico, valoracion, COGS y GL.

Ejecuta la reconciliacion independiente end-to-end exigida por el issue, por
articulo, bodega, corte de periodo y libro:

    cantidad:   StockBin.actual_qty == SUM(StockLedgerEntry.qty_change) == conteo esperado
    valor:      StockBin.stock_value == SUM(SLE.stock_value_difference)
                                     == SUM(StockValuationLayer.stock_value_difference)
                valoracion reportada == saldo GL de la cuenta de inventario de la bodega
    costo:      COGS calculado (consumo de capas por voucher) == debitos GL de la cuenta COGS

Los valores esperados se calculan a mano en cada escenario (capas FIFO o promedio
movil segun ``Entity.valuation_method``) y NO reutilizan las funciones del motor;
cualquier regresion de valoracion rompe las ecuaciones aunque los submayores
siguan cuadrando entre si internamente.

Escenarios cubiertos (ambos metodos de valuacion):
- Capas multiples con consumos parciales que cruzan frontera de capa.
- Receipt retroactivo (backdated) posterior al consumo ya contabilizado: pinnea
  la composicion determinista del consumo subsiguiente y la inmutabilidad del
  costo historico ya publicado (SLE append-only).
- Cancelacion append-only de nota de entrega y de recepcion: restauracion de
  StockBin, espejo GL (is_cancelled/is_reversal) y ecuaciones intactas.
- Transferencia entre bodegas con cuentas GL distintas (valor migra entre
  cuentas sin alterar el inventario consolidado).
- Stock negativo permitido: consistencia interna y cierre a cero.
- Conteo fisico (stock_reconciliation) true-up de cantidad y de valor puro.
- COGS trazable por voucher y acumulado contra la cuenta COGS del articulo.
- Matriz de conciliacion por corte de periodo (subledger == control GL).

Dimensiones fuera de alcance deliberado: conversion multimoneda por libro
(cubierto por #276/#278) y lotes/seriales (#538). El libro unico primario en la
moneda de la compania hace que GL e inventario sean directamente comparables.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting import cancel_document, submit_document
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyDefaultAccount,
    Currency,
    DeliveryNote,
    DeliveryNoteItem,
    Entity,
    GLEntry,
    Item,
    ItemAccount,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.ledger_queries import (
    exclude_cancelled_gl_entries,
    exclude_cancelled_stock_entries,
)
from cacao_accounting.inventario.service import rebuild_stock_valuation_layers
from cacao_accounting.reportes.services import (
    OperationalReportFilters,
    ReconciliationFilters,
    get_inventory_valuation,
    get_reconciliation_matrix,
)

COMPANY = "aud04"
BOOK_CODE = "AUD04L1"
WH_A = "WH-A"
WH_B = "WH-B"

D_MAY_02 = date(2026, 5, 2)
D_MAY_03 = date(2026, 5, 3)
D_MAY_05 = date(2026, 5, 5)
D_MAY_10 = date(2026, 5, 10)
D_MAY_15 = date(2026, 5, 15)
D_MAY_20 = date(2026, 5, 20)
MAY_END = date(2026, 5, 31)
D_JUN_01 = date(2026, 6, 1)
D_JUN_02 = date(2026, 6, 2)
D_JUN_03 = date(2026, 6, 3)
D_JUN_05 = date(2026, 6, 5)
D_JUN_08 = date(2026, 6, 8)
OPEN_END = date(2026, 12, 31)

Q = Decimal


def _dec(value: Any) -> Decimal:
    """Normaliza valores numericos de la base a Decimal."""
    return Decimal(str(value if value is not None else 0))


@pytest.fixture(params=["fifo", "moving_average"])
def env(request):
    """App aislada SQLite en memoria sembrada con el metodo de valuacion del parametro."""
    method = request.param
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        chart = _seed(method)
        yield {"method": method, **chart}
        database.session.remove()
        database.drop_all()


def _seed(method: str) -> dict[str, Any]:
    """Siembra compania, libro, catalogo minimo, bodegas y articulos de la auditoria."""
    database.session.add_all(
        [
            Entity(
                code=COMPANY,
                name="Auditoria Inventario",
                company_name="AUD04 SA",
                tax_id="AUD04-1",
                currency="NIO",
                valuation_method=method,
            ),
            Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
            Book(entity=COMPANY, code=BOOK_CODE, name="Libro Fiscal", currency="NIO", status="activo", is_primary=True),
            UOM(code="UND", name="Unidad"),
        ]
    )
    inv_a = Accounts(entity=COMPANY, code="1120", name="Inventario A", classification="asset")
    inv_b = Accounts(entity=COMPANY, code="1121", name="Inventario B", classification="asset")
    cogs = Accounts(entity=COMPANY, code="5100", name="Costo de Ventas", classification="expense")
    adj = Accounts(entity=COMPANY, code="5200", name="Ajustes de Inventario", classification="expense")
    bridge = Accounts(entity=COMPANY, code="2102", name="Puente Compras", classification="liability")
    database.session.add_all([inv_a, inv_b, cogs, adj, bridge])
    database.session.flush()

    wh_a = Warehouse(code=WH_A, name="Bodega A", company=COMPANY, is_active=True)
    wh_b = Warehouse(code=WH_B, name="Bodega B", company=COMPANY, is_active=True)
    database.session.add_all([wh_a, wh_b])
    database.session.flush()
    database.session.add_all(
        [
            WarehouseCompanyAccount(warehouse_code=WH_A, company=COMPANY, inventory_account_id=inv_a.id, is_active=True),
            WarehouseCompanyAccount(warehouse_code=WH_B, company=COMPANY, inventory_account_id=inv_b.id, is_active=True),
            CompanyDefaultAccount(
                company=COMPANY,
                default_cogs=cogs.id,
                inventory_adjustment_account_id=adj.id,
                bridge_account_id=bridge.id,
            ),
            ItemAccount(item_code="ITF", company=COMPANY, cogs_account_id=cogs.id),
        ]
    )
    database.session.add_all(
        [
            Item(
                code="ITF",
                name="Articulo FIFO/Avg",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                allow_negative_stock=False,
            ),
            Item(
                code="ITN",
                name="Articulo Stock Negativo",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                allow_negative_stock=True,
            ),
        ]
    )
    database.session.commit()
    return {
        "inv_a_id": inv_a.id,
        "inv_b_id": inv_b.id,
        "cogs_id": cogs.id,
        "adj_id": adj.id,
        "book_id": database.session.execute(select(Book).filter_by(entity=COMPANY)).scalar_one().id,
    }


def _receive(env: dict, warehouse: str, item: str, qty: Decimal, rate: Decimal, day: date) -> StockEntry:
    """Recibe material con costo explicito (crea capa de valuacion positiva)."""
    doc = StockEntry(
        company=COMPANY,
        docstatus=0,
        posting_date=day,
        purpose="material_receipt",
        to_warehouse=warehouse,
    )
    database.session.add(doc)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=doc.id,
            item_code=item,
            qty=qty,
            uom="UND",
            qty_in_base_uom=qty,
            target_warehouse=warehouse,
            basic_rate=rate,
            amount=qty * rate,
        )
    )
    database.session.commit()
    submit_document(doc)
    database.session.commit()
    return doc


def _issue(env: dict, warehouse: str, item: str, qty: Decimal, day: date) -> StockEntry:
    """Descarga material cuyo costo resuelve el motor desde las capas.

    La linea no siembra monto ni el atributo transitorio de costo: desde
    AUDIT-004 el GL de salidas resuelve su contrapartida desde el mayor de
    inventario persistido (StockLedgerEntry).
    """
    doc = StockEntry(
        company=COMPANY,
        docstatus=0,
        posting_date=day,
        purpose="material_issue",
        from_warehouse=warehouse,
    )
    database.session.add(doc)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=doc.id,
            item_code=item,
            qty=qty,
            uom="UND",
            qty_in_base_uom=qty,
            source_warehouse=warehouse,
        )
    )
    database.session.commit()
    submit_document(doc)
    database.session.commit()
    return doc


def _transfer(env: dict, source: str, target: str, item: str, qty: Decimal, day: date) -> StockEntry:
    """Transfiere stock entre bodegas con cuentas GL distintas.

    Sin monto de linea: el valor transferido lo resuelve el motor desde capas.
    """
    doc = StockEntry(
        company=COMPANY,
        docstatus=0,
        posting_date=day,
        purpose="material_transfer",
        from_warehouse=source,
        to_warehouse=target,
    )
    database.session.add(doc)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=doc.id,
            item_code=item,
            qty=qty,
            uom="UND",
            qty_in_base_uom=qty,
            source_warehouse=source,
            target_warehouse=target,
        )
    )
    database.session.commit()
    submit_document(doc)
    database.session.commit()
    return doc


def _reconcile(
    env: dict,
    warehouse: str,
    item: str,
    counted_qty: Decimal,
    target_value: Decimal,
    target_rate: Decimal,
    day: date,
) -> StockEntry:
    """Conciliacion fisica con cantidad contada y valor objetivo."""
    doc = StockEntry(
        company=COMPANY,
        docstatus=0,
        posting_date=day,
        purpose="stock_reconciliation",
        to_warehouse=warehouse,
    )
    database.session.add(doc)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=doc.id,
            item_code=item,
            qty=Decimal("0"),
            uom="UND",
            target_warehouse=warehouse,
            counted_qty=counted_qty,
            target_stock_value=target_value,
            target_valuation_rate=target_rate,
        )
    )
    database.session.commit()
    submit_document(doc)
    database.session.commit()
    return doc


def _deliver(env: dict, warehouse: str, item: str, qty: Decimal, price: Decimal, day: date) -> DeliveryNote:
    """Nota de entrega que descarga inventario y publica COGS."""
    doc = DeliveryNote(company=COMPANY, docstatus=0, posting_date=day)
    database.session.add(doc)
    database.session.flush()
    database.session.add(
        DeliveryNoteItem(
            delivery_note_id=doc.id,
            item_code=item,
            item_name=item,
            qty=qty,
            uom="UND",
            qty_in_base_uom=qty,
            rate=price,
            amount=qty * price,
            warehouse=warehouse,
        )
    )
    database.session.commit()
    submit_document(doc)
    database.session.commit()
    return doc


def _bin(env: dict, item: str, warehouse: str) -> StockBin | None:
    """Snapshot StockBin del articulo/bodega."""
    return (
        database.session.execute(select(StockBin).filter_by(company=COMPANY, item_code=item, warehouse=warehouse))
        .scalars()
        .first()
    )


def _sle_totals(env: dict, item: str, warehouse: str, as_of: date | None = None) -> tuple[Decimal, Decimal]:
    """Suma neta operativa (vouchers activos) del mayor de inventario."""
    query = select(
        func.coalesce(func.sum(StockLedgerEntry.qty_change), 0),
        func.coalesce(func.sum(StockLedgerEntry.stock_value_difference), 0),
    ).where(StockLedgerEntry.company == COMPANY, StockLedgerEntry.item_code == item, StockLedgerEntry.warehouse == warehouse)
    if as_of is not None:
        query = query.where(StockLedgerEntry.posting_date <= as_of)
    query = exclude_cancelled_stock_entries(query)
    row = database.session.execute(query).one()
    return _dec(row[0]), _dec(row[1])


def _svl_totals(env: dict, item: str, warehouse: str) -> tuple[Decimal, Decimal]:
    """Suma aritmetica sobre TODAS las capas: las reversas compensan a la original."""
    query = select(
        func.coalesce(func.sum(StockValuationLayer.qty), 0),
        func.coalesce(func.sum(StockValuationLayer.stock_value_difference), 0),
    ).where(
        StockValuationLayer.company == COMPANY,
        StockValuationLayer.item_code == item,
        StockValuationLayer.warehouse == warehouse,
    )
    row = database.session.execute(query).one()
    return _dec(row[0]), _dec(row[1])


def _voucher_sle(env: dict, voucher_type: str, voucher_ids: list[str]) -> dict[str, tuple[Decimal, Decimal]]:
    """Cantidad/valor publicados por voucher activo especifico."""
    query = (
        select(
            StockLedgerEntry.voucher_id,
            func.coalesce(func.sum(StockLedgerEntry.qty_change), 0),
            func.coalesce(func.sum(StockLedgerEntry.stock_value_difference), 0),
        )
        .where(
            StockLedgerEntry.company == COMPANY,
            StockLedgerEntry.voucher_type == voucher_type,
            StockLedgerEntry.voucher_id.in_(voucher_ids),
        )
        .group_by(StockLedgerEntry.voucher_id)
    )
    return {row[0]: (_dec(row[1]), _dec(row[2])) for row in database.session.execute(query)}


def _gl_balance(env: dict, account_id: str, as_of: date | None = None) -> Decimal:
    """Saldo GL operativo de una cuenta filtrado por compania y libro primario."""
    query = select(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).where(
        GLEntry.company == COMPANY,
        GLEntry.account_id == account_id,
        GLEntry.ledger_id == env["book_id"],
    )
    if as_of is not None:
        query = query.where(GLEntry.posting_date <= as_of)
    query = exclude_cancelled_gl_entries(query)
    return _dec(database.session.execute(query).scalar_one())


def _gl_voucher_amount(env: dict, account_id: str, voucher_type: str, voucher_ids: list[str]) -> dict[str, Decimal]:
    """Importe Dr-Cr por voucher para una cuenta (vista operativa)."""
    query = (
        select(GLEntry.voucher_id, func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0))
        .where(
            GLEntry.company == COMPANY,
            GLEntry.account_id == account_id,
            GLEntry.voucher_type == voucher_type,
            GLEntry.voucher_id.in_(voucher_ids),
        )
        .group_by(GLEntry.voucher_id)
    )
    query = exclude_cancelled_gl_entries(query)
    return {row[0]: _dec(row[1]) for row in database.session.execute(query)}


def _matrix_inventory_row(env: dict, as_of: date) -> dict[str, Any]:
    """Fila Inventory de la matriz de conciliacion subledger/GL."""
    report = get_reconciliation_matrix(ReconciliationFilters(company=COMPANY, ledger=BOOK_CODE, as_of_date=as_of))
    for row in report.rows:
        if row.values["area"] == "Inventory":
            return row.values
    raise AssertionError("La matriz de conciliacion no devolvio fila de inventario.")


def _valuation_report(env: dict, date_to: date | None = None) -> dict[tuple[str, str], tuple[Decimal, Decimal]]:
    """Valoracion por articulo/bodega derivada de capas."""
    report = get_inventory_valuation(OperationalReportFilters(company=COMPANY, date_to=date_to))
    return {
        (row.values["item_code"], row.values["warehouse"]): (
            _dec(row.values["remaining_qty"]),
            _dec(row.values["remaining_stock_value"]),
        )
        for row in report.rows
    }


def _assert_consistency(env: dict, keys: list[tuple[str, str, str]], as_of: date | None = None) -> None:
    """Ecuaciones nucleares por articulo/bodega: bin == SLE == SVL == GL."""
    for item, warehouse, account_id in keys:
        sle_qty, sle_value = _sle_totals(env, item, warehouse, as_of=as_of)
        svl_qty, svl_value = _svl_totals(env, item, warehouse)
        bin_row = _bin(env, item, warehouse)
        assert bin_row is not None, f"Sin StockBin para {item}/{warehouse}"
        assert _dec(bin_row.actual_qty) == sle_qty == svl_qty, f"cantidad {item}/{warehouse}"
        assert _dec(bin_row.stock_value) == sle_value == svl_value, f"valor {item}/{warehouse}"
        gl_value = _gl_balance(env, account_id, as_of=as_of)
        assert gl_value == sle_value, f"GL {account_id} != mayor de inventario {item}/{warehouse}"
        valuation = _valuation_report(env, date_to=as_of)
        if sle_qty != 0:
            assert valuation.get((item, warehouse)) == (sle_qty, sle_value), f"valoracion {item}/{warehouse}"


def test_capas_multiples_venta_parcial_ecuaciones_end_to_end(env):
    """Capas multiples, venta parcial cruzando capa, COGS y GL verificados a mano.

    Semilla: 12@100 + 12@140. Venta 15: FIFO 12x100+3x140=1620; promedio 15x120=1800.
    Recepcion 11@150 y segunda venta de 8: FIFO 8x140=1120; promedio 8x136.5=1092.
    """
    _receive(env, WH_A, "ITF", Q("12"), Q("100"), D_MAY_02)
    _receive(env, WH_A, "ITF", Q("12"), Q("140"), D_MAY_05)
    dn1 = _deliver(env, WH_A, "ITF", Q("15"), Q("200"), D_JUN_01)
    expected_dn1 = Q("1620") if env["method"] == "fifo" else Q("1800")
    bin_row = _bin(env, "ITF", WH_A)
    assert _dec(bin_row.actual_qty) == Q("9")
    assert _dec(bin_row.stock_value) == Q("2880") - expected_dn1
    assert _gl_balance(env, env["inv_a_id"]) == _dec(bin_row.stock_value)

    _receive(env, WH_A, "ITF", Q("11"), Q("150"), D_JUN_02)
    dn2 = _deliver(env, WH_A, "ITF", Q("8"), Q("200"), D_JUN_03)
    expected_dn2 = Q("1120") if env["method"] == "fifo" else Q("1092")
    final_value = Q("2880") + Q("1650") - expected_dn1 - expected_dn2

    bin_row = _bin(env, "ITF", WH_A)
    assert _dec(bin_row.actual_qty) == Q("12")
    assert _dec(bin_row.stock_value) == final_value

    movements = _voucher_sle(env, "delivery_note", [dn1.id, dn2.id])
    assert movements[dn1.id] == (Q("-15"), -expected_dn1)
    assert movements[dn2.id] == (Q("-8"), -expected_dn2)
    assert _gl_voucher_amount(env, env["inv_a_id"], "delivery_note", [dn1.id, dn2.id]) == {
        dn1.id: -expected_dn1,
        dn2.id: -expected_dn2,
    }
    cogs_by_voucher = _gl_voucher_amount(env, env["cogs_id"], "delivery_note", [dn1.id, dn2.id])
    assert cogs_by_voucher == {dn1.id: expected_dn1, dn2.id: expected_dn2}

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
    row = _matrix_inventory_row(env, OPEN_END)
    assert row["difference"] == 0 and row["status"] == "reconciled"
    assert row["subledger_amount"] == final_value and row["gl_control_amount"] == final_value


def test_receipt_backdated_cambia_composicion_subsiguiente_y_mantiene_ecuaciones(env):
    """Receipt retroactivo posterior a un consumo ya contabilizado.

    Semilla: 5@90 (05-05), consumo 3 (05-10, costo 270 ambos metodos), receipt
    retroactivo 8@85 fechado 05-01 y consumo 5 (05-15). La reposicion cronologica
    de capas hace que FIFO consuma la capa retroactiva primero (5x85=425) mientras
    el promedio movil usa la tasa del bin (860/10=86 -> 430).
    """
    _receive(env, WH_B, "ITF", Q("5"), Q("90"), D_MAY_05)
    issue1 = _issue(env, WH_B, "ITF", Q("3"), D_MAY_10)
    movements = _voucher_sle(env, "stock_entry", [issue1.id])
    assert movements[issue1.id] == (Q("-3"), Q("-270"))

    _receive(env, WH_B, "ITF", Q("8"), Q("85"), D_MAY_03)

    if env["method"] == "fifo":
        expected_cost, expected_rate = Q("425"), Q("85")
    else:
        expected_cost, expected_rate = Q("430"), Q("86")
    issue2 = _issue(env, WH_B, "ITF", Q("5"), D_MAY_15)
    movements = _voucher_sle(env, "stock_entry", [issue2.id])
    assert movements[issue2.id] == (Q("-5"), -expected_cost)
    sle_row = (
        database.session.execute(
            select(StockLedgerEntry).where(
                StockLedgerEntry.voucher_type == "stock_entry",
                StockLedgerEntry.voucher_id == issue2.id,
                StockLedgerEntry.qty_change < 0,
            )
        )
        .scalars()
        .first()
    )
    assert _dec(sle_row.valuation_rate) == expected_rate

    bin_row = _bin(env, "ITF", WH_B)
    assert _dec(bin_row.actual_qty) == Q("5")
    assert _dec(bin_row.stock_value) == Q("450") - Q("270") + Q("680") - expected_cost

    _assert_consistency(env, [("ITF", WH_B, env["inv_b_id"])])
    row = _matrix_inventory_row(env, OPEN_END)
    assert row["difference"] == 0


def test_cancel_nota_entrega_restaura_bin_y_espeja_gl(env):
    """Cancelacion append-only de nota de entrega restaura estado y espeja GL."""
    _receive(env, WH_A, "ITF", Q("12"), Q("100"), D_MAY_02)
    _receive(env, WH_A, "ITF", Q("12"), Q("140"), D_MAY_05)
    dn1 = _deliver(env, WH_A, "ITF", Q("15"), Q("200"), D_JUN_01)
    cancel_document(dn1)
    database.session.commit()

    bin_row = _bin(env, "ITF", WH_A)
    assert _dec(bin_row.actual_qty) == Q("24")
    assert _dec(bin_row.stock_value) == Q("2880")

    cancelled_originals = database.session.execute(
        select(func.count())
        .select_from(GLEntry)
        .where(GLEntry.voucher_type == "delivery_note", GLEntry.voucher_id == dn1.id, GLEntry.is_cancelled.is_(True))
    ).scalar_one()
    reversals = database.session.execute(
        select(func.count())
        .select_from(GLEntry)
        .where(GLEntry.voucher_type == "delivery_note", GLEntry.voucher_id == dn1.id, GLEntry.is_reversal.is_(True))
    ).scalar_one()
    assert cancelled_originals > 0 and reversals == cancelled_originals
    assert _gl_balance(env, env["cogs_id"], as_of=OPEN_END) == 0
    assert _gl_balance(env, env["inv_a_id"], as_of=OPEN_END) == Q("2880")

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
    assert _matrix_inventory_row(env, OPEN_END)["difference"] == 0


def test_cancel_recepcion_sin_consumo_libera_disponibilidad(env):
    """Cancelar una recepcion previa al consumo devuelve capas y disponibilidad."""
    _receive(env, WH_A, "ITF", Q("12"), Q("100"), D_MAY_02)
    receipt2 = _receive(env, WH_A, "ITF", Q("12"), Q("140"), D_MAY_05)

    cancel_document(receipt2)
    database.session.commit()

    reversal_rows = (
        database.session.execute(select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=receipt2.id))
        .scalars()
        .all()
    )
    assert sum(_dec(row.qty_change) for row in reversal_rows) == 0
    assert sum(_dec(row.stock_value_difference) for row in reversal_rows) == 0

    bin_row = _bin(env, "ITF", WH_A)
    assert _dec(bin_row.actual_qty) == Q("12")
    assert _dec(bin_row.stock_value) == Q("1200")

    dn = _deliver(env, WH_A, "ITF", Q("10"), Q("200"), D_JUN_01)
    movements = _voucher_sle(env, "delivery_note", [dn.id])
    expected_sale = Q("-1000")
    assert movements[dn.id][1] == expected_sale

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
    assert _matrix_inventory_row(env, OPEN_END)["difference"] == 0


def test_transferencia_cross_account_mueve_valor_entre_cuentas_gl(env):
    """Transferencia entre bodegas migra valor entre cuentas GL preservando el total."""
    _receive(env, WH_A, "ITF", Q("12"), Q("100"), D_MAY_02)

    _transfer(env, WH_A, WH_B, "ITF", Q("7"), D_JUN_01)

    bin_a = _bin(env, "ITF", WH_A)
    bin_b = _bin(env, "ITF", WH_B)
    assert (_dec(bin_a.actual_qty), _dec(bin_a.stock_value)) == (Q("5"), Q("500"))
    assert (_dec(bin_b.actual_qty), _dec(bin_b.stock_value)) == (Q("7"), Q("700"))
    assert _gl_balance(env, env["inv_a_id"]) == Q("500")
    assert _gl_balance(env, env["inv_b_id"]) == Q("700")
    total_valuation = _dec(bin_a.stock_value) + _dec(bin_b.stock_value)
    consolidated_gl = _gl_balance(env, env["inv_a_id"]) + _gl_balance(env, env["inv_b_id"])
    assert consolidated_gl == total_valuation == Q("1200")

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"]), ("ITF", WH_B, env["inv_b_id"])])
    assert _matrix_inventory_row(env, OPEN_END)["difference"] == 0


def test_stock_negativo_cierra_a_cero_con_ecuaciones_internas(env):
    """Stock negativo permitido: salida usa tasa de capas disponibles y cierra en cero.

    Recibe 4@40, emite 7 (negativo permitido, costo 7x40=280, bin -3/-120),
    recibe 17@40 y emite 14: ambos metodos cierran en cantidad 0 y valor 0.
    """
    _receive(env, WH_B, "ITN", Q("4"), Q("40"), D_MAY_02)
    issue1 = _issue(env, WH_B, "ITN", Q("7"), D_JUN_01)

    bin_row = _bin(env, "ITN", WH_B)
    assert _dec(bin_row.actual_qty) == Q("-3")
    assert _dec(bin_row.stock_value) == Q("-120")
    assert _gl_balance(env, env["inv_b_id"]) == Q("-120")
    movements = _voucher_sle(env, "stock_entry", [issue1.id])
    assert movements[issue1.id] == (Q("-7"), Q("-280"))
    assert _svl_totals(env, "ITN", WH_B) == (Q("-3"), Q("-120"))

    _receive(env, WH_B, "ITN", Q("17"), Q("40"), D_JUN_05)
    bin_row = _bin(env, "ITN", WH_B)
    assert (_dec(bin_row.actual_qty), _dec(bin_row.stock_value)) == (Q("14"), Q("560"))

    _issue(env, WH_B, "ITN", Q("14"), D_JUN_08)
    bin_row = _bin(env, "ITN", WH_B)
    assert (_dec(bin_row.actual_qty), _dec(bin_row.stock_value)) == (Q("0"), Q("0"))
    assert _dec(bin_row.valuation_rate) == 0

    _assert_consistency(env, [("ITN", WH_B, env["inv_b_id"])])
    assert _matrix_inventory_row(env, OPEN_END)["difference"] == 0


def test_conteo_fisico_true_up_cantidad_y_valor(env):
    """Conciliacion fisica ajusta cantidad y valor objetivo contra el bin bloqueado."""
    _receive(env, WH_A, "ITF", Q("12"), Q("100"), D_MAY_02)

    _reconcile(env, WH_A, "ITF", Q("9"), Q("945"), Q("105"), D_MAY_10)
    bin_row = _bin(env, "ITF", WH_A)
    assert (_dec(bin_row.actual_qty), _dec(bin_row.stock_value)) == (Q("9"), Q("945"))
    assert _gl_balance(env, env["inv_a_id"]) == Q("945")
    assert _gl_balance(env, env["adj_id"]) == Q("-945")
    svl_qty, svl_value = _svl_totals(env, "ITF", WH_A)
    assert (svl_qty, svl_value) == (Q("9"), Q("945"))

    _reconcile(env, WH_A, "ITF", Q("9"), Q("990"), Q("110"), D_MAY_20)
    bin_row = _bin(env, "ITF", WH_A)
    assert (_dec(bin_row.actual_qty), _dec(bin_row.stock_value)) == (Q("9"), Q("990"))
    assert _gl_balance(env, env["inv_a_id"]) == Q("990")
    assert _gl_balance(env, env["adj_id"]) == Q("-990")

    recon_line = (
        database.session.execute(
            select(StockEntryItem)
            .join(StockEntry, StockEntry.id == StockEntryItem.stock_entry_id)
            .where(StockEntry.purpose == "stock_reconciliation", StockEntryItem.counted_qty.is_not(None))
            .order_by(StockEntry.posting_date.desc())
        )
        .scalars()
        .first()
    )
    assert _dec(recon_line.current_qty) == Q("9")
    assert _dec(recon_line.qty_difference) == 0
    assert _dec(recon_line.stock_value_difference) == Q("45")

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
    assert _matrix_inventory_row(env, MAY_END)["difference"] == 0


def test_cogs_gl_trazable_por_voucher_y_acumulado(env):
    """El COGS acumulado en GL iguala al consumo de capas por nota de entrega.

    Los issues de material golpean la cuenta de ajuste, nunca la cuenta COGS.
    """
    _receive(env, WH_A, "ITF", Q("10"), Q("50"), D_MAY_02)
    dn1 = _deliver(env, WH_A, "ITF", Q("4"), Q("90"), D_JUN_01)
    issue = _issue(env, WH_A, "ITF", Q("2"), D_JUN_02)
    dn2 = _deliver(env, WH_A, "ITF", Q("3"), Q("90"), D_JUN_03)

    cogs_total = _gl_balance(env, env["cogs_id"], as_of=OPEN_END)
    assert cogs_total == Q("350")

    dn_movements = _voucher_sle(env, "delivery_note", [dn1.id, dn2.id])
    consumed_by_dns = -sum(value for _, value in dn_movements.values())
    assert consumed_by_dns == cogs_total
    assert dn_movements[dn1.id] == (Q("-4"), Q("-200"))
    assert dn_movements[dn2.id] == (Q("-3"), Q("-150"))

    issue_adjustment = _gl_voucher_amount(env, env["adj_id"], "stock_entry", [issue.id])
    assert issue_adjustment[issue.id] == Q("100")
    issue_cogs = _gl_voucher_amount(env, env["cogs_id"], "stock_entry", [issue.id])
    assert issue_cogs.get(issue.id, 0) == 0

    cogs_rows = database.session.execute(
        select(GLEntry.voucher_id, GLEntry.ledger_id).where(
            GLEntry.account_id == env["cogs_id"], GLEntry.voucher_type == "delivery_note"
        )
    ).all()
    assert {row[0] for row in cogs_rows} == {dn1.id, dn2.id}
    assert {row[1] for row in cogs_rows} == {env["book_id"]}

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
    bin_row = _bin(env, "ITF", WH_A)
    assert (_dec(bin_row.actual_qty), _dec(bin_row.stock_value)) == (Q("1"), Q("50"))


def test_matriz_reconciliacion_por_corte_de_periodo(env):
    """Subledger == control GL por corte de periodo intermedio y final."""
    _receive(env, WH_A, "ITF", Q("12"), Q("100"), D_MAY_02)
    _receive(env, WH_A, "ITF", Q("12"), Q("140"), D_MAY_05)
    _deliver(env, WH_A, "ITF", Q("15"), Q("200"), D_JUN_01)

    mid_value = _sle_totals(env, "ITF", WH_A, as_of=MAY_END)[1]
    assert mid_value == Q("2880")
    mid_gl = _gl_balance(env, env["inv_a_id"], as_of=MAY_END)
    assert mid_gl == Q("2880")

    mid_row = _matrix_inventory_row(env, MAY_END)
    assert mid_row["status"] == "reconciled"
    assert mid_row["subledger_amount"] == mid_value
    assert mid_row["gl_control_amount"] == mid_gl
    assert set(mid_row["account_ids"].split(",")) == {
        str(env["inv_a_id"]),
        str(env["inv_b_id"]),
    }

    end_value = _sle_totals(env, "ITF", WH_A)[1]
    assert end_value == (Q("1260") if env["method"] == "fifo" else Q("1080"))
    end_row = _matrix_inventory_row(env, OPEN_END)
    assert end_row["difference"] == 0
    assert end_row["subledger_amount"] == end_value


def test_receipt_backdated_no_reescribe_capas_ya_consumidas(env):
    """AUDIT-004 hallazgo 1: cada consumo queda fijado a su capa origen.

    B: 5@90 (05-05). Consumo de 3 (05-10): costo 270 desde la capa B.
    Receipt retroactivo A: 8@95 fechado 05-03 pero posteado despues del consumo.
    Consumo de 6 (05-20): la capa A conserva sus 8 unidades, asi que FIFO paga
    6x95=570. La reconstruccion legada habria reasignado el consumo historico a
    la capa retroactiva dejando 5@95 + 2@90 y costado 565.
    """
    _receive(env, WH_B, "ITF", Q("5"), Q("90"), D_MAY_05)
    issue1 = _issue(env, WH_B, "ITF", Q("3"), D_MAY_10)
    movements = _voucher_sle(env, "stock_entry", [issue1.id])
    assert movements[issue1.id] == (Q("-3"), Q("-270"))

    _receive(env, WH_B, "ITF", Q("8"), Q("95"), D_MAY_03)

    issue2 = _issue(env, WH_B, "ITF", Q("6"), D_MAY_15)
    movements = _voucher_sle(env, "stock_entry", [issue1.id, issue2.id])
    assert movements[issue1.id] == (Q("-3"), Q("-270"))
    if env["method"] == "fifo":
        assert movements[issue2.id] == (Q("-6"), Q("-570"))
    else:
        # Promedio movil del bin: (180+760)/10 = 94 por unidad.
        assert movements[issue2.id] == (Q("-6"), Q("-564"))

    bin_row = _bin(env, "ITF", WH_B)
    expected_value = (Q("940") - Q("564")) if env["method"] == "moving_average" else (Q("1210") - Q("840"))
    assert _dec(bin_row.actual_qty) == Q("4")
    assert _dec(bin_row.stock_value) == expected_value

    consumption_layer = (
        database.session.execute(
            select(StockValuationLayer).where(
                StockValuationLayer.voucher_type == "stock_entry",
                StockValuationLayer.voucher_id == issue1.id,
                StockValuationLayer.qty < 0,
            )
        )
        .scalars()
        .first()
    )
    if env["method"] == "fifo":
        source_layer_id = consumption_layer.source_layer_id
        assert source_layer_id is not None
        source_layer = database.session.get(StockValuationLayer, source_layer_id)
        assert source_layer is not None and _dec(source_layer.qty) == Q("5")

    _assert_consistency(env, [("ITF", WH_B, env["inv_b_id"])])
    assert _matrix_inventory_row(env, OPEN_END)["difference"] == 0


def test_cancel_devuelve_valor_a_la_capa_origen_fifo(env):
    """AUDIT-004 hallazgo 2: la reversa restaura la capa consumida original.

    L1: 10@100, L2: 10@200. Venta de 10 consume L1 (1000). Al cancelar, la
    reversa se fija a la capa L1 y la venta subsiguiente de 10 vuelve a costar
    1000 en FIFO; el repliegue legado a la fecha de reversa habria puesto la
    capa restaurada despues de L2 y la venta habria costado 2000.
    """
    _receive(env, WH_A, "ITF", Q("10"), Q("100"), D_MAY_02)
    receipt_l2 = _receive(env, WH_A, "ITF", Q("10"), Q("200"), D_MAY_05)
    dn1 = _deliver(env, WH_A, "ITF", Q("10"), Q("300"), D_JUN_01)
    cancel_document(dn1)
    database.session.commit()

    reversal_row = (
        database.session.execute(
            select(StockValuationLayer).where(
                StockValuationLayer.voucher_type == "delivery_note",
                StockValuationLayer.voucher_id == dn1.id,
                StockValuationLayer.qty > 0,
            )
        )
        .scalars()
        .first()
    )
    assert reversal_row is not None
    if env["method"] == "fifo":
        restored_source = database.session.get(StockValuationLayer, reversal_row.source_layer_id)
        assert restored_source is not None
        assert restored_source.posting_date == D_MAY_02
        assert restored_source.voucher_type == "stock_entry"
        assert restored_source.voucher_id != receipt_l2.id

    dn2 = _deliver(env, WH_A, "ITF", Q("10"), Q("300"), D_JUN_02)
    movements = _voucher_sle(env, "delivery_note", [dn2.id])
    if env["method"] == "fifo":
        assert movements[dn2.id] == (Q("-10"), Q("-1000"))
    else:
        # Promedio movil: 3000/20 = 150 por unidad tras la restauracion.
        assert movements[dn2.id] == (Q("-10"), Q("-1500"))

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
    assert _matrix_inventory_row(env, OPEN_END)["difference"] == 0


def test_gl_salidas_resuelve_costo_del_mayor_persistido(env):
    """AUDIT-004 hallazgo 3: sin atributo transitorio el GL usa StockLedgerEntry.

    Tras recargar las lineas en una sesion limpia no existe
    ``_inventory_cost_amount``; los resolutores GL deben publicar la
    contrapartida desde el mayor de inventario.
    """
    from cacao_accounting.contabilidad.posting_service import (
        _get_delivery_note_line_value,
        _get_stock_entry_line_amount,
    )

    _receive(env, WH_A, "ITF", Q("10"), Q("50"), D_MAY_02)
    issue = _issue(env, WH_A, "ITF", Q("4"), D_JUN_01)
    issue_id = issue.id

    database.session.expunge_all()
    issue_doc = database.session.get(StockEntry, issue_id)
    issue_line = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=issue_id)).scalars().one()
    assert getattr(issue_line, "_inventory_cost_amount", None) is None
    assert _get_stock_entry_line_amount(issue_doc, issue_line, "material_issue") == Q("200")

    dn = _deliver(env, WH_A, "ITF", Q("3"), Q("80"), D_JUN_02)
    dn_id = dn.id

    database.session.expunge_all()
    dn_doc = database.session.get(DeliveryNote, dn_id)
    dn_line = database.session.execute(select(DeliveryNoteItem).filter_by(delivery_note_id=dn_id)).scalars().one()
    assert getattr(dn_line, "_inventory_cost_amount", None) is None
    assert _get_delivery_note_line_value(dn_doc, dn_line) == Q("150")

    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])


def _svl_stream(item: str, warehouse: str) -> list[tuple[Decimal, Decimal, Decimal]]:
    """Stream cronologico de capas como tuplas comparables (qty, rate, valor)."""
    rows = (
        database.session.execute(
            select(StockValuationLayer)
            .filter_by(company=COMPANY, item_code=item, warehouse=warehouse)
            .order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
        )
        .scalars()
        .all()
    )
    return [(_dec(r.qty), _dec(r.rate), _dec(r.stock_value_difference)) for r in rows]


def test_rebuild_preserva_ajuste_de_conciliacion_y_costo_posterior(env):
    """Issue #750: el rebuild conserva la capa de ajuste de valor de la conciliacion.

    Semilla 10@10 = 100; conciliacion a 8 unidades con valor objetivo 90 publica
    consumo FIFO -20 mas ajuste +10. Tras reconstruir ambas capas sobreviven y
    la venta siguiente cuesta 90/8 = 11.25 en ambos metodos de valuacion.
    """
    _receive(env, WH_A, "ITF", Q("10"), Q("10"), D_MAY_02)
    _reconcile(env, WH_A, "ITF", Q("8"), Q("90"), Q("11.25"), D_MAY_10)
    antes = _svl_stream("ITF", WH_A)
    assert antes == [(Q("10"), Q("10"), Q("100")), (Q("-2"), Q("10"), Q("-20")), (Q("0"), Q("11.25"), Q("10"))]

    resultado = rebuild_stock_valuation_layers(COMPANY)
    assert resultado.rebuilt_layers == 3

    despues_capas = (
        database.session.execute(
            select(StockValuationLayer)
            .filter_by(company=COMPANY, item_code="ITF", warehouse=WH_A)
            .order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
        )
        .scalars()
        .all()
    )
    assert [(_dec(r.qty), _dec(r.rate), _dec(r.stock_value_difference)) for r in despues_capas] == [
        (Q("10"), Q("10"), Q("100")),
        (Q("-2"), Q("10"), Q("-20")),
        (Q("0"), Q("11.25"), Q("10")),
    ]
    if env["method"] == "fifo":
        assert despues_capas[1].source_layer_id == despues_capas[0].id
    else:
        assert despues_capas[1].source_layer_id is None

    _deliver(env, WH_A, "ITF", Q("1"), Q("30"), D_MAY_15)
    movimiento = (
        database.session.execute(
            select(StockLedgerEntry).where(
                StockLedgerEntry.company == COMPANY,
                StockLedgerEntry.voucher_type == "delivery_note",
                StockLedgerEntry.posting_date == D_MAY_15,
            )
        )
        .scalars()
        .one()
    )
    assert -_dec(movimiento.stock_value_difference) == Q("11.25")
    bin_row = _bin(env, "ITF", WH_A)
    assert (_dec(bin_row.actual_qty), _dec(bin_row.stock_value)) == (Q("7"), Q("78.75"))
    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])


def test_rebuild_produce_las_mismas_valuaciones_de_salida_que_el_estado_vivo(env):
    """Criterio #750: la cola tras el rebuild valora igual que sin reconstruir.

    Dos articulos con historial identico (receipts, venta, conciliacion con
    ajuste de valor y venta) terminan con streams de capas identicos; solo el
    primero se reconstruye, y la salida posterior cuesta lo mismo en ambos.
    """
    _receive(env, WH_A, "ITF", Q("10"), Q("10"), D_MAY_02)
    _deliver(env, WH_A, "ITF", Q("2"), Q("50"), D_MAY_03)
    _receive(env, WH_A, "ITF", Q("10"), Q("14"), D_MAY_05)
    _reconcile(env, WH_A, "ITF", Q("12"), Q("148"), Q("12.333333333"), D_MAY_10)

    _receive(env, WH_B, "ITN", Q("10"), Q("10"), D_MAY_02)
    _deliver(env, WH_B, "ITN", Q("2"), Q("50"), D_MAY_03)
    _receive(env, WH_B, "ITN", Q("10"), Q("14"), D_MAY_05)
    _reconcile(env, WH_B, "ITN", Q("12"), Q("148"), Q("12.333333333"), D_MAY_10)

    referencia = _svl_stream("ITN", WH_B)
    assert len(referencia) == 5

    rebuild = rebuild_stock_valuation_layers(COMPANY, item_code="ITF")
    assert rebuild.rebuilt_layers == len(referencia)
    assert _svl_stream("ITF", WH_A) == referencia

    _deliver(env, WH_A, "ITF", Q("1"), Q("50"), D_MAY_15)
    _deliver(env, WH_B, "ITN", Q("1"), Q("50"), D_MAY_15)
    costo_itf = _sle_totals(env, "ITF", WH_A)[1]
    costo_itn = _sle_totals(env, "ITN", WH_B)[1]
    assert costo_itf == costo_itn
    if env["method"] == "fifo":
        venta_itf = database.session.execute(
            select(StockLedgerEntry).where(
                StockLedgerEntry.company == COMPANY,
                StockLedgerEntry.item_code == "ITF",
                StockLedgerEntry.voucher_type == "delivery_note",
                StockLedgerEntry.posting_date == D_MAY_15,
            )
        ).scalar_one()
        assert -_dec(venta_itf.stock_value_difference) == Q("9")
    _assert_consistency(env, [("ITF", WH_A, env["inv_a_id"])])
