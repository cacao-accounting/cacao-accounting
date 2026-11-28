# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2285: emisión, uso, rotación y revocación de la credencial API.

El login del navegador emite un JWT y redirige sin exponerlo, por lo que un
integrador no tenía forma de obtener la credencial. Estas pruebas cubren la
acción explícita de Cloud: el secreto se muestra una sola vez, la huella
persistida sigue siendo la autoridad, la rotación invalida la credencial
anterior y la revocación no depende de la caché ni cierra la sesión web.
"""

from __future__ import annotations

from hashlib import sha256
import re

import pytest
from flask import Flask
from flask.testing import FlaskClient

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, UserCompanyAccess, database

PASSWORD = "api-credential-password"
CREDENTIAL_PATH = "/auth/api-credential"
PROFILE_PATH = "/auth/profile"
API_TEST_PATH = "/api/test"

LOCAL_COMPANY = "cacao"
FOREIGN_COMPANY = "otra"

JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


@pytest.fixture
def credential_app() -> Flask:
    """Crea una app Cloud aislada con usuarios de distinto alcance."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "api-credential-test-secret-key-with-32-bytes",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code=LOCAL_COMPANY,
                    name="Cacao",
                    company_name="Cacao Accounting SA",
                    tax_id="J-API-CACAO",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code=FOREIGN_COMPANY,
                    name="Otra",
                    company_name="Compañía Ajena SA",
                    tax_id="J-API-OTRA",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.commit()
        database.session.add_all(
            [
                User(
                    id="api_owner",
                    user="api_owner",
                    name="API Owner",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=LOCAL_COMPANY,
                ),
                User(
                    id="api_foreign",
                    user="api_foreign",
                    name="API Foreign",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=FOREIGN_COMPANY,
                ),
                User(
                    id="api_no_grants",
                    user="api_no_grants",
                    name="API Without Grants",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    company=LOCAL_COMPANY,
                ),
                User(
                    id="api_inactive",
                    user="api_inactive",
                    name="API Inactive",
                    password=proteger_passwd(PASSWORD),
                    active=False,
                    company=LOCAL_COMPANY,
                ),
                UserCompanyAccess(user_id="api_owner", company_code=LOCAL_COMPANY),
                UserCompanyAccess(user_id="api_foreign", company_code=FOREIGN_COMPANY),
                UserCompanyAccess(user_id="api_inactive", company_code=LOCAL_COMPANY),
            ]
        )
        database.session.commit()

    yield app

    with app.app_context():
        database.session.remove()


def _login(app: Flask, user_id: str) -> FlaskClient:
    """Devuelve un cliente con sesión web iniciada como el usuario indicado."""
    client = app.test_client()
    with app.app_context():
        user = database.session.get(User, user_id)
        assert user is not None
        auth_version = user.auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def _extract_credential(response) -> str:
    """Extrae el JWT mostrado por la respuesta HTML de emisión."""
    match = JWT_PATTERN.search(response.get_data(as_text=True))
    assert match is not None, "la respuesta no mostró la credencial"
    return match.group(0)


def _is_authorized(app: Flask, token: str) -> bool:
    """Comprueba el JWT con un cliente HTTP independiente del navegador."""
    with app.test_client() as api_client:
        response = api_client.get(API_TEST_PATH, headers={"Authorization": f"Bearer {token}"})
    return response.status_code == 200


def _credential_hash(app: Flask, user_id: str) -> str | None:
    """Devuelve la huella persistida del usuario."""
    with app.app_context():
        user = database.session.get(User, user_id)
        assert user is not None
        return user.api_token_hash


def test_emision_muestra_el_secreto_una_vez_y_permite_usarlo(credential_app):
    """La emisión entrega el JWT una sola vez y autentica la API sin Redis."""
    app = credential_app
    client = _login(app, "api_owner")

    initial_page = client.get(CREDENTIAL_PATH)
    assert initial_page.status_code == 200
    assert JWT_PATTERN.search(initial_page.get_data(as_text=True)) is None

    response = client.post(CREDENTIAL_PATH, data={"accion": "emitir"})
    assert response.status_code == 200
    token = _extract_credential(response)
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert "Location" not in response.headers
    assert token not in "".join(f"{key}:{value}" for key, value in response.headers.items())

    assert _is_authorized(app, token)
    assert _credential_hash(app, "api_owner") == sha256(token.encode("utf-8")).hexdigest()

    # Un GET posterior no repite el secreto: solo la emisión lo muestra.
    follow_up = client.get(CREDENTIAL_PATH)
    assert follow_up.status_code == 200
    assert token not in follow_up.get_data(as_text=True)


def test_rotacion_invalida_la_credencial_anterior(credential_app):
    """Rotar reemplaza la huella y deja de aceptar el JWT previo."""
    app = credential_app
    client = _login(app, "api_owner")

    first = _extract_credential(client.post(CREDENTIAL_PATH, data={"accion": "emitir"}))
    second = _extract_credential(client.post(CREDENTIAL_PATH, data={"accion": "rotar"}))

    assert first != second
    assert not _is_authorized(app, first)
    assert _is_authorized(app, second)
    assert _credential_hash(app, "api_owner") == sha256(second.encode("utf-8")).hexdigest()


def test_revocacion_invalida_la_credencial_y_conserva_la_sesion(credential_app):
    """Revocar elimina la huella sin cerrar la sesión del navegador."""
    app = credential_app
    client = _login(app, "api_owner")
    token = _extract_credential(client.post(CREDENTIAL_PATH, data={"accion": "emitir"}))
    with app.app_context():
        user = database.session.get(User, "api_owner")
        assert user is not None
        version_before = user.auth_version

    response = client.post(CREDENTIAL_PATH, data={"accion": "revocar"})
    assert response.status_code == 200
    assert token not in response.get_data(as_text=True)
    assert not _is_authorized(app, token)
    assert _credential_hash(app, "api_owner") is None

    with app.app_context():
        user = database.session.get(User, "api_owner")
        assert user is not None
        assert user.auth_version == version_before

    # La sesión web sigue vigente: revocar la integración no expulsa al usuario.
    assert client.get(CREDENTIAL_PATH).status_code == 200


def test_usuario_inactivo_no_emite_ni_usa_credencial(credential_app):
    """Desactivar al usuario invalida la credencial y bloquea nuevas emisiones."""
    app = credential_app
    client = _login(app, "api_owner")
    token = _extract_credential(client.post(CREDENTIAL_PATH, data={"accion": "emitir"}))
    assert _is_authorized(app, token)

    with app.app_context():
        user = database.session.get(User, "api_owner")
        assert user is not None
        user.active = False
        database.session.commit()

    assert not _is_authorized(app, token)
    blocked = client.post(CREDENTIAL_PATH, data={"accion": "emitir"})
    assert blocked.status_code == 302
    assert _credential_hash(app, "api_owner") == sha256(token.encode("utf-8")).hexdigest()


def test_alcance_de_compania_se_hereda_sin_ampliarse(credential_app):
    """La credencial conserva las compañías autorizadas y no revela otras."""
    app = credential_app

    local_page = _login(app, "api_owner").get(CREDENTIAL_PATH)
    assert local_page.status_code == 200
    local_html = local_page.get_data(as_text=True)
    assert f">{LOCAL_COMPANY}<" in local_html
    assert f">{FOREIGN_COMPANY}<" not in local_html

    foreign_page = _login(app, "api_foreign").get(CREDENTIAL_PATH)
    assert foreign_page.status_code == 200
    foreign_html = foreign_page.get_data(as_text=True)
    assert f">{FOREIGN_COMPANY}<" in foreign_html
    assert f">{LOCAL_COMPANY}<" not in foreign_html

    # Un usuario sin concesiones explícitas no puede obtener credencial.
    assert _login(app, "api_no_grants").get(CREDENTIAL_PATH).status_code == 403


def test_desktop_no_expone_la_interfaz_cloud(credential_app):
    """En modo escritorio la acción no existe y el perfil no la enlaza."""
    app = credential_app
    previous_mode = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    try:
        client = _login(app, "api_owner")
        assert client.get(CREDENTIAL_PATH).status_code == 404
        profile = client.get(PROFILE_PATH)
        assert profile.status_code == 200
        assert CREDENTIAL_PATH not in profile.get_data(as_text=True)
    finally:
        app.config["MODO_ESCRITORIO"] = previous_mode


def test_accion_desconocida_no_emite_credencial(credential_app):
    """Una acción fuera del contrato se rechaza sin emitir ni revocar nada."""
    app = credential_app
    client = _login(app, "api_owner")

    response = client.post(CREDENTIAL_PATH, data={"accion": "otra"})

    assert response.status_code == 400
    assert _credential_hash(app, "api_owner") is None
