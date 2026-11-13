# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance explícito de compañía en los listados de Compras.

Escenario de negocio: en Cloud, un usuario con clasificación ``admin`` pero con
asignación explícita solo a ``cacao`` no debe ver solicitudes ni proveedores de
``secreta``. La clasificación administrativa no sustituye el alcance de
compañías; las listas documentales y el directorio de proveedores deben aplicar
el mismo criterio.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Modules,
    Party,
    PurchaseRequest,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "compras-admin-scope-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def compras_cloud():
    """Cloud con dos compañías y un admin asignado solo a cacao."""
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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="secreta",
                    name="Secreta",
                    company_name="Secreta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador Cloud",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="admin", company_code="cacao"),
                PurchaseRequest(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PRQ-CACAO",
                    remarks="Solicitud visible",
                ),
                PurchaseRequest(
                    company="secreta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PRQ-SECRETA",
                    remarks="Solicitud confidencial",
                ),
            ]
        )
        database.session.flush()
        proveedor_visible = Party(code="PROV-CACAO", name="Proveedor Visible", is_supplier=True)
        proveedor_ajeno = Party(code="PROV-SECRETO", name="Proveedor Confidencial", is_supplier=True)
        database.session.add_all([proveedor_visible, proveedor_ajeno])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=proveedor_visible.id, is_active=True),
                CompanyParty(company="secreta", party_id=proveedor_ajeno.id, is_active=True),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_admin_no_ve_solicitudes_de_companias_no_asignadas(compras_cloud):
    """La lista documental respeta las asignaciones explícitas del admin."""
    client = compras_cloud.test_client()
    _iniciar(client)

    response = client.get("/buying/purchase-request/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "PRQ-CACAO" in cuerpo
    assert "PRQ-SECRETA" not in cuerpo


def test_admin_no_ve_proveedores_de_companias_no_asignadas(compras_cloud):
    """El directorio de proveedores usa el mismo alcance explícito."""
    client = compras_cloud.test_client()
    _iniciar(client)

    response = client.get("/buying/supplier/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Proveedor Visible" in cuerpo
    assert "Proveedor Confidencial" not in cuerpo
