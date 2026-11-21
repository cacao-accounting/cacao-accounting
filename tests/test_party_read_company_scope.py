# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lecturas de clientes y proveedores respetan permisos y compañías."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from cacao_accounting import create_app
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import CompanyParty, Currency, Entity, Modules, Party, User, UserCompanyAccess, database

PASSWORD = "party-read-scope-password"


@pytest.fixture
def party_read_scope_app():
    """Create parties spanning authorized and private companies for both modules."""
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
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao Sociedad",
                    tax_id="J-PARTY-CACAO",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code="secreta",
                    name="Secreta",
                    company_name="Secreta Sociedad",
                    tax_id="J-PARTY-SECRET",
                    currency="NIO",
                    enabled=True,
                ),
                User(
                    id="party_sales_reader",
                    user="party_sales_reader",
                    name="Sales Reader",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_purchase_reader",
                    user="party_purchase_reader",
                    name="Purchase Reader",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_sales_editor",
                    user="party_sales_editor",
                    name="Sales Editor",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_purchase_editor",
                    user="party_purchase_editor",
                    name="Purchase Editor",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_sales_editor_all",
                    user="party_sales_editor_all",
                    name="Sales Editor All Companies",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_purchase_editor_all",
                    user="party_purchase_editor_all",
                    name="Purchase Editor All Companies",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_no_access",
                    user="party_no_access",
                    name="No Access",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id="party_cloud_admin_no_grants",
                    user="party_cloud_admin_no_grants",
                    name="Cloud Admin Without Company Grants",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    classification="admin",
                ),
                User(
                    id="party_cloud_admin_cacao_only",
                    user="party_cloud_admin_cacao_only",
                    name="Cloud Admin With One Company Grant",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="party_sales_reader", company_code="cacao"),
                UserCompanyAccess(user_id="party_purchase_reader", company_code="cacao"),
                UserCompanyAccess(user_id="party_sales_editor", company_code="cacao"),
                UserCompanyAccess(user_id="party_purchase_editor", company_code="cacao"),
                UserCompanyAccess(user_id="party_sales_editor_all", company_code="cacao"),
                UserCompanyAccess(user_id="party_sales_editor_all", company_code="secreta"),
                UserCompanyAccess(user_id="party_purchase_editor_all", company_code="cacao"),
                UserCompanyAccess(user_id="party_purchase_editor_all", company_code="secreta"),
                UserCompanyAccess(user_id="party_no_access", company_code="cacao"),
                UserCompanyAccess(user_id="party_cloud_admin_cacao_only", company_code="cacao"),
            ]
        )
        database.session.flush()

        customer_shared = Party(code="CUS-SHARED", name="Cliente Compartido", is_customer=True, is_active=True)
        customer_private = Party(code="CUS-PRIVATE", name="Cliente Privado", is_customer=True, is_active=True)
        supplier_shared = Party(code="SUP-SHARED", name="Proveedor Compartido", is_supplier=True, is_active=True)
        supplier_private = Party(code="SUP-PRIVATE", name="Proveedor Privado", is_supplier=True, is_active=True)
        database.session.add_all([customer_shared, customer_private, supplier_shared, supplier_private])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=customer_shared.id, is_active=True),
                CompanyParty(company="secreta", party_id=customer_shared.id, is_active=True),
                CompanyParty(company="secreta", party_id=customer_private.id, is_active=True),
                CompanyParty(company="cacao", party_id=supplier_shared.id, is_active=True),
                CompanyParty(company="secreta", party_id=supplier_shared.id, is_active=True),
                CompanyParty(company="secreta", party_id=supplier_private.id, is_active=True),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("party_sales_reader", "sales_user")
        asigna_rol_a_usuario("party_purchase_reader", "purchasing_user")
        asigna_rol_a_usuario("party_sales_editor", "sales_auxiliar")
        asigna_rol_a_usuario("party_purchase_editor", "purchasing_auxiliar")
        asigna_rol_a_usuario("party_sales_editor_all", "sales_auxiliar")
        asigna_rol_a_usuario("party_purchase_editor_all", "purchasing_auxiliar")
        ids = {
            "customer_shared": customer_shared.id,
            "customer_private": customer_private.id,
            "supplier_shared": supplier_shared.id,
            "supplier_private": supplier_private.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app: Flask, user_id: str) -> FlaskClient:
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(
    (
        "user_id",
        "list_path",
        "detail_path",
        "shared_id_key",
        "private_id_key",
        "shared_name",
        "private_name",
        "private_code",
        "doctype",
    ),
    [
        (
            "party_sales_reader",
            "/sales/customer/list",
            "/sales/customer/{party_id}",
            "customer_shared",
            "customer_private",
            "Cliente Compartido",
            "Cliente Privado",
            "CUS-PRIVATE",
            "customer",
        ),
        (
            "party_purchase_reader",
            "/buying/supplier/list",
            "/buying/supplier/{party_id}",
            "supplier_shared",
            "supplier_private",
            "Proveedor Compartido",
            "Proveedor Privado",
            "SUP-PRIVATE",
            "supplier",
        ),
    ],
)
def test_party_list_and_detail_require_authorized_module_company(
    party_read_scope_app,
    user_id: str,
    list_path: str,
    detail_path: str,
    shared_id_key: str,
    private_id_key: str,
    shared_name: str,
    private_name: str,
    private_code: str,
    doctype: str,
):
    """Only module readers see parties linked to one of their authorized companies."""
    app, ids = party_read_scope_app
    client = _authenticated_client(app, user_id)

    listing = client.get(list_path)
    assert listing.status_code == 200
    assert shared_name in listing.get_data(as_text=True)
    assert private_name not in listing.get_data(as_text=True)

    searched_listing = client.get(f"{list_path}?search={private_code}")
    assert searched_listing.status_code == 200
    assert private_name not in searched_listing.get_data(as_text=True)

    suggestions = client.get(f"/api/search-select?doctype={doctype}&q={private_code}")
    assert suggestions.status_code == 200
    assert private_name not in suggestions.get_data(as_text=True)

    private_detail = client.get(detail_path.format(party_id=ids[private_id_key]))
    assert private_detail.status_code == 403
    shared_detail = client.get(detail_path.format(party_id=ids[shared_id_key]))
    assert shared_detail.status_code == 200


@pytest.mark.parametrize(
    ("user_id", "detail_path", "shared_id_key"),
    [
        ("party_sales_reader", "/sales/customer/{party_id}", "customer_shared"),
        ("party_purchase_reader", "/buying/supplier/{party_id}", "supplier_shared"),
    ],
)
def test_party_detail_context_omits_other_company_settings(
    party_read_scope_app,
    user_id: str,
    detail_path: str,
    shared_id_key: str,
):
    """A shared party detail does not render settings for an unauthorized company."""
    app, ids = party_read_scope_app
    response = _authenticated_client(app, user_id).get(detail_path.format(party_id=ids[shared_id_key]))

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"company": "cacao"' in body
    assert '"company": "secreta"' not in body


@pytest.mark.parametrize(
    ("list_path", "detail_path", "party_id_key", "doctype", "search_value"),
    [
        (
            "/sales/customer/list",
            "/sales/customer/{party_id}",
            "customer_shared",
            "customer",
            "Cliente",
        ),
        (
            "/buying/supplier/list",
            "/buying/supplier/{party_id}",
            "supplier_shared",
            "supplier",
            "Proveedor",
        ),
    ],
)
def test_party_read_without_module_permission_is_denied(
    party_read_scope_app,
    list_path: str,
    detail_path: str,
    party_id_key: str,
    doctype: str,
    search_value: str,
):
    """A company grant without the sales/purchases read permission grants no party access."""
    app, ids = party_read_scope_app
    client = _authenticated_client(app, "party_no_access")

    listing = client.get(list_path)
    detail = client.get(detail_path.format(party_id=ids[party_id_key]))
    suggestions = client.get(f"/api/search-select?doctype={doctype}&q={search_value}&company=cacao")

    assert listing.status_code == 403
    assert detail.status_code == 403
    assert suggestions.status_code == 403


@pytest.mark.parametrize(
    ("user_id", "edit_path", "party_id_key"),
    [
        ("party_sales_reader", "/sales/customer/{party_id}/edit", "customer_shared"),
        ("party_purchase_reader", "/buying/supplier/{party_id}/edit", "supplier_shared"),
        ("party_no_access", "/sales/customer/{party_id}/edit", "customer_shared"),
    ],
)
def test_party_edit_form_requires_edit_permission(party_read_scope_app, user_id: str, edit_path: str, party_id_key: str):
    """Read-only or unprivileged users cannot load global party edit forms."""
    app, ids = party_read_scope_app

    response = _authenticated_client(app, user_id).get(edit_path.format(party_id=ids[party_id_key]))

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("url", "party_id_key"),
    [
        ("/sales/customer/{party_id}/contacts/missing/deactivate", "customer_shared"),
        ("/sales/customer/{party_id}/addresses/missing/deactivate", "customer_shared"),
        ("/buying/supplier/{party_id}/contacts/missing/deactivate", "supplier_shared"),
        ("/buying/supplier/{party_id}/addresses/missing/deactivate", "supplier_shared"),
        ("/buying/supplier/{party_id}/habilitar-cliente", "supplier_shared"),
    ],
)
def test_party_relationship_mutations_require_edit_permission(party_read_scope_app, url: str, party_id_key: str):
    """Contact, address and role mutations are denied without module edit access."""
    app, ids = party_read_scope_app
    client = _authenticated_client(app, "party_no_access")

    response = client.post(url.format(party_id=ids[party_id_key]), data={"name": "Cambio sin permiso"})

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("user_id", "edit_path", "party_id_key"),
    [
        ("party_sales_editor", "/sales/customer/{party_id}/edit", "customer_shared"),
        ("party_purchase_editor", "/buying/supplier/{party_id}/edit", "supplier_shared"),
    ],
)
def test_party_edit_form_scopes_company_rows_and_rejects_foreign_mutations(
    party_read_scope_app, user_id: str, edit_path: str, party_id_key: str
):
    """Editing displays only authorized settings and cannot rewrite other-company links."""
    app, ids = party_read_scope_app
    client = _authenticated_client(app, user_id)
    edit_url = edit_path.format(party_id=ids[party_id_key])

    response = client.get(edit_url)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"company": "cacao"' in body
    assert '"company": "secreta"' not in body
    assert client.get(f"{edit_url}?company=secreta").status_code == 403

    denied_update = client.post(edit_url, data={"company": "cacao", "name": "Cambio no autorizado"})
    assert denied_update.status_code == 403
    with app.app_context():
        party = database.session.get(Party, ids[party_id_key])
        assert party is not None
        assert party.name in {"Cliente Compartido", "Proveedor Compartido"}


@pytest.mark.parametrize(
    ("user_id", "new_path"),
    [
        ("party_sales_reader", "/sales/customer/new"),
        ("party_purchase_reader", "/buying/supplier/new"),
        ("party_no_access", "/sales/customer/new"),
    ],
)
def test_party_create_form_requires_create_permission(party_read_scope_app, user_id: str, new_path: str):
    """Read-only and unprivileged users cannot enumerate company settings via create forms."""
    app, _ids = party_read_scope_app

    response = _authenticated_client(app, user_id).get(new_path)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("user_id", "new_path"),
    [
        ("party_sales_editor", "/sales/customer/new"),
        ("party_purchase_editor", "/buying/supplier/new"),
    ],
)
def test_party_create_form_rejects_unassigned_company(party_read_scope_app, user_id: str, new_path: str):
    """Create forms neither render nor accept company data outside the editor's grants."""
    app, _ids = party_read_scope_app
    client = _authenticated_client(app, user_id)

    response = client.get(new_path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"company": "cacao"' in body
    assert '"company": "secreta"' not in body
    assert client.get(f"{new_path}?company=secreta").status_code == 403
    assert client.post(new_path, data={"company": "secreta", "name": "No autorizado"}).status_code == 403

    with app.app_context():
        party = database.session.execute(database.select(Party).filter_by(name="No autorizado")).scalar_one_or_none()
        assert party is None


def test_cloud_admin_party_scope_requires_explicit_company_grants(party_read_scope_app):
    """Cloud admins receive only explicit company grants in party forms and selectors."""
    app, _ids = party_read_scope_app
    no_grant_client = _authenticated_client(app, "party_cloud_admin_no_grants")
    granted_client = _authenticated_client(app, "party_cloud_admin_cacao_only")

    assert no_grant_client.get("/sales/customer/new").status_code == 403
    denied_suggestions = no_grant_client.get(
        "/api/search-select?doctype=company&q=Secreta&company_scope_module=sales&company_scope_action=crear"
    )
    assert denied_suggestions.status_code == 403

    create_form = granted_client.get("/sales/customer/new")
    assert create_form.status_code == 200
    body = create_form.get_data(as_text=True)
    assert '"company": "cacao"' in body
    assert '"company": "secreta"' not in body

    suggestions = granted_client.get(
        "/api/search-select?doctype=company&q=Secreta&company_scope_module=sales&company_scope_action=crear"
    )
    assert suggestions.status_code == 200
    assert suggestions.get_json()["results"] == []

    secret_suggestions = granted_client.get(
        "/api/search-select?doctype=company&q=Cacao&company_scope_module=sales&company_scope_action=crear"
    )
    assert secret_suggestions.status_code == 200
    assert [row["value"] for row in secret_suggestions.get_json()["results"]] == ["cacao"]


def test_cloud_admin_party_reads_require_explicit_company_grants(party_read_scope_app):
    """Cloud admins cannot list or search parties outside their explicit grants."""
    app, ids = party_read_scope_app
    no_grant_client = _authenticated_client(app, "party_cloud_admin_no_grants")
    granted_client = _authenticated_client(app, "party_cloud_admin_cacao_only")

    no_grant_listing = no_grant_client.get("/sales/customer/list")
    assert no_grant_listing.status_code == 200
    assert "Cliente Compartido" not in no_grant_listing.get_data(as_text=True)
    assert no_grant_client.get(f"/sales/customer/{ids['customer_shared']}").status_code == 403

    no_grant_search = no_grant_client.get("/api/search-select?doctype=customer&q=CUS-SHARED")
    assert no_grant_search.status_code == 200
    assert no_grant_search.get_json()["results"] == []

    granted_listing = granted_client.get("/sales/customer/list")
    assert granted_listing.status_code == 200
    assert "Cliente Compartido" in granted_listing.get_data(as_text=True)
    assert "Cliente Privado" not in granted_listing.get_data(as_text=True)
    assert granted_client.get(f"/sales/customer/{ids['customer_shared']}").status_code == 200
    assert granted_client.get(f"/sales/customer/{ids['customer_private']}").status_code == 403

    private_search = granted_client.get("/api/search-select?doctype=customer&q=CUS-PRIVATE")
    assert private_search.status_code == 200
    assert private_search.get_json()["results"] == []


@pytest.mark.parametrize(
    ("user_id", "new_path", "edit_path", "party_id_key", "scope_module"),
    [
        (
            "party_sales_editor_all",
            "/sales/customer/new",
            "/sales/customer/{party_id}/edit",
            "customer_shared",
            "sales",
        ),
        (
            "party_purchase_editor_all",
            "/buying/supplier/new",
            "/buying/supplier/{party_id}/edit",
            "supplier_shared",
            "purchases",
        ),
    ],
)
def test_party_form_validation_rerenders_keep_company_selector_scope(
    party_read_scope_app,
    user_id: str,
    new_path: str,
    edit_path: str,
    party_id_key: str,
    scope_module: str,
):
    """Validation errors rerender forms with their action-scoped company selector."""
    app, ids = party_read_scope_app
    client = _authenticated_client(app, user_id)

    create_response = client.post(new_path, data={"company": "cacao", "name": " "})
    assert create_response.status_code == 200
    create_body = create_response.get_data(as_text=True)
    assert f'company_scope_module: "{scope_module}"' in create_body
    assert 'company_scope_action: "crear"' in create_body

    update_response = client.post(
        edit_path.format(party_id=ids[party_id_key]),
        data={"company": ["cacao", "secreta"], "name": " "},
    )
    assert update_response.status_code == 200
    update_body = update_response.get_data(as_text=True)
    assert f'company_scope_module: "{scope_module}"' in update_body
    assert 'company_scope_action: "editar"' in update_body

    with app.app_context():
        party = database.session.get(Party, ids[party_id_key])
        assert party is not None
        assert party.name in {"Cliente Compartido", "Proveedor Compartido"}


def test_generic_party_catalog_applies_module_and_company_scope(party_read_scope_app):
    """The generic party selector follows the same policy as customer/supplier (#1286).

    Un lector de Ventas obtiene solo terceros vinculados a sus compañías, el
    filtro de rol acota a proveedores, una compañía ajena explícita responde 403
    y un usuario sin módulo no accede al catálogo.
    """
    app, ids = party_read_scope_app
    sales_reader = _authenticated_client(app, "party_sales_reader")

    scope_listing = sales_reader.get("/api/search-select?doctype=party")
    assert scope_listing.status_code == 200
    scoped_values = {row["value"] for row in scope_listing.get_json()["results"]}
    assert scoped_values == {ids["customer_shared"], ids["supplier_shared"]}
    assert ids["customer_private"] not in scoped_values
    assert ids["supplier_private"] not in scoped_values

    suppliers = sales_reader.get("/api/search-select?doctype=party&party_type=supplier")
    assert suppliers.status_code == 200
    assert {row["value"] for row in suppliers.get_json()["results"]} == {ids["supplier_shared"]}

    foreign = sales_reader.get("/api/search-select?doctype=party&company=secreta")
    assert foreign.status_code == 403

    no_access = _authenticated_client(app, "party_no_access")
    assert no_access.get("/api/search-select?doctype=party").status_code == 403


def test_party_group_catalog_is_global_but_requires_module(party_read_scope_app):
    """Los grupos de terceros son globales y exigen Ventas o Compras (#1286)."""
    app, _ids = party_read_scope_app
    sales_reader = _authenticated_client(app, "party_sales_reader")
    no_access = _authenticated_client(app, "party_no_access")

    response = sales_reader.get("/api/search-select?doctype=party_group")

    assert response.status_code == 200
    assert no_access.get("/api/search-select?doctype=party_group").status_code == 403
