# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El asistente persiste el país elegido en la compañía creada.

Escenario de negocio (issue #2100): el paso regional guarda SETUP_COUNTRY,
pero el payload de la empresa omitía ``pais`` y ``Entity.country`` quedaba
NULL pese a que el alta administrativa sí lo persiste.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, User, database


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
            "SECRET_KEY": "setup-country-secret",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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


def test_el_asistente_persiste_el_pais():
    """La compañía creada conserva el país configurado en el paso regional."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True
            session["setup_step"] = 3

        respuesta = client.post(
            "/setup/",
            data={
                "id": "NICO",
                "razon_social": "Nicaragua Company",
                "nombre_comercial": "Nica Co",
                "id_fiscal": "J-NICO",
                "tipo_entidad": "Sociedad Anonima",
                "inicio_anio_fiscal": "2026-01-01",
                "fin_anio_fiscal": "2026-12-31",
                "catalogo": "en_cero",
                "step": "3",
                "action": "next",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="NICO")).scalar_one()
            assert entidad.country == "NI"
            assert entidad.currency == "NIO"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
