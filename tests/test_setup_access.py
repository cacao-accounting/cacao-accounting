# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Gestión de acceso al asistente de configuración inicial.

Escenario de negocio (issue #1021): el asistente ``/setup/`` crea la
primer operación de la empresa (idioma/regional globales + compañía con
libro, catálogo y períodos). Es un privilegio de administración del
sistema durante la primera instalación, no una página de la cual
cualquier empleado autenticado pueda disponer; al finalizar queda
sellado y la creación de compañías pasa al módulo administrativo.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, User, database

CONTRASENA = "setup-cacao-2026"


@pytest.fixture
def asistente_sin_configurar():
    """Aplicación en modo cloud sin asistente ejecutado."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import Currency

        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    classification="admin",
                    active=True,
                ),
                User(
                    id="auxiliar",
                    user="auxiliar",
                    name="Auxiliar de Ventas",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.commit()
    yield application, application.test_client()
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar_sesion(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_el_asistente_rechaza_usuarios_no_administradores(asistente_sin_configurar):
    """Un usuario interno sin rol administrativo no dispone del asistente."""
    application, client = asistente_sin_configurar
    _iniciar_sesion(client, "auxiliar")
    response = client.get("/setup/")
    assert response.status_code == 403
    with application.app_context():
        assert list(database.session.execute(database.select(Entity)).scalars().all()) == []


def test_un_usuario_no_administrador_no_puede_avanzar_pasos(asistente_sin_configurar):
    """Los POST del asistente tampoco están al alcance de un empleado común."""
    application, client = asistente_sin_configurar
    _iniciar_sesion(client, "auxiliar")
    response = client.post(
        "/setup/",
        data={"idioma": "es", "action": "apply_language"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    with application.app_context():
        from cacao_accounting.database import CacaoConfig
        from cacao_accounting.setup.service import SETUP_LANGUAGE

        registro = database.session.execute(database.select(CacaoConfig).filter_by(key=SETUP_LANGUAGE)).scalar_one_or_none()
        assert registro is None


def test_el_administrador_completa_el_asistente_y_queda_sellado(asistente_sin_configurar):
    """
    El administrador recorre los tres pasos, crea la primera operación y el
    asistente queda sellado también para él.
    """
    application, client = asistente_sin_configurar
    _iniciar_sesion(client, "admin")
    primera = client.get("/setup/")
    assert primera.status_code == 200

    client.post("/setup/", data={"idioma": "es"}, follow_redirects=False)
    regional = client.post(
        "/setup/",
        data={"pais": "NI", "moneda": "NIO", "zona_horaria": "America/Managua"},
        follow_redirects=False,
    )
    assert regional.status_code == 302
    final = client.post(
        "/setup/",
        data={
            "id": "cafe",
            "razon_social": "Cafe SA",
            "nombre_comercial": "Cafe",
            "id_fiscal": "J0002",
            "tipo_entidad": "Persona Natural",
            "catalogo": "en_cero",
        },
        follow_redirects=False,
    )
    assert final.status_code == 302
    with application.app_context():
        from cacao_accounting.setup.service import SETUP_COMPLETED, SETUP_ENTITY
        from cacao_accounting.setup.repository import get_setup_value

        assert get_setup_value(SETUP_COMPLETED) == "True"
        assert get_setup_value(SETUP_ENTITY) == "cafe"
        nueva = database.session.execute(database.select(Entity).filter_by(code="CAFE")).scalar_one()
        assert nueva.company_name == "Cafe SA"

    # El asistente queda sellado: redirige a la aplicación principal.
    sellado_admin = client.get("/setup/", follow_redirects=True)
    assert sellado_admin.request.path.rstrip("/") != "/setup"
    _iniciar_sesion(client, "auxiliar")
    sellado_auxiliar = client.get("/setup/", follow_redirects=True)
    assert sellado_auxiliar.request.path.rstrip("/") != "/setup"
