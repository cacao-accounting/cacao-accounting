# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El listado de bancos comunica el estado vacío.

Escenario de negocio (issue #2026): una búsqueda sin resultados dejaba la
tabla vacía y anunciaba «Página 1 de 0», sin explicar el estado.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, Entity, Modules, User, database


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
                Bank(name="Banco Visible", swift_code="TESTNI2N", is_active=True),
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


def test_la_busqueda_sin_resultados_muestra_estado_vacio():
    """El estado vacío es accesible y no anuncia una página inexistente."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/bank/list?search=NO-SUCH")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "No se encontraron bancos para los filtros seleccionados." in html
        assert "Página 1 de 0" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_busqueda_con_resultados_conserva_la_fila():
    """El control positivo mantiene el listado normal."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/cash_management/bank/list?search=Banco Visible").get_data(as_text=True)

        assert "Banco Visible" in html
        assert "No se encontraron bancos para los filtros seleccionados." not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
