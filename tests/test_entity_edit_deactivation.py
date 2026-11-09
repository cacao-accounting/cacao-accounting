# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Desactivación de la última entidad desde el formulario de edición.

Escenario de negocio (issue #1771): en modo Desktop la instalación no puede
quedar sin ninguna entidad habilitada. La ruta dedicada de inactivación ya
aplica esa regla, pero el formulario de edición la omitía y permitía apagar la
única compañía enviando el POST sin la casilla ``habilitado``.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Modules, User, database

CONTRASENA = "entidad-edit-2026"


def _crear_app(modo_escritorio: bool, entidades: int):
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
            "MODO_ESCRITORIO": modo_escritorio,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
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
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        if entidades > 1:
            database.session.add(
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                )
            )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("admin", "admin")
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _post_edicion(client, **extra):
    datos = {
        "id_fiscal": "J0001",
        "nombre_comercial": "Cacao",
        "razon_social": "Cacao SA",
        "correo_electronico": "contacto@example.test",
    }
    datos.update(extra)
    return client.post("/accounting/entity/edit/cacao", data=datos)


def test_escritorio_no_deactiva_la_unica_entidad_desde_edicion():
    """Sin la casilla habilitado, la única entidad activa conserva su estado."""
    application = _crear_app(modo_escritorio=True, entidades=1)
    try:
        client = _cliente(application)
        response = _post_edicion(client)

        assert response.status_code == 302
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
            assert entidad.enabled is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_escritorio_permite_deactivar_si_existe_otra_activa():
    """El control positivo conserva la operación normal cuando hay alternativa."""
    application = _crear_app(modo_escritorio=True, entidades=2)
    try:
        client = _cliente(application)
        response = _post_edicion(client)

        assert response.status_code == 302
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
            assert entidad.enabled is False
            beta = database.session.execute(database.select(Entity).filter_by(code="beta")).scalar_one()
            assert beta.enabled is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_escritorio_conserva_la_entidad_habilitada_si_el_post_la_marca():
    """Marcar habilitado no dispara la guardia de desactivación."""
    application = _crear_app(modo_escritorio=True, entidades=1)
    try:
        client = _cliente(application)
        response = _post_edicion(client, habilitado="on")

        assert response.status_code == 302
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
            assert entidad.enabled is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
