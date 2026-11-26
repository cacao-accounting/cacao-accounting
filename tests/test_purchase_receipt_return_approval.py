# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2283: la aprobación final respeta el origen de una devolución física.

Escenario de negocio: una recepción vinculada a una orden de compra genera una
devolución que conserva ``purchase_order_id`` pero no relaciona sus líneas con
la OC: su origen es la recepción original y el consumo se registra mediante
allocations. El motor de aprobación no debe exigir relaciones directas con la
OC, pero sí debe revalidar la recepción de origen, compañía, proveedor y que la
cantidad devuelta no exceda lo recibido.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import ApprovalEngine, approved_execution
from cacao_accounting.compras.purchase_reconciliation_service import (
    PurchaseReconciliationError,
    create_purchase_receipt_return_allocations,
)
from cacao_accounting.compras.services import _validate_return_receipt_against_original
from cacao_accounting.contabilidad.posting_service import post_purchase_receipt
from cacao_accounting.database import (
    Accounts,
    ApprovalMatrix,
    CacaoConfig,
    CompanyDefaultAccount,
    CompanyParty,
    DocumentRelation,
    Entity,
    Item,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReceiptReturnAllocation,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="La aprobación de devoluciones no aplica en modo escritorio.",
)


def _sembrar_cuentas(escenario) -> None:
    """Prepara las cuentas puente y de inventario que exige el posteo."""
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
    almacen = database.session.execute(database.select(Warehouse).limit(1)).scalar_one()
    mapping = database.session.execute(
        database.select(WarehouseCompanyAccount).filter_by(warehouse_code=almacen.code, company="cacao")
    ).scalar_one_or_none()
    if mapping is None:
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=almacen.code,
                company="cacao",
                inventory_account_id=inventario.id,
            )
        )
    else:
        mapping.inventory_account_id = inventario.id
    database.session.commit()


def _sembrar_cadena(devolucion_qty: Decimal, qty_recibida: Decimal = Decimal("4")) -> dict[str, object]:
    """Crea OC, recepción posteada y devolución borrador sin relaciones de línea."""
    sufijo = uuid4().hex[:8]
    supplier = database.session.execute(database.select(Party).limit(1)).scalar_one()
    item = database.session.execute(database.select(Item).limit(1)).scalar_one()
    uom = database.session.execute(database.select(UOM).limit(1)).scalar_one()
    almacen = database.session.execute(database.select(Warehouse).limit(1)).scalar_one()
    fecha = date(2026, 5, 12)

    orden = PurchaseOrder(
        company="cacao",
        posting_date=fecha,
        docstatus=1,
        document_no=f"PO-RET-{sufijo}",
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
        qty=Decimal("10"),
        qty_in_base_uom=Decimal("10"),
        uom=uom.code,
        rate=Decimal("10"),
        amount=Decimal("100"),
    )
    database.session.add(orden_item)
    database.session.flush()

    original = PurchaseReceipt(
        company="cacao",
        posting_date=fecha,
        docstatus=1,
        document_no=f"PR-RET-{sufijo}",
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
        qty=qty_recibida,
        qty_in_base_uom=qty_recibida,
        uom=uom.code,
        rate=Decimal("10"),
        amount=qty_recibida * Decimal("10"),
        base_amount=qty_recibida * Decimal("10"),
        warehouse=almacen.code,
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
            qty=qty_recibida,
            qty_in_base_uom=qty_recibida,
            uom=uom.code,
            relation_type="consume",
            status="active",
        )
    )
    database.session.commit()

    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    with audit_actor(admin.id, admin.name), approved_execution(original, admin.id):
        post_purchase_receipt(original)
    database.session.commit()

    devolucion = PurchaseReceipt(
        company="cacao",
        posting_date=fecha,
        docstatus=0,
        document_no=f"PRT-RET-{sufijo}",
        purchase_order_id=orden.id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        is_return=True,
        reversal_of=original.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        total=devolucion_qty * Decimal("10"),
        base_total=devolucion_qty * Decimal("10"),
        grand_total=devolucion_qty * Decimal("10"),
    )
    database.session.add(devolucion)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=devolucion.id,
            item_code=item.code,
            item_name=item.name,
            qty=devolucion_qty,
            qty_in_base_uom=devolucion_qty,
            uom=uom.code,
            rate=Decimal("10"),
            amount=devolucion_qty * Decimal("10"),
            base_amount=devolucion_qty * Decimal("10"),
            warehouse=almacen.code,
        )
    )
    database.session.commit()
    return {
        "devolucion": devolucion,
        "original": original,
        "admin": admin,
        "orden": orden,
        "item": item,
        "uom": uom,
        "almacen": almacen,
        "supplier": supplier,
    }


def _habilitar_aprobacion(admin) -> None:
    """Activa el motor con una regla que cubre la devolución."""
    database.session.add(CacaoConfig(key="approval_engine_enabled_cacao", value="1"))
    database.session.add(
        ApprovalMatrix(
            company_id="cacao",
            document_type="purchase_receipt",
            user_id=admin.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("1000"),
            approval_level=1,
            enabled=True,
        )
    )
    database.session.commit()


def _aprobar(devolucion: PurchaseReceipt, admin) -> None:
    """Solicita y aprueba la devolución con el motor habilitado."""
    solicitud = ApprovalEngine.request_approval(devolucion, actor=admin)
    assert solicitud is not None
    assert ApprovalEngine.approve(devolucion, admin, "Aprobación de prueba") is True
    database.session.commit()
    database.session.refresh(devolucion)


def _asignaciones(devolucion: PurchaseReceipt) -> list[PurchaseReceiptReturnAllocation]:
    """Devuelve las allocations activas creadas para una devolución."""
    return list(
        database.session.execute(
            database.select(PurchaseReceiptReturnAllocation).where(
                PurchaseReceiptReturnAllocation.return_receipt_item_id.in_(
                    database.select(PurchaseReceiptItem.id).where(PurchaseReceiptItem.purchase_receipt_id == devolucion.id)
                ),
                PurchaseReceiptReturnAllocation.status == "active",
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.parametrize(
    ("qty_devuelta", "mensaje"),
    [
        ("2", None),
        ("6", "devolución excede la cantidad recibida original"),
    ],
)
def test_aprobacion_de_devolucion_desde_oc_valida_origen_y_cantidad(
    entorno_contable_aislado, qty_devuelta: str, mensaje: str | None
) -> None:
    """Una devolución legítima se aprueba; una que excede lo recibido se rechaza."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _sembrar_cuentas(entorno_contable_aislado)
        datos = _sembrar_cadena(Decimal(qty_devuelta))
        devolucion = datos["devolucion"]
        admin = datos["admin"]
        _habilitar_aprobacion(admin)
        solicitud = ApprovalEngine.request_approval(devolucion, actor=admin)
        assert solicitud is not None

        if mensaje:
            with pytest.raises(ValueError, match=mensaje):
                ApprovalEngine.approve(devolucion, admin, "Aprobación de prueba")
            database.session.rollback()
            database.session.refresh(devolucion)
            assert devolucion.docstatus == 0
            assert _asignaciones(devolucion) == []
            return

        _aprobar(devolucion, admin)
        assert devolucion.docstatus == 1
        asignaciones = _asignaciones(devolucion)
        assert len(asignaciones) == 1
        assert asignaciones[0].qty_in_base_uom == Decimal("2")
        assert asignaciones[0].original_receipt_item_id is not None


def _nueva_devolucion(datos: dict[str, object], qty: Decimal) -> PurchaseReceipt:
    """Crea otra devolución borrador sobre la misma recepción original."""
    sufijo = uuid4().hex[:8]
    item = datos["item"]
    uom = datos["uom"]
    almacen = datos["almacen"]
    supplier = datos["supplier"]
    original = datos["original"]
    devolucion = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 13),
        docstatus=0,
        document_no=f"PRT-RET-2-{sufijo}",
        purchase_order_id=datos["orden"].id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        is_return=True,
        reversal_of=original.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        total=qty * Decimal("10"),
        base_total=qty * Decimal("10"),
        grand_total=qty * Decimal("10"),
    )
    database.session.add(devolucion)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=devolucion.id,
            item_code=item.code,
            item_name=item.name,
            qty=qty,
            qty_in_base_uom=qty,
            uom=uom.code,
            rate=Decimal("10"),
            amount=qty * Decimal("10"),
            base_amount=qty * Decimal("10"),
            warehouse=almacen.code,
        )
    )
    database.session.commit()
    return devolucion


def test_devoluciones_secuenciales_respetan_allocations_previas(entorno_contable_aislado) -> None:
    """La segunda devolución considera lo ya devuelto por la primera."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _sembrar_cuentas(entorno_contable_aislado)
        datos = _sembrar_cadena(Decimal("3"))
        admin = datos["admin"]
        _habilitar_aprobacion(admin)
        primera = datos["devolucion"]
        _aprobar(primera, admin)

        segunda = _nueva_devolucion(datos, Decimal("3"))
        solicitud = ApprovalEngine.request_approval(segunda, actor=admin)
        assert solicitud is not None
        with pytest.raises(ValueError, match="devolución excede la cantidad recibida original"):
            ApprovalEngine.approve(segunda, admin, "Revisión de allocations")
        database.session.rollback()
        database.session.refresh(segunda)
        assert segunda.docstatus == 0
        assert _asignaciones(segunda) == []
        assert len(_asignaciones(primera)) == 1


def _preparar_otra_compania(admin) -> str:
    """Crea una compañía con aprobación habilitada para el escenario de rechazo."""
    database.session.add(
        Entity(
            code="otra",
            name="Otra",
            company_name="Otra SA",
            tax_id="J-OTRA-2283",
            currency="NIO",
            enabled=True,
            status="default",
        )
    )
    database.session.add(UserCompanyAccess(user_id=admin.id, company_code="otra"))
    database.session.add(CacaoConfig(key="approval_engine_enabled_otra", value="1"))
    database.session.add(
        ApprovalMatrix(
            company_id="otra",
            document_type="purchase_receipt",
            user_id=admin.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("1000"),
            approval_level=1,
            enabled=True,
        )
    )
    database.session.commit()
    return "otra"


@pytest.mark.parametrize("campo", ["company", "supplier_id"])
def test_devolucion_rechaza_origen_de_otra_compania_o_proveedor(entorno_contable_aislado, campo: str) -> None:
    """La recepción original debe compartir compañía y proveedor con la devolución."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _sembrar_cuentas(entorno_contable_aislado)
        datos = _sembrar_cadena(Decimal("1"))
        devolucion = datos["devolucion"]
        admin = datos["admin"]
        _habilitar_aprobacion(admin)
        if campo == "company":
            devolucion.company = _preparar_otra_compania(admin)
        else:
            otro_proveedor = Party(
                code=f"PRV-OTRA-{uuid4().hex[:6]}",
                name="Proveedor distinto",
                is_supplier=True,
                is_active=True,
            )
            database.session.add(otro_proveedor)
            database.session.flush()
            database.session.add(CompanyParty(company="cacao", party_id=otro_proveedor.id, is_active=True))
            devolucion.supplier_id = otro_proveedor.id
        database.session.commit()

        solicitud = ApprovalEngine.request_approval(devolucion, actor=admin)
        assert solicitud is not None
        with pytest.raises(ValueError, match="misma compañía|mismo proveedor"):
            ApprovalEngine.approve(devolucion, admin, "Revisión de origen")
        database.session.rollback()
        database.session.refresh(devolucion)
        assert devolucion.docstatus == 0


def _mutar_en_otra_sesion(app, *, original_id: str | None = None, allocation_id: str | None = None) -> None:
    """Cambia el estado persistido desde otra sesión sin refrescar la del llamador."""

    def mutar() -> None:
        with app.app_context():
            if original_id is not None:
                original = database.session.get(PurchaseReceipt, original_id)
                original.docstatus = 2
            else:
                allocation = database.session.get(PurchaseReceiptReturnAllocation, allocation_id)
                allocation.status = "cancelled"
            database.session.commit()
            database.session.remove()

    with ThreadPoolExecutor(max_workers=1) as workers:
        workers.submit(mutar).result(timeout=10)


def test_aprobacion_relee_origen_cancelado_en_otra_sesion(entorno_contable_aislado) -> None:
    """La aprobación no acepta una recepción cancelada tras esperar el lock (#2283)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _sembrar_cuentas(entorno_contable_aislado)
        datos = _sembrar_cadena(Decimal("2"))
        devolucion = datos["devolucion"]
        original = datos["original"]
        admin = datos["admin"]
        _habilitar_aprobacion(admin)
        solicitud = ApprovalEngine.request_approval(devolucion, actor=admin)
        assert solicitud is not None
        assert original.docstatus == 1

        _mutar_en_otra_sesion(app, original_id=original.id)
        assert original.docstatus == 1

        with pytest.raises(ValueError, match="recepción original debe estar aprobada"):
            ApprovalEngine.approve(devolucion, admin, "Revisión de origen cancelado")
        database.session.rollback()
        database.session.refresh(devolucion)
        assert devolucion.docstatus == 0
        assert _asignaciones(devolucion) == []


def test_conciliacion_relee_origen_cancelado_en_otra_sesion(entorno_contable_aislado) -> None:
    """La creación de allocations no reutiliza una recepción cancelada en caché (#2283)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _sembrar_cuentas(entorno_contable_aislado)
        datos = _sembrar_cadena(Decimal("2"))
        original = datos["original"]
        devolucion = datos["devolucion"]
        assert original.docstatus == 1

        _mutar_en_otra_sesion(app, original_id=original.id)
        assert original.docstatus == 1

        with pytest.raises(PurchaseReconciliationError, match="recepción original debe estar aprobada"):
            create_purchase_receipt_return_allocations(devolucion.id)
        database.session.rollback()
        assert _asignaciones(devolucion) == []


def test_aprobacion_relee_allocations_canceladas_en_otra_sesion(entorno_contable_aislado) -> None:
    """El consumo se suma desde la fila vigente, no desde la entidad en caché (#2283)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _sembrar_cuentas(entorno_contable_aislado)
        datos = _sembrar_cadena(Decimal("3"), qty_recibida=Decimal("5"))
        admin = datos["admin"]
        _habilitar_aprobacion(admin)
        primera = datos["devolucion"]
        _aprobar(primera, admin)
        allocation = _asignaciones(primera)[0]
        assert allocation.qty_in_base_uom == Decimal("3")

        segunda = _nueva_devolucion(datos, Decimal("3"))
        with pytest.raises(ValueError, match="devolución excede la cantidad recibida original"):
            _validate_return_receipt_against_original(segunda)

        _mutar_en_otra_sesion(app, allocation_id=allocation.id)
        assert allocation.status == "active"

        _validate_return_receipt_against_original(segunda)
        assert _asignaciones(primera) == []
