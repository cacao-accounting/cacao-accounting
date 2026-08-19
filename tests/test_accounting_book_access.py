# SPDX-License-Identifier: Apache-2.0
"""Pruebas de acceso granular por libro contable."""

import pytest

from cacao_accounting import create_app, tiene_acceso_bi_empresa
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import Book, Entity, Modules, Roles, RolesAccess, RolesUser, User, UserBookAccess, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


@pytest.fixture()
def app():
    """Crea una aplicacion aislada con dos libros contables."""
    flask_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "book-access-tests",
        }
    )
    with flask_app.app_context():
        database.create_all()
        _seed_book_access_data()
    yield flask_app


@pytest.fixture()
def client(app):
    """Cliente de pruebas Flask."""
    return app.test_client()


def test_permisos_intersects_accounting_access_with_book_access(app):
    """El permiso contable se limita al libro solicitado cuando existe acceso granular."""
    with app.app_context():
        module_id = obtener_id_modulo_por_nombre("accounting")

        allowed = Permisos(modulo=module_id, usuario="USER-ACCOUNTING", libro="FISC")
        denied = Permisos(modulo=module_id, usuario="USER-ACCOUNTING", libro="MGMT")

        assert allowed.autorizado is True
        assert allowed.consultar is True
        assert denied.autorizado is False
        assert denied.consultar is False


def test_accounting_book_selector_only_returns_authorized_books(client):
    """El selector de comprobantes contables oculta libros no autorizados."""
    _login(client)
    response = client.get("/accounting/journal/books?company=cacao")

    assert response.status_code == 200
    assert [row["value"] for row in response.get_json()["results"]] == ["FISC"]


def test_enterprise_sidebar_requires_bi_and_company_book_access(app):
    """Enterprise links require BI plus at least one readable company book."""
    with app.app_context():
        assert tiene_acceso_bi_empresa("mcp", "USER-ACCOUNTING") is True

        database.session.query(UserBookAccess).delete()
        database.session.commit()
        assert tiene_acceso_bi_empresa("mcp", "USER-ACCOUNTING") is False


def test_operational_modules_do_not_validate_ledger_access(client):
    """Los modulos operativos no se bloquean por parametros ledger accidentales."""
    _login(client)
    response = client.get("/cash_management/?ledger=MGMT")

    assert response.status_code == 200


def test_journal_acl_fails_closed_for_unknown_user(app):
    """Un actor inexistente no puede usar el servicio como bypass interno."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, _authorized_journal_books

    with app.app_context(), pytest.raises(JournalValidationError, match="usuario indicado no existe"):
        _authorized_journal_books("cacao", ["FISC"], "UNKNOWN-USER", "crear")


def test_recurring_template_validates_legacy_primary_ledger(app):
    """Una plantilla legacy sin book_codes también protege su ledger principal."""
    from cacao_accounting.contabilidad.recurring_journal_service import (
        RecurringJournalError,
        validate_recurring_template_access,
    )
    from cacao_accounting.database import RecurringJournalTemplate

    with app.app_context():
        template = RecurringJournalTemplate(company="cacao", ledger_id="MGMT", book_codes=None)
        with pytest.raises(RecurringJournalError, match="no tiene acceso al libro contable MGMT"):
            validate_recurring_template_access(template, "USER-ACCOUNTING", "consultar")


def test_recurring_template_rejects_missing_canonical_books(app):
    """Una plantilla legacy sin ningún libro no se expande implícitamente."""
    from cacao_accounting.contabilidad.recurring_journal_service import (
        RecurringJournalError,
        validate_recurring_template_access,
    )
    from cacao_accounting.database import RecurringJournalTemplate

    with app.app_context():
        template = RecurringJournalTemplate(company="cacao", ledger_id=None, book_codes=None)
        with pytest.raises(RecurringJournalError, match="selección canónica"):
            validate_recurring_template_access(template, "USER-ACCOUNTING", "consultar")


def _seed_book_access_data() -> None:
    """Inserta modulos, usuario y accesos de libro para las pruebas."""
    database.session.add_all(
        [
            Modules(id="MOD-ACCOUNTING", module="accounting", default=True, enabled=True),
            Modules(id="MOD-CASH", module="cash", default=True, enabled=True),
            Modules(id="MOD-MCP", module="mcp", default=False, enabled=True),
            Roles(id="ROLE-ACCOUNTING", name="accounting_user", note="Accounting user"),
            User(id="USER-ACCOUNTING", user="accounting", password=b"test", active=True),
            Entity(id="cacao", code="cacao", company_name="Cacao", tax_id="J000", currency="NIO"),
            Book(id="BOOK-FISC", code="FISC", name="Fiscal", entity="cacao", status="activo", is_primary=True),
            Book(id="BOOK-MGMT", code="MGMT", name="Gestion", entity="cacao", status="activo"),
        ]
    )
    database.session.flush()
    database.session.add(RolesUser(user_id="USER-ACCOUNTING", role_id="ROLE-ACCOUNTING", active=True))
    database.session.add_all(
        [
            RolesAccess(rol_id="ROLE-ACCOUNTING", module_id="MOD-ACCOUNTING", access=True, view=True),
            RolesAccess(rol_id="ROLE-ACCOUNTING", module_id="MOD-CASH", access=True, view=True),
            RolesAccess(rol_id="ROLE-ACCOUNTING", module_id="MOD-MCP", access=True, bi=True),
            UserBookAccess(user_id="USER-ACCOUNTING", book_id="BOOK-FISC", can_read=True),
        ]
    )
    database.session.commit()


def _login(client) -> None:
    """Marca el usuario contable como autenticado en el cliente Flask."""
    with client.session_transaction() as session:
        session["_user_id"] = "USER-ACCOUNTING"
        session["_fresh"] = True
