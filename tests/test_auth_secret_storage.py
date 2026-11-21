# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1695: los secretos de autenticación no se persisten en claro.

Reset de contraseña, OTP y dispositivos reconocidos guardan un HMAC
contextual. La validación compara el digest, el consumo es de un solo uso y
los valores originales no aparecen en la base ni en los logs.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth.device_verification import (
    establecer_cookie_dispositivo,
    generar_otp,
    generar_token_recuperacion,
    validar_otp,
    validar_token_recuperacion,
    verificar_cookie_dispositivo,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    OtpVerification,
    PasswordResetToken,
    RecognizedDevice,
    User,
    database,
)


@pytest.fixture
def auth_secret_scenario():
    """Create one active user for the secret issuance flows."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(
                    id=f"user-{suffix}",
                    user=f"user-{suffix}",
                    name="Usuario",
                    password=b"unused",
                    active=True,
                ),
            ]
        )
        database.session.commit()
        ids = {"user": f"user-{suffix}"}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_reset_token_is_stored_as_a_non_reversible_digest(auth_secret_scenario, caplog):
    """The reset link works once and the raw token never reaches storage or logs."""
    app, ids = auth_secret_scenario
    caplog.set_level(logging.DEBUG)

    with app.app_context():
        token = generar_token_recuperacion(ids["user"])
        registro = database.session.execute(database.select(PasswordResetToken).filter_by(user_id=ids["user"])).scalar_one()

        assert registro.token != token
        assert token not in registro.token
        assert registro.token.startswith("$")
        assert len(registro.token) == 64

        assert validar_token_recuperacion(token) is not None
        assert validar_token_recuperacion(token) is None

    assert token not in caplog.text


def test_otp_is_stored_as_a_non_reversible_digest(auth_secret_scenario, caplog):
    """The six-digit code validates once and is not persisted verbatim."""
    app, ids = auth_secret_scenario
    caplog.set_level(logging.DEBUG)

    with app.app_context():
        code = generar_otp(ids["user"])
        registro = database.session.execute(database.select(OtpVerification).filter_by(user_id=ids["user"])).scalar_one()

        assert registro.code != code
        assert code not in registro.code
        assert registro.code.startswith("$")
        assert len(registro.code) == 6

        assert validar_otp(ids["user"], code) is True
        assert validar_otp(ids["user"], code) is False

    assert code not in caplog.text


def test_wrong_otp_is_rejected_and_uses_an_attempt(auth_secret_scenario):
    """A wrong code does not authorize and increments the attempt counter."""
    app, ids = auth_secret_scenario

    with app.app_context():
        code = generar_otp(ids["user"])

        assert validar_otp(ids["user"], "000000" if code != "000000" else "111111") is False
        registro = database.session.execute(database.select(OtpVerification).filter_by(user_id=ids["user"])).scalar_one()
        assert registro.attempts == 1
        assert validar_otp(ids["user"], code) is True


def test_device_cookie_token_is_stored_as_a_non_reversible_digest(auth_secret_scenario, caplog):
    """The browser device token is verified by digest and never stored raw."""
    app, ids = auth_secret_scenario
    caplog.set_level(logging.DEBUG)

    with app.app_context():
        token = establecer_cookie_dispositivo(ids["user"], user_agent="pytest", ip_address="127.0.0.1")
        registro = database.session.execute(database.select(RecognizedDevice).filter_by(user_id=ids["user"])).scalar_one()

        assert registro.token != token
        assert token not in registro.token
        assert registro.token.startswith("$")
        assert verificar_cookie_dispositivo(ids["user"], token) is True
        assert verificar_cookie_dispositivo(ids["user"], str(uuid4())) is False

    assert token not in caplog.text


def test_issuance_requires_a_stable_secret_key(auth_secret_scenario):
    """Without a stable key the flow fails closed instead of storing plaintext."""
    app, ids = auth_secret_scenario

    with app.app_context():
        app.config["AUTH_TOKEN_KEY_STABLE"] = False
        try:
            with pytest.raises(RuntimeError):
                generar_otp(ids["user"])
        finally:
            app.config["AUTH_TOKEN_KEY_STABLE"] = True
