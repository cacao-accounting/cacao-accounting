# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Aislamiento de compañía en el motor documental de la API.

Escenario de negocio (issue #1019): una empresa comercial opera dos compañías
(``cacao`` y ``cafe``); un vendedor de la primera no debe poder crear
documentos en la segunda ni copiar líneas de sus documentos, ni siquiera
presentando una cabecera propia en el ``payload`` del endpoint
``POST /api/document-flow/create-target``. El endpoint de líneas pendientes
autoriza cada documento origen de forma individual y exige el permiso del
módulo fuente, no solo acceso a la compañía.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    DeliveryNote,
    DocumentRelation,
    Entity,
    Item,
    Modules,
    SalesInvoice,
    SalesOrder,
    SalesOrderItem,
    SalesRequest,
    SalesRequestItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

FECHA = date(2026, 10, 15)
CONTRASENA = "cafecacao-2026"


def _sembrar_escenario() -> dict[str, str]:
    """Crea dos compañías, un vendedor con alcance solo en 'cacao' y documentos reales."""
    database.session.add_all(
        [
            Modules(module="sales", default=False, enabled=True),
            Modules(module="inventory", default=False, enabled=True),
            Entity(
                code="cacao",
                name="Cacao Accounting",
                company_name="Cacao Accounting SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            ),
            Entity(code="cafe", name="Cafe SA", company_name="Cafe SA", tax_id="J0002", currency="NIO", enabled=True),
            AccountingPeriod(
                entity="cacao",
                name="PERIODO-AUTORIZADO-CACAO",
                start=FECHA,
                end=FECHA,
                enabled=True,
                is_closed=False,
            ),
            AccountingPeriod(
                entity="cafe",
                name="PERIODO-CONFIDENCIAL-CAFE",
                start=FECHA,
                end=FECHA,
                enabled=True,
                is_closed=False,
            ),
            UOM(code="Unidad", name="Unidad"),
            Item(
                code="CACAO-ABARROTES-EXPO",
                name="Cacao en Grano",
                item_type="goods",
                is_stock_item=False,
                default_uom="Unidad",
            ),
            User(id="vendedor", user="vendedor", name="Vendedor Local", password=proteger_passwd(CONTRASENA), active=True),
            User(id="tesorero", user="tesorero", name="Tesorero", password=proteger_passwd(CONTRASENA), active=True),
            User(id="bodeguero", user="bodeguero", name="Bodeguero", password=proteger_passwd(CONTRASENA), active=True),
            User(id="operador", user="operador", name="Operador O2C", password=proteger_passwd(CONTRASENA), active=True),
            UserCompanyAccess(user_id="vendedor", company_code="cacao"),
            UserCompanyAccess(user_id="tesorero", company_code="cacao"),
            UserCompanyAccess(user_id="bodeguero", company_code="cacao"),
            UserCompanyAccess(user_id="operador", company_code="cacao"),
            SalesRequest(company="cacao", posting_date=FECHA, docstatus=1, customer_name="Cliente Cacao"),
            SalesRequest(
                company="cafe",
                posting_date=FECHA,
                docstatus=1,
                document_no="SR-CAFE-1",
                customer_name="Cliente Confidencial Cafe",
            ),
            SalesOrder(company="cafe", posting_date=FECHA, docstatus=1, document_no="SO-CAFE-1", customer_name="Cliente Cafe"),
            DeliveryNote(
                company="cacao",
                posting_date=FECHA,
                docstatus=1,
                document_no="DN-CACAO-1",
                customer_name="Cliente Cacao",
            ),
            DeliveryNote(
                company="cafe",
                posting_date=FECHA,
                docstatus=1,
                document_no="DN-CAFE-1",
                customer_name="Cliente Confidencial Cafe",
            ),
        ]
    )
    database.session.commit()
    crea_roles_predeterminados()
    cargar_permisos_predeterminados()
    asigna_rol_a_usuario("vendedor", "sales_auxiliar")
    asigna_rol_a_usuario("tesorero", "user_of_treasury")
    asigna_rol_a_usuario("bodeguero", "inventory_auxiliar")
    asigna_rol_a_usuario("operador", "sales_auxiliar")
    asigna_rol_a_usuario("operador", "inventory_auxiliar")
    database.session.flush()

    pedido_propio = database.session.execute(database.select(SalesRequest).filter_by(company="cacao")).scalar_one()
    solicitud_ajena = database.session.execute(database.select(SalesRequest).filter_by(company="cafe")).scalar_one()
    orden_ajena = database.session.execute(database.select(SalesOrder)).scalar_one()
    entrega_propia = database.session.execute(database.select(DeliveryNote).filter_by(company="cacao")).scalar_one()
    entrega_ajena = database.session.execute(database.select(DeliveryNote).filter_by(company="cafe")).scalar_one()
    linea_propia = SalesRequestItem(
        sales_request_id=pedido_propio.id,
        item_code="CACAO-ABARROTES-EXPO",
        item_name="Cacao en Grano",
        qty=Decimal("50"),
        qty_in_base_uom=Decimal("50"),
        uom="Unidad",
        rate=Decimal("10"),
        amount=Decimal("500"),
    )
    linea_ajena = SalesOrderItem(
        sales_order_id=orden_ajena.id,
        item_code="CACAO-ABARROTES-EXPO",
        item_name="Cacao en Grano",
        qty=Decimal("10"),
        qty_in_base_uom=Decimal("10"),
        uom="Unidad",
        rate=Decimal("25"),
        amount=Decimal("250"),
    )
    database.session.add_all([linea_propia, linea_ajena])
    database.session.commit()
    return {
        "pedido_propio": pedido_propio.id,
        "linea_propia": linea_propia.id,
        "orden_ajena": orden_ajena.id,
        "linea_ajena": linea_ajena.id,
        "solicitud_ajena": solicitud_ajena.id,
        "entrega_propia": entrega_propia.id,
        "entrega_ajena": entrega_ajena.id,
    }


@pytest.fixture
def escenario_multicompania():
    """Aplicación en modo cloud con el escenario de negocio sembrado."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        ids = _sembrar_escenario()
    yield application, application.test_client(), ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar_sesion(client, usuario: str = "vendedor") -> None:
    """Autentica al usuario indicado (por defecto, el vendedor de 'cacao')."""
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_dashboard_solo_serializa_periodos_de_companias_autorizadas(escenario_multicompania):
    """Refs: 1608. El HTML inicial no debe revelar periodos de otra compañía."""
    _, client, _ = escenario_multicompania
    _iniciar_sesion(client)

    response = client.get("/app")

    assert response.status_code == 200
    assert b"PERIODO-AUTORIZADO-CACAO" in response.data
    assert b"PERIODO-CONFIDENCIAL-CAFE" not in response.data


def _payload_crear(pedido_propio: str, lines: list[dict]) -> dict:
    """Payload con cabecera legítima del vendedor sobre su propio pedido."""
    return {
        "target_document_type": "sales_order",
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "customer_name": "Cliente Cacao",
        "source_document_type": "sales_request",
        "source_document_id": pedido_propio,
        "lines": lines,
    }


def test_crear_orden_con_lineas_propias_copia_datos_del_pedido(escenario_multicompania):
    """Control positivo: el vendedor materializa su pedido en su propia compañía."""
    application, client, ids = escenario_multicompania
    _iniciar_sesion(client)
    payload = _payload_crear(
        ids["pedido_propio"],
        [
            {
                "source_document_type": "sales_request",
                "source_document_id": ids["pedido_propio"],
                "source_row_id": ids["linea_propia"],
                "qty": 10,
            }
        ],
    )
    response = client.post("/api/document-flow/create-target", json=payload)
    assert response.status_code == 201
    with application.app_context():
        orden = database.session.execute(
            database.select(SalesOrderItem)
            .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
            .filter(SalesOrder.company == "cacao")
        ).scalar_one()
        assert orden.item_code == "CACAO-ABARROTES-EXPO"
        assert Decimal(str(orden.rate)) == Decimal("10")


def test_rechaza_lineas_de_otra_compania_aun_con_cabecera_propia(escenario_multicompania):
    """La cabecera propia no autoriza copiar ítems, cantidades ni tarifas ajenas."""
    application, client, ids = escenario_multicompania
    _iniciar_sesion(client)
    payload = _payload_crear(
        ids["pedido_propio"],
        [
            {
                "source_document_type": "sales_order",
                "source_document_id": ids["orden_ajena"],
                "source_row_id": ids["linea_ajena"],
                "qty": 10,
            }
        ],
    )
    response = client.post("/api/document-flow/create-target", json=payload)
    assert response.status_code == 403
    with application.app_context():
        ordenes = database.session.execute(database.select(SalesOrder).filter(SalesOrder.company == "cacao")).scalars().all()
        assert ordenes == []
        relaciones = database.session.execute(database.select(DocumentRelation)).scalars().all()
        assert relaciones == []


def test_rechaza_linea_ajena_camuflada_con_id_de_cabecera_propia(escenario_multicompania):
    """Una línea ajena con ``source_document_id`` propio no debe cruzar por el servicio."""
    application, client, ids = escenario_multicompania
    _iniciar_sesion(client)
    payload = _payload_crear(
        ids["pedido_propio"],
        [
            {
                "source_document_type": "sales_order",
                "source_document_id": ids["pedido_propio"],
                "source_row_id": ids["linea_ajena"],
                "qty": 10,
            }
        ],
    )
    response = client.post("/api/document-flow/create-target", json=payload)
    assert response.status_code == 400
    with application.app_context():
        ordenes = database.session.execute(database.select(SalesOrder).filter(SalesOrder.company == "cacao")).scalars().all()
        assert ordenes == []
        relaciones = database.session.execute(database.select(DocumentRelation)).scalars().all()
        assert relaciones == []


def test_rechaza_compania_destino_sin_acceso_del_usuario(escenario_multicompania):
    """El vendedor no puede materializar la orden en la compañía 'cafe'."""
    application, client, ids = escenario_multicompania
    _iniciar_sesion(client)
    payload = _payload_crear(
        ids["pedido_propio"],
        [
            {
                "source_document_type": "sales_request",
                "source_document_id": ids["pedido_propio"],
                "source_row_id": ids["linea_propia"],
                "qty": 10,
            }
        ],
    )
    payload["company"] = "cafe"
    response = client.post("/api/document-flow/create-target", json=payload)
    assert response.status_code == 403
    with application.app_context():
        ordenes_cafe = (
            database.session.execute(database.select(SalesOrder).filter(SalesOrder.company == "cafe")).scalars().all()
        )
        assert len(ordenes_cafe) == 1  # solo la orden víctima original del escenario


def test_el_cierre_de_saldo_respeta_el_alcance_de_compania(escenario_multicompania):
    """close-line solo opera sobre documentos de la compañía del usuario."""
    application, client, ids = escenario_multicompania
    _iniciar_sesion(client)
    response = client.post(
        "/api/document-flow/close-line",
        json={
            "source_document_type": "sales_order",
            "source_document_id": ids["orden_ajena"],
            "source_row_id": ids["linea_ajena"],
            "target_document_type": "sales_invoice",
            "reason": "Cierre de saldo sin derecho",
        },
    )
    assert response.status_code == 403
    with application.app_context():
        estados = database.session.execute(database.select(DocumentRelation)).scalars().all()
        assert estados == []


def test_el_vendedor_puede_cerrar_saldo_de_su_propia_linea(escenario_multicompania):
    """El mismo endpoint funciona sobre documentos del alcance del usuario."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client)
    response = client.post(
        "/api/document-flow/close-line",
        json={
            "source_document_type": "sales_request",
            "source_document_id": ids["pedido_propio"],
            "source_row_id": ids["linea_propia"],
            "target_document_type": "sales_order",
            "reason": "Pedido cancelado por el cliente",
        },
    )
    assert response.status_code == 200
    state = response.get_json()["state"]
    assert Decimal(str(state["closed_qty"])) == Decimal("50")
    assert Decimal(str(state["pending_qty"])) == Decimal("0")


def test_cotizacion_no_precarga_una_solicitud_de_otra_compania(escenario_multicompania):
    """El formulario de cotización no serializa datos del origen ajeno."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client)

    response = client.get(f"/sales/quotation/new?from_request={ids['solicitud_ajena']}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "Cliente Confidencial Cafe" not in cuerpo


def test_cotizacion_precarga_una_solicitud_propia(escenario_multicompania):
    """Control positivo: el origen autorizado se sigue precargando."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client)

    response = client.get(f"/sales/quotation/new?from_request={ids['pedido_propio']}")

    assert response.status_code == 200
    assert "Cliente Cacao" in response.get_data(as_text=True)


def test_orden_venta_no_precarga_una_solicitud_ajena(escenario_multicompania):
    """El alta de orden no serializa el origen de otra compañía."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "operador")

    response = client.get(f"/sales/sales-order/new?from_request={ids['solicitud_ajena']}")

    assert response.status_code == 403
    assert "Cliente Confidencial Cafe" not in response.get_data(as_text=True)


def test_orden_venta_precarga_una_solicitud_propia(escenario_multicompania):
    """Control positivo: la solicitud autorizada se sigue precargando."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "operador")

    response = client.get(f"/sales/sales-order/new?from_request={ids['pedido_propio']}")

    assert response.status_code == 200
    assert "Cliente Cacao" in response.get_data(as_text=True)


def test_factura_venta_no_precarga_una_entrega_ajena(escenario_multicompania):
    """El alta de factura no serializa la entrega de otra compañía."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "operador")

    response = client.get(f"/sales/sales-invoice/new?from_note={ids['entrega_ajena']}")

    assert response.status_code == 403
    assert "Cliente Confidencial Cafe" not in response.get_data(as_text=True)


def test_factura_venta_precarga_una_entrega_propia(escenario_multicompania):
    """Control positivo: la entrega autorizada se sigue precargando."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "operador")

    response = client.get(f"/sales/sales-invoice/new?from_note={ids['entrega_propia']}")

    assert response.status_code == 200
    assert "Cliente Cacao" in response.get_data(as_text=True)


def test_remision_no_precarga_una_entrega_de_otra_compania(escenario_multicompania):
    """El alta de remisión no serializa el origen ajeno antes de autorizarlo."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "bodeguero")

    response = client.get(f"/sales/delivery-note/new?from_note={ids['entrega_ajena']}")

    assert response.status_code == 403
    assert "Cliente Confidencial Cafe" not in response.get_data(as_text=True)


def test_remision_exige_lectura_del_modulo_de_ventas(escenario_multicompania):
    """Inventory create no autoriza por sí solo leer el origen de ventas."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "bodeguero")

    response = client.get(f"/sales/delivery-note/new?from_note={ids['entrega_propia']}")

    assert response.status_code == 403
    assert "Cliente Cacao" not in response.get_data(as_text=True)


def test_remision_precarga_una_entrega_propia(escenario_multicompania):
    """Control positivo: con lectura de ventas, la entrega propia se precarga."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client, "operador")

    response = client.get(f"/sales/delivery-note/new?from_note={ids['entrega_propia']}")

    assert response.status_code == 200
    assert "Cliente Cacao" in response.get_data(as_text=True)


def test_items_del_flujo_rechazan_fuentes_de_otra_compania(escenario_multicompania):
    """#1468: cada documento origen del endpoint de líneas exige su propio ACL."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client)
    response = client.get(f"/api/document-flow/items?target_type=sales_invoice&source=sales_order:{ids['orden_ajena']}")
    assert response.status_code == 403


def test_items_del_flujo_rechaza_la_mezcla_de_origenes_ajenos(escenario_multicompania):
    """Una petición con origen propio y ajeno no filtra el ajeno."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client)
    response = client.get(
        "/api/document-flow/items"
        f"?target_type=sales_invoice&source=sales_request:{ids['pedido_propio']}&source=sales_order:{ids['orden_ajena']}"
    )
    assert response.status_code == 403
    assert response.get_json() is None


def test_items_del_flujo_exige_permiso_del_modulo_fuente(escenario_multicompania):
    """Tener acceso a la compañía no basta; la fuente de ventas exige ventas/consultar."""
    application, client, _ = escenario_multicompania
    with application.app_context():
        orden = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="SO-CACAO-SECRETO",
            customer_name="Cliente Cacao",
        )
        database.session.add(orden)
        database.session.flush()
        linea = SalesOrderItem(
            sales_order_id=orden.id,
            item_code="ITEM-SECRETO",
            item_name="Item solo ventas",
            qty=Decimal("7"),
            qty_in_base_uom=Decimal("7"),
            uom="Unidad",
            rate=Decimal("250"),
            amount=Decimal("1750"),
        )
        database.session.add(linea)
        database.session.commit()
        orden_id = orden.id

    _iniciar_sesion(client, "tesorero")
    response = client.get(f"/api/document-flow/items?target_type=sales_invoice&source=sales_order:{orden_id}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "ITEM-SECRETO" not in cuerpo
    assert "1750" not in cuerpo


def test_items_del_flujo_devuelve_las_lineas_de_sus_propias_fuentes(escenario_multicompania):
    """Control positivo: las líneas del propio pedido quedan disponibles."""
    client, ids = escenario_multicompania[1], escenario_multicompania[2]
    _iniciar_sesion(client)
    response = client.get(f"/api/document-flow/items?target_type=sales_order&source=sales_request:{ids['pedido_propio']}")
    assert response.status_code == 200
    datos = response.get_json()
    assert datos["target_type"] == "sales_order"
    items = datos["items"]
    assert items
    assert any(str(item.get("item_code") or "") == "CACAO-ABARROTES-EXPO" for item in items)


def test_arbol_documental_expone_el_contrato_recursivo_actual(escenario_multicompania):
    """Refs: #1071. El árbol activo devuelve nodos y metadatos recursivos."""
    application, client, ids = escenario_multicompania
    with application.app_context():
        destino = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="SO-CACAO-ARBOL-1",
            customer_name="Cliente Cacao",
        )
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="INV-CACAO-ARBOL-1",
            customer_name="Cliente Cacao",
            total=Decimal("50"),
            grand_total=Decimal("50"),
        )
        database.session.add_all([destino, factura])
        database.session.flush()
        database.session.add_all(
            [
                DocumentRelation(
                    source_type="sales_request",
                    source_id=ids["pedido_propio"],
                    target_type="sales_order",
                    target_id=destino.id,
                    company="cacao",
                    qty=Decimal("5"),
                    qty_in_base_uom=Decimal("5"),
                    uom="Unidad",
                    relation_type="sales_order",
                    status="active",
                ),
                DocumentRelation(
                    source_type="sales_order",
                    source_id=destino.id,
                    target_type="sales_invoice",
                    target_id=factura.id,
                    company="cacao",
                    qty=Decimal("5"),
                    qty_in_base_uom=Decimal("5"),
                    uom="Unidad",
                    relation_type="sales_invoice",
                    status="active",
                ),
            ]
        )
        database.session.commit()
        orden_id = destino.id
        factura_id = factura.id

    _iniciar_sesion(client)
    response = client.get(
        "/api/document-flow/tree" f"?document_type=sales_request&document_id={ids['pedido_propio']}&direction=downstream"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["current"]["document_id"] == ids["pedido_propio"]
    assert [node["document_id"] for node in payload["downstream"]] == [orden_id]
    orden = payload["downstream"][0]
    assert orden["document_no"] == "SO-CACAO-ARBOL-1"
    assert [node["document_id"] for node in orden["children"]] == [factura_id]
    assert orden["children"][0]["document_no"] == "INV-CACAO-ARBOL-1"
    assert payload["meta"]["node_count"] == 2
