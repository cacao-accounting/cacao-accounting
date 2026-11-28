# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1755: la devolución de recepción conserva el proveedor del origen.

La invariante ya se validaba al postear; ahora se rechaza al crear o editar
el borrador, para no preparar un documento que siempre será rechazado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    CompanyParty,
    Item,
    Party,
    PurchaseReceipt,
    PurchaseReceiptItem,
    Warehouse,
    database,
)

FECHA = date(2026, 5, 12)


def _sembrar_origen(app) -> dict[str, str]:
    """Crea una recepción aprobada y un segundo proveedor habilitado."""
    with app.app_context():
        origen = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        sufijo = uuid4().hex[:6].upper()
        ajeno = Party(code=f"PRV-AJENO-{sufijo}", name=f"Proveedor ajeno {sufijo}", is_supplier=True)
        database.session.add(ajeno)
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        bodega = database.session.execute(database.select(Warehouse).filter_by(company="cacao")).scalars().first()
        receipt = PurchaseReceipt(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PR-1755-{sufijo}",
            supplier_id=origen.id,
            supplier_name=origen.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(receipt)
        database.session.flush()
        for party in (origen, ajeno):
            enlace = database.session.execute(
                database.select(CompanyParty).filter_by(company="cacao", party_id=party.id)
            ).scalar_one_or_none()
            if enlace is None:
                database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
            else:
                enlace.is_active = True
        linea = PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("10"),
            base_amount=Decimal("10"),
            warehouse=bodega.code,
        )
        database.session.add(linea)
        database.session.commit()
        return {
            "origen": receipt.id,
            "origen_supplier": str(origen.id),
            "ajeno": str(ajeno.id),
            "item": item.code,
            "linea": linea.id,
            "bodega": bodega.code,
        }


def _formulario(datos: dict[str, str], supplier_id: str) -> dict[str, str]:
    """Payload de alta/edición de la devolución física."""
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "from_receipt": datos["origen"],
        "supplier_id": supplier_id,
        "to_warehouse": datos["bodega"],
        "item_code_0": datos["item"],
        "item_name_0": "Artículo 1755",
        "qty_0": "1",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "10",
        "source_type_0": "purchase_receipt",
        "source_id_0": datos["origen"],
        "source_item_id_0": datos["linea"],
    }


def _devoluciones(app, origen_id: str) -> list[PurchaseReceipt]:
    """Devuelve los borradores de devolución del origen indicado."""
    with app.app_context():
        return list(
            database.session.execute(database.select(PurchaseReceipt).where(PurchaseReceipt.reversal_of == origen_id))
            .scalars()
            .all()
        )


def _cliente(app):
    """Cliente autenticado sobre la app aislada del escenario."""
    from cacao_accounting.database import User

    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(admin.id)
    cliente = app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["_user_id"] = admin_id
        sesion["_fresh"] = True
    return cliente


def test_alta_de_devolucion_rechaza_proveedor_ajeno(entorno_contable_aislado):
    """Un POST manipulado con otro proveedor no crea el borrador."""
    app = entorno_contable_aislado.app
    datos = _sembrar_origen(app)

    respuesta = _cliente(app).post(
        "/buying/purchase-receipt/new",
        data=_formulario(datos, datos["ajeno"]),
    )

    assert respuesta.status_code != 302
    assert _devoluciones(app, datos["origen"]) == []


def test_alta_de_devolucion_acepta_el_proveedor_del_origen(entorno_contable_aislado):
    """Con el proveedor correcto el borrador se crea y conserva el vínculo."""
    app = entorno_contable_aislado.app
    datos = _sembrar_origen(app)

    respuesta = _cliente(app).post(
        "/buying/purchase-receipt/new",
        data=_formulario(datos, datos["origen_supplier"]),
    )

    assert respuesta.status_code == 302
    devoluciones = _devoluciones(app, datos["origen"])
    assert len(devoluciones) == 1
    assert str(devoluciones[0].supplier_id) == datos["origen_supplier"]
    assert devoluciones[0].is_return is True


def test_edicion_de_devolucion_rechaza_cambiar_el_proveedor(entorno_contable_aislado):
    """Editar el borrador no permite desvincularlo del proveedor original."""
    app = entorno_contable_aislado.app
    datos = _sembrar_origen(app)
    cliente = _cliente(app)
    cliente.post("/buying/purchase-receipt/new", data=_formulario(datos, datos["origen_supplier"]))
    devolucion_id = _devoluciones(app, datos["origen"])[0].id

    respuesta = cliente.post(
        f"/buying/purchase-receipt/{devolucion_id}/edit",
        data=_formulario(datos, datos["ajeno"]),
    )

    assert respuesta.status_code == 302
    with app.app_context():
        persistida = database.session.get(PurchaseReceipt, devolucion_id)
        assert str(persistida.supplier_id) == datos["origen_supplier"]
        assert persistida.is_return is True
