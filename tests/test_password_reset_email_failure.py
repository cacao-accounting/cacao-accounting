# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2023: si el correo de recuperación falla, el token previo sigue vigente."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import PasswordResetToken, User, database

EMAIL = "reset-failure@example.com"


@pytest.fixture
def escenario_reset():
    """Usuario con correo y un token previo aún utilizable."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "reset-failure-secret-key-2026",
            "AUTH_TOKEN_KEY_STABLE": True,
        }
    )
    user_id = f"reset-{uuid4().hex[:6]}"
    with app.app_context():
        database.create_all()
        database.session.add(
            User(
                id=user_id,
                user=user_id,
                name="Reset",
                password=proteger_passwd("Clave-2026!"),
                e_mail=EMAIL,
                email_identity=EMAIL,
                active=True,
            )
        )
        database.session.flush()
        database.session.add(
            PasswordResetToken(
                user_id=user_id,
                token="previo-" + uuid4().hex,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
                consumed=False,
            )
        )
        database.session.commit()
    yield app, user_id
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _tokens(app, user_id: str):
    with app.app_context():
        return database.session.execute(database.select(PasswordResetToken).filter_by(user_id=user_id)).scalars().all()


def test_fallo_de_correo_conserva_el_token_previo(escenario_reset, monkeypatch):
    """No se consume el enlace anterior ni queda un token nuevo inaccesible."""
    from cacao_accounting.auth import device_verification

    app, user_id = escenario_reset
    monkeypatch.setattr(device_verification, "enviar_token_recuperacion_email", lambda user, token: False)

    response = app.test_client().post("/auth/forgot-password", data={"email": EMAIL})

    assert response.status_code == 302
    tokens = _tokens(app, user_id)
    assert len(tokens) == 1
    assert tokens[0].consumed is False


def test_falta_clave_estable_presenta_error_danger_en_recuperacion(escenario_reset):
    """La pantalla de recuperación conserva y presenta la categoría de error."""
    app, _user_id = escenario_reset
    app.config["AUTH_TOKEN_KEY_STABLE"] = False
    client = app.test_client()

    response = client.get("/auth/reset-password/token-invalido")

    assert response.status_code == 302
    recovery_page = client.get(response.headers["Location"])
    assert recovery_page.status_code == 200
    assert b"alert-danger" in recovery_page.data
    assert b"SECRET_KEY" in recovery_page.data


def test_envio_exitoso_consume_el_previo_y_crea_uno_nuevo(escenario_reset, monkeypatch):
    """Control positivo: con entrega aceptada se renueva el token."""
    from cacao_accounting.auth import device_verification

    app, user_id = escenario_reset
    monkeypatch.setattr(device_verification, "enviar_token_recuperacion_email", lambda user, token: True)

    response = app.test_client().post("/auth/forgot-password", data={"email": EMAIL})

    assert response.status_code == 302
    tokens = _tokens(app, user_id)
    assert len(tokens) == 2
    assert sorted(token.consumed for token in tokens) == [False, True]
