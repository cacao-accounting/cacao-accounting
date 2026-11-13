# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El alta de banco valida la longitud del código SWIFT.

Escenario de negocio (issue #2028): ``Bank.swift_code`` es String(20); SQLite
aceptaba 21 caracteres y PostgreSQL fallaba con un 500. El formulario no
imponía límite ni mostraba error.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, Currency, Entity, Modules, User, database


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
            "MODO_ESCRITORIO": True,
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
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


def test_rechaza_swift_de_mas_de_20_caracteres():
    """El formulario muestra el error y no persiste el banco."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/bank/new",
            data={"name": "Banco Largo", "swift_code": "X" * 21},
        )

        assert respuesta.status_code == 200
        assert "El código SWIFT no puede superar los 20 caracteres." in respuesta.get_data(as_text=True)
        assert 'maxlength="20"' in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(Bank)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_acepta_swift_de_20_caracteres():
    """El límite exacto sigue siendo válido."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/bank/new",
            data={"name": "Banco Límite", "swift_code": "Y" * 20},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            banco = database.session.execute(database.select(Bank)).scalar_one()
            assert banco.swift_code == "Y" * 20
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
