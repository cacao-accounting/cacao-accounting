# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance por compañía del origen en el alta de recepción de compra.

Escenario de negocio: un bodeguero autorizado solo en ``alpha`` no debe poder
precargar una orden o recepción de ``beta`` en el formulario de recepción,
aunque conozca el identificador. El origen aporta proveedor, compañía y
bodegas antes de cualquier validación del POST.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Entity,
    Modules,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseQuotation,
    PurchaseReceipt,
    PurchaseRequest,
    SupplierQuotation,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "recepcion-origen-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def recepciones_cloud():
    """Cloud con órdenes y recepciones de compra en alpha y beta."""
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
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="bodeguero",
                    user="bodeguero",
                    name="Bodeguero Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="comprador",
                    user="comprador",
                    name="Comprador Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="bodeguero", company_code="alpha"),
                UserCompanyAccess(user_id="comprador", company_code="alpha"),
                PurchaseOrder(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PO-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                PurchaseOrder(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PO-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
                PurchaseReceipt(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PR-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                PurchaseReceipt(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PR-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
                PurchaseInvoice(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PI-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                PurchaseInvoice(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PI-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
                PurchaseRequest(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PRQ-ALPHA",
                    remarks="Solicitud Alpha",
                ),
                PurchaseRequest(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PRQ-BETA",
                    remarks="Solicitud Confidencial Beta",
                ),
                PurchaseQuotation(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="RFQ-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                PurchaseQuotation(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="RFQ-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
                SupplierQuotation(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="SQ-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                SupplierQuotation(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="SQ-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("bodeguero", "inventory_auxiliar")
        asigna_rol_a_usuario("comprador", "purchasing_auxiliar")
        database.session.commit()
        ids = {
            "orden_alpha": database.session.execute(database.select(PurchaseOrder).filter_by(company="alpha")).scalar_one().id,
            "orden_beta": database.session.execute(database.select(PurchaseOrder).filter_by(company="beta")).scalar_one().id,
            "recepcion_beta": database.session.execute(database.select(PurchaseReceipt).filter_by(company="beta"))
            .scalar_one()
            .id,
            "factura_alpha": database.session.execute(database.select(PurchaseInvoice).filter_by(company="alpha"))
            .scalar_one()
            .id,
            "factura_beta": database.session.execute(database.select(PurchaseInvoice).filter_by(company="beta"))
            .scalar_one()
            .id,
            "solicitud_alpha": database.session.execute(database.select(PurchaseRequest).filter_by(company="alpha"))
            .scalar_one()
            .id,
            "solicitud_beta": database.session.execute(database.select(PurchaseRequest).filter_by(company="beta"))
            .scalar_one()
            .id,
            "rfq_alpha": database.session.execute(database.select(PurchaseQuotation).filter_by(company="alpha"))
            .scalar_one()
            .id,
            "rfq_beta": database.session.execute(database.select(PurchaseQuotation).filter_by(company="beta")).scalar_one().id,
            "cotizacion_alpha": database.session.execute(database.select(SupplierQuotation).filter_by(company="alpha"))
            .scalar_one()
            .id,
            "cotizacion_beta": database.session.execute(database.select(SupplierQuotation).filter_by(company="beta"))
            .scalar_one()
            .id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str = "bodeguero") -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_recepcion_no_precarga_orden_de_otra_compania(recepciones_cloud):
    """La orden ajena no serializa proveedor ni compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/buying/purchase-receipt/new?from_order={ids['orden_beta']}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "Proveedor Confidencial Beta" not in cuerpo


def test_recepcion_no_precarga_recepcion_de_otra_compania(recepciones_cloud):
    """La recepción ajena tampoco se usa como origen de devolución."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/buying/purchase-receipt/new?from_receipt={ids['recepcion_beta']}")

    assert response.status_code == 403
    assert "Proveedor Confidencial Beta" not in response.get_data(as_text=True)


def test_recepcion_precarga_orden_propia(recepciones_cloud):
    """Control positivo: la orden de la compañía autorizada se precarga."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/buying/purchase-receipt/new?from_order={ids['orden_alpha']}")

    assert response.status_code == 200
    assert "Proveedor Alpha" in response.get_data(as_text=True)


def test_orden_compra_no_precarga_solicitud_ajena(recepciones_cloud):
    """El alta de orden de compra no usa una solicitud de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-order/new?from_request={ids['solicitud_beta']}")

    assert response.status_code == 403
    assert "Solicitud Confidencial Beta" not in response.get_data(as_text=True)


def test_orden_compra_precarga_solicitud_propia(recepciones_cloud):
    """Control positivo: la solicitud autorizada se sigue precargando."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-order/new?from_request={ids['solicitud_alpha']}")

    assert response.status_code == 200
    assert f'name="from_request" value="{ids["solicitud_alpha"]}"' in response.get_data(as_text=True)


def test_factura_compra_no_precarga_orden_ajena(recepciones_cloud):
    """El alta de factura de compra no usa una orden de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-invoice/new?from_order={ids['orden_beta']}")

    assert response.status_code == 403
    assert "Proveedor Confidencial Beta" not in response.get_data(as_text=True)


def test_factura_compra_precarga_orden_propia(recepciones_cloud):
    """Control positivo: la orden autorizada se sigue precargando."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-invoice/new?from_order={ids['orden_alpha']}")

    assert response.status_code == 200
    assert "Proveedor Alpha" in response.get_data(as_text=True)


def test_orden_compra_no_precarga_un_rfq_ajeno(recepciones_cloud):
    """El alta de orden tampoco acepta un RFQ de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-order/new?from_rfq={ids['rfq_beta']}")

    assert response.status_code == 403
    assert "Proveedor Confidencial Beta" not in response.get_data(as_text=True)


def test_orden_compra_no_precarga_una_cotizacion_ajena(recepciones_cloud):
    """El alta de orden tampoco acepta una cotización de proveedor ajena."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-order/new?from_supplier_quotation={ids['cotizacion_beta']}")

    assert response.status_code == 403
    assert "Proveedor Confidencial Beta" not in response.get_data(as_text=True)


def test_orden_compra_rechaza_post_con_origen_ajeno(recepciones_cloud):
    """El POST no debe crear una orden desde una solicitud de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.post("/buying/purchase-order/new", data={"from_request": ids["solicitud_beta"]})

    assert response.status_code == 403
    with application.app_context():
        ordenes = database.session.execute(database.select(PurchaseOrder)).scalars().all()
        assert len(ordenes) == 2


def test_factura_compra_no_precarga_recepcion_ajena(recepciones_cloud):
    """El alta de factura no usa una recepción de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-invoice/new?from_receipt={ids['recepcion_beta']}")

    assert response.status_code == 403
    assert "Proveedor Confidencial Beta" not in response.get_data(as_text=True)


def test_factura_compra_no_precarga_factura_ajena(recepciones_cloud):
    """El alta de nota no usa una factura de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/purchase-invoice/new?from_invoice={ids['factura_beta']}")

    assert response.status_code == 403
    assert "Proveedor Confidencial Beta" not in response.get_data(as_text=True)


def test_factura_compra_rechaza_post_con_origen_ajeno(recepciones_cloud):
    """El POST no debe crear una factura desde una orden de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.post("/buying/purchase-invoice/new", data={"from_order": ids["orden_beta"]})

    assert response.status_code == 403
    with application.app_context():
        facturas = database.session.execute(database.select(PurchaseInvoice)).scalars().all()
        assert len(facturas) == 2


def test_solicitud_cotizacion_no_precarga_solicitud_ajena(recepciones_cloud):
    """El alta de solicitud de cotización no usa una solicitud de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/request-for-quotation/new?from_request={ids['solicitud_beta']}")

    assert response.status_code == 403
    assert "Solicitud Confidencial Beta" not in response.get_data(as_text=True)


def test_solicitud_cotizacion_rechaza_post_con_origen_ajeno(recepciones_cloud):
    """El POST no debe crear una solicitud desde un origen de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.post("/buying/request-for-quotation/new", data={"from_request": ids["solicitud_beta"]})

    assert response.status_code == 403
    with application.app_context():
        assert len(database.session.execute(database.select(PurchaseQuotation)).scalars().all()) == 2
        assert len(database.session.execute(database.select(SupplierQuotation)).scalars().all()) == 2


def test_solicitud_cotizacion_precarga_solicitud_propia(recepciones_cloud):
    """Control positivo: la solicitud autorizada se sigue precargando."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/request-for-quotation/new?from_request={ids['solicitud_alpha']}")

    assert response.status_code == 200
    assert f'value="{ids["solicitud_alpha"]}"' in response.get_data(as_text=True)


def test_costo_importado_no_expone_factura_ajena(recepciones_cloud):
    """El alta de costo importado no precarga una factura de otra compañía."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/import-landed-cost/new?from_invoice={ids['factura_beta']}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "PI-BETA" not in cuerpo
    assert "Proveedor Confidencial Beta" not in cuerpo


def test_costo_importado_precarga_factura_propia(recepciones_cloud):
    """Control positivo: la factura de la compañía autorizada se precarga."""
    application, ids = recepciones_cloud
    client = application.test_client()
    _iniciar(client, "comprador")

    response = client.get(f"/buying/import-landed-cost/new?from_invoice={ids['factura_alpha']}")

    assert response.status_code == 200
    assert "PI-ALPHA" in response.get_data(as_text=True)
