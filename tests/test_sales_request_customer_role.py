# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El pedido de venta solo acepta terceros con rol cliente.

Escenario de negocio (issue #2056): el Smart Select filtraba por
``party_type=customer``, pero los writers de alta y edición cargaban el
``Party`` por ID sin comprobar ``is_customer``. Un proveedor podía quedar
como cliente del pedido, y un ID inexistente se persistía hasta fallar en la
base.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    SalesRequest,
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
        cliente = Party(code="CLI-1", name="Cliente Uno", is_customer=True)
        proveedor = Party(code="PRV-1", name="Proveedor Uno", is_supplier=True, is_customer=False)
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="sales", default=False, enabled=True),
                UOM(code="Unidad", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code="ART-1",
                    name="Artículo vendible",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=True,
                    default_uom="Unidad",
                ),
                cliente,
                proveedor,
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.commit()
        ids = {"cliente": cliente.id, "proveedor": proveedor.id}
    return application, ids


def _cliente_autenticado(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _payload(customer_id: str | None) -> dict[str, str]:
    datos = {
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "item_code_0": "ART-1",
        "item_name_0": "Artículo vendible",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "Unidad",
    }
    if customer_id:
        datos["customer_id"] = customer_id
    return datos


def test_rechaza_un_proveedor_como_cliente_del_pedido():
    """Un tercero sin rol cliente no se persiste como cabecera."""
    application, ids = _crear_app()
    try:
        client = _cliente_autenticado(application)
        respuesta = client.post("/sales/sales-request/new", data=_payload(ids["proveedor"]))

        assert respuesta.status_code == 200
        assert "no está habilitado como cliente" in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(SalesRequest)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_rechaza_un_tercero_inexistente():
    """Un ID que no existe se rechaza antes de tocar la base."""
    application, _ = _crear_app()
    try:
        client = _cliente_autenticado(application)
        respuesta = client.post("/sales/sales-request/new", data=_payload("NO-EXISTE"))

        assert respuesta.status_code == 200
        assert "El tercero no existe" in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(SalesRequest)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_no_muta_la_cabecera_con_un_proveedor():
    """La edición rechaza el cambio y conserva el cliente original."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            pedido = SalesRequest(
                company="cacao",
                posting_date=FECHA,
                docstatus=0,
                customer_id=ids["cliente"],
                customer_name="Cliente Uno",
            )
            database.session.add(pedido)
            database.session.commit()
            pedido_id = pedido.id

        client = _cliente_autenticado(application)
        respuesta = client.post(f"/sales/sales-request/{pedido_id}/edit", data=_payload(ids["proveedor"]))

        assert respuesta.status_code == 302
        with application.app_context():
            registro = database.session.execute(database.select(SalesRequest).filter_by(id=pedido_id)).scalar_one()
            assert registro.customer_id == ids["cliente"]
            assert registro.customer_name == "Cliente Uno"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_acepta_una_solicitud_interna_sin_cliente():
    """El flujo interno sin cliente se conserva."""
    application, _ = _crear_app()
    try:
        client = _cliente_autenticado(application)
        respuesta = client.post("/sales/sales-request/new", data=_payload(None))

        assert respuesta.status_code == 302
        with application.app_context():
            pedidos = database.session.execute(database.select(SalesRequest)).scalars().all()
            assert len(pedidos) == 1
            assert pedidos[0].customer_id is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
