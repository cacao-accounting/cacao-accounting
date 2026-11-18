# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1546: el catálogo contable solo expone la compañía autorizada.

Los listados, detalles, formularios de edición y borrados de proyectos, cuentas,
centros de costo y unidades de negocio deben exigir acceso a la compañía dueña
del registro. Una compañía ajena no aparece como opción ni entrega datos aunque
se fuerce su código en la URL o se repita su código entre compañías.
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
    Accounts,
    CostCenter,
    Currency,
    Entity,
    Modules,
    Project,
    Roles,
    RolesAccess,
    Unit,
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

LOCAL_ACCOUNT_CODE = "1100"
LOCAL_ACCOUNT_NAME = "Cuenta Local Cacao"
FOREIGN_ACCOUNT_CODE = "SECRET"
FOREIGN_ACCOUNT_NAME = "B_PRIVATE_AR"

LOCAL_UNIT_CODE = "ULOCAL"
LOCAL_UNIT_NAME = "Unidad Local Cacao"
FOREIGN_UNIT_CODE = "USECRET"
FOREIGN_UNIT_NAME = "Unidad Privada Alpha"

LOCAL_COST_CENTER_CODE = "CCLOCAL"
LOCAL_COST_CENTER_NAME = "Centro Local Cacao"
FOREIGN_COST_CENTER_CODE = "CCSECRET"
FOREIGN_COST_CENTER_NAME = "Centro Privado Alpha"
DUPLICATED_COST_CENTER_CODE = "CC-DUP"
LOCAL_DUPLICATED_NAME = "Centro Duplicado Local"
FOREIGN_DUPLICATED_NAME = "Centro Duplicado Privado"

LIST_PATH = "/accounting/project/list"
DETAIL_PATH = "/accounting/project/{code}"
EDIT_PATH = "/accounting/project/{code}/edit"
DELETE_PATH = "/accounting/project/{code}/delete"

UNIT_LIST_PATH = "/accounting/unit/list"
UNIT_DETAIL_PATH = "/accounting/unit/{code}"
UNIT_EDIT_PATH = "/accounting/unit/{code}/edit"
UNIT_DELETE_PATH = "/accounting/unit/delete/{code}"

ACCOUNT_LIST_PATH = "/accounting/accounts"
ACCOUNT_DETAIL_PATH = "/accounting/account/{entity}/{code}"
ACCOUNT_EDIT_PATH = "/accounting/account/{entity}/{code}/edit"

COST_CENTER_LIST_PATH = "/accounting/costs_center"
COST_CENTER_DETAIL_PATH = "/accounting/costs_center/{code}"
COST_CENTER_EDIT_PATH = "/accounting/costs_center/{code}/edit"
COST_CENTER_DELETE_PATH = "/accounting/costs_center/{code}/delete"


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
            ]
        )
        database.session.commit()
        database.session.add_all(
            [
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
                Accounts(entity=LOCAL_COMPANY_CODE, code="1100", name=LOCAL_ACCOUNT_NAME, classification="asset"),
                Accounts(entity=FOREIGN_COMPANY_CODE, code="SECRET", name=FOREIGN_ACCOUNT_NAME, classification="asset"),
                Unit(code=LOCAL_UNIT_CODE, name=LOCAL_UNIT_NAME, entity=LOCAL_COMPANY_CODE, enabled=True),
                Unit(code=FOREIGN_UNIT_CODE, name=FOREIGN_UNIT_NAME, entity=FOREIGN_COMPANY_CODE, enabled=True),
                CostCenter(code=LOCAL_COST_CENTER_CODE, name=LOCAL_COST_CENTER_NAME, entity=LOCAL_COMPANY_CODE),
                CostCenter(code=FOREIGN_COST_CENTER_CODE, name=FOREIGN_COST_CENTER_NAME, entity=FOREIGN_COMPANY_CODE),
                CostCenter(code=DUPLICATED_COST_CENTER_CODE, name=LOCAL_DUPLICATED_NAME, entity=LOCAL_COMPANY_CODE),
                CostCenter(code=DUPLICATED_COST_CENTER_CODE, name=FOREIGN_DUPLICATED_NAME, entity=FOREIGN_COMPANY_CODE),
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


def test_unit_list_and_detail_require_company_access(catalog_scope_app):
    """The unit catalogue and its detail only expose the authorized company."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")

    listing = client.get(UNIT_LIST_PATH)
    assert listing.status_code == 200
    body = listing.get_data(as_text=True)
    assert LOCAL_UNIT_NAME in body
    assert FOREIGN_UNIT_NAME not in body
    assert FOREIGN_UNIT_CODE not in body
    assert FOREIGN_COMPANY_NAME not in body

    forced = client.get(f"{UNIT_LIST_PATH}?entidad={FOREIGN_COMPANY_CODE}")
    assert forced.status_code == 403
    assert FOREIGN_UNIT_NAME not in forced.get_data(as_text=True)

    own_detail = client.get(UNIT_DETAIL_PATH.format(code=LOCAL_UNIT_CODE))
    assert own_detail.status_code == 200
    assert LOCAL_UNIT_NAME in own_detail.get_data(as_text=True)

    foreign_detail = client.get(UNIT_DETAIL_PATH.format(code=FOREIGN_UNIT_CODE))
    assert foreign_detail.status_code == 403
    body = foreign_detail.get_data(as_text=True)
    assert FOREIGN_UNIT_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body


def test_unit_list_uses_authorized_company_instead_of_foreign_default(catalog_scope_app):
    """A user granted only a non-default company never receives the default catalogue."""
    client = _authenticated_client(catalog_scope_app, "catalog_alpha_only")

    response = client.get(UNIT_LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert FOREIGN_UNIT_NAME in body
    assert LOCAL_UNIT_NAME not in body
    assert LOCAL_UNIT_CODE not in body
    assert LOCAL_COMPANY_NAME not in body


def test_unit_edit_and_delete_require_company_access(catalog_scope_app):
    """Editing or deleting a unit demands access to its owning company."""
    app = catalog_scope_app
    deleter = _authenticated_client(app, "catalog_deleter")
    reader = _authenticated_client(app, "catalog_reader")

    assert deleter.get(UNIT_EDIT_PATH.format(code=LOCAL_UNIT_CODE)).status_code == 200
    assert deleter.get(UNIT_EDIT_PATH.format(code=FOREIGN_UNIT_CODE)).status_code == 403

    forged = deleter.post(
        UNIT_EDIT_PATH.format(code=FOREIGN_UNIT_CODE),
        data={"id": FOREIGN_UNIT_CODE, "nombre": "Unidad alterada", "entidad": LOCAL_COMPANY_CODE, "habilitado": "y"},
    )
    assert forged.status_code == 403
    with app.app_context():
        unit = database.session.execute(database.select(Unit).filter_by(code=FOREIGN_UNIT_CODE)).scalar_one()
        assert unit.name == FOREIGN_UNIT_NAME
        assert unit.entity == FOREIGN_COMPANY_CODE

    cross_move = reader.post(
        UNIT_EDIT_PATH.format(code=LOCAL_UNIT_CODE),
        data={"id": LOCAL_UNIT_CODE, "nombre": LOCAL_UNIT_NAME, "entidad": FOREIGN_COMPANY_CODE, "habilitado": "y"},
    )
    assert cross_move.status_code == 200
    with app.app_context():
        unit = database.session.execute(database.select(Unit).filter_by(code=LOCAL_UNIT_CODE)).scalar_one()
        assert unit.entity == LOCAL_COMPANY_CODE

    denied = deleter.post(UNIT_DELETE_PATH.format(code=FOREIGN_UNIT_CODE))
    assert denied.status_code == 403
    with app.app_context():
        assert (
            database.session.execute(database.select(Unit).filter_by(code=FOREIGN_UNIT_CODE)).scalar_one_or_none() is not None
        )

    allowed = deleter.post(UNIT_DELETE_PATH.format(code=LOCAL_UNIT_CODE))
    assert allowed.status_code == 302
    with app.app_context():
        assert database.session.execute(database.select(Unit).filter_by(code=LOCAL_UNIT_CODE)).scalar_one_or_none() is None


def test_account_list_detail_and_edit_require_company_access(catalog_scope_app):
    """The account catalogue, its detail and edit form are company scoped."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")
    without_grants = _authenticated_client(catalog_scope_app, "catalog_no_grants")

    listing = client.get(ACCOUNT_LIST_PATH)
    assert listing.status_code == 200
    body = listing.get_data(as_text=True)
    assert LOCAL_ACCOUNT_NAME in body
    assert FOREIGN_ACCOUNT_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body

    forced = client.get(f"{ACCOUNT_LIST_PATH}?entidad={FOREIGN_COMPANY_CODE}")
    assert forced.status_code == 403
    assert FOREIGN_ACCOUNT_NAME not in forced.get_data(as_text=True)

    assert without_grants.get(ACCOUNT_LIST_PATH).status_code == 403

    own_detail = client.get(ACCOUNT_DETAIL_PATH.format(entity=LOCAL_COMPANY_CODE, code=LOCAL_ACCOUNT_CODE))
    assert own_detail.status_code == 200
    assert LOCAL_ACCOUNT_NAME in own_detail.get_data(as_text=True)

    foreign_detail = client.get(ACCOUNT_DETAIL_PATH.format(entity=FOREIGN_COMPANY_CODE, code=FOREIGN_ACCOUNT_CODE))
    assert foreign_detail.status_code == 403
    body = foreign_detail.get_data(as_text=True)
    assert FOREIGN_ACCOUNT_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body

    own_form = client.get(ACCOUNT_EDIT_PATH.format(entity=LOCAL_COMPANY_CODE, code=LOCAL_ACCOUNT_CODE))
    assert own_form.status_code == 200
    assert LOCAL_ACCOUNT_NAME in own_form.get_data(as_text=True)

    foreign_form = client.get(ACCOUNT_EDIT_PATH.format(entity=FOREIGN_COMPANY_CODE, code=FOREIGN_ACCOUNT_CODE))
    assert foreign_form.status_code == 403
    assert FOREIGN_ACCOUNT_NAME not in foreign_form.get_data(as_text=True)


def test_cost_center_list_detail_and_edit_require_company_access(catalog_scope_app):
    """The cost center catalogue, detail and edit form are company scoped."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")
    without_grants = _authenticated_client(catalog_scope_app, "catalog_no_grants")

    listing = client.get(COST_CENTER_LIST_PATH)
    assert listing.status_code == 200
    body = listing.get_data(as_text=True)
    assert LOCAL_COST_CENTER_NAME in body
    assert FOREIGN_COST_CENTER_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body

    assert without_grants.get(COST_CENTER_LIST_PATH).status_code == 403
    assert without_grants.get(COST_CENTER_DETAIL_PATH.format(code=LOCAL_COST_CENTER_CODE)).status_code == 403

    forced = client.get(f"{COST_CENTER_LIST_PATH}?entidad={FOREIGN_COMPANY_CODE}")
    assert forced.status_code == 403
    assert FOREIGN_COST_CENTER_NAME not in forced.get_data(as_text=True)

    own_detail = client.get(COST_CENTER_DETAIL_PATH.format(code=LOCAL_COST_CENTER_CODE))
    assert own_detail.status_code == 200
    assert LOCAL_COST_CENTER_NAME in own_detail.get_data(as_text=True)

    foreign_detail = client.get(COST_CENTER_DETAIL_PATH.format(code=FOREIGN_COST_CENTER_CODE))
    assert foreign_detail.status_code == 403
    body = foreign_detail.get_data(as_text=True)
    assert FOREIGN_COST_CENTER_NAME not in body
    assert FOREIGN_COMPANY_NAME not in body

    own_form = client.get(COST_CENTER_EDIT_PATH.format(code=LOCAL_COST_CENTER_CODE))
    assert own_form.status_code == 200
    assert LOCAL_COST_CENTER_NAME in own_form.get_data(as_text=True)

    foreign_form = client.get(COST_CENTER_EDIT_PATH.format(code=FOREIGN_COST_CENTER_CODE))
    assert foreign_form.status_code == 403
    assert FOREIGN_COST_CENTER_NAME not in foreign_form.get_data(as_text=True)

    missing = client.get(COST_CENTER_DETAIL_PATH.format(code="CC-DOES-NOT-EXIST"))
    assert missing.status_code == 302
    assert missing.headers["Location"].endswith(COST_CENTER_LIST_PATH)


def test_cost_center_duplicate_code_resolves_inside_authorized_company(catalog_scope_app):
    """A code repeated in two companies resolves to the authorized company row."""
    client = _authenticated_client(catalog_scope_app, "catalog_reader")

    response = client.get(COST_CENTER_DETAIL_PATH.format(code=DUPLICATED_COST_CENTER_CODE))

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert LOCAL_DUPLICATED_NAME in body
    assert FOREIGN_DUPLICATED_NAME not in body


def test_cost_center_edit_and_delete_reject_foreign_company(catalog_scope_app):
    """A forged company change is rejected and a foreign center cannot be deleted."""
    app = catalog_scope_app
    reader = _authenticated_client(app, "catalog_reader")
    deleter = _authenticated_client(app, "catalog_deleter")

    forged = reader.post(
        COST_CENTER_EDIT_PATH.format(code=LOCAL_COST_CENTER_CODE),
        data={"id": LOCAL_COST_CENTER_CODE, "nombre": "Centro alterado", "entidad": FOREIGN_COMPANY_CODE},
    )
    assert forged.status_code == 403
    with app.app_context():
        center = database.session.execute(database.select(CostCenter).filter_by(code=LOCAL_COST_CENTER_CODE)).scalar_one()
        assert center.name == LOCAL_COST_CENTER_NAME
        assert center.entity == LOCAL_COMPANY_CODE

    denied = deleter.post(COST_CENTER_DELETE_PATH.format(code=FOREIGN_COST_CENTER_CODE))
    assert denied.status_code == 403
    with app.app_context():
        assert (
            database.session.execute(database.select(CostCenter).filter_by(code=FOREIGN_COST_CENTER_CODE)).scalar_one_or_none()
            is not None
        )

    allowed = deleter.post(COST_CENTER_DELETE_PATH.format(code=LOCAL_COST_CENTER_CODE))
    assert allowed.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(CostCenter).filter_by(code=LOCAL_COST_CENTER_CODE)).scalar_one_or_none()
            is None
        )
