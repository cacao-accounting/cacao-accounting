# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Pruebas unitarias para recuperación de contraseña."""

from datetime import datetime, timedelta

import pytest
from argon2 import PasswordHasher

from cacao_accounting import create_app
from cacao_accounting.database import (
    PasswordResetToken,
    User,
    database,
)
from cacao_accounting.auth.device_verification import (
    PASSWORD_RESET_TTL_HOURS,
    generar_token_recuperacion,
    validar_token_recuperacion,
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
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.drop_all()


@pytest.fixture()
def user(app):
    """Create a test user in the database."""
    with app.app_context():
        u = User(
            user="testuser",
            name="Test",
            e_mail="test@example.com",
            password=ph.hash("Secret123!").encode(),
            classification="system",
            active=True,
        )
        database.session.add(u)
        database.session.commit()
        return u.id


class TestGenerarTokenRecuperacion:
    def test_generates_token_string(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            assert isinstance(token, str)
            assert len(token) > 20

    def test_stores_in_database(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            registro = database.session.scalar(database.select(PasswordResetToken).filter_by(token=token))
            assert registro is not None
            assert registro.user_id == user
            assert registro.consumed is False

    def test_previous_tokens_consumed(self, app, user):
        with app.app_context():
            token1 = generar_token_recuperacion(user)
            token2 = generar_token_recuperacion(user)
            assert token1 != token2
            previos = database.session.scalars(database.select(PasswordResetToken).filter_by(user_id=user)).all()
            consumidos = [t for t in previos if t.consumed]
            assert len(consumidos) == 1

    def test_expiry_set_correctly(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            registro = database.session.scalar(database.select(PasswordResetToken).filter_by(token=token))
            now = datetime.utcnow()
            expected = now + timedelta(hours=PASSWORD_RESET_TTL_HOURS)
            diff = abs((registro.expires_at - expected).total_seconds())
            assert diff < 60


class TestValidarTokenRecuperacion:
    def test_valid_token_returns_user(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            result = validar_token_recuperacion(token)
            assert result is not None
            assert result.id == user

    def test_token_consumed_after_use(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            validar_token_recuperacion(token)
            registro = database.session.scalar(database.select(PasswordResetToken).filter_by(token=token))
            assert registro.consumed is True

    def test_invalid_token_returns_none(self, app):
        with app.app_context():
            assert validar_token_recuperacion("invalid-token-abc") is None

    def test_expired_token_returns_none(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            registro = database.session.scalar(database.select(PasswordResetToken).filter_by(token=token))
            registro.expires_at = datetime.utcnow() - timedelta(hours=1)
            database.session.flush()
            assert validar_token_recuperacion(token) is None

    def test_used_token_returns_none(self, app, user):
        with app.app_context():
            token = generar_token_recuperacion(user)
            validar_token_recuperacion(token)
            result = validar_token_recuperacion(token)
            assert result is None

    def test_inactive_user_returns_none(self, app):
        with app.app_context():
            u = User(
                user="inactive",
                password=ph.hash("x").encode(),
                active=False,
                e_mail="inact@example.com",
            )
            database.session.add(u)
            database.session.commit()
            token = generar_token_recuperacion(u.id)
            assert validar_token_recuperacion(token) is None


class TestPasswordResetFlow:
    def test_full_reset_flow(self, app, user):
        """Test the full password reset flow: generate token, validate, new password would be set."""
        with app.app_context():
            token = generar_token_recuperacion(user)
            result = validar_token_recuperacion(token)
            assert result is not None

            result.password = ph.hash("NewSecure123!").encode()
            database.session.commit()

            refreshed = database.session.get(User, user)
            assert ph.verify(refreshed.password.decode(), "NewSecure123!")

    def test_different_users_get_different_tokens(self, app):
        with app.app_context():
            u1 = User(user="user1", password=ph.hash("x").encode(), active=True, e_mail="u1@ex.com")
            u2 = User(user="user2", password=ph.hash("x").encode(), active=True, e_mail="u2@ex.com")
            database.session.add_all([u1, u2])
            database.session.commit()

            t1 = generar_token_recuperacion(u1.id)
            t2 = generar_token_recuperacion(u2.id)
            assert t1 != t2

            r1 = validar_token_recuperacion(t1)
            r2 = validar_token_recuperacion(t2)
            assert r1.id == u1.id
            assert r2.id == u2.id
