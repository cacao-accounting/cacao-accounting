# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""A recovery reset invalidates every browser session and API token."""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.device_verification import generar_token_recuperacion
from cacao_accounting.cache import cache
from cacao_accounting.config import configuracion
from cacao_accounting.database import User, database

PASSWORD = "Current-Password-2026!"
NEW_PASSWORD = "Recovered-Password-2026!"


def _crear_app():
    """Create an isolated Cloud app for browser, API, and reset requests."""
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
            "SECRET_KEY": "password-reset-revocation-test-key",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(
            User(
                id="reset-user",
                user="reset-user",
                name="Reset User",
                password=proteger_passwd(PASSWORD),
                active=True,
                classification="system",
                e_mail="reset@example.com",
            )
        )
        database.session.commit()
    return application


def test_password_reset_revoca_sesiones_y_jwt_sin_afectar_nuevo_login(monkeypatch):
    """Only a fresh password login works after the recovery transaction commits."""

    def fail_cache_delete(_key: str) -> None:
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(cache, "delete", fail_cache_delete)
    application = _crear_app()
    try:
        browser_client = application.test_client()
        login_response = browser_client.post(
            "/login",
            data={"usuario": "reset-user", "acceso": PASSWORD},
        )
        assert login_response.status_code == 302
        assert browser_client.get("/auth/profile").status_code == 200

        with application.app_context():
            user = database.session.get(User, "reset-user")
            assert user is not None
            old_token = user.token
            assert old_token
            reset_token = generar_token_recuperacion(user.id)
            database.session.commit()
            assert user.auth_version == 0

        api_client = application.test_client()
        auth_header = {"Authorization": f"Bearer {old_token}"}
        assert api_client.get("/api/test", headers=auth_header).status_code == 200

        reset_client = application.test_client()
        reset_url = f"/auth/reset-password/{reset_token}"
        assert reset_client.get(reset_url).status_code == 200
        with application.app_context():
            user = database.session.get(User, "reset-user")
            assert user is not None and user.auth_version == 0

        reset_response = reset_client.post(
            reset_url,
            data={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert reset_response.status_code == 302
        with application.app_context():
            user = database.session.get(User, "reset-user")
            assert user is not None
            assert user.auth_version == 1
            assert user.token == old_token

        assert browser_client.get("/auth/profile").status_code == 302
        assert api_client.get("/api/test", headers=auth_header).status_code == 401

        new_login = reset_client.post(
            "/login",
            data={"usuario": "reset-user", "acceso": NEW_PASSWORD},
        )
        assert new_login.status_code == 302
        with reset_client.session_transaction() as session:
            assert session.get("_user_id") == "reset-user"
            assert session.get("_auth_version") == 1

        with application.app_context():
            user = database.session.get(User, "reset-user")
            assert user is not None
            assert user.auth_version == 1
            new_token = user.token
            assert new_token and new_token != old_token

        new_api_client = application.test_client()
        assert (
            new_api_client.get(
                "/api/test",
                headers={"Authorization": f"Bearer {new_token}"},
            ).status_code
            == 200
        )
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
