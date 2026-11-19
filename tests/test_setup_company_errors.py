# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los errores de negocio del asistente no terminan en HTTP 500.

Escenario de negocio (issue #2101): finalize_setup propaga ValueError por
código de compañía duplicado, catálogo ausente o límite de compañías. El paso
empresa no lo capturaba y el usuario recibía 500 en lugar de un mensaje
corregible con el formulario intacto.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, User, database

CONTRASENA = "setup-company-2026"


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
            "SECRET_KEY": "setup-company-secret",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="CAFE",
                    name="Cafe",
                    company_name="Cafe SA",
                    tax_id="J-CAFE",
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
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
        session["setup_step"] = 3
    return client


def _formulario(codigo: str) -> dict[str, str]:
    return {
        "id": codigo,
        "razon_social": "Compañía de Prueba",
        "nombre_comercial": "Prueba",
        "id_fiscal": "J-PRUEBA",
        "tipo_entidad": "Sociedad Anonima",
        "inicio_anio_fiscal": "2026-01-01",
        "fin_anio_fiscal": "2026-12-31",
        "catalogo": "en_cero",
        "step": "3",
        "action": "next",
    }


def test_codigo_duplicado_no_produce_500():
    """El error de compañía existente se muestra en el formulario."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/setup/", data=_formulario("CAFE"))

        assert respuesta.status_code == 200
        assert "ya existe" in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(Entity)).scalars().all() != []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_alta_valida_completa_el_asistente():
    """El control positivo crea la compañía y redirige a la aplicación."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/setup/", data=_formulario("NEWCO"))

        assert respuesta.status_code == 302
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="NEWCO")).scalar_one()
            assert entidad.company_name == "Compañía de Prueba"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
