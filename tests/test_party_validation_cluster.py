# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de servidor del maestro de terceros y sus contactos.

Escenario de negocio (paraguas #1717): las rutas de cliente/proveedor y sus
contactos confiaban en la validación del navegador.

Cubre #1722 (nombre vacío), #2202 (correo inválido) y #1978 (vínculo ajeno).
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Address,
    CompanyParty,
    Contact,
    Entity,
    Modules,
    Party,
    PartyAddress,
    PartyContact,
    User,
    database,
)


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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
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
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        cliente = Party(code="CLI-1", name="Cliente", is_customer=True, is_supplier=False)
        proveedor = Party(code="PROV-1", name="Proveedor", is_customer=False, is_supplier=True)
        contacto_cliente = Contact(first_name="Ajeno", last_name="Cliente", email="ajeno-cli@example.com", is_active=True)
        contacto_proveedor = Contact(first_name="Ajeno", last_name="Proveedor", email="ajeno-prov@example.com", is_active=True)
        database.session.add_all([cliente, proveedor, contacto_cliente, contacto_proveedor])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente.id, is_active=True),
                CompanyParty(company="cacao", party_id=proveedor.id, is_active=True),
            ]
        )
        database.session.flush()
        enlace_cliente = PartyContact(party_id=cliente.id, contact_id=contacto_cliente.id)
        enlace_proveedor = PartyContact(party_id=proveedor.id, contact_id=contacto_proveedor.id)
        direccion_cliente = Address(address_line1="Calle Cliente 1", is_active=True)
        direccion_proveedor = Address(address_line1="Calle Proveedor 1", is_active=True)
        database.session.add_all([enlace_cliente, enlace_proveedor, direccion_cliente, direccion_proveedor])
        database.session.flush()
        enlace_direccion_cliente = PartyAddress(party_id=cliente.id, address_id=direccion_cliente.id)
        enlace_direccion_proveedor = PartyAddress(party_id=proveedor.id, address_id=direccion_proveedor.id)
        database.session.add_all([enlace_direccion_cliente, enlace_direccion_proveedor])
        database.session.commit()
        ids = {
            "cliente": cliente.id,
            "proveedor": proveedor.id,
            "contacto_cliente": contacto_cliente.id,
            "contacto_proveedor": contacto_proveedor.id,
            "enlace_cliente": enlace_cliente.id,
            "enlace_proveedor": enlace_proveedor.id,
            "direccion_cliente": direccion_cliente.id,
            "direccion_proveedor": direccion_proveedor.id,
            "enlace_direccion_cliente": enlace_direccion_cliente.id,
            "enlace_direccion_proveedor": enlace_direccion_proveedor.id,
        }
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(
    "url",
    ["/sales/customer/new", "/buying/supplier/new"],
)
@pytest.mark.parametrize("nombre", ["", "   "])
def test_rechaza_tercero_sin_nombre(url, nombre):
    """#1722: el alta no persiste un Party con nombre vacío."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(url, data={"name": nombre, "company": "cacao"})

        assert respuesta.status_code == 200
        assert "El nombre del tercero es obligatorio." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(Party).where(Party.name == "")).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("url", "campo"),
    [
        ("/sales/customer/{}/edit", "cliente"),
        ("/buying/supplier/{}/edit", "proveedor"),
    ],
)
def test_edicion_no_borra_el_nombre(url, campo):
    """#1722: un POST de edición sin nombre conserva el valor anterior."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            url.format(ids[campo]),
            data={"name": "   ", "company": "cacao"},
        )

        assert respuesta.status_code == 200
        assert "El nombre del tercero es obligatorio." in respuesta.get_data(as_text=True)
        with application.app_context():
            party = database.session.get(Party, ids[campo])
            assert party is not None and party.name == ("Cliente" if campo == "cliente" else "Proveedor")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("url", "campo"),
    [
        ("/sales/customer/{}/contacts", "cliente"),
        ("/buying/supplier/{}/contacts", "proveedor"),
    ],
)
def test_rechaza_correo_de_contacto_invalido(url, campo):
    """#2202: el contacto no se persiste con un correo sin formato."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            url.format(ids[campo]),
            data={"first_name": "Ana", "email": "not-an-email"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(Contact).where(Contact.first_name == "Ana")).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_acepta_correo_de_contacto_valido():
    """#2202: el formato válido sigue creando el contacto."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            f"/sales/customer/{ids['cliente']}/contacts",
            data={"first_name": "Ana", "email": "ana@example.com"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            contacto = database.session.execute(database.select(Contact).where(Contact.first_name == "Ana")).scalar_one()
            assert contacto.email == "ana@example.com"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("url", "campo", "enlace_ajeno", "contacto_propio"),
    [
        ("/sales/customer/{}/contacts/{}/deactivate", "cliente", "enlace_proveedor", "contacto_cliente"),
        ("/buying/supplier/{}/contacts/{}/deactivate", "proveedor", "enlace_cliente", "contacto_proveedor"),
    ],
)
def test_rechaza_desactivar_un_vinculo_ajeno(url, campo, enlace_ajeno, contacto_propio):
    """#1978: un enlace de otro tercero responde 404 sin mutar el contacto."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(url.format(ids[campo], ids[enlace_ajeno]))

        assert respuesta.status_code == 404
        with application.app_context():
            contacto = database.session.get(Contact, ids[contacto_propio])
            assert contacto is not None and contacto.is_active is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("url", "campo", "enlace_ajeno", "direccion_propia"),
    [
        ("/sales/customer/{}/addresses/{}/deactivate", "cliente", "enlace_direccion_proveedor", "direccion_cliente"),
        ("/buying/supplier/{}/addresses/{}/deactivate", "proveedor", "enlace_direccion_cliente", "direccion_proveedor"),
    ],
)
def test_rechaza_desactivar_una_direccion_ajena(url, campo, enlace_ajeno, direccion_propia):
    """#1978: la ruta de direcciones aplica el mismo control de ownership."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(url.format(ids[campo], ids[enlace_ajeno]))

        assert respuesta.status_code == 404
        with application.app_context():
            direccion = database.session.get(Address, ids[direccion_propia])
            assert direccion is not None and direccion.is_active is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_normaliza_el_dominio_del_correo():
    """#2202: email-validator normaliza el dominio antes de persistir."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            f"/sales/customer/{ids['cliente']}/contacts",
            data={"first_name": "Ana", "email": "Ana@Example.COM"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            contacto = database.session.execute(database.select(Contact).where(Contact.first_name == "Ana")).scalar_one()
            assert contacto.email == "Ana@example.com"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("url", ["/sales/customer/new", "/buying/supplier/new"])
def test_rechaza_identificacion_fiscal_duplicada(url):
    """#2130: el alta manual no reutiliza el tax_id de otro tercero."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        datos = {"name": "Primero", "company": "cacao", "tax_id": "J-DUP"}
        primera = client.post(url, data=datos)
        segunda = client.post(url, data={**datos, "name": "Segundo"})

        assert primera.status_code == 302
        assert segunda.status_code == 200
        assert "Ya existe un tercero con ese identificador fiscal." in segunda.get_data(as_text=True)
        with application.app_context():
            mismos = database.session.execute(database.select(Party).where(Party.tax_id == "J-DUP")).scalars().all()
            assert len(mismos) == 1 and mismos[0].name == "Primero"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_permite_conservar_su_propia_identificacion():
    """#2130: la exclusión por id evita falsos positivos al editar."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        creacion = client.post(
            "/sales/customer/new",
            data={"name": "Con RUC", "company": "cacao", "tax_id": "J-SELF"},
        )
        assert creacion.status_code == 302

        with application.app_context():
            party_id = database.session.execute(database.select(Party).filter_by(name="Con RUC")).scalar_one().id

        respuesta = client.post(
            f"/sales/customer/{party_id}/edit",
            data={"name": "Con RUC", "company": "cacao", "tax_id": "J-SELF"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            party = database.session.get(Party, party_id)
            assert party is not None and party.tax_id == "J-SELF"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_rechaza_la_identificacion_de_otro():
    """#2130: cambiar a un tax_id ajeno se rechaza sin persistir."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        client.post(
            "/sales/customer/new",
            data={"name": "Con RUC", "company": "cacao", "tax_id": "J-OTRO"},
        )

        respuesta = client.post(
            f"/sales/customer/{ids['cliente']}/edit",
            data={"name": "Cliente", "company": "cacao", "tax_id": "J-OTRO"},
        )

        assert respuesta.status_code == 200
        assert "Ya existe un tercero con ese identificador fiscal." in respuesta.get_data(as_text=True)
        with application.app_context():
            cliente = database.session.get(Party, ids["cliente"])
            assert cliente is not None and cliente.tax_id is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
