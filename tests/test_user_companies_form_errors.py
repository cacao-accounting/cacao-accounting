# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El formulario de compañías explica las opciones inválidas.

Escenario de negocio (issue #2021): un POST con una compañía fuera de las
choices se rechazaba correctamente, pero la pantalla no mostraba el error y
la asignación persistida quedaba intacta sin explicación.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    User,
    UserCompanyAccess,
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
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
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
                UserCompanyAccess(user_id="objetivo", company_code="cacao"),
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_una_compania_invalida_muestra_error_y_no_muta_asignaciones():
    """El rechazo de choices deja feedback sin tocar el alcance persistido."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/users/objetivo/companies",
            data={"companies": "not-a-company"},
        )

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "no es una opción válida para este campo" in html
        assert "Not a valid choice" not in html
        with application.app_context():
            asignaciones = (
                database.session.execute(database.select(UserCompanyAccess).filter_by(user_id="objetivo")).scalars().all()
            )
            assert [asignacion.company_code for asignacion in asignaciones] == ["cacao"]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
