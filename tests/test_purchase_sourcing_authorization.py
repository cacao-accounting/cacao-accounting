# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La autorización de abastecimiento respeta la vigencia de asignaciones de rol."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    _validate_award_authorization,
    is_purchase_manager,
    is_purchase_sourcing_authorizer,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import Roles, RolesUser, User, database


@pytest.fixture
def purchase_roles(tmp_path: Path):
    """Provide active, revoked, legacy, and admin users with persisted assignments."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'purchase_roles.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    users = {
        "active": User(id="active", user="active", name="Activo", password=b"x", active=True),
        "revoked": User(id="revoked", user="revoked", name="Revocado", password=b"x", active=True),
        "legacy": User(id="legacy", user="legacy", name="Histórico", password=b"x", active=True),
        "admin": User(
            id="admin",
            user="admin",
            name="Administrador",
            password=b"x",
            active=True,
            classification="admin",
        ),
    }
    with application.app_context():
        database.create_all()
        database.session.add_all([*users.values(), Roles(name="Gerente de Compras", note="Gerente de Compras")])
        database.session.flush()
        manager_role = database.session.execute(database.select(Roles).filter_by(name="Gerente de Compras")).scalar_one()
        database.session.add_all(
            [
                RolesUser(user_id=users["active"].id, role_id=manager_role.id, active=True),
                RolesUser(user_id=users["revoked"].id, role_id=manager_role.id, active=False),
                RolesUser(user_id=users["legacy"].id, role_id=manager_role.id, active=None),
            ]
        )
        user_ids = {key: user.id for key, user in users.items()}
        database.session.commit()
    yield application, user_ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize(
    ("assignment", "expected"),
    [("active", True), ("revoked", False), ("legacy", True)],
)
def test_purchase_manager_checks_assignment_state(purchase_roles, assignment, expected):
    """A revoked assignment is denied while NULL remains a legacy active value."""
    application, users = purchase_roles
    with application.app_context():
        assert is_purchase_manager(users[assignment]) is expected
        assert is_purchase_sourcing_authorizer(users[assignment]) is expected


@pytest.mark.parametrize(("assignment", "authorized"), [("active", True), ("revoked", False), ("legacy", True)])
def test_only_current_or_legacy_manager_can_authorize_single_offer(purchase_roles, assignment, authorized):
    """The role state controls the insufficient-offer exception used by award flows."""
    application, users = purchase_roles
    with application.app_context():
        if authorized:
            _validate_award_authorization([], minimum_offers=1, user_id=users[assignment], reason="Excepción aprobada")
            return

        with pytest.raises(PurchaseSourcingError, match="Se requieren al menos"):
            _validate_award_authorization([], minimum_offers=1, user_id=users[assignment], reason="Excepción aprobada")


def test_administrador_conserva_autorización_de_excepciones(purchase_roles):
    """The admin classification remains an independent authorization path."""
    application, users = purchase_roles
    with application.app_context():
        assert not is_purchase_manager(users["admin"])
        assert is_purchase_sourcing_authorizer(users["admin"])
        _validate_award_authorization([], minimum_offers=1, user_id=users["admin"], reason="Excepción aprobada")
