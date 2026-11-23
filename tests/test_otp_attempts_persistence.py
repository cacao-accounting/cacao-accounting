# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1762: los intentos fallidos de OTP se persisten entre peticiones.

Cada POST incorrecto incrementa el contador en la base y, al alcanzar el
límite, el código queda consumido sin permitir más intentos.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth.device_verification import OTP_MAX_ATTEMPTS, generar_otp
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, OtpVerification, User, database

CONTRASENA = "otp-2026"


@pytest.fixture
def otp_http_scenario():
    """App con clave estable y rate limit desactivado para el flujo OTP."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "otp-http-regression-secret-key",
            "AUTH_TOKEN_KEY_STABLE": True,
        }
    )
    application.config["RATELIMIT_ENABLED"] = False
    suffix = uuid4().hex[:6]
    user_id = f"otp-http-{suffix}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(
                    id=user_id,
                    user=f"otp_{suffix}",
                    name="Usuario OTP",
                    password=b"unused",
                    active=True,
                    e_mail=f"otp-{suffix}@example.com",
                ),
            ]
        )
        database.session.commit()
        codigo = generar_otp(user_id)
        database.session.commit()
    yield application, user_id, codigo
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _cliente_con_otp(application, user_id: str):  # noqa: ANN001 - fixture helper
    """Cliente con la sesión de verificación preparada."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["otp_user_id"] = user_id
        session["otp_ip"] = "127.0.0.1"
        session["otp_user_agent"] = "pytest"
    return client


def _estado_otp(application, user_id: str) -> OtpVerification:  # noqa: ANN001 - fixture helper
    """Lee el OTP vigente desde una sesión limpia."""
    with application.app_context():
        database.session.remove()
        return database.session.execute(
            database.select(OtpVerification).filter_by(user_id=user_id, purpose="device_verification")
        ).scalar_one()


def _codigo_incorrecto(codigo: str) -> str:
    """Devuelve un código de seis dígitos distinto al emitido."""
    return "000000" if codigo != "000000" else "111111"


def test_intentos_fallidos_se_persisten_entre_peticiones(otp_http_scenario):
    """Cada POST incorrecto deja el contador incrementado en la base."""
    application, user_id, codigo = otp_http_scenario
    client = _cliente_con_otp(application, user_id)

    for esperado in range(1, OTP_MAX_ATTEMPTS + 1):
        response = client.post("/auth/verify-otp", data={"code": _codigo_incorrecto(codigo)})
        assert response.status_code == 200
        assert _estado_otp(application, user_id).attempts == esperado
        assert b"alert-danger" in response.data
        assert "C\u00f3digo de verificaci\u00f3n incorrecto o expirado.".encode() in response.data


def test_alcanzar_el_limite_consume_el_codigo(otp_http_scenario):
    """Al llegar al máximo el OTP queda consumido y no admite más intentos."""
    application, user_id, codigo = otp_http_scenario
    client = _cliente_con_otp(application, user_id)

    for _ in range(OTP_MAX_ATTEMPTS):
        client.post("/auth/verify-otp", data={"code": _codigo_incorrecto(codigo)})

    estado = _estado_otp(application, user_id)
    assert estado.attempts == OTP_MAX_ATTEMPTS
    assert estado.consumed is True

    response = client.post("/auth/verify-otp", data={"code": _codigo_incorrecto(codigo)})
    assert response.status_code == 200
    assert _estado_otp(application, user_id).attempts == OTP_MAX_ATTEMPTS


def test_post_exitoso_conserva_destino_y_cookie(otp_http_scenario):
    """#1917: el POST exitoso responde con un Location válido, cookie y sesión."""
    application, user_id, codigo = otp_http_scenario
    client = _cliente_con_otp(application, user_id)

    response = client.post("/auth/verify-otp", data={"code": codigo})

    assert response.status_code in {301, 302, 303}
    location = response.headers.get("Location", "")
    assert location.startswith("/")
    assert "Response" not in location
    assert "device-id" in response.headers.get("Set-Cookie", "")
    with client.session_transaction() as session:
        assert session.get("_user_id") == user_id
        assert "otp_user_id" not in session
