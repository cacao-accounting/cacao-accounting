# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La orden de compra manual valida rol, estado y membresía del proveedor.

Escenario de negocio (issue #1823): creación, edición y aprobación aceptaban
cualquier ``supplier_id``. Una OC con cliente, proveedor inactivo o sin
``CompanyParty`` activo rompía la cadena S2P en recepción o factura.
"""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import login_user
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.services import (
    _create_purchase_order_from_request,
    _update_purchase_order_from_request,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    UOM,
    User,
    database,
)

FECHA = date(2026, 10, 15)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        valido = Party(code="PRV-OK", name="Proveedor Válido", is_supplier=True, is_active=True)
        cliente = Party(code="CLI-1", name="Cliente", is_customer=True, is_supplier=False)
        inactivo = Party(code="PRV-OFF", name="Proveedor Inactivo", is_supplier=True, is_active=False)
        sin_membresia = Party(code="PRV-SIN", name="Proveedor Sin Vínculo", is_supplier=True, is_active=True)
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="Unidad", name="Unidad"),
                Item(
                    code="ART-1",
                    name="Artículo",
                    item_type="goods",
                    is_stock_item=False,
                    is_purchase_item=True,
                    is_active=True,
                    default_uom="Unidad",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
                valido,
                cliente,
                inactivo,
                sin_membresia,
            ]
        )
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=valido.id, is_active=True))
        database.session.commit()
        ids = {
            "valido": valido.id,
            "cliente": cliente.id,
            "inactivo": inactivo.id,
            "sin_membresia": sin_membresia.id,
        }
    return application, ids


def _formulario(supplier_id: str | None) -> dict[str, str]:
    datos = {
        "company": "cacao",
        "transaction_currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "item_code_0": "ART-1",
        "item_name_0": "Artículo",
        "qty_0": "1",
        "rate_0": "10",
        "amount_0": "10",
        "uom_0": "Unidad",
    }
    if supplier_id:
        datos["supplier_id"] = supplier_id
    return datos


def test_el_alta_rechaza_proveedores_invalidos():
    """Cliente, inactivo y sin vínculo no se persisten."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            admin = database.session.get(User, "admin")
            for clave in ("cliente", "inactivo", "sin_membresia"):
                with application.test_request_context("/", method="POST", data=_formulario(ids[clave])):
                    login_user(admin)
                    assert _create_purchase_order_from_request(request.form) is None, clave

            assert database.session.execute(database.select(PurchaseOrder)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_alta_acepta_un_proveedor_con_membresia():
    """El control positivo conserva el alta normal."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            admin = database.session.get(User, "admin")
            with application.test_request_context("/", method="POST", data=_formulario(ids["valido"])):
                login_user(admin)
                respuesta = _create_purchase_order_from_request(request.form)

            assert respuesta is not None
            orden = database.session.execute(database.select(PurchaseOrder)).scalar_one()
            assert orden.supplier_id == ids["valido"]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_conserva_el_proveedor_original():
    """Cambiar a un cliente se rechaza con rollback."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            orden = PurchaseOrder(
                company="cacao",
                posting_date=FECHA,
                docstatus=0,
                supplier_id=ids["valido"],
                supplier_name="Proveedor Válido",
                transaction_currency="NIO",
            )
            database.session.add(orden)
            database.session.commit()
            admin = database.session.get(User, "admin")

            with application.test_request_context("/", method="POST", data=_formulario(ids["cliente"])):
                login_user(admin)
                respuesta = _update_purchase_order_from_request(orden)

            assert respuesta is not None
            registro = database.session.execute(database.select(PurchaseOrder).filter_by(id=orden.id)).scalar_one()
            assert registro.supplier_id == ids["valido"]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_aprobacion_rechaza_un_proveedor_invalido():
    """El submit no publica una OC con cliente como proveedor."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            orden = PurchaseOrder(
                company="cacao",
                posting_date=FECHA,
                docstatus=0,
                supplier_id=ids["cliente"],
                supplier_name="Cliente",
                transaction_currency="NIO",
            )
            database.session.add(orden)
            database.session.flush()
            database.session.add(
                PurchaseOrderItem(
                    purchase_order_id=orden.id,
                    item_code="ART-1",
                    item_name="Artículo",
                    qty=1,
                    rate=10,
                    amount=10,
                    uom="Unidad",
                )
            )
            database.session.commit()
            orden_id = orden.id

        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.post(f"/buying/purchase-order/{orden_id}/submit")

        assert respuesta.status_code == 302
        with application.app_context():
            registro = database.session.execute(database.select(PurchaseOrder).filter_by(id=orden_id)).scalar_one()
            assert registro.docstatus == 0
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
