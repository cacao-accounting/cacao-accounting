# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas unitarias para los decoradores de seguridad del módulo de decorators."""

from __future__ import annotations

import pytest
from werkzeug.exceptions import Forbidden

from cacao_accounting import create_app
from cacao_accounting.database import (
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    database,
)


@pytest.fixture()
def app():
    """Crea una app aislada para pruebas de decoradores."""
    flask_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "decorator-tests",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with flask_app.app_context():
        database.create_all()
        _seed_minimal_data()
    yield flask_app
    with flask_app.app_context():
        database.session.remove()
        database.drop_all()


def _seed_minimal_data() -> None:
    """Crea el mínimo de datos para probar decoradores de permisos."""
    module = Modules(id="MOD-CASH", module="cash", default=True, enabled=True)
    database.session.add(module)
    database.session.flush()

    role_with_approve = Roles(id="ROLE-APPROVE", name="Aprobador", note="Role con permiso de aprobar")
    role_without_approve = Roles(id="ROLE-NO-APPROVE", name="Sin Aprobación", note="Role sin permiso de aprobar")
    database.session.add_all([role_with_approve, role_without_approve])
    database.session.flush()

    database.session.add(
        RolesAccess(
            rol_id="ROLE-APPROVE",
            module_id="MOD-CASH",
            access=True,
            view=True,
            approve=True,
        )
    )
    database.session.add(
        RolesAccess(
            rol_id="ROLE-NO-APPROVE",
            module_id="MOD-CASH",
            access=True,
            view=True,
            approve=False,
        )
    )

    user_approve = User(
        id="USER-APPROVE",
        user="approve_user",
        name="Aprobador",
        password=b"x",
        classification="user",
        active=True,
    )
    user_no_approve = User(
        id="USER-NO-APPROVE",
        user="no_approve_user",
        name="Sin Aprobación",
        password=b"x",
        classification="user",
        active=True,
    )
    user_inactive = User(
        id="USER-INACTIVE",
        user="inactive_user",
        name="Inactivo",
        password=b"x",
        classification="user",
        active=False,
    )
    database.session.add_all([user_approve, user_no_approve, user_inactive])
    database.session.flush()

    database.session.add_all(
        [
            RolesUser(user_id="USER-APPROVE", role_id="ROLE-APPROVE", active=True),
            RolesUser(user_id="USER-NO-APPROVE", role_id="ROLE-NO-APPROVE", active=True),
        ]
    )
    database.session.commit()


def test_verifica_permiso_allows_authorized_user(app):
    """Un usuario con permiso 'autorizar' puede ejecutar la ruta protegida."""
    from flask_login import login_user

    from cacao_accounting.decorators import verifica_permiso

    with app.app_context():
        user = database.session.get(User, "USER-APPROVE")

        @verifica_permiso("cash", "autorizar")
        def protected_route():
            return "ok"

        with app.test_request_context():
            login_user(user)
            result = protected_route()
            assert result == "ok"


def test_verifica_permiso_rejects_unauthorized_user(app):
    """Un usuario sin permiso 'autorizar' recibe 403."""
    from flask_login import login_user

    from cacao_accounting.decorators import verifica_permiso

    with app.app_context():
        user = database.session.get(User, "USER-NO-APPROVE")

        @verifica_permiso("cash", "autorizar")
        def protected_route():
            return "ok"

        with app.test_request_context():
            login_user(user)
            with pytest.raises(Forbidden):
                protected_route()


def test_verifica_permiso_rejects_unauthenticated_user(app):
    """Un usuario no autenticado recibe 403 sin intentar buscar permisos."""
    from cacao_accounting.decorators import verifica_permiso

    with app.app_context():

        @verifica_permiso("cash", "autorizar")
        def protected_route():
            return "ok"

        with app.test_request_context():
            with pytest.raises(Forbidden):
                protected_route()


def test_verifica_permiso_rejects_wrong_action(app):
    """Un usuario con permiso de 'crear' no puede ejecutar 'autorizar'."""
    from flask_login import login_user

    from cacao_accounting.decorators import verifica_permiso

    with app.app_context():
        user = database.session.get(User, "USER-NO-APPROVE")

        @verifica_permiso("cash", "autorizar")
        def protected_route():
            return "ok"

        with app.test_request_context():
            login_user(user)
            with pytest.raises(Forbidden):
                protected_route()


def test_exige_acceso_compania_blocks_unauthenticated(app):
    """exige_acceso_compania aborta 403 para usuarios no autenticados."""
    from cacao_accounting.decorators import exige_acceso_compania

    with app.test_request_context():
        with pytest.raises(Forbidden):
            exige_acceso_compania("cash", "TEST", "consultar")


def test_exige_acceso_compania_allows_unauthenticated_when_flag_set(app):
    """exige_acceso_compania permite llamadas internas con allow_unauthenticated."""
    from cacao_accounting.decorators import exige_acceso_compania

    with app.test_request_context():
        exige_acceso_compania("cash", "TEST", "consultar", allow_unauthenticated=True)


def test_verifica_permiso_preserves_function_metadata(app):
    """El decorator preserva __name__ y __doc__ de la función original."""
    from cacao_accounting.decorators import verifica_permiso

    @verifica_permiso("cash", "autorizar")
    def documented_route():
        """Docstring de prueba."""

    assert documented_route.__name__ == "documented_route"
    assert documented_route.__doc__ == "Docstring de prueba."
