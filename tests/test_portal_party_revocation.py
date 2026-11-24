# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1919: el portal revoca el acceso cuando el tercero o su vínculo se desactiva.

La decisión acordada exige `Party.is_active` y `CompanyParty.is_active` para la
compañía del usuario en cada consulta del portal, incluidos documentos
históricos. La desactivación no modifica la evidencia.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Party,
    PurchaseInvoice,
    Roles,
    RolesUser,
    SalesInvoice,
    User,
    database,
)

FECHA = date(2026, 5, 15)
CONTRASENA_PORTAL = "PortalPass-2026!"


@pytest.fixture
def portal_revocable():
    """Portal cloud con cliente y proveedor activos en la compañía."""
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
    suffix = uuid4().hex[:6]
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        cliente = Party(code=f"CLI-{suffix}", name="Cliente Portal", is_customer=True, is_active=True)
        proveedor = Party(code=f"PRV-{suffix}", name="Proveedor Portal", is_supplier=True, is_active=True)
        otro_cliente = Party(code=f"OTR-{suffix}", name="Otro Cliente", is_customer=True, is_active=True)
        database.session.add_all([cliente, proveedor, otro_cliente])
        database.session.flush()
        rol_admin = Roles(name="admin", note="Administración")
        database.session.add(rol_admin)
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente.id, is_active=True),
                CompanyParty(company="cacao", party_id=proveedor.id, is_active=True),
                CompanyParty(company="cacao", party_id=otro_cliente.id, is_active=True),
                User(
                    id=f"portal-cliente-{suffix}",
                    user=f"portal_cliente_{suffix}",
                    name="Cliente Portal",
                    password=proteger_passwd(CONTRASENA_PORTAL),
                    active=True,
                    classification="customer",
                    party_id=cliente.id,
                    company="cacao",
                ),
                User(
                    id=f"portal-proveedor-{suffix}",
                    user=f"portal_proveedor_{suffix}",
                    name="Proveedor Portal",
                    password=proteger_passwd(CONTRASENA_PORTAL),
                    active=True,
                    classification="supplier",
                    party_id=proveedor.id,
                    company="cacao",
                ),
                User(
                    id=f"portal-mixto-{suffix}",
                    user=f"portal_mixto_{suffix}",
                    name="Cliente con rol admin",
                    password=proteger_passwd(CONTRASENA_PORTAL),
                    active=True,
                    classification="customer",
                    party_id=cliente.id,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(RolesUser(user_id=f"portal-mixto-{suffix}", role_id=rol_admin.id, active=True))
        database.session.flush()
        factura_venta = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="FAC-PORTAL-1919",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("100"),
            total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        factura_compra = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="CMP-PORTAL-1919",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
        )
        factura_otro = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="FAC-PORTAL-OTRO",
            customer_id=otro_cliente.id,
            customer_name=otro_cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("50"),
            total=Decimal("50"),
            outstanding_amount=Decimal("50"),
        )
        database.session.add_all([factura_venta, factura_compra, factura_otro])
        database.session.commit()
        ids = {
            "cliente": cliente.id,
            "proveedor": proveedor.id,
            "cliente_user": f"portal-cliente-{suffix}",
            "proveedor_user": f"portal-proveedor-{suffix}",
            "mixto_user": f"portal-mixto-{suffix}",
            "factura_venta": factura_venta.id,
            "factura_compra": factura_compra.id,
            "factura_otro": factura_otro.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _client_for(application: Any, user_id: str):
    """Cliente HTTP con sesión del usuario indicado."""
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def _deactivate_party(application: Any, party_id: str) -> None:
    """Desactiva el tercero conservando la evidencia."""
    with application.app_context():
        party = database.session.get(Party, party_id)
        party.is_active = False
        database.session.commit()


def _deactivate_link(application: Any, party_id: str) -> None:
    """Desactiva el vínculo del tercero con la compañía."""
    with application.app_context():
        link = database.session.execute(
            database.select(CompanyParty).filter_by(company="cacao", party_id=party_id)
        ).scalar_one()
        link.is_active = False
        database.session.commit()


def test_portal_cliente_activo_consulta_su_factura(portal_revocable):
    """Con tercero y vínculo activos el cliente ve su dashboard y su factura."""
    application, ids = portal_revocable
    client = _client_for(application, ids["cliente_user"])

    assert client.get("/portal/customer").status_code == 200
    detail = client.get(f"/portal/customer/invoice/{ids['factura_venta']}")
    assert detail.status_code == 200
    assert "FAC-PORTAL-1919" in detail.get_data(as_text=True)


def test_portal_cliente_revocado_por_tercero_inactivo(portal_revocable):
    """Desactivar el tercero revoca dashboard y documento histórico."""
    application, ids = portal_revocable
    client = _client_for(application, ids["cliente_user"])
    _deactivate_party(application, ids["cliente"])

    assert client.get("/portal/customer").status_code == 403
    assert client.get(f"/portal/customer/invoice/{ids['factura_venta']}").status_code == 403


def test_portal_cliente_revocado_por_vinculo_inactivo(portal_revocable):
    """Desactivar el vínculo con la compañía también revoca el acceso."""
    application, ids = portal_revocable
    client = _client_for(application, ids["cliente_user"])
    _deactivate_link(application, ids["cliente"])

    assert client.get("/portal/customer").status_code == 403
    assert client.get(f"/portal/customer/invoice/{ids['factura_venta']}").status_code == 403


def test_portal_proveedor_revocado_por_tercero_inactivo(portal_revocable):
    """El proveedor inactivo pierde el acceso a su dashboard y documento."""
    application, ids = portal_revocable
    client = _client_for(application, ids["proveedor_user"])
    assert client.get("/portal/supplier").status_code == 200
    _deactivate_party(application, ids["proveedor"])

    assert client.get("/portal/supplier").status_code == 403
    assert client.get(f"/portal/supplier/invoice/{ids['factura_compra']}").status_code == 403


def test_portal_conserva_la_evidencia_tras_la_revocacion(portal_revocable):
    """La revocación no elimina ni modifica las facturas del tercero."""
    application, ids = portal_revocable
    _deactivate_party(application, ids["cliente"])

    with application.app_context():
        factura = database.session.get(SalesInvoice, ids["factura_venta"])
        assert factura is not None
        assert factura.docstatus == 1
        assert factura.document_no == "FAC-PORTAL-1919"


def test_login_no_redirige_al_portal_con_vinculo_revocado(portal_revocable):
    """#1920: sin vínculo vigente el login no redirige a un portal que dará 403."""
    from flask_login import login_user

    from cacao_accounting.portal import portal_home_for_user

    application, ids = portal_revocable
    _deactivate_link(application, ids["cliente"])

    with application.app_context():
        user = database.session.get(User, ids["cliente_user"])
        with application.test_request_context("/"):
            login_user(user)
            assert portal_home_for_user() is None


def test_login_redirige_al_portal_con_vinculo_vigente(portal_revocable):
    """Control positivo: el cliente elegible conserva su portal."""
    from flask_login import login_user

    from cacao_accounting.portal import portal_home_for_user

    application, ids = portal_revocable
    with application.app_context():
        user = database.session.get(User, ids["cliente_user"])
        with application.test_request_context("/"):
            login_user(user)
            assert portal_home_for_user() == "/portal/customer"


def _login_http(application: Any, user_id: str):
    """Inicia sesión por la ruta real y devuelve el cliente y el redirect."""
    with application.app_context():
        username = database.session.get(User, user_id).user
    client = application.test_client()
    response = client.post(
        "/login",
        data={"usuario": username, "acceso": CONTRASENA_PORTAL},
    )
    return client, response


def test_login_http_redirige_al_portal_de_cliente(portal_revocable):
    """Control positivo del flujo real: cliente vigente llega a su portal."""
    application, ids = portal_revocable

    _client, response = _login_http(application, ids["cliente_user"])

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portal/customer")


def test_login_http_redirige_al_portal_de_proveedor(portal_revocable):
    """Control positivo del flujo real: proveedor vigente llega a su portal."""
    application, ids = portal_revocable

    _client, response = _login_http(application, ids["proveedor_user"])

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portal/supplier")


def test_login_http_no_redirige_al_portal_con_vinculo_revocado(portal_revocable):
    """Un vínculo inactivo se resuelve en /index, no en un portal que daría 403."""
    application, ids = portal_revocable
    _deactivate_link(application, ids["cliente"])

    client, response = _login_http(application, ids["cliente_user"])

    assert response.status_code == 302
    assert "/portal/" not in response.headers["Location"]
    assert client.get("/portal/customer").status_code == 403


def test_login_http_no_redirige_al_portal_con_tercero_inactivo(portal_revocable):
    """Un proveedor inactivo tampoco es enviado al portal."""
    application, ids = portal_revocable
    _deactivate_party(application, ids["proveedor"])

    client, response = _login_http(application, ids["proveedor_user"])

    assert response.status_code == 302
    assert "/portal/" not in response.headers["Location"]
    assert client.get("/portal/supplier").status_code == 403


def test_perfil_mixto_admin_solo_ve_sus_documentos(portal_revocable):
    """Un cliente con rol admin conserva el filtro de su tercero."""
    application, ids = portal_revocable
    client = _client_for(application, ids["mixto_user"])

    dashboard = client.get("/portal/customer")
    propio = client.get(f"/portal/customer/invoice/{ids['factura_venta']}")
    ajeno = client.get(f"/portal/customer/invoice/{ids['factura_otro']}")

    assert dashboard.status_code == 200
    cuerpo = dashboard.get_data(as_text=True)
    assert "FAC-PORTAL-1919" in cuerpo
    assert "FAC-PORTAL-OTRO" not in cuerpo
    assert propio.status_code == 200
    assert ajeno.status_code == 403


def test_perfil_mixto_admin_revocado_por_tercero(portal_revocable):
    """El rol admin no evita la revocación cuando el tercero se desactiva."""
    application, ids = portal_revocable
    client = _client_for(application, ids["mixto_user"])
    _deactivate_party(application, ids["cliente"])

    assert client.get("/portal/customer").status_code == 403
    assert client.get(f"/portal/customer/invoice/{ids['factura_venta']}").status_code == 403


def test_perfil_mixto_admin_revocado_por_vinculo(portal_revocable):
    """El rol admin no evita la revocación cuando el vínculo se desactiva."""
    application, ids = portal_revocable
    client = _client_for(application, ids["mixto_user"])
    _deactivate_link(application, ids["cliente"])

    assert client.get("/portal/customer").status_code == 403
    assert client.get(f"/portal/customer/invoice/{ids['factura_venta']}").status_code == 403


def test_login_no_redirige_al_portal_mixto_revocado(portal_revocable):
    """El perfil mixto revocado tampoco recibe redirección al portal."""
    from flask_login import login_user

    from cacao_accounting.portal import portal_home_for_user

    application, ids = portal_revocable
    _deactivate_link(application, ids["cliente"])

    with application.app_context():
        user = database.session.get(User, ids["mixto_user"])
        with application.test_request_context("/"):
            login_user(user)
            assert portal_home_for_user() is None
