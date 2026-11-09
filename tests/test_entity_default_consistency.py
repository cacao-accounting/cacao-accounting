# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La entidad predeterminada debe ser única para todos los lectores.

Escenario de negocio: al marcar la entidad B como predeterminada, los lectores
que usan ``Entity.status`` deben resolver B, no quedarse en A. El flag booleano
``default`` y ``status`` deben describir la misma compañía.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.auxiliares import obtener_entidad
from cacao_accounting.database import Entity, Modules, User, database

CONTRASENA = "entidad-default-2026"


@pytest.fixture
def entidades_default():
    """Dos entidades activas, A predeterminada y B secundaria."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                    default=True,
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                    default=False,
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        beta_id = database.session.execute(database.select(Entity).filter_by(code="beta")).scalar_one().id
    yield application, beta_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_predeterminar_actualiza_default_y_status(entidades_default):
    """B queda como única entidad predeterminada para ambos contratos."""
    application, beta_id = entidades_default
    client = application.test_client()
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200

    response = client.get(f"/accounting/entity/set_default/{beta_id}")

    assert response.status_code == 302
    with application.app_context():
        alpha = database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one()
        beta = database.session.execute(database.select(Entity).filter_by(code="beta")).scalar_one()
        assert beta.default is True
        assert beta.status == "default"
        assert alpha.default is False
        assert alpha.status != "default"
        assert obtener_entidad()[0].code == "beta"
