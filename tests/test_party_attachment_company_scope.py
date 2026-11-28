# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1284: adjuntos de terceros respetan activaciones y permisos.

Política aprobada: el archivo de un tercero es visible para las compañías donde
el tercero está activo, respetando el permiso del módulo. Un tercero inactivo,
sin vínculo activo con una compañía habilitada o fuera del alcance del usuario
no expone listado, descarga ni cargas.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    File,
    FileAttachment,
    Modules,
    Party,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def party_attachment_scenario():
    """Create shared, foreign, inactive-link and inactive parties with files."""
    app = create_app(
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
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"
    users = {
        "alpha_reader": f"alpha-reader-{suffix}",
        "alpha_editor": f"alpha-editor-{suffix}",
        "beta_reader": f"beta-reader-{suffix}",
        "sales_reader": f"sales-reader-{suffix}",
        "no_grants": f"no-grants-{suffix}",
        "admin": f"admin-{suffix}",
    }

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code=company_alpha,
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        shared = Party(code=f"SUP-SH-{suffix}", name="Proveedor Compartido", is_supplier=True, is_active=True)
        beta_only = Party(code=f"SUP-B-{suffix}", name="Proveedor Beta", is_supplier=True, is_active=True)
        inactive_link = Party(code=f"SUP-IL-{suffix}", name="Proveedor Vínculo Inactivo", is_supplier=True, is_active=True)
        inactive_party = Party(code=f"SUP-IP-{suffix}", name="Proveedor Inactivo", is_supplier=True, is_active=False)
        customer_shared = Party(code=f"CUS-SH-{suffix}", name="Cliente Compartido", is_customer=True, is_active=True)
        database.session.add_all([shared, beta_only, inactive_link, inactive_party, customer_shared])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company=company_alpha, party_id=shared.id, is_active=True),
                CompanyParty(company=company_beta, party_id=shared.id, is_active=True),
                CompanyParty(company=company_beta, party_id=beta_only.id, is_active=True),
                CompanyParty(company=company_alpha, party_id=inactive_link.id, is_active=False),
                CompanyParty(company=company_beta, party_id=inactive_link.id, is_active=True),
                CompanyParty(company=company_alpha, party_id=inactive_party.id, is_active=True),
                CompanyParty(company=company_alpha, party_id=customer_shared.id, is_active=True),
                CompanyParty(company=company_beta, party_id=customer_shared.id, is_active=True),
            ]
        )
        shared_file = File(file_name="contrato-shared.pdf", mime_type="application/pdf")
        beta_file = File(file_name="contrato-beta.pdf", mime_type="application/pdf")
        inactive_file = File(file_name="contrato-inactivo.pdf", mime_type="application/pdf")
        customer_file = File(file_name="contrato-cliente.pdf", mime_type="application/pdf")
        database.session.add_all([shared_file, beta_file, inactive_file, customer_file])
        database.session.flush()
        database.session.add_all(
            [
                FileAttachment(file_id=shared_file.id, reference_type="supplier", reference_id=shared.id),
                FileAttachment(file_id=beta_file.id, reference_type="supplier", reference_id=beta_only.id),
                FileAttachment(file_id=inactive_file.id, reference_type="supplier", reference_id=inactive_party.id),
                FileAttachment(file_id=customer_file.id, reference_type="customer", reference_id=customer_shared.id),
            ]
        )
        database.session.add_all(
            [
                User(id=user_id, user=user_id, name=user_id, password=b"unused", active=True, company=company_alpha)
                for user_id in users.values()
            ]
        )
        database.session.flush()
        purchases_module = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        reader_role = Roles(name=f"attachment-reader-{suffix}", note="Consulta de compras")
        editor_role = Roles(name=f"attachment-editor-{suffix}", note="Edición de compras")
        sales_role = Roles(name=f"attachment-sales-{suffix}", note="Consulta de ventas")
        database.session.add_all([reader_role, editor_role, sales_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=reader_role.id, module_id=purchases_module, access=True, view=True),
                RolesAccess(rol_id=editor_role.id, module_id=purchases_module, access=True, view=True, edit=True),
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesUser(user_id=users["alpha_reader"], role_id=reader_role.id, active=True),
                RolesUser(user_id=users["alpha_editor"], role_id=editor_role.id, active=True),
                RolesUser(user_id=users["beta_reader"], role_id=reader_role.id, active=True),
                RolesUser(user_id=users["sales_reader"], role_id=sales_role.id, active=True),
                RolesUser(user_id=users["no_grants"], role_id=reader_role.id, active=True),
                UserCompanyAccess(user_id=users["alpha_reader"], company_code=company_alpha),
                UserCompanyAccess(user_id=users["alpha_editor"], company_code=company_alpha),
                UserCompanyAccess(user_id=users["beta_reader"], company_code=company_beta),
                UserCompanyAccess(user_id=users["sales_reader"], company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "shared_party": shared.id,
            "beta_party": beta_only.id,
            "inactive_link_party": inactive_link.id,
            "inactive_party": inactive_party.id,
            "customer_party": customer_shared.id,
            "shared_file": shared_file.id,
            "beta_file": beta_file.id,
            **users,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_shared_party_attachment_visible_to_both_linked_companies(party_attachment_scenario):
    """A party active in Alfa and Beta shares its files with both companies."""
    app, ids = party_attachment_scenario

    alpha_listing = _authenticated_client(app, ids["alpha_reader"]).get(f"/api/attachments/supplier/{ids['shared_party']}")
    beta_listing = _authenticated_client(app, ids["beta_reader"]).get(f"/api/attachments/supplier/{ids['shared_party']}")

    assert alpha_listing.status_code == 200
    assert beta_listing.status_code == 200
    assert alpha_listing.get_json()[0]["file_name"] == "contrato-shared.pdf"
    assert beta_listing.get_json()[0]["file_name"] == "contrato-shared.pdf"


def test_party_attachment_listing_requires_a_linked_company(party_attachment_scenario):
    """A user without the party's companies cannot list its files."""
    app, ids = party_attachment_scenario
    client = _authenticated_client(app, ids["no_grants"])

    response = client.get(f"/api/attachments/supplier/{ids['shared_party']}")

    assert response.status_code == 403


def test_party_attachment_listing_rejects_foreign_linked_party(party_attachment_scenario):
    """A party linked only to Beta is not readable from Alfa."""
    app, ids = party_attachment_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.get(f"/api/attachments/supplier/{ids['beta_party']}")

    assert response.status_code == 403


def test_party_attachment_listing_ignores_inactive_company_link(party_attachment_scenario):
    """An inactive link in Alfa does not grant access; only the active Beta link exists."""
    app, ids = party_attachment_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.get(f"/api/attachments/supplier/{ids['inactive_link_party']}")

    assert response.status_code == 403


def test_inactive_party_attachment_is_denied_even_for_admin(party_attachment_scenario):
    """An inactive party hides its files from every user, including administrators."""
    app, ids = party_attachment_scenario
    reader = _authenticated_client(app, ids["alpha_reader"])
    admin = _authenticated_client(app, ids["admin"])

    assert reader.get(f"/api/attachments/supplier/{ids['inactive_party']}").status_code == 403
    assert admin.get(f"/api/attachments/supplier/{ids['inactive_party']}").status_code == 403


def test_customer_attachment_listing_uses_sales_scope(party_attachment_scenario):
    """A customer file follows the sales permission and its company links."""
    app, ids = party_attachment_scenario
    sales_reader = _authenticated_client(app, ids["sales_reader"])
    purchases_reader = _authenticated_client(app, ids["alpha_reader"])

    listing = sales_reader.get(f"/api/attachments/customer/{ids['customer_party']}")
    denied = purchases_reader.get(f"/api/attachments/customer/{ids['customer_party']}")

    assert listing.status_code == 200
    assert listing.get_json()[0]["file_name"] == "contrato-cliente.pdf"
    assert denied.status_code == 403


def test_party_attachment_download_uses_the_same_scope(party_attachment_scenario):
    """Download is authorized by the party link before looking for the file."""
    app, ids = party_attachment_scenario

    assert (
        _authenticated_client(app, ids["alpha_reader"]).get(f"/attachments/download/{ids['shared_file']}").status_code == 404
    )
    assert _authenticated_client(app, ids["beta_reader"]).get(f"/attachments/download/{ids['shared_file']}").status_code == 404
    assert _authenticated_client(app, ids["no_grants"]).get(f"/attachments/download/{ids['shared_file']}").status_code == 403
    assert _authenticated_client(app, ids["alpha_reader"]).get(f"/attachments/download/{ids['beta_file']}").status_code == 403


def test_party_attachment_upload_requires_edit_permission(party_attachment_scenario):
    """Reading the party does not allow uploading files."""
    app, ids = party_attachment_scenario
    path = f"/api/attachments/supplier/{ids['shared_party']}/upload"

    viewer = _authenticated_client(app, ids["alpha_reader"]).post(path)
    editor = _authenticated_client(app, ids["alpha_editor"]).post(path)

    assert viewer.status_code == 403
    assert editor.status_code == 400


def test_party_attachment_delete_requires_edit_permission(party_attachment_scenario):
    """Deletion keeps requiring the edit action of the party's module."""
    app, ids = party_attachment_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.post(
        f"/api/attachments/{ids['shared_file']}/delete",
        data={"reference_type": "supplier", "reference_id": ids["shared_party"]},
    )

    assert response.status_code == 403
