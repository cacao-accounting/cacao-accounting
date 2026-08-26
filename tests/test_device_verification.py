# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Pruebas unitarias para verificación de dispositivos y OTP."""

from datetime import datetime, timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.database import (
    OtpVerification,
    RecognizedDevice,
    User,
    database,
)
from cacao_accounting.auth.device_verification import (
    DEVICE_COOKIE_TTL_DAYS,
    OTP_LENGTH,
    OTP_MAX_ATTEMPTS,
    establecer_cookie_dispositivo,
    generar_otp,
    listar_dispositivos,
    revocar_dispositivo,
    usuario_tiene_email,
    validar_otp,
    verificar_cookie_dispositivo,
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
            password=ph.hash("Secret123!".encode()).encode(),
            classification="system",
            active=True,
        )
        database.session.add(u)
        database.session.commit()
        return u.id


class TestGenerarOtp:
    def test_generates_six_digit_code(self, app, user):
        with app.app_context():
            code = generar_otp(user)
            assert len(code) == OTP_LENGTH
            assert code.isdigit()

    def test_stores_otp_in_database(self, app, user):
        with app.app_context():
            code = generar_otp(user)
            otp = database.session.scalar(database.select(OtpVerification).filter_by(user_id=user, consumed=False))
            assert otp is not None
            assert otp.code == code
            assert otp.purpose == "device_verification"
            assert otp.consumed is False

    def test_previous_otps_are_consumed(self, app, user):
        with app.app_context():
            code1 = generar_otp(user)
            code2 = generar_otp(user)
            assert code1 != code2
            previos = database.session.scalars(
                database.select(OtpVerification).filter_by(user_id=user, purpose="device_verification")
            ).all()
            assert len(previos) == 2
            consumidos = [o for o in previos if o.consumed]
            assert len(consumidos) == 1

    def test_custom_purpose(self, app, user):
        with app.app_context():
            generar_otp(user, purpose="password_reset")
            otp = database.session.scalar(database.select(OtpVerification).filter_by(user_id=user, purpose="password_reset"))
            assert otp is not None


class TestValidarOtp:
    def test_valid_code_returns_true(self, app, user):
        with app.app_context():
            code = generar_otp(user)
            assert validar_otp(user, code) is True

    def test_invalid_code_returns_false(self, app, user):
        with app.app_context():
            generar_otp(user)
            assert validar_otp(user, "000000") is False

    def test_code_is_marked_consumed_after_validation(self, app, user):
        with app.app_context():
            code = generar_otp(user)
            validar_otp(user, code)
            otp = database.session.scalars(
                database.select(OtpVerification)
                .filter_by(user_id=user, consumed=True)
                .order_by(OtpVerification.created.desc())
            ).first()
            assert otp is not None
            assert otp.consumed is True

    def test_expired_otp_returns_false(self, app, user):
        with app.app_context():
            code = generar_otp(user)
            otp = database.session.scalar(select(OtpVerification).filter_by(user_id=user, consumed=False))
            otp.expires_at = datetime.utcnow() - timedelta(minutes=1)
            database.session.flush()
            assert validar_otp(user, code) is False

    def test_max_attempts_blocks_otp(self, app, user):
        with app.app_context():
            code = generar_otp(user)
            for _ in range(OTP_MAX_ATTEMPTS):
                validar_otp(user, "999999")
            assert validar_otp(user, code) is False

    def test_no_otp_returns_false(self, app, user):
        with app.app_context():
            assert validar_otp(user, "123456") is False

    def test_otp_with_wrong_purpose_returns_false(self, app, user):
        with app.app_context():
            code = generar_otp(user, purpose="device_verification")
            assert validar_otp(user, code, purpose="password_reset") is False


class TestDispositivoCookie:
    def test_establecer_cookie_returns_uuid(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user)
            assert len(token) == 36
            assert token.count("-") == 4

    def test_establecer_cookie_stores_in_db(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user, user_agent="TestBrowser/1.0", ip_address="127.0.0.1")
            device = database.session.scalar(select(RecognizedDevice).filter_by(token=token))
            assert device is not None
            assert device.user_id == user
            assert device.user_agent == "TestBrowser/1.0"
            assert device.ip_address == "127.0.0.1"

    def test_establecer_cookie_expiry(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user)
            device = database.session.scalar(select(RecognizedDevice).filter_by(token=token))
            now = datetime.utcnow()
            expected = now + timedelta(days=DEVICE_COOKIE_TTL_DAYS)
            diff = abs((device.expires_at - expected).total_seconds())
            assert diff < 60

    def test_verificar_cookie_valid(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user)
            assert verificar_cookie_dispositivo(user, token) is True

    def test_verificar_cookie_invalid_token(self, app, user):
        with app.app_context():
            assert verificar_cookie_dispositivo(user, "invalid-token") is False

    def test_verificar_cookie_wrong_user(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user)
            assert verificar_cookie_dispositivo("other-user-id", token) is False

    def test_verificar_cookie_expired(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user)
            device = database.session.scalar(select(RecognizedDevice).filter_by(token=token))
            device.expires_at = datetime.utcnow() - timedelta(days=1)
            database.session.flush()
            assert verificar_cookie_dispositivo(user, token) is False

    def test_user_agent_truncated(self, app, user):
        with app.app_context():
            long_ua = "A" * 300
            token = establecer_cookie_dispositivo(user, user_agent=long_ua)
            device = database.session.scalar(select(RecognizedDevice).filter_by(token=token))
            assert len(device.user_agent) == 255


class TestRevocarDispositivo:
    def test_revocar_existente(self, app, user):
        with app.app_context():
            token = establecer_cookie_dispositivo(user)
            device = database.session.scalar(select(RecognizedDevice).filter_by(token=token))
            revocar_dispositivo(device.id)
            assert database.session.get(RecognizedDevice, device.id) is None

    def test_revocar_inexistente_no_error(self, app):
        with app.app_context():
            revocar_dispositivo("nonexistent-id")


class TestListarDispositivos:
    def test_lista_vacia(self, app, user):
        with app.app_context():
            assert listar_dispositivos(user) == []

    def test_lista_dispositivos(self, app, user):
        with app.app_context():
            establecer_cookie_dispositivo(user)
            establecer_cookie_dispositivo(user)
            dispositivos = listar_dispositivos(user)
            assert len(dispositivos) == 2


class TestUsuarioTieneEmail:
    def test_con_email(self, app, user):
        with app.app_context():
            u = database.session.get(User, user)
            assert usuario_tiene_email(u) is True

    def test_sin_email(self, app):
        with app.app_context():
            u = User(user="noemail", password=ph.hash("x").encode(), active=True)
            database.session.add(u)
            database.session.commit()
            assert usuario_tiene_email(u) is False

    def test_email_vacio(self, app):
        with app.app_context():
            u = User(user="emptyemail", e_mail="  ", password=ph.hash("x").encode(), active=True)
            database.session.add(u)
            database.session.commit()
            assert usuario_tiene_email(u) is False
