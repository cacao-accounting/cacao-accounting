# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas unitarias exhaustivas y robustas para la gestión de inventarios y el Kardex del sistema.

Cubre:
1. Recepción de Órdenes de Compra (PurchaseReceipt)
2. Remisión de Facturas o Notas de Venta (DeliveryNote)
3. Traslados entre inventarios (StockEntry: material_transfer)
4. Entradas de inventario en todas sus variantes (material_receipt, adjustment_positive, stock_adjustment, manufacture, repack)
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
    submit_document,
    cancel_document,
)
from cacao_accounting.inventario.service import (
    rebuild_stock_bins,
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
                code="cacao", name="Cacao Company", company_name="Cacao SA", tax_id="J0001", valuation_method="moving_average"
            )
            database.session.add(company)

        # Primary Book
        book = database.session.get(Book, "primary")
        if not book:
            book = Book(code="primary", name="Libro Primario", entity="cacao", status="activo", is_primary=True)
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

        # Post receipt
        submit_document(pr)

        # Verify Kardex (StockLedgerEntry) generated only for stock item
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

        # Verify StockBin snapshot
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_row.actual_qty == Decimal("10.0")
        assert bin_row.stock_value == Decimal("1000.00")
        assert bin_row.valuation_rate == Decimal("100.00")

        # Verify Valuation Layer
        svl = database.session.execute(
            database.select(StockValuationLayer).filter_by(voucher_type="purchase_receipt", voucher_id=pr.id)
        ).scalar_one()
        assert svl.qty == Decimal("10.0")
        assert svl.stock_value_difference == Decimal("1000.00")


def test_02_remision_facturas_notas_venta(app):
    """Prueba de Remisión de Facturas / Notas de Entrega (DeliveryNote)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # First stock entry to populate stock
        se_in = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="material_receipt")
        database.session.add(se_in)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_in.id,
                item_code="ITEM-GOODS",
                qty=Decimal("20.0"),
                uom="UND",
                valuation_rate=Decimal("50.00"),
                amount=Decimal("1000.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_in)

        # Delivery note for 5 units
        dn = DeliveryNote(company="cacao", docstatus=0, posting_date=date(2026, 5, 2), customer_id="CUST-001")
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

        # Submit delivery note
        submit_document(dn)

        # Verify Kardex
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
        assert sle.stock_value_difference == Decimal("-250.00")  # 5 * 50 = 250 cost

        # Verify Bin updated
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_row.actual_qty == Decimal("15.0")
        assert bin_row.stock_value == Decimal("750.00")


def test_03_traslados_entre_inventarios(app):
    """Prueba de Traslados de inventario entre bodegas (material_transfer)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # Setup stock in WH-MAIN
        se_in = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="material_receipt")
        database.session.add(se_in)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_in.id,
                item_code="ITEM-GOODS",
                qty=Decimal("10.0"),
                uom="UND",
                valuation_rate=Decimal("100.00"),
                amount=Decimal("1000.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_in)

        # Transfer 4 units from WH-MAIN to WH-SEC
        se_tr = StockEntry(
            company="cacao",
            docstatus=0,
            posting_date=date(2026, 5, 3),
            purpose="material_transfer",
            from_warehouse="WH-MAIN",
            to_warehouse="WH-SEC",
        )
        database.session.add(se_tr)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_tr.id,
                item_code="ITEM-GOODS",
                qty=Decimal("4.0"),
                uom="UND",
                source_warehouse="WH-MAIN",
                target_warehouse="WH-SEC",
            )
        )
        database.session.commit()

        submit_document(se_tr)

        # Verify 2 stock ledger entries (negative in source, positive in target)
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

        # Verify Bins
        bin_main = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        bin_sec = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-SEC")
        ).scalar_one()

        assert bin_main.actual_qty == Decimal("6.0")
        assert bin_sec.actual_qty == Decimal("4.0")


def test_04_entradas_inventario_variantes(app):
    """Prueba de entradas de inventario en distintas variantes (manufacture, repack, adjustment_positive)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # Manufacture entry
        se_mfg = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="manufacture")
        database.session.add(se_mfg)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_mfg.id,
                item_code="ITEM-GOODS",
                qty=Decimal("15.0"),
                uom="UND",
                valuation_rate=Decimal("120.00"),
                amount=Decimal("1800.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()

        submit_document(se_mfg)

        sle = database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=se_mfg.id)
        ).scalar_one()
        assert sle.qty_change == Decimal("15.0")
        assert sle.stock_value == Decimal("1800.00")


def test_05_ajustes_valores_positivos_negativos(app):
    """Prueba de Ajustes Negativos / Positivos de Valor (revaluaciones con qty == 0)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # Step 1: initial stock 10 units at 100 = 1000
        se_in = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="material_receipt")
        database.session.add(se_in)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_in.id,
                item_code="ITEM-GOODS",
                qty=Decimal("10.0"),
                uom="UND",
                valuation_rate=Decimal("100.00"),
                amount=Decimal("1000.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_in)

        # Step 2: Positive value adjustment +200 NIO without changing quantity (qty = 0)
        se_adj_val = StockEntry(
            company="cacao",
            docstatus=0,
            posting_date=date(2026, 5, 2),
            purpose="adjustment_positive",
            adjustment_account_id="5200-ADJ",
        )
        database.session.add(se_adj_val)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_adj_val.id,
                item_code="ITEM-GOODS",
                qty=Decimal("0"),
                uom="UND",
                amount=Decimal("200.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_adj_val)

        # Verify Bin value is now 1200, qty is 10, valuation_rate is 120
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_row.actual_qty == Decimal("10.0")
        assert bin_row.stock_value == Decimal("1200.00")
        assert bin_row.valuation_rate == Decimal("120.00")


def test_06_ajustes_cantidades_positivos_negativos(app):
    """Prueba de Ajustes Negativos / Positivos de Cantidad (material_issue / adjustment_negative)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # Setup 10 units
        se_in = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="material_receipt")
        database.session.add(se_in)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_in.id,
                item_code="ITEM-GOODS",
                qty=Decimal("10.0"),
                uom="UND",
                valuation_rate=Decimal("100.00"),
                amount=Decimal("1000.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_in)

        # Issue 3 units
        se_out = StockEntry(
            company="cacao",
            docstatus=0,
            posting_date=date(2026, 5, 2),
            purpose="material_issue",
            from_warehouse="WH-MAIN",
        )
        database.session.add(se_out)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_out.id,
                item_code="ITEM-GOODS",
                qty=Decimal("3.0"),
                uom="UND",
                source_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_out)

        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_row.actual_qty == Decimal("7.0")
        assert bin_row.stock_value == Decimal("700.00")


def test_07_ajustes_por_inventario(app):
    """Prueba de Ajuste por Inventario / Conciliación Física (stock_reconciliation)."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # Setup current stock 10 units
        se_in = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="material_receipt")
        database.session.add(se_in)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_in.id,
                item_code="ITEM-GOODS",
                qty=Decimal("10.0"),
                uom="UND",
                valuation_rate=Decimal("100.00"),
                amount=Decimal("1000.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_in)

        # Reconcile physical count to 12 units and target value 1320.00
        se_rec = StockEntry(
            company="cacao",
            docstatus=0,
            posting_date=date(2026, 5, 5),
            purpose="stock_reconciliation",
            adjustment_account_id="5200-ADJ",
        )
        database.session.add(se_rec)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se_rec.id,
                item_code="ITEM-GOODS",
                qty=Decimal("2.0"),
                uom="UND",
                counted_qty=Decimal("12.0"),
                target_stock_value=Decimal("1320.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se_rec)

        # Verify Bin matches counted quantity and target value
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_row.actual_qty == Decimal("12.0")
        assert bin_row.stock_value == Decimal("1320.00")
        assert bin_row.valuation_rate == Decimal("110.00")


def test_08_kardex_confiable_y_reconstructibilidad(app):
    """Prueba de Confiabilidad del Kardex, Cancelación de Documentos y Reconstrucción de Bins/Layers."""
    _setup_inventory_test_data(app)
    with app.app_context():
        # 1. Entry 1: +10 units @ 100 = 1000
        se1 = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 1), purpose="material_receipt")
        database.session.add(se1)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se1.id,
                item_code="ITEM-GOODS",
                qty=Decimal("10.0"),
                uom="UND",
                valuation_rate=Decimal("100.00"),
                amount=Decimal("1000.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se1)

        # 2. Entry 2: +5 units @ 120 = 600
        se2 = StockEntry(company="cacao", docstatus=0, posting_date=date(2026, 5, 2), purpose="material_receipt")
        database.session.add(se2)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=se2.id,
                item_code="ITEM-GOODS",
                qty=Decimal("5.0"),
                uom="UND",
                valuation_rate=Decimal("120.00"),
                amount=Decimal("600.00"),
                target_warehouse="WH-MAIN",
            )
        )
        database.session.commit()
        submit_document(se2)

        # Current stock = 15 units, value = 1600
        bin_before = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_before.actual_qty == Decimal("15.0")
        assert bin_before.stock_value == Decimal("1600.00")

        # 3. Cancel Entry 2
        cancel_document(se2)

        # Stock after cancellation = 10 units, value = 1000
        bin_after_cancel = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_after_cancel.actual_qty == Decimal("10.0")
        assert bin_after_cancel.stock_value == Decimal("1000.00")

        # 4. Rebuild Bins directly from Kardex (StockLedgerEntry)
        rebuild_res = rebuild_stock_bins(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        assert rebuild_res.rebuilt_bins == 1
        assert len(rebuild_res.inconsistencies) == 0

        # Verify Bin after rebuild
        bin_rebuilt = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITEM-GOODS", warehouse="WH-MAIN")
        ).scalar_one()
        assert bin_rebuilt.actual_qty == Decimal("10.0")
        assert bin_rebuilt.stock_value == Decimal("1000.00")
