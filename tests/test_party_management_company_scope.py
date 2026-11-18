# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1524/#1525: clientes y proveedores exigen permiso y vínculo de compañía.

Los listados y detalles solo muestran terceros vinculados a compañías
consultables del módulo; las rutas de escritura exigen la acción del módulo y
autorización sobre cada compañía que intentan modificar.
"""

from __future__ import annotations

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
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

SUPPLIER_LIST_PATH = "/buying/supplier/list"
CUSTOMER_LIST_PATH = "/sales/customer/list"


@pytest.fixture
def party_scope_scenario():
    """Create suppliers and customers linked to different companies."""
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
    supplier_alpha_name = f"Proveedor Alfa {suffix}"
    supplier_beta_name = f"Proveedor Beta {suffix}"
    customer_alpha_name = f"Cliente Alfa {suffix}"
    customer_beta_name = f"Cliente Beta {suffix}"

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
        supplier_alpha = Party(code=f"SUP-A-{suffix}", name=supplier_alpha_name, is_supplier=True, is_active=True)
        supplier_beta = Party(code=f"SUP-B-{suffix}", name=supplier_beta_name, is_supplier=True, is_active=True)
        customer_alpha = Party(code=f"CUS-A-{suffix}", name=customer_alpha_name, is_customer=True, is_active=True)
        customer_beta = Party(code=f"CUS-B-{suffix}", name=customer_beta_name, is_customer=True, is_active=True)
        supplier_shared = Party(
            code=f"SUP-SH-{suffix}", name=f"Proveedor Compartido {suffix}", is_supplier=True, is_active=True
        )
        customer_shared = Party(code=f"CUS-SH-{suffix}", name=f"Cliente Compartido {suffix}", is_customer=True, is_active=True)
        database.session.add_all(
            [supplier_alpha, supplier_beta, customer_alpha, customer_beta, supplier_shared, customer_shared]
        )
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company=company_alpha, party_id=supplier_alpha.id, is_active=True),
                CompanyParty(company=company_beta, party_id=supplier_beta.id, is_active=True),
                CompanyParty(company=company_alpha, party_id=customer_alpha.id, is_active=True),
                CompanyParty(company=company_beta, party_id=customer_beta.id, is_active=True),
                CompanyParty(company=company_alpha, party_id=supplier_shared.id, is_active=True),
                CompanyParty(company=company_beta, party_id=supplier_shared.id, is_active=True),
                CompanyParty(company=company_alpha, party_id=customer_shared.id, is_active=True),
                CompanyParty(company=company_beta, party_id=customer_shared.id, is_active=True),
            ]
        )
        database.session.add_all(
            [
                User(
                    id=f"purchases-viewer-{suffix}",
                    user=f"purchases-viewer-{suffix}",
                    name="Consulta de Compras",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=f"purchases-editor-{suffix}",
                    user=f"purchases-editor-{suffix}",
                    name="Edición de Compras",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=f"sales-viewer-{suffix}",
                    user=f"sales-viewer-{suffix}",
                    name="Consulta de Ventas",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=f"sales-editor-{suffix}",
                    user=f"sales-editor-{suffix}",
                    name="Edición de Ventas",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=f"denied-{suffix}",
                    user=f"denied-{suffix}",
                    name="Sin Roles",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
            ]
        )
        database.session.flush()

        purchases_module = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        purchases_viewer_role = Roles(name=f"purchases-viewer-{suffix}", note="Consulta de compras")
        purchases_editor_role = Roles(name=f"purchases-editor-{suffix}", note="Edición de compras")
        sales_viewer_role = Roles(name=f"sales-viewer-{suffix}", note="Consulta de ventas")
        sales_editor_role = Roles(name=f"sales-editor-{suffix}", note="Edición de ventas")
        database.session.add_all([purchases_viewer_role, purchases_editor_role, sales_viewer_role, sales_editor_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=purchases_viewer_role.id, module_id=purchases_module, access=True, view=True),
                RolesAccess(rol_id=purchases_editor_role.id, module_id=purchases_module, access=True, view=True, edit=True),
                RolesAccess(rol_id=sales_viewer_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=sales_editor_role.id, module_id=sales_module, access=True, view=True, edit=True),
                RolesUser(user_id=f"purchases-viewer-{suffix}", role_id=purchases_viewer_role.id, active=True),
                RolesUser(user_id=f"purchases-editor-{suffix}", role_id=purchases_editor_role.id, active=True),
                RolesUser(user_id=f"sales-viewer-{suffix}", role_id=sales_viewer_role.id, active=True),
                RolesUser(user_id=f"sales-editor-{suffix}", role_id=sales_editor_role.id, active=True),
                UserCompanyAccess(user_id=f"purchases-viewer-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"purchases-editor-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"sales-viewer-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"sales-editor-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"denied-{suffix}", company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "supplier_alpha": supplier_alpha.id,
            "supplier_alpha_name": supplier_alpha_name,
            "supplier_beta": supplier_beta.id,
            "supplier_beta_name": supplier_beta_name,
            "customer_alpha": customer_alpha.id,
            "customer_alpha_name": customer_alpha_name,
            "customer_beta": customer_beta.id,
            "customer_beta_name": customer_beta_name,
            "supplier_shared": supplier_shared.id,
            "customer_shared": customer_shared.id,
            "purchases_viewer": f"purchases-viewer-{suffix}",
            "purchases_editor": f"purchases-editor-{suffix}",
            "sales_viewer": f"sales-viewer-{suffix}",
            "sales_editor": f"sales-editor-{suffix}",
            "denied": f"denied-{suffix}",
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


def test_supplier_list_requires_purchases_permission(party_scope_scenario):
    """An authenticated user without purchases roles cannot list suppliers."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["denied"])

    response = client.get(SUPPLIER_LIST_PATH)

    assert response.status_code == 403
    assert ids["supplier_alpha_name"] not in response.get_data(as_text=True)


def test_supplier_list_only_shows_authorized_company_links(party_scope_scenario):
    """The listing hides suppliers linked only to a foreign company."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_viewer"])

    response = client.get(SUPPLIER_LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["supplier_alpha_name"] in body
    assert ids["supplier_beta_name"] not in body


def test_supplier_detail_requires_authorized_company_link(party_scope_scenario):
    """The supplier detail denies a party linked only to another company."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_viewer"])

    own_detail = client.get(f"/buying/supplier/{ids['supplier_alpha']}")
    assert own_detail.status_code == 200
    assert ids["supplier_alpha_name"] in own_detail.get_data(as_text=True)

    foreign_detail = client.get(f"/buying/supplier/{ids['supplier_beta']}")
    assert foreign_detail.status_code == 403
    assert ids["supplier_beta_name"] not in foreign_detail.get_data(as_text=True)


def test_customer_list_and_detail_are_company_scoped(party_scope_scenario):
    """Sales customer list and detail follow the same company link rule."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["sales_viewer"])

    listing = client.get(CUSTOMER_LIST_PATH)
    body = listing.get_data(as_text=True)
    assert listing.status_code == 200
    assert ids["customer_alpha_name"] in body
    assert ids["customer_beta_name"] not in body

    assert client.get(f"/sales/customer/{ids['customer_alpha']}").status_code == 200
    foreign_detail = client.get(f"/sales/customer/{ids['customer_beta']}")
    assert foreign_detail.status_code == 403
    assert ids["customer_beta_name"] not in foreign_detail.get_data(as_text=True)


def test_supplier_creation_requires_create_permission(party_scope_scenario):
    """A purchases reader cannot open the supplier creation form."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_viewer"])

    response = client.get("/buying/supplier/new")

    assert response.status_code == 403


def test_supplier_company_settings_reject_foreign_company(party_scope_scenario):
    """Company settings cannot add or remove links outside the editor's grant."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_editor"])

    response = client.post(
        f"/buying/supplier/{ids['supplier_alpha']}/company-settings",
        data={"company": ids["company_beta"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    with app.app_context():
        companies = set(
            database.session.execute(database.select(CompanyParty.company).filter_by(party_id=ids["supplier_alpha"])).scalars()
        )
        assert companies == {ids["company_alpha"]}


def test_supplier_contacts_require_edit_permission(party_scope_scenario):
    """A reader cannot add contacts; an editor can."""
    app, ids = party_scope_scenario
    reader = _authenticated_client(app, ids["purchases_viewer"])
    editor = _authenticated_client(app, ids["purchases_editor"])

    denied = reader.post(f"/buying/supplier/{ids['supplier_alpha']}/contacts", data={"first_name": "Contacto Ajeno"})
    assert denied.status_code == 403
    with app.app_context():
        assert database.session.execute(database.select(Contact).filter_by(first_name="Contacto Ajeno")).first() is None

    allowed = editor.post(f"/buying/supplier/{ids['supplier_alpha']}/contacts", data={"first_name": "Contacto Propio"})
    assert allowed.status_code == 302
    with app.app_context():
        assert database.session.execute(database.select(Contact).filter_by(first_name="Contacto Propio")).first() is not None


def test_supplier_customer_role_toggle_requires_edit_permission(party_scope_scenario):
    """The cross-role toggle mutates the shared party and therefore needs edit."""
    app, ids = party_scope_scenario
    reader = _authenticated_client(app, ids["purchases_viewer"])
    editor = _authenticated_client(app, ids["purchases_editor"])

    denied = reader.post(f"/buying/supplier/{ids['supplier_alpha']}/habilitar-cliente")
    assert denied.status_code == 403
    with app.app_context():
        assert database.session.get(Party, ids["supplier_alpha"]).is_customer is False

    allowed = editor.post(f"/buying/supplier/{ids['supplier_alpha']}/habilitar-cliente")
    assert allowed.status_code == 302
    with app.app_context():
        assert database.session.get(Party, ids["supplier_alpha"]).is_customer is True


def test_supplier_edit_rejects_foreign_company_and_requires_edit(party_scope_scenario):
    """Editing a party cannot relink it to another company or bypass the edit action."""
    app, ids = party_scope_scenario
    reader = _authenticated_client(app, ids["purchases_viewer"])
    editor = _authenticated_client(app, ids["purchases_editor"])

    assert reader.get(f"/buying/supplier/{ids['supplier_alpha']}/edit").status_code == 403

    forged = editor.post(
        f"/buying/supplier/{ids['supplier_alpha']}/edit",
        data={
            "name": "Nombre Alterado",
            "company": ids["company_beta"],
            "company_is_active": "on",
        },
    )

    assert forged.status_code == 403
    with app.app_context():
        supplier = database.session.get(Party, ids["supplier_alpha"])
        assert supplier.name == ids["supplier_alpha_name"]
        companies = set(
            database.session.execute(database.select(CompanyParty.company).filter_by(party_id=ids["supplier_alpha"])).scalars()
        )
        assert companies == {ids["company_alpha"]}


def _linked_companies(app, party_id: str) -> set[str]:
    """Return the companies linked to a party."""
    with app.app_context():
        return set(database.session.execute(database.select(CompanyParty.company).filter_by(party_id=party_id)).scalars())


def test_supplier_company_settings_reject_foreign_shared_link(party_scope_scenario):
    """Sending a foreign company for a shared supplier is denied without mutation (#1280)."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_editor"])

    response = client.post(
        f"/buying/supplier/{ids['supplier_shared']}/company-settings",
        data={"company": ids["company_beta"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    assert _linked_companies(app, ids["supplier_shared"]) == {ids["company_alpha"], ids["company_beta"]}


def test_supplier_company_settings_reject_omitting_foreign_link(party_scope_scenario):
    """Omitting the foreign link of a shared supplier is denied, not deleted (#1280)."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_editor"])

    response = client.post(
        f"/buying/supplier/{ids['supplier_shared']}/company-settings",
        data={"company": ids["company_alpha"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    assert _linked_companies(app, ids["supplier_shared"]) == {ids["company_alpha"], ids["company_beta"]}


def test_supplier_company_settings_require_edit_permission(party_scope_scenario):
    """A purchases reader cannot modify supplier settings."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["purchases_viewer"])

    response = client.post(
        f"/buying/supplier/{ids['supplier_alpha']}/company-settings",
        data={"company": ids["company_alpha"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    assert _linked_companies(app, ids["supplier_alpha"]) == {ids["company_alpha"]}


def test_customer_company_settings_reject_foreign_shared_link(party_scope_scenario):
    """Sending a foreign company for a shared customer is denied without mutation (#1280)."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["sales_editor"])

    response = client.post(
        f"/sales/customer/{ids['customer_shared']}/company-settings",
        data={"company": ids["company_beta"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    assert _linked_companies(app, ids["customer_shared"]) == {ids["company_alpha"], ids["company_beta"]}


def test_customer_company_settings_reject_omitting_foreign_link(party_scope_scenario):
    """Omitting the foreign link of a shared customer is denied, not deleted (#1280)."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["sales_editor"])

    response = client.post(
        f"/sales/customer/{ids['customer_shared']}/company-settings",
        data={"company": ids["company_alpha"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    assert _linked_companies(app, ids["customer_shared"]) == {ids["company_alpha"], ids["company_beta"]}


def test_customer_company_settings_require_edit_permission(party_scope_scenario):
    """A sales reader cannot modify customer settings."""
    app, ids = party_scope_scenario
    client = _authenticated_client(app, ids["sales_viewer"])

    response = client.post(
        f"/sales/customer/{ids['customer_alpha']}/company-settings",
        data={"company": ids["company_alpha"], "company_is_active": "on"},
    )

    assert response.status_code == 403
    assert _linked_companies(app, ids["customer_alpha"]) == {ids["company_alpha"]}
