# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1873: valor sin existencias y regularización de residuos de inventario."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _persist_single_allocation,
    cancel_document,
    post_stock_entry,
)
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.internal_control_service import audit_actor
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    ExchangeRate,
    GLEntry,
    ImportLandedCost,
    ImportLandedCostItem,
    Item,
    LandedCostAllocation,
    PurchaseInvoice,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerBookEntry,
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


def _preparar_libros_multimoneda(app) -> list[tuple[str, str]]:
    """Configura libros NIO/USD y una tasa histórica para el escenario aislado."""
    with app.app_context():
        usd = database.session.execute(database.select(Currency).filter_by(code="USD")).scalar_one_or_none()
        if usd is None:
            database.session.add(Currency(code="USD", name="Dólar", decimals=2, active=True, default=False))
            database.session.flush()

        books = (
            database.session.execute(
                database.select(Book).filter_by(entity="cacao", status="activo").order_by(Book.is_primary.desc(), Book.code)
            )
            .scalars()
            .all()
        )
        assert len(books) >= 2
        for book in books:
            book.currency = "NIO" if book.is_primary else "USD"

        rate = database.session.execute(
            database.select(ExchangeRate).filter_by(origin="NIO", destination="USD", date=FECHA)
        ).scalar_one_or_none()
        if rate is None:
            rate = ExchangeRate(origin="NIO", destination="USD", date=FECHA, rate=Decimal("1") / Decimal("36"))
            database.session.add(rate)
        else:
            rate.rate = Decimal("1") / Decimal("36")
        database.session.commit()
        return [(str(book.id), str(book.currency)) for book in books]


def _registrar_stock_ledger_inicial(app, item_code: str, warehouse: str, books: list[tuple[str, str]]) -> None:
    """Añade el movimiento append-only que respalda el saldo inicial sembrado."""
    with app.app_context():
        layer = database.session.execute(
            database.select(StockValuationLayer).filter_by(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse,
                voucher_type="seed",
            )
        ).scalar_one()
        movement = StockLedgerEntry(
            posting_date=FECHA,
            item_code=item_code,
            warehouse=warehouse,
            company="cacao",
            qty_change=Decimal("100"),
            qty_after_transaction=Decimal("100"),
            valuation_rate=Decimal("100"),
            stock_value_difference=Decimal("10000"),
            stock_value=Decimal("10000"),
            voucher_type=layer.voucher_type,
            voucher_id=layer.voucher_id,
        )
        database.session.add(movement)
        database.session.flush()
        for ledger_id, currency in books:
            book_rate = Decimal("1") if currency == "NIO" else Decimal("1") / Decimal("36")
            database.session.add(
                StockLedgerBookEntry(
                    stock_ledger_entry_id=movement.id,
                    ledger_id=ledger_id,
                    posting_date=FECHA,
                    book_currency=currency,
                    book_amount=(Decimal("10000") * book_rate).quantize(Decimal("0.0001")),
                    exchange_rate=book_rate,
                )
            )
        database.session.commit()


def _crear_landed_cost_capitalizado(
    app,
    item_code: str,
    warehouse: str,
    books: list[tuple[str, str]],
    *,
    split_allocations: bool = False,
) -> str:
    """Crea una capitalización USD/NIO con GL balanceado en cada libro activo."""
    with app.app_context():
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            document_type="purchase_invoice",
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36"),
            docstatus=0,
        )
        database.session.add(invoice)
        database.session.flush()
        document = ImportLandedCost(
            company="cacao",
            purchase_invoice_id=invoice.id,
            posting_date=FECHA,
            document_type="import_landed_cost",
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36"),
            docstatus=1,
        )
        database.session.add(document)
        database.session.flush()
        line_count = 2 if split_allocations else 1
        line_qty = Decimal("100") / line_count
        allocated_amount = Decimal("100") / line_count
        functional_amount = Decimal("3600") / line_count
        unit_inventory_cost = Decimal("100") + functional_amount / line_qty
        for _ in range(line_count):
            line = ImportLandedCostItem(
                import_landed_cost_id=document.id,
                item_code=item_code,
                item_name="Artículo con costo capitalizado",
                qty=line_qty,
                uom="UND",
                rate=Decimal("1"),
                amount=Decimal("100") / line_count,
                base_rate=Decimal("36"),
                base_amount=functional_amount,
                warehouse=warehouse,
            )
            database.session.add(line)
            database.session.flush()
            _persist_single_allocation(
                document=document,
                allocation=SimpleNamespace(
                    item_line_id=line.id,
                    allocated_total=allocated_amount,
                    base_amount=functional_amount,
                    final_inventory_cost=line_qty * unit_inventory_cost,
                    unit_inventory_cost=unit_inventory_cost,
                    allocated_costs=[],
                ),
                items_by_line_id={str(line.id): line},
                create_valuation_adjustment=True,
            )
        database.session.flush()

        inventory = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        offset = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        for ledger_id, currency in books:
            book_amount = Decimal("3600") if currency == "NIO" else Decimal("100")
            for account, debit, credit in (
                (inventory, book_amount, Decimal("0")),
                (offset, Decimal("0"), book_amount),
            ):
                database.session.add(
                    GLEntry(
                        posting_date=FECHA,
                        company="cacao",
                        ledger_id=ledger_id,
                        account_id=account.id,
                        account_code=account.code,
                        debit=debit,
                        credit=credit,
                        debit_in_account_currency=debit,
                        credit_in_account_currency=credit,
                        account_currency=currency,
                        company_currency=currency,
                        exchange_rate=Decimal("1"),
                        voucher_type="import_landed_cost",
                        voucher_id=document.id,
                        is_cancelled=False,
                    )
                )
        database.session.commit()
        return str(document.id)


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
    """Sin diferencia de valor no se crea una regularización extra."""
    app = entorno_contable_aislado.app
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


def test_reversion_de_documento_regularizado_no_falla(entorno_contable_aislado):
    """La reversa también atraviesa la regularización de residuo append-only."""
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
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name), approved_execution(entrada, actor.id):
            cancel_document(
                entrada,
                reason="Reversa del residuo",
                actor_user_id=actor.id,
                cancellation_date=FECHA,
            )
        database.session.commit()
        bin_final = database.session.execute(
            database.select(StockBin).filter_by(item_code=codigo_item, warehouse=codigo_bodega)
        ).scalar_one()
        assert bin_final.actual_qty == Decimal("1")
        assert bin_final.stock_value == Decimal("10.0001")


@pytest.mark.parametrize("valuation_method", ["fifo", "moving_average"])
@pytest.mark.parametrize(
    ("consumed_qty", "expected_qty", "expected_value"),
    [("40", Decimal("60"), Decimal("8160")), ("100", Decimal("0"), Decimal("0"))],
)
def test_cancelar_landed_cost_con_consumo_bloquea_atomico(
    entorno_contable_aislado,
    valuation_method,
    consumed_qty,
    expected_qty,
    expected_value,
):
    """Un consumo posterior bloquea la cancelación si no se puede repartir el costo por libro."""
    app = entorno_contable_aislado.app
    books = _preparar_libros_multimoneda(app)
    with app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        entity.valuation_method = valuation_method
        database.session.commit()
    item_code, warehouse = _escenario(app, qty="100", stock_value="10000", layer_value="10000")
    _registrar_stock_ledger_inicial(app, item_code, warehouse, books)
    landed_cost_id = _crear_landed_cost_capitalizado(app, item_code, warehouse, books, split_allocations=True)

    with app.app_context():
        landed_cost = database.session.get(ImportLandedCost, landed_cost_id)
        assert landed_cost is not None
        entry = _entrada(
            item_code,
            warehouse,
            "adjustment_negative",
            consumed_qty,
            str(Decimal(consumed_qty) * Decimal("136")),
        )
        _postear(app, entry)
        database.session.commit()
        item_bin = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
        ).scalar_one()
        assert item_bin.actual_qty == expected_qty
        assert item_bin.stock_value == expected_value

        layer_ids_before = set(
            database.session.execute(
                database.select(StockValuationLayer.id).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        movement_ids_before = set(
            database.session.execute(
                database.select(StockLedgerEntry.id).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        book_entry_ids_before = set(
            database.session.execute(
                database.select(StockLedgerBookEntry.id)
                .join(StockLedgerEntry, StockLedgerEntry.id == StockLedgerBookEntry.stock_ledger_entry_id)
                .filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        original_gl_ids = set(
            database.session.execute(
                database.select(GLEntry.id).filter_by(voucher_type="import_landed_cost", voucher_id=landed_cost_id)
            )
            .scalars()
            .all()
        )
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        with audit_actor(actor.id, actor.name), approved_execution(landed_cost, actor.id):
            with pytest.raises(PostingError, match="evidencia disponible no permite reconstruir"):
                cancel_document(
                    landed_cost,
                    reason="No se puede distribuir costo consumido por libro",
                    actor_user_id=actor.id,
                    cancellation_date=FECHA,
                )
        database.session.rollback()

        cancelled_document = database.session.get(ImportLandedCost, landed_cost_id)
        assert cancelled_document is not None
        assert cancelled_document.docstatus == 1
        bin_after = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
        ).scalar_one()
        assert (bin_after.actual_qty, bin_after.stock_value) == (expected_qty, expected_value)
        assert (
            set(
                database.session.execute(
                    database.select(StockValuationLayer.id).filter_by(
                        company="cacao", item_code=item_code, warehouse=warehouse
                    )
                )
                .scalars()
                .all()
            )
            == layer_ids_before
        )
        assert (
            set(
                database.session.execute(
                    database.select(StockLedgerEntry.id).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
                )
                .scalars()
                .all()
            )
            == movement_ids_before
        )
        assert (
            set(
                database.session.execute(
                    database.select(StockLedgerBookEntry.id)
                    .join(StockLedgerEntry, StockLedgerEntry.id == StockLedgerBookEntry.stock_ledger_entry_id)
                    .filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
                )
                .scalars()
                .all()
            )
            == book_entry_ids_before
        )
        landed_cost_gl = (
            database.session.execute(
                database.select(GLEntry).filter_by(voucher_type="import_landed_cost", voucher_id=landed_cost_id)
            )
            .scalars()
            .all()
        )
        assert {entry.id for entry in landed_cost_gl if not entry.is_reversal} == original_gl_ids
        assert all(not entry.is_cancelled for entry in landed_cost_gl)
        assert all(not entry.is_reversal for entry in landed_cost_gl)


def test_cancelar_landed_cost_sin_consumo_reversa_por_libro_y_moneda(entorno_contable_aislado):
    """Con trazabilidad completa, revierte solo el costo aún disponible por libro."""
    app = entorno_contable_aislado.app
    books = _preparar_libros_multimoneda(app)
    item_code, warehouse = _escenario(app, qty="100", stock_value="10000", layer_value="10000")
    _registrar_stock_ledger_inicial(app, item_code, warehouse, books)
    landed_cost_id = _crear_landed_cost_capitalizado(app, item_code, warehouse, books, split_allocations=True)

    with app.app_context():
        landed_cost = database.session.get(ImportLandedCost, landed_cost_id)
        assert landed_cost is not None
        original_layer_ids = set(
            database.session.execute(
                database.select(LandedCostAllocation.stock_valuation_layer_id).filter_by(document_id=landed_cost_id)
            )
            .scalars()
            .all()
        )
        assert len(original_layer_ids) == 2
        stock_movements_before = (
            database.session.execute(
                database.select(StockLedgerEntry.id).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        book_entries_before = (
            database.session.execute(
                database.select(StockLedgerBookEntry.id)
                .join(StockLedgerEntry, StockLedgerEntry.id == StockLedgerBookEntry.stock_ledger_entry_id)
                .filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        with audit_actor(actor.id, actor.name), approved_execution(landed_cost, actor.id):
            cancel_document(
                landed_cost,
                reason="Revertir costo capitalizado aún disponible",
                actor_user_id=actor.id,
                cancellation_date=FECHA,
            )
        database.session.commit()

        assert landed_cost.docstatus == 2
        item_bin = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
        ).scalar_one()
        assert item_bin.actual_qty == Decimal("100")
        assert item_bin.stock_value == Decimal("10000")

        cost_layers = (
            database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=landed_cost_id)).scalars().all()
        )
        assert len(cost_layers) == 4
        reversal_layers = [layer for layer in cost_layers if layer.id not in original_layer_ids]
        assert len(reversal_layers) == 2
        assert sum((layer.stock_value_difference for layer in reversal_layers), Decimal("0")) == Decimal("-3600")
        assert all(layer.remaining_qty == Decimal("100") for layer in reversal_layers)
        assert {layer.remaining_stock_value for layer in reversal_layers} == {Decimal("10000"), Decimal("11800")}
        assert sum((layer.stock_value_difference for layer in cost_layers), Decimal("0")) == Decimal("0")
        assert sum(
            (layer.stock_value_difference for layer in cost_layers if layer.id in original_layer_ids), Decimal("0")
        ) == Decimal("3600")

        stock_movements_after = (
            database.session.execute(
                database.select(StockLedgerEntry.id).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        book_entries_after = (
            database.session.execute(
                database.select(StockLedgerBookEntry.id)
                .join(StockLedgerEntry, StockLedgerEntry.id == StockLedgerBookEntry.stock_ledger_entry_id)
                .filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
            )
            .scalars()
            .all()
        )
        assert stock_movements_after == stock_movements_before
        assert book_entries_after == book_entries_before

        gl_entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(voucher_type="import_landed_cost", voucher_id=landed_cost_id)
            )
            .scalars()
            .all()
        )
        totals_by_book: dict[str, list[Decimal]] = {}
        for row in gl_entries:
            totals_by_book.setdefault(str(row.ledger_id), [Decimal("0"), Decimal("0")])
            totals_by_book[str(row.ledger_id)][0] += row.debit
            totals_by_book[str(row.ledger_id)][1] += row.credit
        assert set(totals_by_book) == {ledger_id for ledger_id, _currency in books}
        for debit, credit in totals_by_book.values():
            assert debit == credit
        for ledger_id, currency in books:
            original_inventory = next(
                row for row in gl_entries if row.ledger_id == ledger_id and row.account_code == "1109" and not row.is_reversal
            )
            reversal_inventory = next(
                row for row in gl_entries if row.ledger_id == ledger_id and row.account_code == "1109" and row.is_reversal
            )
            assert reversal_inventory.reversal_of == original_inventory.id
            assert reversal_inventory.credit == original_inventory.debit
            assert original_inventory.debit == (Decimal("3600") if currency == "NIO" else Decimal("100"))

        with audit_actor(actor.id, actor.name), approved_execution(landed_cost, actor.id):
            with pytest.raises(PostingError, match="documento aprobado"):
                cancel_document(
                    landed_cost,
                    reason="Reintento de cancelación",
                    actor_user_id=actor.id,
                    cancellation_date=FECHA,
                )
