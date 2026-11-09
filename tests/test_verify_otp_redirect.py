# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La verificación OTP conserva el destino real del login.

Escenario de negocio (issue #1917): la ruta envolvía en ``redirect()`` una
respuesta que ya era una redirección. Werkzeug serializaba el objeto como
texto en ``Location``, el OTP se consumía y el usuario quedaba autenticado
apuntando a una URL inválida.
"""

from __future__ import annotations

from flask import url_for
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.device_verification import generar_otp
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, OtpVerification, User, database

CONTRASENA = "verify-otp-2026"


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
            "SECRET_KEY": "verify-otp-secret",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
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
                    e_mail="admin@example.com",
                ),
            ]
        )
        database.session.commit()
    return application


def test_otp_exitoso_redirige_al_destino_real():
    """El Location apunta a la aplicación, no a la representación de un Response."""
    application = _crear_app()
    try:
        with application.app_context():
            codigo = generar_otp("admin")
            database.session.commit()
            with application.test_request_context():
                destino = url_for("cacao_app.pagina_inicio")

        client = application.test_client()
        with client.session_transaction() as session:
            session["otp_user_id"] = "admin"

        respuesta = client.post("/auth/verify-otp", data={"code": codigo})

        assert respuesta.status_code == 302
        assert respuesta.headers["Location"] == destino
        assert "%3CResponse" not in respuesta.headers["Location"]
        with client.session_transaction() as session:
            assert session.get("_user_id") == "admin"
            assert session.get("otp_user_id") is None
        assert "device-id=" in respuesta.headers.get("Set-Cookie", "")
        with application.app_context():
            otp = database.session.execute(database.select(OtpVerification).filter_by(user_id="admin")).scalars().one()
            assert otp.consumed is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
