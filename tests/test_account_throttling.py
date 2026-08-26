# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Pruebas unitarias para throttling de intentos de login por cuenta."""

from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher

from cacao_accounting import create_app
from cacao_accounting.database import User, database


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


def _get_user(user_id):
    return database.session.get(User, user_id)


def _now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestLockoutMinutes:
    def test_below_threshold_returns_zero(self):
        from cacao_accounting.auth.account_throttling import _lockout_minutes

        assert _lockout_minutes(1) == 0
        assert _lockout_minutes(4) == 0

    def test_threshold_5_returns_1_minute(self):
        from cacao_accounting.auth.account_throttling import _lockout_minutes

        assert _lockout_minutes(5) == 1

    def test_threshold_6_returns_5_minutes(self):
        from cacao_accounting.auth.account_throttling import _lockout_minutes

        assert _lockout_minutes(6) == 5

    def test_threshold_7_returns_15_minutes(self):
        from cacao_accounting.auth.account_throttling import _lockout_minutes

        assert _lockout_minutes(7) == 15

    def test_threshold_8_returns_30_minutes(self):
        from cacao_accounting.auth.account_throttling import _lockout_minutes

        assert _lockout_minutes(8) == 30
        assert _lockout_minutes(10) == 30
        assert _lockout_minutes(100) == 30


class TestEstaBloqueada:
    def test_no_lockout_by_default(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import esta_bloqueada

            u = _get_user(user)
            assert esta_bloqueada(u) is False

    def test_locked_when_lockout_until_in_future(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import esta_bloqueada

            u = _get_user(user)
            u.lockout_until = _now_utc() + timedelta(minutes=5)
            database.session.flush()
            assert esta_bloqueada(u) is True

    def test_not_locked_when_lockout_until_in_past(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import esta_bloqueada

            u = _get_user(user)
            u.lockout_until = _now_utc() - timedelta(minutes=5)
            database.session.flush()
            assert esta_bloqueada(u) is False


class TestRegistrarIntentoFallido:
    def test_increments_count(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            count = registrar_intento_fallido(u)
            assert count == 1
            assert u.failed_login_count == 1

    def test_no_lockout_below_threshold(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            for _ in range(4):
                registrar_intento_fallido(u)
            assert u.lockout_until is None

    def test_lockout_at_threshold_5(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            for _ in range(5):
                registrar_intento_fallido(u)
            assert u.lockout_until is not None
            assert u.failed_login_count == 5

    def test_lockout_increases_with_attempts(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            for _ in range(7):
                registrar_intento_fallido(u)
            assert u.failed_login_count == 7
            assert u.lockout_until is not None

    def test_sets_last_failed_login(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            registrar_intento_fallido(u)
            assert u.last_failed_login is not None


class TestRegistrarIntentoExitoso:
    def test_resets_counters(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import (
                registrar_intento_exitoso,
                registrar_intento_fallido,
            )

            u = _get_user(user)
            for _ in range(5):
                registrar_intento_fallido(u)
            assert u.failed_login_count == 5

            registrar_intento_exitoso(u)
            assert u.failed_login_count == 0
            assert u.lockout_until is None

    def test_no_error_when_count_already_zero(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_exitoso

            u = _get_user(user)
            registrar_intento_exitoso(u)
            assert u.failed_login_count == 0


class TestDesbloquearCuenta:
    def test_unlock_resets_all_fields(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import (
                desbloquear_cuenta,
                registrar_intento_fallido,
            )

            u = _get_user(user)
            for _ in range(8):
                registrar_intento_fallido(u)
            assert u.lockout_until is not None

            desbloquear_cuenta(u)
            assert u.failed_login_count == 0
            assert u.lockout_until is None


class TestTiempoRestanteBloqueo:
    def test_returns_none_when_not_locked(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import tiempo_restante_bloqueo

            u = _get_user(user)
            assert tiempo_restante_bloqueo(u) is None

    def test_returns_seconds_when_locked(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import tiempo_restante_bloqueo

            u = _get_user(user)
            u.lockout_until = _now_utc() + timedelta(minutes=5)
            database.session.flush()
            remaining = tiempo_restante_bloqueo(u)
            assert remaining is not None
            assert remaining > 0
            assert remaining <= 300

    def test_unlocks_when_expired(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import tiempo_restante_bloqueo

            u = _get_user(user)
            u.lockout_until = _now_utc() - timedelta(minutes=1)
            database.session.flush()
            remaining = tiempo_restante_bloqueo(u)
            assert remaining is None


class TestListarCuentasBloqueadas:
    def test_empty_when_no_lockouts(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import listar_cuentas_bloqueadas

            assert listar_cuentas_bloqueadas() == []

    def test_returns_locked_accounts(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            for _ in range(5):
                registrar_intento_fallido(u)

            from cacao_accounting.auth.account_throttling import listar_cuentas_bloqueadas

            locked = listar_cuentas_bloqueadas()
            assert len(locked) == 1
            assert locked[0][0].id == user
            assert locked[0][1] > 0

    def test_excludes_unlocked_accounts(self, app, user):
        with app.app_context():
            from cacao_accounting.auth.account_throttling import (
                desbloquear_cuenta,
                registrar_intento_fallido,
            )

            u = _get_user(user)
            for _ in range(5):
                registrar_intento_fallido(u)
            desbloquear_cuenta(u)

            from cacao_accounting.auth.account_throttling import listar_cuentas_bloqueadas

            assert listar_cuentas_bloqueadas() == []


class TestAdminUnlockService:
    def test_desbloquear_cuenta_usuario(self, app, user):
        with app.app_context():
            from cacao_accounting.admin.session_security_service import (
                desbloquear_cuenta_usuario,
            )
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            for _ in range(5):
                registrar_intento_fallido(u)
            assert u.lockout_until is not None

            result = desbloquear_cuenta_usuario(user)
            assert result is True
            assert u.failed_login_count == 0
            assert u.lockout_until is None

    def test_desbloquear_inexistente(self, app):
        with app.app_context():
            from cacao_accounting.admin.session_security_service import (
                desbloquear_cuenta_usuario,
            )

            assert desbloquear_cuenta_usuario("nonexistent") is False

    def test_desbloquear_no_bloqueada(self, app, user):
        with app.app_context():
            from cacao_accounting.admin.session_security_service import (
                desbloquear_cuenta_usuario,
            )

            assert desbloquear_cuenta_usuario(user) is False


class TestListarCuentasBloqueadasService:
    def test_service_delegates(self, app, user):
        with app.app_context():
            from cacao_accounting.admin.session_security_service import (
                listar_cuentas_bloqueadas,
            )
            from cacao_accounting.auth.account_throttling import registrar_intento_fallido

            u = _get_user(user)
            for _ in range(5):
                registrar_intento_fallido(u)

            locked = listar_cuentas_bloqueadas()
            assert len(locked) == 1
