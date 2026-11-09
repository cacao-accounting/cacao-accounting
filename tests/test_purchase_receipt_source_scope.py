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
    PurchaseOrder,
    PurchaseReceipt,
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
                UserCompanyAccess(user_id="bodeguero", company_code="alpha"),
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
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("bodeguero", "inventory_auxiliar")
        database.session.commit()
        ids = {
            "orden_alpha": database.session.execute(database.select(PurchaseOrder).filter_by(company="alpha")).scalar_one().id,
            "orden_beta": database.session.execute(database.select(PurchaseOrder).filter_by(company="beta")).scalar_one().id,
            "recepcion_beta": database.session.execute(database.select(PurchaseReceipt).filter_by(company="beta"))
            .scalar_one()
            .id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "bodeguero", "acceso": CONTRASENA}, follow_redirects=True)
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
