# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El dashboard de caja alinea el enlace de pronósticos con el permiso real.

Escenario de negocio (issue #2025): el gate usaba ``cash.access`` y las rutas
de pronóstico exigen ``cash.consultar``; un usuario con solo acceso veía un
enlace navegable que respondía 403.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


def _crear_app(puede_consultar: bool):
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
                Modules(module="cash", default=False, enabled=True),
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
                    id="operador",
                    user="operador",
                    name="Operador",
                    password=b"x",
                    active=True,
                    classification="system",
                    company="cacao",
                ),
                UserCompanyAccess(user_id="operador", company_code="cacao"),
            ]
        )
        database.session.flush()
        modulo = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        rol = Roles(name=f"cash_{puede_consultar}", note="Prueba")
        database.session.add(rol)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=rol.id,
                module_id=modulo.id,
                access=True,
                view=puede_consultar,
            )
        )
        database.session.add(RolesUser(user_id="operador", role_id=rol.id, active=True))
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "operador"
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(("puede_consultar", "visible"), [(False, False), (True, True)])
def test_el_enlace_de_pronosticos_sigue_al_permiso_consultar(puede_consultar, visible):
    """El enlace aparece solo si el endpoint de consulta lo permitiría."""
    application = _crear_app(puede_consultar)
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/cash")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert ("/cash-forecast/list" in html) is visible
        assert "Proyección de Flujo de Caja" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
