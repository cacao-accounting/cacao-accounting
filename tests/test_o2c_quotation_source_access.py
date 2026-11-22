# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1971: el alta de cotización autoriza la solicitud de origen antes de renderizar.

Un usuario con acceso a Ventas en una compañía no debe recibir los metadatos
del cliente ni de la compañía de una solicitud de venta ajena al abrir el
formulario con ``from_request``.
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
    Currency,
    Entity,
    Modules,
    SalesRequest,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "cotizacion-2026"
FECHA = date(2026, 5, 12)


@pytest.fixture
def solicitudes_por_compania():
    """Dos compañías con una solicitud de venta privada en cada una."""
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
                Entity(code="cafe", name="Café", company_name="Café SA", tax_id="J-2", currency="NIO", enabled=True),
                User(
                    id="vendedor_cacao",
                    user="vendedor_cacao",
                    name="Vendedor Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="vendedor_cacao", company_code="cacao"),
            ]
        )
        database.session.flush()
        propia = SalesRequest(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            customer_name="Cliente Cacao",
        )
        ajena = SalesRequest(
            company="cafe",
            posting_date=FECHA,
            docstatus=0,
            customer_name="Cliente Confidencial Cafe",
        )
        database.session.add_all([propia, ajena])
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("vendedor_cacao", "sales_auxiliar")
        ids = {"propia": propia.id, "ajena": ajena.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(client, usuario: str) -> None:
    """Autentica al usuario del escenario mediante el login real."""
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_cotizacion_expone_solicitud_de_la_misma_compania(solicitudes_por_compania):
    """El origen autorizado se serializa en el formulario de cotización."""
    application, ids = solicitudes_por_compania
    client = application.test_client()
    _login(client, "vendedor_cacao")

    response = client.get(f"/sales/quotation/new?from_request={ids['propia']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Cliente Cacao" in body


def test_cotizacion_oculta_solicitud_de_otra_compania(solicitudes_por_compania):
    """La solicitud ajena se rechaza sin serializar cliente ni compañía."""
    application, ids = solicitudes_por_compania
    client = application.test_client()
    _login(client, "vendedor_cacao")

    response = client.get(f"/sales/quotation/new?from_request={ids['ajena']}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "Cliente Confidencial Cafe" not in body
    assert "cafe" not in body


def test_cotizacion_requiere_login_para_el_origen(solicitudes_por_compania):
    """Sin sesión no se expone la solicitud de origen."""
    application, ids = solicitudes_por_compania
    client = application.test_client()

    response = client.get(f"/sales/quotation/new?from_request={ids['ajena']}")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
