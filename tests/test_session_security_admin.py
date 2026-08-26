# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Pruebas unitarias para la configuración administrativa de seguridad de sesión."""

from datetime import datetime, timedelta

import pytest
from argon2 import PasswordHasher

from cacao_accounting import create_app
from cacao_accounting.database import (
    CacaoConfig,
    Modules,
    RecognizedDevice,
    User,
    database,
)
from cacao_accounting.admin.session_security_service import (
    SESSION_SECURITY_KEY,
    is_session_security_enabled,
    listar_todos_dispositivos,
    revocar_dispositivo,
    set_session_security_enabled,
    smtp_is_configured,
)


ph = PasswordHasher()


@pytest.fixture()
def app():
    """Create application for testing."""
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Modules(module="admin", default=True, enabled=True))
        database.session.commit()
        yield app
        database.drop_all()


class TestSmtpIsConfigured:
    def test_returns_false_when_no_config(self, app):
        with app.app_context():
            assert smtp_is_configured() is False

    def test_returns_false_when_only_server(self, app):
        with app.app_context():
            database.session.add(CacaoConfig(key="smtp_server", value="smtp.example.com"))
            database.session.commit()
            assert smtp_is_configured() is False

    def test_returns_true_when_complete(self, app):
        with app.app_context():
            database.session.add(CacaoConfig(key="smtp_server", value="smtp.example.com"))
            database.session.add(CacaoConfig(key="smtp_from_email", value="test@example.com"))
            database.session.commit()
            assert smtp_is_configured() is True


class TestSessionSecurityToggle:
    def test_disabled_by_default(self, app):
        with app.app_context():
            assert is_session_security_enabled() is False

    def test_enable_and_disable(self, app):
        with app.app_context():
            set_session_security_enabled(True)
            database.session.commit()
            assert is_session_security_enabled() is True

            set_session_security_enabled(False)
            database.session.commit()
            assert is_session_security_enabled() is False

    def test_creates_config_if_missing(self, app):
        with app.app_context():
            set_session_security_enabled(True)
            registro = database.session.scalar(database.select(CacaoConfig).filter_by(key=SESSION_SECURITY_KEY))
            assert registro is not None
            assert registro.value == "true"

    def test_updates_existing_config(self, app):
        with app.app_context():
            database.session.add(CacaoConfig(key=SESSION_SECURITY_KEY, value="false"))
            database.session.commit()
            set_session_security_enabled(True)
            database.session.commit()
            registro = database.session.scalar(database.select(CacaoConfig).filter_by(key=SESSION_SECURITY_KEY))
            assert registro.value == "true"


class TestListarTodosDispositivos:
    def test_empty_list(self, app):
        with app.app_context():
            assert listar_todos_dispositivos() == []

    def test_returns_devices_with_username(self, app):
        with app.app_context():
            u = User(user="testadmin", password=ph.hash("x").encode(), active=True, e_mail="a@b.com")
            database.session.add(u)
            database.session.commit()

            device = RecognizedDevice(
                user_id=u.id,
                token="test-token-123",
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            database.session.add(device)
            database.session.commit()

            result = listar_todos_dispositivos()
            assert len(result) == 1
            assert result[0][1] == "testadmin"
            assert result[0][0].token == "test-token-123"


class TestRevocarDispositivo:
    def test_revocar_exitoso(self, app):
        with app.app_context():
            u = User(user="devuser", password=ph.hash("x").encode(), active=True, e_mail="d@e.com")
            database.session.add(u)
            database.session.commit()

            device = RecognizedDevice(
                user_id=u.id,
                token="revoke-me",
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            database.session.add(device)
            database.session.commit()
            device_id = device.id

            assert revocar_dispositivo(device_id) is True
            assert database.session.get(RecognizedDevice, device_id) is None

    def test_revocar_inexistente(self, app):
        with app.app_context():
            assert revocar_dispositivo("nonexistent") is False


class TestSessionSecurityAdminRoute:
    def test_requires_admin(self, app):
        with app.app_context():
            client = app.test_client()
            resp = client.get("/settings/session-security")
            assert resp.status_code == 302

    def test_admin_can_access(self, app):
        with app.app_context():
            u = User(user="admin", password=ph.hash("x").encode(), active=True, classification="admin", e_mail="a@b.com")
            database.session.add(u)
            database.session.commit()

            client = app.test_client()
            with client.session_transaction() as sess:
                sess["_user_id"] = u.id
                sess["_fresh"] = True

            resp = client.get("/settings/session-security")
            assert resp.status_code == 200
            assert "Seguridad" in resp.data.decode() or "seguridad" in resp.data.decode()

    def test_toggle_requires_smtp(self, app):
        with app.app_context():
            u = User(user="admin", password=ph.hash("x").encode(), active=True, classification="admin", e_mail="a@b.com")
            database.session.add(u)
            database.session.commit()

            client = app.test_client()
            with client.session_transaction() as sess:
                sess["_user_id"] = u.id
                sess["_fresh"] = True

            resp = client.post(
                "/settings/session-security",
                data={"action": "toggle", "enabled": "on"},
                follow_redirects=True,
            )
            assert resp.status_code == 200
            assert is_session_security_enabled() is False

    def test_toggle_with_smtp_enabled(self, app):
        with app.app_context():
            u = User(user="admin", password=ph.hash("x").encode(), active=True, classification="admin", e_mail="a@b.com")
            database.session.add(u)
            database.session.add(CacaoConfig(key="smtp_server", value="smtp.test.com"))
            database.session.add(CacaoConfig(key="smtp_from_email", value="test@test.com"))
            database.session.commit()

            client = app.test_client()
            with client.session_transaction() as sess:
                sess["_user_id"] = u.id
                sess["_fresh"] = True

            resp = client.post(
                "/settings/session-security",
                data={"action": "toggle", "enabled": "on"},
                follow_redirects=True,
            )
            assert resp.status_code == 200
            assert is_session_security_enabled() is True
