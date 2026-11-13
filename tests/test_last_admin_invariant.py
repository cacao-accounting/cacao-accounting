# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El sistema conserva al menos un administrador activo.

Escenario de negocio (issue #1767): desactivar, desclasificar o retirar el rol
administrativo al último administrador deja la instalación sin ninguna
identidad capaz de entrar a ``/settings/*``. En Desktop, donde solo se permite
un administrador, la recuperación exige tocar la base de datos.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, Roles, RolesUser, User, database

CONTRASENA = "ultimo-admin-2026"


def _crear_app(admins: int = 1, admin_por_rol: bool = False):
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
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
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
                    id="root",
                    user="root",
                    name="Root",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="system" if admin_por_rol else "admin",
                ),
            ]
        )
        for indice in range(1, admins):
            database.session.add(
                User(
                    id=f"admin{indice}",
                    user=f"admin{indice}",
                    name=f"Admin {indice}",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                )
            )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        if admin_por_rol:
            asigna_rol_a_usuario("root", "admin")
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "root"
        session["_fresh"] = True
    return client


def _usuario(application, user_id: str = "root") -> User:
    return database.session.execute(database.select(User).filter_by(id=user_id)).scalar_one()


def test_no_desactiva_al_ultimo_administrador():
    """El toggle de estado rechaza dejar el sistema sin administradores."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/users", data={"user_id": "root", "action": "toggle"})

        assert respuesta.status_code == 302
        with application.app_context():
            assert _usuario(application).active is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_permite_desactivar_cuando_queda_otro_administrador():
    """El control positivo mantiene operativa la desactivación normal."""
    application = _crear_app(admins=2)
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/users", data={"user_id": "root", "action": "toggle"})

        assert respuesta.status_code == 302
        with application.app_context():
            assert _usuario(application).active is False
            assert _usuario(application, "admin1").active is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_no_desclasifica_al_ultimo_administrador():
    """Cambiar la clasificación a system deja de ser un administrador."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/users/root/edit",
            data={
                "usuario": "root",
                "name": "Root",
                "classification": "system",
                "active": "on",
            },
        )

        assert respuesta.status_code == 200
        with application.app_context():
            assert _usuario(application).classification == "admin"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_permite_retirar_el_rol_admin_si_queda_otro_administrador():
    """Retirar el rol es válido cuando otro administrador activo lo respalda."""
    application = _crear_app(admins=2, admin_por_rol=True)
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/users/root/roles", data={})

        assert respuesta.status_code == 302
        with application.app_context():
            admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
            asignaciones = (
                database.session.execute(database.select(RolesUser).filter_by(user_id="root", role_id=admin_role.id))
                .scalars()
                .all()
            )
            assert len(asignaciones) == 1
            assert asignaciones[0].active is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_no_retira_el_rol_admin_al_ultimo_administrador():
    """El administrador cuya autoridad viene del rol conserva la asignación."""
    application = _crear_app(admin_por_rol=True)
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/users/root/roles", data={})

        assert respuesta.status_code == 302
        with application.app_context():
            admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
            asignaciones = (
                database.session.execute(database.select(RolesUser).filter_by(user_id="root", role_id=admin_role.id))
                .scalars()
                .all()
            )
            assert len(asignaciones) == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
