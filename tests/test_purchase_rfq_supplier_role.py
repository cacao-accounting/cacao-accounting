# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La solicitud de cotización solo acepta terceros proveedores.

Escenario de negocio (issue #2136): el alta y la edición manual guardaban el
nombre de cualquier ``supplier_id`` enviado, sin comprobar ``is_supplier``.
La RFQ interna puede no llevar proveedor, pero un ID informado debe tener el
rol correcto.
"""

from __future__ import annotations

from datetime import date

from flask_login import login_user
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.services import (
    _create_purchase_quotation_from_request,
    _handle_purchase_quotation_edit_post,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseQuotation,
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
        proveedor = Party(code="PRV-1", name="Proveedor Uno", is_supplier=True, is_customer=False)
        cliente = Party(code="CLI-1", name="Cliente Uno", is_customer=True, is_supplier=False)
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
                proveedor,
                cliente,
            ]
        )
        database.session.commit()
        ids = {"proveedor": proveedor.id, "cliente": cliente.id}
    return application, ids


def _formulario(supplier_id: str | None) -> dict[str, str]:
    datos = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "item_code_0": "ART-1",
        "item_name_0": "Artículo",
        "qty_0": "1",
        "uom_0": "Unidad",
    }
    if supplier_id:
        datos["supplier_id"] = supplier_id
    return datos


def test_el_alta_rechaza_un_cliente_como_proveedor():
    """Un Party sin rol proveedor no se persiste."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            admin = database.session.get(User, "admin")
            with application.test_request_context("/", method="POST", data=_formulario(ids["cliente"])):
                login_user(admin)
                assert _create_purchase_quotation_from_request() is None

            assert database.session.execute(database.select(PurchaseQuotation)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_alta_acepta_proveedor_y_solicitud_sin_proveedor():
    """El control positivo conserva ambos caminos válidos."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            admin = database.session.get(User, "admin")
            with application.test_request_context("/", method="POST", data=_formulario(ids["proveedor"])):
                login_user(admin)
                respuesta = _create_purchase_quotation_from_request()
            assert respuesta is not None

            with application.test_request_context("/", method="POST", data=_formulario(None)):
                login_user(admin)
                respuesta = _create_purchase_quotation_from_request()
            assert respuesta is not None

            cotizaciones = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
            assert len(cotizaciones) == 2
            assert {cotizacion.supplier_id for cotizacion in cotizaciones} == {ids["proveedor"], None}
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_no_muta_la_cabecera_con_un_cliente():
    """La edición rechaza el cambio y conserva el proveedor original."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            cotizacion = PurchaseQuotation(
                company="cacao",
                posting_date=FECHA,
                docstatus=0,
                supplier_id=ids["proveedor"],
                supplier_name="Proveedor Uno",
                transaction_currency="NIO",
            )
            database.session.add(cotizacion)
            database.session.commit()
            cotizacion_id = cotizacion.id

            admin = database.session.get(User, "admin")
            with application.test_request_context("/", method="POST", data=_formulario(ids["cliente"])):
                login_user(admin)
                respuesta = _handle_purchase_quotation_edit_post(cotizacion)

            assert respuesta is not None
            registro = database.session.execute(database.select(PurchaseQuotation).filter_by(id=cotizacion_id)).scalar_one()
            assert registro.supplier_id == ids["proveedor"]
            assert registro.supplier_name == "Proveedor Uno"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
