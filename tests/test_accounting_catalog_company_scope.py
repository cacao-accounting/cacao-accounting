# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1546: el catálogo contable solo expone la compañía autorizada.

El listado y el detalle de proyectos, su formulario de edición y su borrado,
más el selector de compañía del árbol, deben exigir acceso a la compañía dueña
del registro. Una compañía ajena no aparece como opción ni entrega datos aunque
se fuerce su código en la URL.
"""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_login import login_user

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.auxiliares import obtener_entidades
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Project,
    Roles,
    RolesAccess,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

PASSWORD = "catalog-scope-password"

LOCAL_COMPANY_CODE = "cacao"
LOCAL_COMPANY_NAME = "Cacao Accounting SA"
FOREIGN_COMPANY_CODE = "alpha"
FOREIGN_COMPANY_NAME = "Alpha Privada SA"

LOCAL_PROJECT_CODE = "P-LOCAL"
LOCAL_PROJECT_NAME = "Proyecto Local Cacao"
FOREIGN_PROJECT_CODE = "P-PRIVATE"
FOREIGN_PROJECT_NAME = "Proyecto Privado Alpha"

LIST_PATH = "/accounting/project/list"
DETAIL_PATH = "/accounting/project/{code}"
EDIT_PATH = "/accounting/project/{code}/edit"
DELETE_PATH = "/accounting/project/{code}/delete"


@pytest.fixture
def catalog_scope_app():
    """Create two companies, their private projects and scoped accounting users."""
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
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code=LOCAL_COMPANY_CODE,
                    name="Cacao",
                    company_name=LOCAL_COMPANY_NAME,
                    tax_id="J-CATALOG-CACAO",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code=FOREIGN_COMPANY_CODE,
                    name="Alpha",
                    company_name=FOREIGN_COMPANY_NAME,
                    tax_id="J-CATALOG-ALPHA",
                    currency="USD",
                    enabled=True,
                ),
                User(
                    id="catalog_reader",
                    user="catalog_reader",
                    name="Catalog Reader",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=LOCAL_COMPANY_CODE,
                ),
                User(
                    id="catalog_no_grants",
                    user="catalog_no_grants",
                    name="Catalog Reader Without Company Grants",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=LOCAL_COMPANY_CODE,
                ),
                User(
                    id="catalog_alpha_only",
                    user="catalog_alpha_only",
                    name="Catalog Reader Of The Foreign Company",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=FOREIGN_COMPANY_CODE,
                ),
                User(
                    id="catalog_deleter",
                    user="catalog_deleter",
                    name="Catalog Deleter",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=LOCAL_COMPANY_CODE,
                ),
                UserCompanyAccess(user_id="catalog_reader", company_code=LOCAL_COMPANY_CODE),
                UserCompanyAccess(user_id="catalog_alpha_only", company_code=FOREIGN_COMPANY_CODE),
                UserCompanyAccess(user_id="catalog_deleter", company_code=LOCAL_COMPANY_CODE),
                Project(code=LOCAL_PROJECT_CODE, name=LOCAL_PROJECT_NAME, entity=LOCAL_COMPANY_CODE, enabled=True),
                Project(code=FOREIGN_PROJECT_CODE, name=FOREIGN_PROJECT_NAME, entity=FOREIGN_COMPANY_CODE, enabled=True),
            ]
        )
        database.session.commit()

        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("catalog_reader", "accounting_auxiliar")
        asigna_rol_a_usuario("catalog_no_grants", "accounting_auxiliar")
        asigna_rol_a_usuario("catalog_alpha_only", "accounting_auxiliar")

        deletion_role = Roles(name="catalog_deleter_role", note="Elimina proyectos de su compañía")
        database.session.add(deletion_role)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=deletion_role.id,
                module_id=obtener_id_modulo_por_nombre("accounting"),
                access=True,
                view=True,
                edit=True,
                delete=True,
            )
        )
        database.session.commit()
        asigna_rol_a_usuario("catalog_deleter", "catalog_deleter_role")

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app: Flask, user_id: str) -> FlaskClient:
    """Authenticate an isolated test client as the requested seeded user."""
    client: FlaskClient = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_project_list_hides_foreign_company_data_and_selector_option(catalog_scope_app):
    """The tree and its company selector only contain authorized companies."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")

    response = client.get(LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert LOCAL_PROJECT_NAME in body
    assert LOCAL_COMPANY_NAME in body
    assert FOREIGN_PROJECT_NAME not in body
    assert FOREIGN_PROJECT_CODE not in body
    assert FOREIGN_COMPANY_NAME not in body


def test_project_list_uses_authorized_company_instead_of_foreign_default(catalog_scope_app):
    """A user granted only a non-default company never receives the default catalog."""
    client = _authenticated_client(catalog_scope_app, "catalog_alpha_only")

    response = client.get(LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert FOREIGN_PROJECT_NAME in body
    assert LOCAL_PROJECT_NAME not in body
    assert LOCAL_PROJECT_CODE not in body
    assert LOCAL_COMPANY_NAME not in body


def test_project_list_rejects_forced_foreign_company(catalog_scope_app):
    """Forcing an unauthorized company in the query string is denied without data."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")

    response = client.get(f"{LIST_PATH}?entidad={FOREIGN_COMPANY_CODE}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert FOREIGN_PROJECT_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body


def test_project_list_accepts_own_company_and_requires_any_grant(catalog_scope_app):
    """An authorized company is listed while a user without grants receives 403."""
    reader = _authenticated_client(catalog_scope_app, "catalog_reader")
    without_grants = _authenticated_client(catalog_scope_app, "catalog_no_grants")

    own_company = reader.get(f"{LIST_PATH}?entidad={LOCAL_COMPANY_CODE}")
    assert own_company.status_code == 200
    assert LOCAL_PROJECT_NAME in own_company.get_data(as_text=True)

    assert without_grants.get(LIST_PATH).status_code == 403


def test_project_detail_requires_company_access(catalog_scope_app):
    """Detail by code exposes its own company and denies a foreign project."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")

    own_project = client.get(DETAIL_PATH.format(code=LOCAL_PROJECT_CODE))
    assert own_project.status_code == 200
    assert LOCAL_PROJECT_NAME in own_project.get_data(as_text=True)

    foreign_project = client.get(DETAIL_PATH.format(code=FOREIGN_PROJECT_CODE))
    assert foreign_project.status_code == 403
    body = foreign_project.get_data(as_text=True)
    assert FOREIGN_PROJECT_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body


def test_project_detail_unknown_code_keeps_not_found_behavior(catalog_scope_app):
    """A missing project redirects to the listing without revealing other companies."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")

    response = client.get(DETAIL_PATH.format(code="P-DOES-NOT-EXIST"))

    assert response.status_code == 302
    assert response.headers["Location"].endswith(LIST_PATH)


def test_project_edit_form_requires_company_access(catalog_scope_app):
    """The edit form neither renders nor accepts a project from another company."""
    app = catalog_scope_app
    client = _authenticated_client(app, "catalog_reader")

    own_form = client.get(EDIT_PATH.format(code=LOCAL_PROJECT_CODE))
    assert own_form.status_code == 200
    assert LOCAL_PROJECT_NAME in own_form.get_data(as_text=True)

    assert client.get(EDIT_PATH.format(code=FOREIGN_PROJECT_CODE)).status_code == 403

    forged_update = client.post(
        EDIT_PATH.format(code=FOREIGN_PROJECT_CODE),
        data={"id": FOREIGN_PROJECT_CODE, "nombre": "Nombre alterado", "entidad": LOCAL_COMPANY_CODE},
    )
    assert forged_update.status_code == 403
    with app.app_context():
        project = database.session.execute(database.select(Project).filter_by(code=FOREIGN_PROJECT_CODE)).scalar_one()
        assert project.name == FOREIGN_PROJECT_NAME
        assert project.entity == FOREIGN_COMPANY_CODE


def test_company_selector_is_empty_without_company_grants(catalog_scope_app):
    """The tree selector never falls back to every company for a user without grants."""
    app = catalog_scope_app
    with app.app_context():
        user = database.session.get(User, "catalog_no_grants")
        with app.test_request_context():
            login_user(user)
            assert obtener_entidades() == []


def test_project_delete_requires_company_access(catalog_scope_app):
    """Deleting a foreign project is denied while an authorized project is removed."""
    app = catalog_scope_app
    client = _authenticated_client(app, "catalog_deleter")

    denied = client.post(DELETE_PATH.format(code=FOREIGN_PROJECT_CODE))
    assert denied.status_code == 403
    with app.app_context():
        assert (
            database.session.execute(database.select(Project).filter_by(code=FOREIGN_PROJECT_CODE)).scalar_one_or_none()
            is not None
        )

    allowed = client.post(DELETE_PATH.format(code=LOCAL_PROJECT_CODE))
    assert allowed.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(Project).filter_by(code=LOCAL_PROJECT_CODE)).scalar_one_or_none() is None
        )
