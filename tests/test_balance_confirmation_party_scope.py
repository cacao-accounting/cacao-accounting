# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1998: balance confirmation forms disclose party contacts only in scope."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Contact,
    Currency,
    Entity,
    Modules,
    Party,
    PartyContact,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def confirmation_party_scope_scenario():
    """Seed authorized, foreign, unassociated parties and users for the GET guard."""
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
    alpha = f"a{suffix}"
    beta = f"b{suffix}"
    requester_id = f"confirmation-requester-{suffix}"
    read_requester_id = f"confirmation-read-requester-{suffix}"
    denied_id = f"confirmation-denied-{suffix}"
    own_party_id = f"own-party-{suffix}"
    foreign_party_id = f"foreign-party-{suffix}"
    unassociated_party_id = f"unassociated-party-{suffix}"
    own_email = f"own-{suffix}@example.test"
    foreign_email = f"private-{suffix}@example.test"
    unassociated_email = f"unlinked-{suffix}@example.test"

    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code=alpha,
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=beta,
                    name="Beta",
                    company_name="Beta SA",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                User(id=requester_id, user=requester_id, name="Solicitante autorizado", password=b"unused", active=True),
                User(
                    id=read_requester_id,
                    user=read_requester_id,
                    name="Solicitante de solo lectura",
                    password=b"unused",
                    active=True,
                ),
                User(id=denied_id, user=denied_id, name="Usuario sin RBAC", password=b"unused", active=True),
                Party(
                    id=own_party_id,
                    code=f"OWN-{suffix}",
                    name="Cliente propio",
                    is_customer=True,
                    primary_email=own_email,
                    is_active=True,
                ),
                Party(
                    id=foreign_party_id,
                    code=f"FOREIGN-{suffix}",
                    name="Cliente de otra compañía",
                    is_customer=True,
                    primary_email=foreign_email,
                    is_active=True,
                ),
                Party(
                    id=unassociated_party_id,
                    code=f"NONE-{suffix}",
                    name="Cliente sin compañía activa",
                    is_customer=True,
                    primary_email=unassociated_email,
                    is_active=True,
                ),
                Contact(first_name="Propio", email=own_email, is_active=True),
                Contact(first_name="Ajeno", email=f"contact-{foreign_email}", is_active=True),
                Contact(first_name="Sin vínculo", email=f"contact-{unassociated_email}", is_active=True),
                UserCompanyAccess(user_id=requester_id, company_code=alpha),
                UserCompanyAccess(user_id=read_requester_id, company_code=alpha),
            ]
        )
        database.session.flush()
        own_contact = database.session.execute(database.select(Contact).filter_by(first_name="Propio")).scalar_one()
        foreign_contact = database.session.execute(database.select(Contact).filter_by(first_name="Ajeno")).scalar_one()
        unassociated_contact = database.session.execute(
            database.select(Contact).filter_by(first_name="Sin vínculo")
        ).scalar_one()
        database.session.add_all(
            [
                PartyContact(party_id=own_party_id, contact_id=own_contact.id, role="primary"),
                PartyContact(party_id=foreign_party_id, contact_id=foreign_contact.id, role="primary"),
                PartyContact(party_id=unassociated_party_id, contact_id=unassociated_contact.id, role="primary"),
                CompanyParty(company=alpha, party_id=own_party_id, is_active=True),
                CompanyParty(company=beta, party_id=foreign_party_id, is_active=True),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        role = Roles(name=f"confirmation-requester-role-{suffix}", note="Crear confirmaciones")
        read_role = Roles(name=f"confirmation-read-role-{suffix}", note="Consultar y solicitar confirmaciones")
        view_role = Roles(name=f"confirmation-view-role-{suffix}", note="Consultar clientes")
        database.session.add(role)
        database.session.add(read_role)
        database.session.add(view_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True, create=True, request=True),
                RolesUser(user_id=requester_id, role_id=role.id, active=True),
                RolesAccess(rol_id=read_role.id, module_id=module_id, access=True, view=True, create=False, request=True),
                RolesUser(user_id=read_requester_id, role_id=read_role.id, active=True),
                RolesAccess(rol_id=view_role.id, module_id=module_id, access=True, view=True, create=False, request=False),
                RolesUser(user_id=denied_id, role_id=view_role.id, active=True),
            ]
        )
        database.session.commit()

    yield application, {
        "requester": requester_id,
        "read_requester": read_requester_id,
        "denied": denied_id,
        "company": alpha,
        "own_party": own_party_id,
        "foreign_party": foreign_party_id,
        "unassociated_party": unassociated_party_id,
        "own_email": own_email,
        "foreign_email": foreign_email,
        "unassociated_email": unassociated_email,
    }

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(application, user_id: str):
    """Authenticate a client against the isolated confirmation fixture."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _form_url(party_id: str) -> str:
    """Build the read-only form URL for a customer party."""
    return f"/accounting/balance-confirmations/new?party_id={party_id}&party_type=customer"


def test_confirmation_form_requires_rbac_before_party_lookup(confirmation_party_scope_scenario):
    """An authenticated user without accounting request permission cannot read the form."""
    application, ids = confirmation_party_scope_scenario
    client = _authenticated_client(application, ids["denied"])

    response = client.get(_form_url(ids["own_party"]))

    assert response.status_code == 403
    assert ids["own_email"] not in response.get_data(as_text=True)


def test_confirmation_form_read_does_not_grant_creation_permission(confirmation_party_scope_scenario):
    """A requester may read an in-scope form without create permission, but cannot submit it."""
    application, ids = confirmation_party_scope_scenario
    client = _authenticated_client(application, ids["read_requester"])

    get_response = client.get(_form_url(ids["own_party"]))

    assert get_response.status_code == 200
    assert ids["own_email"] in get_response.get_data(as_text=True)

    post_response = client.post(
        _form_url(ids["own_party"]),
        data={"company_id": ids["company"], "cutoff_date": date.today().isoformat(), "emails": ids["own_email"]},
    )

    assert post_response.status_code == 403


@pytest.mark.parametrize("party_key", ["foreign_party", "unassociated_party"])
def test_confirmation_form_hides_foreign_or_unassociated_party_pii(confirmation_party_scope_scenario, party_key):
    """A request-authorized user cannot render another or unlinked party's contacts."""
    application, ids = confirmation_party_scope_scenario
    client = _authenticated_client(application, ids["requester"])
    private_email = ids["foreign_email"] if party_key == "foreign_party" else ids["unassociated_email"]

    response = client.get(_form_url(ids[party_key]))

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert private_email not in body
    assert f"contact-{private_email}" not in body
    assert "Cliente de otra compañía" not in body
    assert "Cliente sin compañía activa" not in body


def test_confirmation_form_renders_contacts_for_active_authorized_party(confirmation_party_scope_scenario):
    """The active company-party association permits the intended confirmation form."""
    application, ids = confirmation_party_scope_scenario
    client = _authenticated_client(application, ids["requester"])

    response = client.get(_form_url(ids["own_party"]))

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Cliente propio" in body
    assert ids["own_email"] in body
