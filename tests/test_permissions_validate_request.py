# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1576: `validar_solicitud` refleja el campo `validate` del rol.

El modelo de permisos solo tiene `validate`; el diagnóstico de roles muestra
ambos nombres y el permiso calculado no debe aparecer siempre denegado.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, Roles, RolesAccess, RolesUser, User, database


@pytest.fixture
def validate_request_scenario():
    """Create roles with and without the validate field."""
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

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code=f"c{suffix}",
                    name="Compañía",
                    company_name=f"Compañía {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        validator = User(
            id=f"validator-{suffix}", user=f"validator-{suffix}", name="Validador", password=b"unused", active=True
        )
        plain = User(id=f"plain-{suffix}", user=f"plain-{suffix}", name="Sin validar", password=b"unused", active=True)
        database.session.add_all([validator, plain])
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        validating_role = Roles(name=f"validator-{suffix}", note="Valida solicitudes")
        plain_role = Roles(name=f"plain-{suffix}", note="Sin validar")
        database.session.add_all([validating_role, plain_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=validating_role.id, module_id=module_id, access=True, view=True, validate=True),
                RolesAccess(rol_id=plain_role.id, module_id=module_id, access=True, view=False),
                RolesUser(user_id=validator.id, role_id=validating_role.id, active=True),
                RolesUser(user_id=plain.id, role_id=plain_role.id, active=True),
            ]
        )
        database.session.commit()
        ids = {
            "module_id": module_id,
            "validator": validator.id,
            "plain": plain.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_validate_request_matches_validate_field(validate_request_scenario):
    """A role with validate=True grants both diagnostic permission names."""
    app, ids = validate_request_scenario

    with app.app_context():
        permissions = Permisos(modulo=ids["module_id"], usuario=ids["validator"])

    assert permissions.validar is True
    assert permissions.validar_solicitud is True


def test_validate_request_is_false_without_validate_field(validate_request_scenario):
    """A role without validate keeps both names denied."""
    app, ids = validate_request_scenario

    with app.app_context():
        permissions = Permisos(modulo=ids["module_id"], usuario=ids["plain"])

    assert permissions.validar is False
    assert permissions.validar_solicitud is False


def test_listar_refleja_el_campo_view(validate_request_scenario):
    """La accion Listar del diagnostico usa el mismo campo view que consultar."""
    app, ids = validate_request_scenario

    with app.app_context():
        con_vista = Permisos(modulo=ids["module_id"], usuario=ids["validator"])
        sin_vista = Permisos(modulo=ids["module_id"], usuario=ids["plain"])

    assert con_vista.listar is True
    assert con_vista.consultar is True
    assert sin_vista.listar is False
    assert sin_vista.consultar is False
