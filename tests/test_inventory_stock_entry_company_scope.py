# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1416/#1176/#1543: el listado de movimientos respeta el alcance de Inventario.

El parámetro ``company`` no debe ampliar el alcance del usuario: una compañía
autorizada filtra, una ajena responde 403. El selector del formulario de alta
también usa las compañías del módulo de Inventario, no las de Contabilidad
(#1173).
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    StockEntry,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)
from cacao_accounting.inventario.services import _inventory_company_choices

LIST_PATH = "/inventory/stock-entry/list"
NEW_ENTRY_PATH = "/inventory/stock-entry/material-receipt/new"


@pytest.fixture
def stock_entry_scope_scenario():
    """Create stock entries in two companies with readers scoped to one."""
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
    reader_id = f"reader-{suffix}"
    editor_id = f"editor-{suffix}"
    denied_id = f"denied-{suffix}"
    admin_id = f"admin-{suffix}"
    alpha_document = f"ALPHA-DOC-{suffix}"
    beta_document = f"BETA-DOC-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=False, enabled=True),
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
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code=f"ITEM-{suffix}", name="Artículo compartido", item_type="goods", is_stock_item=True, default_uom="EA"
                ),
                Warehouse(code=f"WA-{suffix}", name="Bodega Alfa", company=company_alpha),
                Warehouse(code=f"WB-{suffix}", name="Bodega Beta", company=company_beta),
                User(id=reader_id, user=reader_id, name="Lector Alfa", password=b"unused", active=True, company=company_alpha),
                User(id=editor_id, user=editor_id, name="Editor Alfa", password=b"unused", active=True, company=company_alpha),
                User(
                    id=denied_id, user=denied_id, name="Sin Inventario", password=b"unused", active=True, company=company_alpha
                ),
                User(
                    id=admin_id,
                    user=admin_id,
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()

        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        reader_role = Roles(name=f"stock-reader-{suffix}", note="Consulta de inventario")
        editor_role = Roles(name=f"stock-editor-{suffix}", note="Alta de inventario")
        database.session.add_all([reader_role, editor_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=reader_role.id, module_id=module_id, access=True, view=True),
                RolesAccess(rol_id=editor_role.id, module_id=module_id, access=True, view=True, create=True),
                RolesUser(user_id=reader_id, role_id=reader_role.id, active=True),
                RolesUser(user_id=editor_id, role_id=editor_role.id, active=True),
                UserCompanyAccess(user_id=reader_id, company_code=company_alpha),
                UserCompanyAccess(user_id=editor_id, company_code=company_alpha),
                UserCompanyAccess(user_id=denied_id, company_code=company_alpha),
                StockEntry(
                    company=company_alpha,
                    purpose="material_receipt",
                    document_no=alpha_document,
                    posting_date=date(2026, 11, 10),
                ),
                StockEntry(
                    company=company_beta,
                    purpose="material_receipt",
                    document_no=beta_document,
                    posting_date=date(2026, 11, 11),
                ),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "alpha_document": alpha_document,
            "beta_document": beta_document,
            "reader_id": reader_id,
            "editor_id": editor_id,
            "denied_id": denied_id,
            "admin_id": admin_id,
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


def test_stock_entry_list_shows_only_authorized_company_documents(stock_entry_scope_scenario):
    """Without a company parameter the listing stays inside the grant."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_document"] in body
    assert ids["beta_document"] not in body


def test_stock_entry_list_accepts_authorized_company_filter(stock_entry_scope_scenario):
    """An authorized explicit company narrows the listing without widening it."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"{LIST_PATH}?company={ids['company_alpha']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_document"] in body
    assert ids["beta_document"] not in body


def test_stock_entry_list_rejects_foreign_company_filter(stock_entry_scope_scenario):
    """A foreign company in the URL is refused instead of filtered (#1176/#1543)."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"{LIST_PATH}?company={ids['company_beta']}")

    assert response.status_code == 403
    assert ids["beta_document"] not in response.get_data(as_text=True)


def test_stock_entry_list_rejects_company_filter_without_inventory_permission(stock_entry_scope_scenario):
    """A user without inventory permissions cannot read another company via the URL."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["denied_id"])

    response = client.get(f"{LIST_PATH}?company={ids['company_alpha']}")

    assert response.status_code == 403
    assert ids["alpha_document"] not in response.get_data(as_text=True)
    assert ids["beta_document"] not in response.get_data(as_text=True)


def test_stock_entry_list_admin_keeps_global_scope_and_validates_company(stock_entry_scope_scenario):
    """An administrator sees every company and may filter by any enabled one."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["admin_id"])

    listing = client.get(LIST_PATH)
    body = listing.get_data(as_text=True)
    assert listing.status_code == 200
    assert ids["alpha_document"] in body
    assert ids["beta_document"] in body

    filtered = client.get(f"{LIST_PATH}?company={ids['company_beta']}")
    filtered_body = filtered.get_data(as_text=True)
    assert filtered.status_code == 200
    assert ids["beta_document"] in filtered_body
    assert ids["alpha_document"] not in filtered_body


def test_stock_entry_new_form_uses_inventory_company_choices(stock_entry_scope_scenario):
    """The creation form offers only companies granted in Inventory (#1173).

    El editor solo tiene rol de Inventario, no de Contabilidad: el selector
    debe seguir aceptando su compañía y excluir la ajena.
    """
    app, ids = stock_entry_scope_scenario

    with app.test_request_context(NEW_ENTRY_PATH):
        login_user(database.session.get(User, ids["editor_id"]))
        choices = _inventory_company_choices()

    assert [code for code, _name in choices] == [ids["company_alpha"]]
    assert _authenticated_client(app, ids["editor_id"]).get(NEW_ENTRY_PATH).status_code == 200


def test_stock_entry_new_form_has_no_choices_without_inventory_permission(stock_entry_scope_scenario):
    """A user without Inventory grants receives no selectable company (#1173)."""
    app, ids = stock_entry_scope_scenario

    with app.test_request_context(NEW_ENTRY_PATH):
        login_user(database.session.get(User, ids["denied_id"]))
        choices = _inventory_company_choices()

    assert choices == []


def test_stock_entry_new_form_admin_gets_every_enabled_company(stock_entry_scope_scenario):
    """An administrator keeps the global inventory scope in the form."""
    app, ids = stock_entry_scope_scenario

    with app.test_request_context(NEW_ENTRY_PATH):
        login_user(database.session.get(User, ids["admin_id"]))
        choices = _inventory_company_choices()

    assert [code for code, _name in choices] == [ids["company_alpha"], ids["company_beta"]]


def test_stock_entry_new_form_rejects_foreign_company_parameter(stock_entry_scope_scenario):
    """The GET refuses to render another company's warehouses (#1173)."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])

    response = client.get(f"{NEW_ENTRY_PATH}?company={ids['company_beta']}")

    assert response.status_code == 403


def test_inventory_lists_require_consult_permission(stock_entry_scope_scenario):
    """The item and stock-entry listings require inventory read permission."""
    app, ids = stock_entry_scope_scenario
    client = _authenticated_client(app, ids["denied_id"])

    assert client.get("/inventory/item/list").status_code == 403
    assert client.get(LIST_PATH).status_code == 403
