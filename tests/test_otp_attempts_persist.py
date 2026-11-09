# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los intentos fallidos de OTP se persisten entre peticiones.

Escenario de negocio (issue #1762): el contador se incrementaba con flush()
pero la rama de error no hacía commit, por lo que Flask-SQLAlchemy revertía
al terminar la petición. El límite de intentos nunca se alcanzaba y el código
seguía vigente hasta expirar.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.device_verification import OTP_MAX_ATTEMPTS, generar_otp
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, OtpVerification, User, database

CONTRASENA = "otp-attempts-2026"


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
            "SECRET_KEY": "otp-attempts-secret",
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


def _registro(application) -> OtpVerification:
    return database.session.execute(database.select(OtpVerification).filter_by(user_id="admin")).scalars().one()


def test_cada_fallo_incrementa_y_persiste_el_contador():
    """Tras cinco fallos el código queda consumido y no admite reintentos."""
    application = _crear_app()
    try:
        with application.app_context():
            codigo = generar_otp("admin")
            database.session.commit()
            incorrecto = "111111" if codigo != "111111" else "222222"

        client = application.test_client()
        with client.session_transaction() as session:
            session["otp_user_id"] = "admin"

        for esperado in range(1, OTP_MAX_ATTEMPTS + 1):
            respuesta = client.post("/auth/verify-otp", data={"code": incorrecto})
            assert respuesta.status_code == 200
            with application.app_context():
                registro = _registro(application)
                assert registro.attempts == esperado
                assert registro.consumed is (esperado == OTP_MAX_ATTEMPTS)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
