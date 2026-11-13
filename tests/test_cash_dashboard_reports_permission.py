# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El dashboard de caja muestra reportes según cash.reportes.

Escenario de negocio (issue #2024): la sección de reportes se gateaba por
``cash.access`` aunque los endpoints exigen ``cash.reportes``. Un rol solo
reportes podía abrir el reporte directamente pero no lo veía en el menú.
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


def _crear_app(puede_reportar: bool):
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
                    id="auditor",
                    user="auditor",
                    name="Auditor",
                    password=b"x",
                    active=True,
                    classification="system",
                    company="cacao",
                ),
                UserCompanyAccess(user_id="auditor", company_code="cacao"),
            ]
        )
        database.session.flush()
        modulo = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        rol = Roles(name=f"reports_{puede_reportar}", note="Prueba")
        database.session.add(rol)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=rol.id,
                module_id=modulo.id,
                access=False,
                view=False,
                report=puede_reportar,
            )
        )
        database.session.add(RolesUser(user_id="auditor", role_id=rol.id, active=True))
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "auditor"
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(("puede_reportar", "visible"), [(False, False), (True, True)])
def test_la_seccion_de_reportes_sigue_el_permiso_reportes(puede_reportar, visible):
    """El enlace aparece solo si cash.reportes lo permite, aunque no haya access."""
    application = _crear_app(puede_reportar)
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/cash")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert ("Resumen de Saldos Bancarios" in html) is visible
        assert ("Detalle de Movimiento Bancario" in html) is visible
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
