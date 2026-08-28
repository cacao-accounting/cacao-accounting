# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas unitarias exhaustivas y robustas para la gestión de inventarios y el Kardex del sistema.

Cubre:
1. Recepción de Órdenes de Compra (PurchaseReceipt)
2. Remisión de Facturas o Notas de Venta (DeliveryNote)
3. Traslados entre inventarios (StockEntry: material_transfer)
4. Entradas de inventario en todas sus variantes (material_receipt, adjustment_positive, stock_adjustment)
5. Ajustes negativos/positivos de valores (qty == 0, amount != 0)
6. Ajustes negativos/positivos de cantidades (material_issue, adjustment_negative)
7. Ajustes por inventario / Conciliación de inventario (stock_reconciliation)
8. Kardex de inventario confiable (StockLedgerEntry, cancelaciones, rebuild_stock_bins, rebuild_stock_valuation_layers)
"""

from decimal import Decimal
from datetime import date
import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    database,
    Entity,
    Item,
    Warehouse,
    WarehouseCompanyAccount,
    UOM,
    Accounts,
    Book,
    CompanyDefaultAccount,
    User,
    AccountingPeriod,
    StockEntry,
    StockEntryItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    DeliveryNote,
    DeliveryNoteItem,
    StockBin,
    StockLedgerEntry,
    StockValuationLayer,
    GLEntry,
)
from cacao_accounting.contabilidad.posting import (
    PostingError,
    submit_document,
    cancel_document,
)
from cacao_accounting.inventario.service import (
    rebuild_stock_bins,
    rebuild_stock_valuation_layers,
)


@pytest.fixture()
def app():
    test_app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with test_app.app_context():
        database.create_all()
        yield test_app


def _setup_inventory_test_data(app):
    """Inicializa datos maestros para pruebas de inventario."""
    with app.app_context():
        # Clean existing data
        database.session.query(GLEntry).delete()
        database.session.query(StockLedgerEntry).delete()
        database.session.query(StockValuationLayer).delete()
        database.session.query(StockBin).delete()
        database.session.query(DeliveryNoteItem).delete()
        database.session.query(DeliveryNote).delete()
        database.session.query(PurchaseReceiptItem).delete()
        database.session.query(PurchaseReceipt).delete()
        database.session.query(StockEntryItem).delete()
        database.session.query(StockEntry).delete()
        database.session.commit()

        # Company
        company = database.session.get(Entity, "cacao")
        if not company:
            company = Entity(
                code="cacao",
                name="Cacao Company",
                company_name="Cacao SA",
                tax_id="J0001",
                valuation_method="moving_average",
                currency="NIO",
            )
            database.session.add(company)

        # Primary Book
        book = database.session.get(Book, "primary")
        if not book:
            book = Book(
                code="primary", name="Libro Primario", entity="cacao", status="activo", is_primary=True, currency="NIO"
            )
            database.session.add(book)

        # UOM
        uom = database.session.get(UOM, "UND")
        if not uom:
            uom = UOM(code="UND", name="Unidad")
            database.session.add(uom)

        # Accounts
        for acc_id, acc_code, acc_name, acc_type in [
            ("1100-INV-MAIN", "1100-INV-MAIN", "Inventario Principal", "Asset"),
            ("1100-INV-SEC", "1100-INV-SEC", "Inventario Secundario", "Asset"),
            ("2100-BRIDGE", "2100-BRIDGE", "Cuenta Puente Compras", "Liability"),
            ("5100-COGS", "5100-COGS", "Costo de Ventas", "Expense"),
            ("5200-ADJ", "5200-ADJ", "Ajustes de Inventario", "Expense"),
        ]:
            if not database.session.get(Accounts, acc_id):
                database.session.add(
                    Accounts(
                        id=acc_id,
                        code=acc_code,
                        name=acc_name,
                        account_type=acc_type,
                        entity="cacao",
                        currency="NIO",
                        status="activo",
                    )
                )

        # Company Defaults
        if not database.session.get(User, "test-user"):
            database.session.add(
                User(id="test-user", user="test-user", name="Test User", password=b"x", classification="admin", active=True)
            )
        if not database.session.execute(database.select(AccountingPeriod).filter_by(entity="cacao", name="2026-05")).scalar_one_or_none():
            database.session.add(
                AccountingPeriod(
                    entity="cacao",
                    name="2026-05",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                )
            )

        defaults = database.session.execute(
            database.select(CompanyDefaultAccount).filter_by(company="cacao")
        ).scalar_one_or_none()
        if not defaults:
            defaults = CompanyDefaultAccount(
                company="cacao",
                default_cogs="5100-COGS",
                inventory_adjustment_account_id="5200-ADJ",
                bridge_account_id="2100-BRIDGE",
            )
            database.session.add(defaults)
        else:
            defaults.default_cogs = "5100-COGS"
            defaults.inventory_adjustment_account_id = "5200-ADJ"
            defaults.bridge_account_id = "2100-BRIDGE"

        # Warehouses
        wh_main = database.session.execute(database.select(Warehouse).filter_by(code="WH-MAIN")).scalar_one_or_none()
        if not wh_main:
            wh_main = Warehouse(code="WH-MAIN", name="Bodega Principal", company="cacao", is_active=True)
            database.session.add(wh_main)
            database.session.add(
                WarehouseCompanyAccount(warehouse_code="WH-MAIN", company="cacao", inventory_account_id="1100-INV-MAIN")
            )

        wh_sec = database.session.execute(database.select(Warehouse).filter_by(code="WH-SEC")).scalar_one_or_none()
        if not wh_sec:
            wh_sec = Warehouse(code="WH-SEC", name="Bodega Secundaria", company="cacao", is_active=True)
            database.session.add(wh_sec)
            database.session.add(
                WarehouseCompanyAccount(warehouse_code="WH-SEC", company="cacao", inventory_account_id="1100-INV-SEC")
            )

        # Items
        item_goods = database.session.get(Item, "ITEM-GOODS")
        if not item_goods:
            item_goods = Item(
                code="ITEM-GOODS",
                name="Artículo de Inventario",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                allow_negative_stock=False,
            )
            database.session.add(item_goods)

        item_svc = database.session.get(Item, "ITEM-SVC")
        if not item_svc:
            item_svc = Item(
                code="ITEM-SVC",
                name="Servicio de Transporte",
                item_type="service",
                is_stock_item=False,
                default_uom="UND",
            )
            database.session.add(item_svc)

        database.session.commit()


def _create_and_submit_stock_entry(
    purpose: str,
    posting_date: date,
    item_code: str,
    qty: Decimal,
    target_warehouse: str | None = None,
    source_warehouse: str | None = None,
    valuation_rate: Decimal | None = None,
    amount: Decimal | None = None,
    adjustment_account_id: str | None = None,
    counted_qty: Decimal | None = None,
    target_stock_value: Decimal | None = None,
    target_valuation_rate: Decimal | None = None,
) -> StockEntry:
    """Helper para crear y aprobar una entrada de stock."""
    se = StockEntry(
        company="cacao",
        docstatus=0,
        posting_date=posting_date,
        purpose=purpose,
        from_warehouse=source_warehouse,
        to_warehouse=target_warehouse,
        adjustment_account_id=adjustment_account_id,
        transaction_currency="NIO",
        base_currency="NIO",
    )
    database.session.add(se)
    database.session.flush()

    item_kwargs = {
        "stock_entry_id": se.id,
        "item_code": item_code,
        "qty": qty,
        "uom": "UND",
        "target_warehouse": target_warehouse,
        "source_warehouse": source_warehouse,
    }
    if valuation_rate is not None:
        item_kwargs["valuation_rate"] = valuation_rate
    if amount is not None:
        item_kwargs["amount"] = amount
    if counted_qty is not None:
        item_kwargs["counted_qty"] = counted_qty
    if target_stock_value is not None:
        item_kwargs["target_stock_value"] = target_stock_value
    if target_valuation_rate is not None:
        item_kwargs["target_valuation_rate"] = target_valuation_rate

    database.session.add(StockEntryItem(**item_kwargs))
    database.session.commit()
    submit_document(se)
    return se


def _get_bin(warehouse: str = "WH-MAIN", item_code: str = "ITEM-GOODS") -> StockBin:
    """Obtiene la fila de StockBin para las aserciones."""
    return database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code=item_code, warehouse=warehouse)
    ).scalar_one()


def test_valuation_layer_rebuild_dry_run_does_not_mutate_existing_layers(app):
    """Dry runs must preview rebuilt layers without deleting FIFO evidence."""
    _setup_inventory_test_data(app)
    with app.app_context():
        existing = StockValuationLayer(
            id="SVL-DRY-RUN-EXISTING",
            item_code="ITEM-GOODS",
            warehouse="WH-MAIN",
            company="cacao",
            qty=Decimal("3"),
            rate=Decimal("11"),
            remaining_qty=Decimal("3"),
            remaining_stock_value=Decimal("33"),
            voucher_type="seed",
            voucher_id="SEED-DRY-RUN",
            posting_date=date(2026, 1, 1),
        )
        database.session.add_all(
            [
                existing,
                StockLedgerEntry(
                    id="SLE-DRY-RUN",
                    company="cacao",
                    posting_date=date(2026, 1, 1),
                    item_code="ITEM-GOODS",
                    warehouse="WH-MAIN",
                    qty_change=Decimal("3"),
                    qty_after_transaction=Decimal("3"),
                    valuation_rate=Decimal("10"),
                    stock_value_difference=Decimal("30"),
                    stock_value=Decimal("30"),
                    voucher_type="seed",
                    voucher_id="SEED-DRY-RUN",
                ),
            ]
        )
        database.session.commit()

        result = rebuild_stock_valuation_layers("cacao", item_code="ITEM-GOODS", dry_run=True)
        layers = (
            database.session.execute(database.select(StockValuationLayer).filter_by(company="cacao", item_code="ITEM-GOODS"))
            .scalars()
            .all()
        )

        assert result.rebuilt_layers == 1
        assert [layer.id for layer in layers] == [existing.id]
        assert layers[0].rate == Decimal("11")


def test_valuation_layer_rebuild_preserva_capa_huerfana_sin_ledger(app):
    """El rebuild conserva capas de ajuste sin movimiento en el ledger (issue #750).

    Los costos capitalizables publican capas qty=0 con comprobante propio sin
    StockLedgerEntry; tras reconstruir deben sobrevivir en su posicion
    cronologica y el consumo conserva su capa origen fijada.
    """
    _setup_inventory_test_data(app)
    with app.app_context():
        receipt = StockValuationLayer(
            id="SVL-ORPHAN-RECEIPT",
            item_code="ITEM-GOODS",
            warehouse="WH-MAIN",
            company="cacao",
            qty=Decimal("10"),
            rate=Decimal("10"),
            stock_value_difference=Decimal("100"),
            remaining_qty=Decimal("10"),
            remaining_stock_value=Decimal("100"),
            voucher_type="seed",
            voucher_id="SEED-RECEIPT",
            posting_date=date(2026, 1, 1),
        )
        orphan = StockValuationLayer(
            id="SVL-ORPHAN-LANDING",
            item_code="ITEM-GOODS",
            warehouse="WH-MAIN",
            company="cacao",
            qty=Decimal("0"),
            rate=Decimal("11"),
            stock_value_difference=Decimal("20"),
            remaining_qty=Decimal("10"),
            remaining_stock_value=Decimal("120"),
            voucher_type="purchase_invoice",
            voucher_id="SEED-LANDING",
            posting_date=date(2026, 1, 2),
        )
        consumption = StockValuationLayer(
            id="SVL-ORPHAN-CONSUMPTION",
            item_code="ITEM-GOODS",
            warehouse="WH-MAIN",
            company="cacao",
            qty=Decimal("-3"),
            rate=Decimal("10"),
            stock_value_difference=Decimal("-30"),
            remaining_qty=Decimal("7"),
            remaining_stock_value=Decimal("90"),
            voucher_type="seed",
            voucher_id="SEED-DELIVERY",
            posting_date=date(2026, 1, 3),
            source_layer_id="SVL-ORPHAN-RECEIPT",
        )
        database.session.add_all([receipt, orphan, consumption])
        database.session.add_all(
            [
                StockLedgerEntry(
                    id="SLE-ORPHAN-RECEIPT",
                    company="cacao",
                    posting_date=date(2026, 1, 1),
                    item_code="ITEM-GOODS",
                    warehouse="WH-MAIN",
                    qty_change=Decimal("10"),
                    qty_after_transaction=Decimal("10"),
                    valuation_rate=Decimal("10"),
                    stock_value_difference=Decimal("100"),
                    stock_value=Decimal("100"),
                    voucher_type="seed",
                    voucher_id="SEED-RECEIPT",
                ),
                StockLedgerEntry(
                    id="SLE-ORPHAN-DELIVERY",
                    company="cacao",
                    posting_date=date(2026, 1, 3),
                    item_code="ITEM-GOODS",
                    warehouse="WH-MAIN",
                    qty_change=Decimal("-3"),
                    qty_after_transaction=Decimal("7"),
                    valuation_rate=Decimal("10"),
                    stock_value_difference=Decimal("-30"),
                    stock_value=Decimal("70"),
                    voucher_type="seed",
                    voucher_id="SEED-DELIVERY",
                ),
            ]
        )
        database.session.commit()

        result = rebuild_stock_valuation_layers("cacao", item_code="ITEM-GOODS")
        assert result.rebuilt_layers == 3

        layers = (
            database.session.execute(
                database.select(StockValuationLayer).order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
            )
            .scalars()
            .all()
        )
        assert [(layer.voucher_type, layer.qty) for layer in layers] == [
            ("seed", Decimal("10")),
            ("purchase_invoice", Decimal("0")),
            ("seed", Decimal("-3")),
        ]
        assert layers[0].stock_value_difference == Decimal("100")
        assert layers[1].stock_value_difference == Decimal("20")
        assert layers[1].source_layer_id is None
        assert layers[2].stock_value_difference == Decimal("-30")
        assert layers[2].source_layer_id == layers[0].id


def test_01_recepcion_ordenes_compra(app):
    """Prueba de Recepción de Compras (PurchaseReceipt) con mercancías y servicios."""
    _setup_inventory_test_data(app)
    with app.app_context():
        pr = PurchaseReceipt(
            company="cacao",
            docstatus=0,
            posting_date=date(2026, 5, 1),
            supplier_id="SUP-001",
            status="Borrador",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(pr)
        database.session.flush()

        item_stock = PurchaseReceiptItem(
            purchase_receipt_id=pr.id,
            item_code="ITEM-GOODS",
            qty=Decimal("10.0"),
            uom="UND",
            rate=Decimal("100.00"),
            amount=Decimal("1000.00"),
            warehouse="WH-MAIN",
        )
        item_service = PurchaseReceiptItem(
            purchase_receipt_id=pr.id,
            item_code="ITEM-SVC",
            qty=Decimal("1.0"),
            uom="UND",
            rate=Decimal("200.00"),
            amount=Decimal("200.00"),
            warehouse="WH-MAIN",
        )
        database.session.add_all([item_stock, item_service])
        database.session.commit()

        submit_document(pr)

        sle_list = (
            database.session.execute(
                database.select(StockLedgerEntry).filter_by(voucher_type="purchase_receipt", voucher_id=pr.id)
            )
            .scalars()
            .all()
        )
        assert len(sle_list) == 1
        sle = sle_list[0]
        assert sle.item_code == "ITEM-GOODS"
        assert sle.warehouse == "WH-MAIN"
        assert sle.qty_change == Decimal("10.0")
        assert sle.stock_value == Decimal("1000.00")
        assert sle.valuation_rate == Decimal("100.00")

        bin_row = _get_bin()
        assert bin_row.actual_qty == Decimal("10.0")
        assert bin_row.stock_value == Decimal("1000.00")
        assert bin_row.valuation_rate == Decimal("100.00")

        svl = database.session.execute(
            database.select(StockValuationLayer).filter_by(voucher_type="purchase_receipt", voucher_id=pr.id)
        ).scalar_one()
        assert svl.qty == Decimal("10.0")
        assert svl.stock_value_difference == Decimal("1000.00")


def test_02_remision_facturas_notas_venta(app):
    """Prueba de Remisión de Facturas / Notas de Entrega (DeliveryNote)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("20.0"),
            valuation_rate=Decimal("50.00"),
            amount=Decimal("1000.00"),
            target_warehouse="WH-MAIN",
        )

        dn = DeliveryNote(
            company="cacao",
            docstatus=0,
            posting_date=date(2026, 5, 2),
            customer_id="CUST-001",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(dn)
        database.session.flush()
        database.session.add(
            DeliveryNoteItem(
                delivery_note_id=dn.id,
                item_code="ITEM-GOODS",
                qty=Decimal("5.0"),
                uom="UND",
                rate=Decimal("80.00"),
                amount=Decimal("400.00"),
                warehouse="WH-MAIN",
            )
        )
        database.session.commit()

        submit_document(dn)

        sle_list = (
            database.session.execute(
                database.select(StockLedgerEntry).filter_by(voucher_type="delivery_note", voucher_id=dn.id)
            )
            .scalars()
            .all()
        )
        assert len(sle_list) == 1
        sle = sle_list[0]
        assert sle.qty_change == Decimal("-5.0")
        assert sle.qty_after_transaction == Decimal("15.0")
        assert sle.stock_value_difference == Decimal("-250.00")

        bin_row = _get_bin()
        assert bin_row.actual_qty == Decimal("15.0")
        assert bin_row.stock_value == Decimal("750.00")


def test_03_traslados_entre_inventarios(app):
    """Prueba de Traslados de inventario entre bodegas (material_transfer)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("10.0"),
            valuation_rate=Decimal("100.00"),
            amount=Decimal("1000.00"),
            target_warehouse="WH-MAIN",
        )

        se_tr = _create_and_submit_stock_entry(
            purpose="material_transfer",
            posting_date=date(2026, 5, 3),
            item_code="ITEM-GOODS",
            qty=Decimal("4.0"),
            source_warehouse="WH-MAIN",
            target_warehouse="WH-SEC",
        )

        sles = (
            database.session.execute(
                database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=se_tr.id)
            )
            .scalars()
            .all()
        )
        assert len(sles) == 2
        sle_out = next(s for s in sles if s.warehouse == "WH-MAIN")
        sle_in = next(s for s in sles if s.warehouse == "WH-SEC")

        assert sle_out.qty_change == Decimal("-4.0")
        assert sle_out.stock_value_difference == Decimal("-400.00")
        assert sle_in.qty_change == Decimal("4.0")
        assert sle_in.stock_value_difference == Decimal("400.00")

        assert _get_bin("WH-MAIN").actual_qty == Decimal("6.0")
        assert _get_bin("WH-SEC").actual_qty == Decimal("4.0")


def test_material_transfer_rejects_the_same_source_and_target_warehouse(app):
    """A same-warehouse transfer must not reorder FIFO valuation layers."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("10"),
            valuation_rate=Decimal("100"),
            amount=Decimal("1000"),
            target_warehouse="WH-MAIN",
        )

        with pytest.raises(PostingError, match="bodegas de origen y destino distintas"):
            _create_and_submit_stock_entry(
                purpose="material_transfer",
                posting_date=date(2026, 5, 3),
                item_code="ITEM-GOODS",
                qty=Decimal("4"),
                source_warehouse="WH-MAIN",
                target_warehouse="WH-MAIN",
            )


def test_05_ajustes_valores_positivos_negativos(app):
    """Prueba de Ajustes Negativos / Positivos de Valor (revaluaciones con qty == 0)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("10.0"),
            valuation_rate=Decimal("100.00"),
            amount=Decimal("1000.00"),
            target_warehouse="WH-MAIN",
        )

        _create_and_submit_stock_entry(
            purpose="adjustment_positive",
            posting_date=date(2026, 5, 2),
            item_code="ITEM-GOODS",
            qty=Decimal("0"),
            amount=Decimal("200.00"),
            target_warehouse="WH-MAIN",
            adjustment_account_id="5200-ADJ",
        )

        bin_row = _get_bin()
        assert bin_row.actual_qty == Decimal("10.0")
        assert bin_row.stock_value == Decimal("1200.00")
        assert bin_row.valuation_rate == Decimal("120.00")


def test_06_ajustes_cantidades_positivos_negativos(app):
    """Prueba de Ajustes Negativos / Positivos de Cantidad (material_issue / adjustment_negative)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("10.0"),
            valuation_rate=Decimal("100.00"),
            amount=Decimal("1000.00"),
            target_warehouse="WH-MAIN",
        )

        _create_and_submit_stock_entry(
            purpose="material_issue",
            posting_date=date(2026, 5, 2),
            item_code="ITEM-GOODS",
            qty=Decimal("3.0"),
            source_warehouse="WH-MAIN",
        )

        bin_row = _get_bin()
        assert bin_row.actual_qty == Decimal("7.0")
        assert bin_row.stock_value == Decimal("700.00")


def test_07_ajustes_por_inventario(app):
    """Prueba de Ajuste por Inventario / Conciliación Física (stock_reconciliation)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("10.0"),
            valuation_rate=Decimal("100.00"),
            amount=Decimal("1000.00"),
            target_warehouse="WH-MAIN",
        )

        _create_and_submit_stock_entry(
            purpose="stock_reconciliation",
            posting_date=date(2026, 5, 5),
            item_code="ITEM-GOODS",
            qty=Decimal("2.0"),
            counted_qty=Decimal("12.0"),
            target_stock_value=Decimal("1320.00"),
            target_valuation_rate=Decimal("110.00"),
            target_warehouse="WH-MAIN",
            adjustment_account_id="5200-ADJ",
        )

        bin_row = _get_bin()
        assert bin_row.actual_qty == Decimal("12.0")
        assert bin_row.stock_value == Decimal("1320.00")
        assert bin_row.valuation_rate == Decimal("110.00")


def test_08_kardex_confiable_y_reconstructibilidad(app):
    """Prueba de Confiabilidad del Kardex, Cancelación de Documentos y Reconstrucción de Bins/Layers."""
    _setup_inventory_test_data(app)
    with app.app_context():
        _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            item_code="ITEM-GOODS",
            qty=Decimal("10.0"),
            valuation_rate=Decimal("100.00"),
            amount=Decimal("1000.00"),
            target_warehouse="WH-MAIN",
        )

        se2 = _create_and_submit_stock_entry(
            purpose="material_receipt",
            posting_date=date(2026, 5, 2),
            item_code="ITEM-GOODS",
            qty=Decimal("5.0"),
            valuation_rate=Decimal("120.00"),
            amount=Decimal("600.00"),
            target_warehouse="WH-MAIN",
        )

        assert _get_bin().actual_qty == Decimal("15.0")
        assert _get_bin().stock_value == Decimal("1600.00")

        cancel_document(se2, reason="Corrección de inventario", actor_user_id="test-user")

        assert _get_bin().actual_qty == Decimal("10.0")
        assert _get_bin().stock_value == Decimal("1000.00")

        rebuild_res = rebuild_stock_bins(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        assert rebuild_res.rebuilt_bins == 1
        assert len(rebuild_res.inconsistencies) == 0

        assert _get_bin().actual_qty == Decimal("10.0")
        assert _get_bin().stock_value == Decimal("1000.00")
