# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Fail-closed del administrador de plantillas de impresión.

Escenario de negocio: si la base no contiene el rol ``admin`` (instalación
incompleta o rol retirado), un usuario autenticado cualquiera no debe heredar
el CRUD de plantillas de impresión. La ausencia de la referencia administrativa
debe denegar, no conceder.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Roles, RolesUser, User, database

CONTRASENA = "print-admin-2026"


@pytest.fixture
def impresion_sin_rol_admin():
    """Aplicación con un usuario activo y sin fila del rol admin."""
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
        database.session.add(
            User(
                id="ventas",
                user="ventas",
                name="Ventas",
                password=proteger_passwd(CONTRASENA),
                active=True,
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "ventas", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_sin_rol_admin_las_plantillas_se_deniegan(impresion_sin_rol_admin):
    """La ausencia del rol admin no abre el CRUD de plantillas."""
    client = impresion_sin_rol_admin.test_client()
    _iniciar(client)

    response = client.get("/admin/print-templates")

    assert response.status_code == 403


def test_con_rol_admin_las_plantillas_se_permiten(impresion_sin_rol_admin):
    """Control positivo: el administrador real conserva el acceso."""
    application = impresion_sin_rol_admin
    with application.app_context():
        rol = Roles(name="admin", note="Administrador")
        database.session.add(rol)
        database.session.flush()
        database.session.add(RolesUser(user_id="ventas", role_id=rol.id, active=True))
        database.session.commit()

    client = application.test_client()
    _iniciar(client)

    response = client.get("/admin/print-templates")

    assert response.status_code == 200
