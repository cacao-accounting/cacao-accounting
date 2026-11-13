# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La edición de roles reemplaza por vigencia, no por borrado.

Escenario de negocio (issue #2006): ``usuario_roles`` borraba las filas
existentes y las recreaba; el guard de modelos sensibles rechazaba el DELETE y
la ruta devolvía 500 sin poder conservar, cambiar o retirar roles.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
    User,
    database,
)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                User(
                    id="objetivo",
                    user="objetivo",
                    name="Objetivo",
                    password=b"x",
                    active=True,
                    classification="system",
                ),
                Roles(name="sales_user", note="Usuario de ventas"),
                Roles(name="sales_manager", note="Gerente de ventas"),
            ]
        )
        database.session.flush()
        rol_user = database.session.execute(database.select(Roles).filter_by(name="sales_user")).scalar_one()
        database.session.add(RolesUser(user_id="objetivo", role_id=rol_user.id, active=True))
        database.session.commit()
        roles = {
            "sales_user": rol_user.id,
            "sales_manager": database.session.execute(database.select(Roles).filter_by(name="sales_manager")).scalar_one().id,
        }
    return application, roles


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _asignaciones(application):
    return {
        row.role_id: row.active
        for row in database.session.execute(database.select(RolesUser).filter_by(user_id="objetivo")).scalars().all()
    }


def test_cambia_y_retira_roles_sin_borrar_filas():
    """Cambiar a manager y luego retirar todo usa active, sin DELETE."""
    application, roles = _crear_app()
    try:
        client = _cliente(application)

        cambio = client.post(
            "/settings/users/objetivo/roles",
            data={"roles": roles["sales_manager"]},
        )
        assert cambio.status_code == 302
        with application.app_context():
            assert _asignaciones(application) == {roles["sales_user"]: False, roles["sales_manager"]: True}

        retiro = client.post("/settings/users/objetivo/roles", data={})
        assert retiro.status_code == 302
        with application.app_context():
            asignaciones = _asignaciones(application)
            assert asignaciones == {roles["sales_user"]: False, roles["sales_manager"]: False}
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_conservar_el_mismo_rol_no_falla():
    """Reenviar la asignación vigente mantiene el rol activo."""
    application, roles = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/users/objetivo/roles",
            data={"roles": roles["sales_user"]},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            assert _asignaciones(application) == {roles["sales_user"]: True}
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
