"""Pruebas de tipos, edicion y contactos de terceros."""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Crea una aplicacion con esquema limpio para pruebas de terceros."""
    app = create_app(
        {
            **configuracion,
            "TESTING": True,
            "SECRET_KEY": "party-tests",
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Entity(
                    code="cacao",
                    company_name="Cacao",
                    name="Cacao",
                    tax_id="J0310000000001",
                    entity_type="company",
                    enabled=True,
                ),
                Modules(module="admin", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
                Modules(module="purchases", default=True, enabled=True),
            ]
        )
        database.session.commit()
        yield app


@pytest.fixture()
def client(app_ctx):
    """Cliente autenticado como administrador."""
    from cacao_accounting.database import User, database

    user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    test_client = app_ctx.test_client()
    with test_client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True
    return test_client


def test_party_group_crud_and_customer_type_flow(app_ctx, client):
    """El tipo de cliente se crea, se asigna y aparece en el detalle."""
    from cacao_accounting.database import Contact, Party, PartyGroup, database

    response = client.post(
        "/settings/party-groups",
        data={"group_type": "customer", "name": "Mayorista", "description": "Clientes mayoristas", "is_active": "on"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    group = database.session.execute(database.select(PartyGroup).filter_by(name="Mayorista")).scalar_one()

    response = client.post(
        "/sales/customer/new",
        data={
            "name": "Cliente Test",
            "comercial_name": "Cliente Comercial",
            "tax_id": "C-001",
            "party_group_id": group.id,
            "is_active": "on",
            "company": "cacao",
            "company_is_active": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    customer = database.session.execute(database.select(Party).filter_by(name="Cliente Test")).scalar_one()
    assert customer.party_group_id == group.id
    assert customer.classification == "Mayorista"

    response = client.post(
        f"/sales/customer/{customer.id}/contacts",
        data={"first_name": "Ana", "last_name": "Lopez", "email": "ana@example.com", "role": "Ventas"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Contactos" in response.data
    assert b"Direcciones" in response.data
    assert b"Tipo de Cliente" in response.data
    assert "Mayorista".encode() in response.data

    contact = database.session.execute(database.select(Contact).filter_by(first_name="Ana")).scalar_one()
    assert contact.is_active is True


def test_supplier_edit_and_address_deactivation(app_ctx, client):
    """Proveedor permite tipo, edicion y desactivacion de direcciones."""
    from cacao_accounting.database import Address, Party, PartyAddress, PartyGroup, database

    supplier_group = PartyGroup(group_type="supplier", name="Importador", is_active=True)
    database.session.add(supplier_group)
    database.session.commit()

    response = client.post(
        "/buying/supplier/new",
        data={
            "name": "Proveedor Test",
            "tax_id": "P-001",
            "party_group_id": supplier_group.id,
            "is_active": "on",
            "company": "cacao",
            "company_is_active": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    supplier = database.session.execute(database.select(Party).filter_by(name="Proveedor Test")).scalar_one()

    response = client.post(
        f"/buying/supplier/{supplier.id}/addresses",
        data={"address_line1": "Zona 1", "city": "Managua", "address_type": "Bodega", "is_primary": "on"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Tipo de Proveedor" in response.data
    assert "Importador".encode() in response.data

    link = database.session.execute(database.select(PartyAddress).filter_by(party_id=supplier.id)).scalar_one()
    client.post(f"/buying/supplier/{supplier.id}/addresses/{link.id}/deactivate", follow_redirects=True)
    address = database.session.get(Address, link.address_id)
    assert address is not None
    assert address.is_active is False

    client.post(
        f"/buying/supplier/{supplier.id}/edit",
        data={"name": "Proveedor Editado", "party_group_id": supplier_group.id, "is_active": "on", "company": "cacao"},
    )
    database.session.refresh(supplier)
    assert supplier.name == "Proveedor Editado"
