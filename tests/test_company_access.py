# SPDX-License-Identifier: Apache-2.0
"""Pruebas del alcance paralelo de compañías para usuarios internos."""

import pytest

from cacao_accounting import create_app, tiene_acceso_bi_empresa
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
from cacao_accounting.contabilidad.posting_service import _active_books
from cacao_accounting.database import (
    Book,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


@pytest.fixture()
def app():
    """Crea una aplicación aislada con dos compañías y libros."""
    flask_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "company-access-tests",
        }
    )
    with flask_app.app_context():
        database.create_all()
        _seed_company_access_data()
    yield flask_app


@pytest.fixture()
def client(app):
    """Cliente Flask autenticado por cada prueba."""
    return app.test_client()


def test_roles_and_company_access_are_parallel(app):
    """Un rol habilita acciones, pero el grant delimita la compañía."""
    with app.app_context():
        permissions = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario="USER-ACCOUNTING")
        assert permissions.consultar is True
        assert permissions.tiene_acceso_compania("cacao") is True
        assert permissions.tiene_acceso_compania("cafe") is False


def test_company_selector_does_not_disclose_unassigned_active_company(client):
    """Un selector muestra solo compañías activas expresamente asignadas."""
    from flask_login import login_user

    with client.application.test_request_context():
        login_user(database.session.get(User, "USER-ACCOUNTING"))
        assert obtener_lista_entidades_por_id_razonsocial() == [("", ""), ("cacao", "Cacao")]


def test_journal_book_selector_returns_all_active_books_for_assigned_company(client):
    """Los libros no son ACL y todos los activos permanecen visibles para posting."""
    _login(client)
    response = client.get("/accounting/journal/books?company=cacao")
    assert response.status_code == 200
    assert [row["value"] for row in response.get_json()["results"]] == ["FISC", "MGMT"]


def test_journal_book_selector_does_not_disclose_unassigned_company(client):
    """Un endpoint de selector no revela los libros de otra compañía."""
    _login(client)
    response = client.get("/accounting/journal/books?company=cafe")
    assert response.status_code == 200
    assert response.get_json() == {"results": []}


def test_posting_book_resolution_ignores_legacy_subset(app):
    """El límite de posting siempre retorna todos los libros activos de la compañía."""
    with app.app_context():
        assert [book.code for book in _active_books("cacao", "FISC")] == ["FISC", "MGMT"]


def test_enterprise_sidebar_requires_bi_and_company_access(app):
    """BI requiere su rol global y al menos una compañía asignada."""
    with app.app_context():
        assert tiene_acceso_bi_empresa("mcp", "USER-ACCOUNTING") is True
        database.session.query(UserCompanyAccess).delete()
        database.session.commit()
        assert tiene_acceso_bi_empresa("mcp", "USER-ACCOUNTING") is False


def _seed_company_access_data() -> None:
    """Inserta roles globales, compañías y grants explícitos."""
    database.session.add_all(
        [
            Modules(id="MOD-ACCOUNTING", module="accounting", default=True, enabled=True),
            Modules(id="MOD-MCP", module="mcp", default=False, enabled=True),
            Roles(id="ROLE-ACCOUNTING", name="accounting_user", note="Accounting user"),
            User(id="USER-ACCOUNTING", user="accounting", password=b"test", active=True),
            Entity(id="cacao", code="cacao", name="Cacao", company_name="Cacao", tax_id="J000", currency="NIO"),
            Entity(id="cafe", code="cafe", name="Cafe", company_name="Cafe", tax_id="J001", currency="NIO"),
            Book(id="BOOK-FISC", code="FISC", name="Fiscal", entity="cacao", status="activo", is_primary=True),
            Book(id="BOOK-MGMT", code="MGMT", name="Gestion", entity="cacao", status="activo"),
            Book(id="BOOK-CAFE", code="FISC-CAFE", name="Fiscal", entity="cafe", status="activo", is_primary=True),
            RolesUser(user_id="USER-ACCOUNTING", role_id="ROLE-ACCOUNTING", active=True),
            RolesAccess(rol_id="ROLE-ACCOUNTING", module_id="MOD-ACCOUNTING", access=True, view=True),
            RolesAccess(rol_id="ROLE-ACCOUNTING", module_id="MOD-MCP", access=True, bi=True),
            UserCompanyAccess(user_id="USER-ACCOUNTING", company_code="cacao"),
        ]
    )
    database.session.commit()


def _login(client) -> None:
    """Marca al usuario interno como autenticado."""
    with client.session_transaction() as session:
        session["_user_id"] = "USER-ACCOUNTING"
        session["_fresh"] = True
