# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2148: la devolución cross-UOM valora la cantidad base de la recepción original."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from cacao_accounting.approval_engine import ApprovalEngine, approved_execution
from cacao_accounting.internal_control_service import audit_actor
from cacao_accounting.contabilidad.posting_service import post_purchase_receipt
from cacao_accounting.database import (
    Accounts,
    CacaoConfig,
    CompanyDefaultAccount,
    ApprovalMatrix,
    DocumentRelation,
    GLEntry,
    Item,
    ItemUOMConversion,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReceiptReturnAllocation,
    StockLedgerEntry,
    UOM,
    User,
    WarehouseCompanyAccount,
    database,
)

FECHA = date(2026, 5, 12)

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="La aprobación de devoluciones no aplica en modo escritorio.",
)


def _preparar_asiento(escenario) -> str:
    """Configura las cuentas puente/inventario que exige el posteo de compras."""
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    bridge = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="2103")).scalar_one_or_none()
    if bridge is None:
        bridge = Accounts(
            entity="cacao",
            code="2103",
            name="Puente de compras",
            classification="liability",
            account_type="bridge",
        )
        database.session.add(bridge)
        database.session.flush()
    defaults.bridge_account_id = bridge.id
    inventario = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
    almacen = database.session.execute(database.select(WarehouseCompanyAccount).limit(1)).scalar_one_or_none()
    if almacen is None:
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code="BOD01",
                company="cacao",
                inventory_account_id=inventario.id,
            )
        )
    else:
        almacen.inventory_account_id = inventario.id
    database.session.commit()
    return bridge.id


def _sembrar_recepcion_en_cajas(escenario) -> dict[str, object]:
    """Crea una recepción de 2 cajas (24 unidades base) ya posteada."""
    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    sufijo = uuid4().hex[:8]
    supplier = database.session.execute(database.select(Party).limit(1)).scalar_one()
    item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()

    database.session.add(UOM(code="CAJA-2148", name="Caja", is_active=True))
    database.session.flush()
    database.session.add(
        ItemUOMConversion(
            item_code=item.code,
            from_uom="CAJA-2148",
            to_uom="UND",
            conversion_factor=Decimal("12"),
        )
    )

    orden = PurchaseOrder(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no=f"PO-CROSS-{sufijo}",
        supplier_id=supplier.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(orden)
    database.session.flush()
    orden_item = PurchaseOrderItem(
        purchase_order_id=orden.id,
        item_code=item.code,
        qty=Decimal("2"),
        qty_in_base_uom=Decimal("24"),
        uom="CAJA-2148",
        rate=Decimal("900"),
        amount=Decimal("1800"),
    )
    database.session.add(orden_item)
    database.session.flush()

    original = PurchaseReceipt(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no=f"PR-CROSS-{sufijo}",
        purchase_order_id=orden.id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(original)
    database.session.flush()
    original_item = PurchaseReceiptItem(
        purchase_receipt_id=original.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("2"),
        qty_in_base_uom=Decimal("24"),
        uom="CAJA-2148",
        rate=Decimal("900"),
        amount=Decimal("1800"),
        base_amount=Decimal("1800"),
        warehouse="BOD01",
    )
    database.session.add(original_item)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            company="cacao",
            source_type="purchase_order",
            source_id=orden.id,
            source_item_id=orden_item.id,
            target_type="purchase_receipt",
            target_id=original.id,
            target_item_id=original_item.id,
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("24"),
            uom="CAJA-2148",
            relation_type="consume",
            status="active",
        )
    )
    database.session.commit()

    with audit_actor(admin.id, admin.name), approved_execution(original, admin.id):
        post_purchase_receipt(original)
    database.session.commit()

    database.session.add(CacaoConfig(key="approval_engine_enabled_cacao", value="1"))
    database.session.add(
        ApprovalMatrix(
            company_id="cacao",
            document_type="purchase_receipt",
            user_id=admin.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("100000"),
            approval_level=1,
            enabled=True,
        )
    )
    database.session.commit()
    return {"admin": admin, "original": original, "original_item": original_item, "item": item}


def test_devolucion_en_unidades_valora_cajas_originales(entorno_contable_aislado) -> None:
    """24 unidades devueltas valoran 1800, no 21600, y cuadran en GL y stock."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _preparar_asiento(entorno_contable_aislado)
        datos = _sembrar_recepcion_en_cajas(entorno_contable_aislado)
        original_id = datos["original"].id
        original_item_id = datos["original_item"].id
        admin_id = str(inspect(datos["admin"]).identity[0])

    client = app.test_client()
    with client.session_transaction() as sesion:
        sesion["_user_id"] = admin_id
        sesion["_fresh"] = True

    respuesta = client.post(
        "/buying/purchase-receipt/new",
        data={
            "company": "cacao",
            "posting_date": FECHA.isoformat(),
            "from_receipt": original_id,
            "to_warehouse": "BOD01",
            "item_code_0": "ART01",
            "item_name_0": "Articulo comercial",
            "qty_0": "24",
            "uom_0": "UND",
            "rate_0": "0",
            "amount_0": "0",
            "source_type_0": "purchase_receipt",
            "source_id_0": original_id,
            "source_item_id_0": original_item_id,
        },
    )
    assert respuesta.status_code == 302

    with app.app_context():
        devolucion = database.session.execute(
            database.select(PurchaseReceipt).where(PurchaseReceipt.reversal_of == original_id)
        ).scalar_one()
        linea = database.session.execute(
            database.select(PurchaseReceiptItem).where(PurchaseReceiptItem.purchase_receipt_id == devolucion.id)
        ).scalar_one()
        assert linea.qty == Decimal("24")
        assert linea.qty_in_base_uom == Decimal("24")
        assert linea.rate == Decimal("75")
        assert linea.amount == Decimal("1800")
        devolucion_id = devolucion.id

        admin = database.session.get(User, admin_id)
        solicitud = ApprovalEngine.request_approval(devolucion, actor=admin)
        assert solicitud is not None
        assert ApprovalEngine.approve(devolucion, admin, "Prueba cross-UOM") is True
        database.session.commit()

        asignacion = database.session.execute(
            database.select(PurchaseReceiptReturnAllocation).where(
                PurchaseReceiptReturnAllocation.return_receipt_item_id == linea.id
            )
        ).scalar_one()
        assert asignacion.qty_in_base_uom == Decimal("24")
        assert asignacion.amount == Decimal("1800")

        gl = (
            database.session.execute(
                database.select(GLEntry).where(
                    GLEntry.voucher_type == "purchase_receipt",
                    GLEntry.voucher_id == devolucion_id,
                )
            )
            .scalars()
            .all()
        )
        assert gl
        assert {entry.debit for entry in gl if entry.debit} == {Decimal("1800")}
        assert {entry.credit for entry in gl if entry.credit} == {Decimal("1800")}

        movimiento = database.session.execute(
            database.select(StockLedgerEntry).where(
                StockLedgerEntry.voucher_type == "purchase_receipt",
                StockLedgerEntry.voucher_id == devolucion_id,
            )
        ).scalar_one()
        assert movimiento.qty_change == Decimal("-24")
        assert movimiento.stock_value_difference == Decimal("-1800")
