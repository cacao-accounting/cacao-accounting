# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de los invariantes del kardex (issue #773).

Bloquea por regresión las propiedades que el issue exige al mayor de
inventario:

- Kardex inmutable: las filas de ``StockLedgerEntry`` no se actualizan ni se
  borran; solo el flag de anulación puede mutar.
- Anulación por transacción recíproca: cancelar un documento de inventario
  agrega una contrapartida en el mismo período contable, únicamente si ese
  período está abierto; no existe un flujo de reversión en otro período.
- Separación de roles: la recepción de compra (S2P) y la entrega de venta
  (O2C) afectan inventario solo con permisos del módulo inventory; compras y
  ventas conservan acceso de solo lectura a sus documentos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def kardex_app():
    """Crea una app aislada con compañía, libros, módulos, roles y períodos."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "kardex-invariants",
        }
    )
    with app.app_context():
        from cacao_accounting.database import (
            AccountingPeriod,
            Book,
            Entity,
            Modules,
            Roles,
            RolesAccess,
            RolesUser,
            User,
            UserCompanyAccess,
            database,
        )

        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO"),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                AccountingPeriod(
                    entity="cacao",
                    name="05-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="06-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 6, 1),
                    end=date(2026, 6, 30),
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Roles(id="ROLE-BUYER", name="Comprador", note="Rol de compras sin inventario"),
                Roles(id="ROLE-SELLER", name="Vendedor", note="Rol de ventas sin inventario"),
                Roles(id="ROLE-STOCK", name="Almacenista", note="Rol de inventario"),
            ]
        )
        database.session.flush()
        purchases_module = database.session.execute(database.select(Modules).filter_by(module="purchases")).scalar_one()
        sales_module = database.session.execute(database.select(Modules).filter_by(module="sales")).scalar_one()
        inventory_module = database.session.execute(database.select(Modules).filter_by(module="inventory")).scalar_one()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id="ROLE-BUYER",
                    module_id=purchases_module.id,
                    access=True,
                    view=True,
                    create=True,
                    edit=True,
                    approve=True,
                ),
                RolesAccess(
                    rol_id="ROLE-SELLER",
                    module_id=sales_module.id,
                    access=True,
                    view=True,
                    create=True,
                    edit=True,
                    approve=True,
                ),
                RolesAccess(
                    rol_id="ROLE-STOCK",
                    module_id=inventory_module.id,
                    access=True,
                    view=True,
                    create=True,
                    edit=True,
                    approve=True,
                    set_null=True,
                ),
            ]
        )
        database.session.add_all(
            [
                User(id="USER-BUYER", user="buyer", name="Comprador", password=b"x", classification="user", active=True),
                User(id="USER-SELLER", user="seller", name="Vendedor", password=b"x", classification="user", active=True),
                User(id="USER-STOCK", user="stock", name="Almacenista", password=b"x", classification="user", active=True),
                User(id="admin", user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                RolesUser(user_id="USER-BUYER", role_id="ROLE-BUYER", active=True),
                RolesUser(user_id="USER-SELLER", role_id="ROLE-SELLER", active=True),
                RolesUser(user_id="USER-STOCK", role_id="ROLE-STOCK", active=True),
                UserCompanyAccess(user_id="USER-BUYER", company_code="cacao"),
                UserCompanyAccess(user_id="USER-SELLER", company_code="cacao"),
                UserCompanyAccess(user_id="USER-STOCK", company_code="cacao"),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    """Autentica un usuario de prueba sin depender del hash de contraseña."""
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _seed_stock_master() -> None:
    """Crea el maestro mínimo para postear una recepción de compra."""
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        Item,
        ItemAccount,
        PartyAccount,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-KX",
        name="Inventario KX",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-KX",
        name="Cuenta puente KX",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    database.session.add_all(
        [
            inventory_account,
            bridge_account,
            UOM(code="EA-KX", name="Each KX"),
            Item(code="ITEM-KX", name="Item KX", item_type="goods", is_stock_item=True, default_uom="EA-KX"),
            Warehouse(code="WH-KX", name="Bodega KX", company="cacao", is_active=True),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-KX", company="cacao"),
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
            WarehouseCompanyAccount(
                warehouse_code="WH-KX", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            PartyAccount(party_id="SUPP-KX", company="cacao", payable_account_id=None),
        ]
    )
    database.session.commit()


def _posted_receipt():
    """Postea una recepción de compra aprobada en el período 05-2026."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database

    _seed_stock_master()
    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-KX",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
        total=Decimal("50.00"),
        grand_total=Decimal("50.00"),
    )
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-KX",
            item_name="Item KX",
            qty=Decimal("2"),
            uom="EA-KX",
            qty_in_base_uom=Decimal("2"),
            rate=Decimal("25.00"),
            amount=Decimal("50.00"),
            warehouse="WH-KX",
            valuation_rate=Decimal("25.00"),
        )
    )
    database.session.commit()
    post_document_to_gl(receipt)
    database.session.commit()
    return receipt


def _seed_operative_documents():
    """Crea borradores y documentos aprobados para las pruebas de roles."""
    from cacao_accounting.database import (
        DeliveryNote,
        DeliveryNoteItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        database,
    )

    _seed_stock_master()
    draft_receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 10),
        supplier_id="SUPP-KX",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
        document_no="REC-KX-0001",
    )
    submitted_receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 11),
        supplier_id="SUPP-KX",
        supplier_name="Proveedor KX",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
        document_no="REC-KX-0002",
    )
    database.session.add_all([draft_receipt, submitted_receipt])
    database.session.flush()
    for receipt in (draft_receipt, submitted_receipt):
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code="ITEM-KX",
                item_name="Item KX",
                qty=Decimal("1"),
                uom="EA-KX",
                qty_in_base_uom=Decimal("1"),
                rate=Decimal("25.00"),
                amount=Decimal("25.00"),
                warehouse="WH-KX",
            )
        )
    draft_note = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 12),
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
        document_no="ENT-KX-0001",
    )
    submitted_note = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 13),
        customer_name="Cliente KX",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
        document_no="ENT-KX-0002",
    )
    database.session.add_all([draft_note, submitted_note])
    database.session.flush()
    for note in (draft_note, submitted_note):
        database.session.add(
            DeliveryNoteItem(
                delivery_note_id=note.id,
                item_code="ITEM-KX",
                item_name="Item KX",
                qty=Decimal("1"),
                uom="EA-KX",
                qty_in_base_uom=Decimal("1"),
                rate=Decimal("25.00"),
                amount=Decimal("25.00"),
                warehouse="WH-KX",
            )
        )
    database.session.commit()
    return draft_receipt, submitted_receipt, draft_note, submitted_note


# --------------------------------------------------------------------------- #
# 1. Kardex inmutable: ni update ni delete, solo el flag de anulación.
# --------------------------------------------------------------------------- #


def _kardex_row():
    """Inserta una fila de kardex directa con FK válidas."""
    from cacao_accounting.database import Item, StockLedgerEntry, UOM, Warehouse, database

    database.session.add_all(
        [
            UOM(code="EA-KX", name="Each KX"),
            Item(code="ITEM-KX", name="Item KX", item_type="goods", is_stock_item=True, default_uom="EA-KX"),
            Warehouse(code="WH-KX", name="Bodega KX", company="cacao", is_active=True),
        ]
    )
    database.session.commit()
    entry = StockLedgerEntry(
        posting_date=date(2026, 5, 4),
        item_code="ITEM-KX",
        warehouse="WH-KX",
        company="cacao",
        qty_change=Decimal("2"),
        qty_after_transaction=Decimal("2"),
        valuation_rate=Decimal("25.00"),
        stock_value_difference=Decimal("50.00"),
        stock_value=Decimal("50.00"),
        voucher_type="seed",
        voucher_id="seed-kx",
    )
    database.session.add(entry)
    database.session.commit()
    return entry


def test_stock_ledger_entry_rejects_field_mutation(kardex_app):
    """Modificar una cifra del kardex lanza ValueError; el historial no se reescribe."""
    from cacao_accounting.database import database

    entry = _kardex_row()
    entry.qty_change = Decimal("999")
    with pytest.raises(ValueError, match="inmutables"):
        database.session.flush()
    database.session.rollback()

    database.session.expire_all()
    fresh = _select_single_kardex_row()
    assert fresh.qty_change == Decimal("2.000000000")


def test_stock_ledger_entry_rejects_non_amount_mutation(kardex_app):
    """Cambiar metadatos como el serial también está prohibido: la fila es evidencia."""
    from cacao_accounting.database import database

    entry = _kardex_row()
    entry.serial_no = "SERIAL-EDITADO"
    with pytest.raises(ValueError, match="inmutables"):
        database.session.flush()
    database.session.rollback()

    database.session.expire_all()
    assert _select_single_kardex_row().serial_no is None


def test_stock_ledger_entry_rejects_physical_delete(kardex_app):
    """Borrar una fila del kardex está prohibido; la corrección va por contra-asientos."""
    from cacao_accounting.database import database

    entry = _kardex_row()
    database.session.delete(entry)
    with pytest.raises(ValueError, match="no se pueden eliminar"):
        database.session.flush()
    database.session.rollback()

    assert _select_single_kardex_row() is not None


def test_stock_ledger_entry_allows_cancellation_flag_only(kardex_app):
    """El único campo mutable del kardex es el flag lógico de anulación."""
    from cacao_accounting.database import database

    entry = _kardex_row()
    entry.is_cancelled = True
    database.session.flush()
    database.session.commit()

    database.session.expire_all()
    fresh = _select_single_kardex_row()
    assert fresh.is_cancelled is True
    assert fresh.qty_change == Decimal("2.000000000")


def _select_single_kardex_row():
    from cacao_accounting.database import StockLedgerEntry, database

    return database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id="seed-kx")).scalars().one()


# --------------------------------------------------------------------------- #
# 2. Anulación recíproca en el mismo período, únicamente si está abierto.
# --------------------------------------------------------------------------- #


def test_stock_cancellation_appends_reciprocal_kardex_entry(kardex_app):
    """Cancelar una recepción agrega una contrapartida en vez de borrar historia."""
    from cacao_accounting.contabilidad.posting import cancel_document
    from cacao_accounting.database import GLEntry, StockLedgerEntry, StockValuationLayer, database

    receipt = _posted_receipt()
    cancel_document(
        receipt,
        reason="Anulación de prueba",
        actor_user_id="admin",
        cancellation_date=receipt.posting_date,
    )
    database.session.commit()

    movements = (
        database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id)
        )
        .scalars()
        .all()
    )
    assert len(movements) == 2
    original = next(row for row in movements if row.is_cancelled)
    reciprocal = next(row for row in movements if row.is_reversal)
    assert receipt.docstatus == 2
    assert reciprocal.reversal_of == original.id
    assert reciprocal.qty_change == -original.qty_change
    assert reciprocal.stock_value_difference == -original.stock_value_difference
    assert reciprocal.valuation_rate == original.valuation_rate
    assert reciprocal.posting_date == original.posting_date
    assert sum(row.qty_change for row in movements) == Decimal("0E-9")

    layers = (
        database.session.execute(
            database.select(StockValuationLayer).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id)
        )
        .scalars()
        .all()
    )
    incoming = next(layer for layer in layers if layer.qty > 0)
    outgoing = next(layer for layer in layers if layer.qty < 0)
    assert outgoing.source_layer_id == incoming.id

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id))
        .scalars()
        .all()
    )
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.is_reversal for entry in entries)


def test_stock_cancellation_rejects_different_period(kardex_app):
    """Inventario no tiene reversiones en otro período: la anulación debe quedar en el mismo."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import StockLedgerEntry, database

    receipt = _posted_receipt()
    with pytest.raises(PostingError, match="mismo periodo"):
        cancel_document(
            receipt,
            reason="Anulación fuera de período",
            actor_user_id="admin",
            cancellation_date=date(2026, 6, 15),
        )
    database.session.rollback()

    database.session.refresh(receipt)
    assert receipt.docstatus == 1
    reversals = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=receipt.id, is_reversal=True))
        .scalars()
        .all()
    )
    assert reversals == []


def test_stock_cancellation_rejects_closed_period(kardex_app):
    """Un período cerrado bloquea la anulación sin escribir contrapartidas parciales."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import AccountingPeriod, StockLedgerEntry, database

    receipt = _posted_receipt()
    period = database.session.execute(database.select(AccountingPeriod).filter_by(entity="cacao", name="05-2026")).scalar_one()
    period.is_closed = True
    database.session.commit()

    with pytest.raises(PostingError, match="cerrado"):
        cancel_document(
            receipt,
            reason="Anulación con período cerrado",
            actor_user_id="admin",
            cancellation_date=receipt.posting_date,
        )
    database.session.rollback()

    database.session.refresh(receipt)
    assert receipt.docstatus == 1
    reversals = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=receipt.id, is_reversal=True))
        .scalars()
        .all()
    )
    assert reversals == []


def test_stock_cancellation_rejects_disabled_period(kardex_app):
    """Un período deshabilitado tampoco admite anulaciones de inventario."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import AccountingPeriod, StockLedgerEntry, database

    receipt = _posted_receipt()
    period = database.session.execute(database.select(AccountingPeriod).filter_by(entity="cacao", name="05-2026")).scalar_one()
    period.enabled = False
    database.session.commit()

    with pytest.raises(PostingError, match="deshabilitado"):
        cancel_document(
            receipt,
            reason="Anulación con período deshabilitado",
            actor_user_id="admin",
            cancellation_date=receipt.posting_date,
        )
    database.session.rollback()

    database.session.refresh(receipt)
    assert receipt.docstatus == 1
    reversals = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=receipt.id, is_reversal=True))
        .scalars()
        .all()
    )
    assert reversals == []


# --------------------------------------------------------------------------- #
# 3. Separación de roles: compras/ventas no afectan inventario, solo lo consultan.
# --------------------------------------------------------------------------- #


def test_buyer_cannot_affect_inventory_through_purchase_receipts(kardex_app):
    """Un comprador sin permisos de inventario no puede crear ni aprobar recepciones."""
    draft_receipt, _, _, _ = _seed_operative_documents()
    client = kardex_app.test_client()
    _login(client, "USER-BUYER")

    assert client.get("/buying/purchase-receipt/new").status_code == 403
    assert client.post(f"/buying/purchase-receipt/{draft_receipt.id}/submit", data={}).status_code == 403
    assert client.post(f"/buying/purchase-receipt/{draft_receipt.id}/edit", data={}).status_code == 403
    assert client.post(f"/buying/purchase-receipt/{draft_receipt.id}/cancel", data={}).status_code == 403

    from cacao_accounting.database import database

    database.session.refresh(draft_receipt)
    assert draft_receipt.docstatus == 0


def test_buyer_can_view_purchase_receipts(kardex_app):
    """Compras conserva acceso de solo lectura sobre las recepciones de producto."""
    _, submitted_receipt, _, _ = _seed_operative_documents()
    client = kardex_app.test_client()
    _login(client, "USER-BUYER")

    assert client.get("/buying/purchase-receipt/list").status_code == 200
    assert client.get(f"/buying/purchase-receipt/{submitted_receipt.id}").status_code == 200


def test_seller_cannot_affect_inventory_through_delivery_notes(kardex_app):
    """Un vendedor sin permisos de inventario no puede crear ni aprobar entregas."""
    _, _, draft_note, _ = _seed_operative_documents()
    client = kardex_app.test_client()
    _login(client, "USER-SELLER")

    assert client.get("/sales/delivery-note/new").status_code == 403
    assert client.post(f"/sales/delivery-note/{draft_note.id}/submit", data={}).status_code == 403
    assert client.post(f"/sales/delivery-note/{draft_note.id}/edit", data={}).status_code == 403
    assert client.post(f"/sales/delivery-note/{draft_note.id}/cancel", data={}).status_code == 403

    from cacao_accounting.database import database

    database.session.refresh(draft_note)
    assert draft_note.docstatus == 0


def test_seller_can_view_delivery_notes(kardex_app):
    """Ventas conserva acceso de solo lectura sobre las entregas de producto vendido."""
    _, _, _, submitted_note = _seed_operative_documents()
    client = kardex_app.test_client()
    _login(client, "USER-SELLER")

    assert client.get("/sales/delivery-note/list").status_code == 200
    assert client.get(f"/sales/delivery-note/{submitted_note.id}").status_code == 200


def test_inventory_user_can_manage_receipts_and_deliveries(kardex_app):
    """El usuario de almacén sí puede abrir los formularios que afectan el inventario."""
    _, _, _, _ = _seed_operative_documents()
    client = kardex_app.test_client()
    _login(client, "USER-STOCK")

    assert client.get("/buying/purchase-receipt/new").status_code == 200
    assert client.get("/sales/delivery-note/new").status_code == 200
