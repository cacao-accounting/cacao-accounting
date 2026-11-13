# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Auth bearer secrets are returned to callers but never stored in plaintext."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier

import pytest
from datetime import datetime, timedelta, timezone
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.pool import StaticPool

from cacao_accounting import alembic, create_app
from cacao_accounting.auth.device_verification import (
    establecer_cookie_dispositivo,
    generar_otp,
    generar_token_recuperacion,
    revocar_dispositivo,
    _secret_issuance_statement,
    validar_otp,
    validar_token_recuperacion,
    verificar_cookie_dispositivo,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AuthSecretIssuanceLock,
    Currency,
    Entity,
    OtpVerification,
    PasswordResetToken,
    RecognizedDevice,
    User,
    database,
)


def _crear_app(database_uri="sqlite://", database_options=None):
    """Create an isolated app with a stable secret key for auth-token checks."""
    options = database_options or {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": options,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "auth-secret-storage-test-key",
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
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
                    id="usuario",
                    user="usuario",
                    name="Usuario",
                    password=b"x",
                    active=True,
                    classification="system",
                    e_mail="usuario@example.com",
                ),
            ]
        )
        database.session.commit()
    return application


def test_otp_guardado_como_hmac_sigue_validando_el_codigo_entregado():
    """The DB holds an opaque fixed-width digest while the caller gets a usable OTP."""
    application = _crear_app()
    try:
        with application.app_context():
            code = generar_otp("usuario", purpose="device_verification")
            registro = database.session.execute(database.select(OtpVerification)).scalar_one()

            assert registro.code != code
            assert len(registro.code) == 6
            assert registro.code.startswith("$")
            assert validar_otp("usuario", registro.code, purpose="device_verification") is False
            assert validar_otp("usuario", code, purpose="device_verification") is True
            assert validar_otp("usuario", code, purpose="device_verification") is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_reset_almacena_hmac_y_conserva_el_consumo_de_un_solo_uso():
    """The reset bearer token validates normally without a plaintext DB copy."""
    application = _crear_app()
    try:
        with application.app_context():
            token = generar_token_recuperacion("usuario")
            registro = database.session.execute(database.select(PasswordResetToken)).scalar_one()

            assert registro.token != token
            assert len(registro.token) == 64
            assert validar_token_recuperacion(registro.token) is None
            assert validar_token_recuperacion(token, consumir=False).id == "usuario"
            assert validar_token_recuperacion(token).id == "usuario"
            assert validar_token_recuperacion(token) is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cookie_de_dispositivo_se_compara_con_hmac_sin_guardar_el_token():
    """The recognized-device cookie remains usable while the stored token is opaque."""
    application = _crear_app()
    try:
        with application.app_context():
            token = establecer_cookie_dispositivo("usuario", user_agent="Browser")
            registro = database.session.execute(database.select(RecognizedDevice)).scalar_one()

            assert registro.token != token
            assert len(registro.token) == 36
            assert verificar_cookie_dispositivo("usuario", registro.token) is False
            assert verificar_cookie_dispositivo("usuario", token) is True
            assert verificar_cookie_dispositivo("usuario", "not-a-device-token") is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("dialect", "clause"),
    [
        (sqlite.dialect(), "ON CONFLICT"),
        (postgresql.dialect(), "ON CONFLICT"),
        (mysql.dialect(), "ON DUPLICATE KEY UPDATE"),
    ],
)
def test_lock_de_emision_compila_para_cada_motor_soportado(dialect, clause):
    """The cross-process lock uses valid upsert syntax for supported engines."""
    statement = _secret_issuance_statement(dialect.name, AuthSecretIssuanceLock.__table__, "usuario")

    assert clause in str(statement.compile(dialect=dialect))


def test_lock_de_emision_rechaza_motores_sin_upsert_soportado():
    """Unsupported engines fail before issuing credentials without a lock."""
    with pytest.raises(RuntimeError, match="unsupported"):
        _secret_issuance_statement("unknown", AuthSecretIssuanceLock.__table__, "usuario")


def test_generacion_de_otp_y_reset_falla_sin_invalidar_secreto_existente():
    """Missing HMAC keys cannot persist raw secrets or revoke previous ones."""
    application = _crear_app()
    try:
        with application.app_context():
            code = generar_otp("usuario")
            reset_token = generar_token_recuperacion("usuario")
            database.session.commit()
            previous_key = application.secret_key
            application.config["AUTH_TOKEN_KEY_STABLE"] = False

            with pytest.raises(RuntimeError, match="stable Flask SECRET_KEY"):
                generar_otp("usuario")

            application.config["AUTH_TOKEN_KEY_STABLE"] = True
            application.secret_key = None

            with pytest.raises(RuntimeError, match="SECRET_KEY"):
                generar_otp("usuario")
            with pytest.raises(RuntimeError, match="SECRET_KEY"):
                generar_token_recuperacion("usuario")
            database.session.commit()

            assert database.session.execute(database.select(OtpVerification)).scalar_one().consumed is False
            assert database.session.execute(database.select(PasswordResetToken)).scalar_one().consumed is False
            application.secret_key = previous_key
            assert validar_otp("usuario", code) is True
            assert validar_token_recuperacion(reset_token, consumir=False).id == "usuario"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_rutas_auth_rechazan_secreto_efimero_sin_error_500():
    """Misconfigured ephemeral keys fail closed with a recoverable response."""
    application = _crear_app()
    try:
        application.config["AUTH_TOKEN_KEY_STABLE"] = False
        client = application.test_client()

        forgot_response = client.post("/auth/forgot-password", data={"email": "usuario@example.com"})
        assert forgot_response.status_code == 302
        with client.session_transaction() as session:
            active_account_flashes = session.pop("_flashes", [])

        unknown_response = client.post("/auth/forgot-password", data={"email": "missing@example.com"})
        assert unknown_response.status_code == 302
        with client.session_transaction() as session:
            unknown_account_flashes = session.pop("_flashes", [])
        assert active_account_flashes == unknown_account_flashes

        with application.app_context():
            assert database.session.execute(database.select(PasswordResetToken)).scalars().all() == []

        with client.session_transaction() as session:
            session["otp_user_id"] = "usuario"
        otp_response = client.post("/auth/verify-otp", data={"code": "123456"})
        assert otp_response.status_code == 302
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_generar_otp_nuevo_invalida_el_anterior_sin_comparar_hashes_en_claro():
    """Only the newest OTP remains usable after a code is resent."""
    application = _crear_app()
    try:
        with application.app_context():
            anterior = generar_otp("usuario")
            database.session.commit()
            nuevo = generar_otp("usuario")
            registros = (
                database.session.execute(database.select(OtpVerification).order_by(OtpVerification.created)).scalars().all()
            )

            assert len(registros) == 2
            assert sum(registro.consumed for registro in registros) == 1
            assert sum(not registro.consumed for registro in registros) == 1
            assert validar_otp("usuario", anterior) is False
            assert validar_otp("usuario", nuevo) is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_otp_expirado_se_consumo_y_no_se_acepta():
    """An expired opaque OTP cannot be used even when its raw value is known."""
    application = _crear_app()
    try:
        with application.app_context():
            code = generar_otp("usuario")
            registro = database.session.execute(database.select(OtpVerification)).scalar_one()
            registro.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            database.session.commit()

            assert validar_otp("usuario", code) is False
            assert registro.consumed is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_dispositivo_expirado_o_revocado_no_valida_su_cookie():
    """Expiry and explicit revocation both invalidate a recognized-device token."""
    application = _crear_app()
    try:
        with application.app_context():
            token_expirado = establecer_cookie_dispositivo("usuario")
            expirado = database.session.execute(database.select(RecognizedDevice)).scalar_one()
            expirado.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            database.session.commit()
            assert verificar_cookie_dispositivo("usuario", token_expirado) is False

            token_revocado = establecer_cookie_dispositivo("usuario")
            revocado = database.session.execute(
                database.select(RecognizedDevice).where(RecognizedDevice.token != expirado.token)
            ).scalar_one()
            revocar_dispositivo(revocado.id)
            database.session.commit()
            assert verificar_cookie_dispositivo("usuario", token_revocado) is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_token_reset_expirado_se_consumo():
    """An expired reset token remains one-time and cannot be replayed."""
    application = _crear_app()
    try:
        with application.app_context():
            token = generar_token_recuperacion("usuario")
            registro = database.session.execute(database.select(PasswordResetToken)).scalar_one()
            registro.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            database.session.commit()

            assert validar_token_recuperacion(token) is None
            assert registro.consumed is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_token_reset_de_usuario_inactivo_se_consume():
    """An inactive account cannot use a previously issued reset bearer token."""
    application = _crear_app()
    try:
        with application.app_context():
            token = generar_token_recuperacion("usuario")
            registro = database.session.execute(database.select(PasswordResetToken)).scalar_one()
            usuario = database.session.get(User, "usuario")
            usuario.active = False
            database.session.commit()

            assert validar_token_recuperacion(token) is None
            assert registro.consumed is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_migracion_convierte_secretos_legacy_y_sigue_validandolos():
    """Existing bearer values become opaque without invalidating valid users."""
    application = _crear_app()
    otp_code = "318024"
    reset_token = "legacy-reset-token-that-was-previously-stored"
    device_token = "923a7c14-8f8d-4cda-9b6b-63d9a081d933"
    try:
        with application.app_context():
            database.session.add_all(
                [
                    OtpVerification(
                        user_id="usuario",
                        code=otp_code,
                        purpose="device_verification",
                        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                        attempts=0,
                        consumed=False,
                    ),
                    PasswordResetToken(
                        user_id="usuario",
                        token=reset_token,
                        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                        consumed=False,
                    ),
                    RecognizedDevice(
                        user_id="usuario",
                        token=device_token,
                        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    ),
                ]
            )
            database.session.commit()
            database.session.remove()
            AuthSecretIssuanceLock.__table__.drop(database.engine)

            alembic.upgrade()
            migration = import_module("cacao_accounting.migrations.20261113_0002_auth_secret_hmac")
            with database.engine.begin() as connection:
                context = MigrationContext.configure(connection)
                with Operations.context(context):
                    migration.upgrade()
                    with pytest.raises(RuntimeError, match="irreversible"):
                        migration.downgrade()

            assert inspect(database.engine).has_table("auth_secret_issuance_lock")

            database.session.expire_all()
            otp = database.session.execute(database.select(OtpVerification)).scalar_one()
            password_reset = database.session.execute(database.select(PasswordResetToken)).scalar_one()
            device = database.session.execute(database.select(RecognizedDevice)).scalar_one()

            assert otp.code.startswith("$") and otp.code != otp_code
            assert password_reset.token.startswith("$") and password_reset.token != reset_token
            assert device.token.startswith("$") and device.token != device_token
            assert validar_otp("usuario", otp_code) is True
            assert validar_token_recuperacion(reset_token, consumir=False).id == "usuario"
            assert verificar_cookie_dispositivo("usuario", device_token) is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_otp_correcto_concurrente_solo_se_reclama_una_vez(tmp_path):
    """Two concurrent requests cannot both consume the same valid OTP."""
    database_path = tmp_path / "otp-correct-race.sqlite"
    application = _crear_app(f"sqlite:///{database_path}", {"connect_args": {"timeout": 30}})
    try:
        with application.app_context():
            code = generar_otp("usuario")
            database.session.commit()

        barrier = Barrier(2)

        def validar_en_sesion_propia():
            with application.app_context():
                barrier.wait(timeout=10)
                result = validar_otp("usuario", code)
                database.session.commit()
                database.session.remove()
                return result

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: validar_en_sesion_propia(), range(2)))

        assert results.count(True) == 1
        assert results.count(False) == 1
        with application.app_context():
            registro = database.session.execute(database.select(OtpVerification)).scalar_one()
            assert registro.consumed is True
            assert registro.attempts == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_intentos_otp_incorrectos_concurrentes_agotan_el_limite(tmp_path):
    """Parallel invalid requests each consume a persisted attempt exactly once."""
    database_path = tmp_path / "otp-fail-race.sqlite"
    application = _crear_app(f"sqlite:///{database_path}", {"connect_args": {"timeout": 30}})
    try:
        with application.app_context():
            code = generar_otp("usuario")
            database.session.commit()

        barrier = Barrier(5)

        def validar_codigo_incorrecto(_):
            with application.app_context():
                barrier.wait(timeout=10)
                result = validar_otp("usuario", "000000" if code != "000000" else "999999")
                database.session.commit()
                database.session.remove()
                return result

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(validar_codigo_incorrecto, range(5)))

        assert results == [False] * 5
        with application.app_context():
            registro = database.session.execute(database.select(OtpVerification)).scalar_one()
            assert registro.attempts == 5
            assert registro.consumed is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_emision_concurrente_de_otp_revoca_los_codigos_previos(tmp_path):
    """Only one OTP remains active after two simultaneous issuances."""
    database_path = tmp_path / "otp-issuance-race.sqlite"
    application = _crear_app(f"sqlite:///{database_path}", {"connect_args": {"timeout": 30}})
    try:
        barrier = Barrier(2)

        def generar_en_sesion_propia(_):
            with application.app_context():
                database.session.get(User, "usuario")
                database.session.rollback()
                barrier.wait(timeout=10)
                code = generar_otp("usuario")
                database.session.commit()
                database.session.remove()
                return code

        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = list(executor.map(generar_en_sesion_propia, range(2)))

        with application.app_context():
            registros = database.session.execute(database.select(OtpVerification)).scalars().all()
            assert len(registros) == 2
            assert sum(not registro.consumed for registro in registros) == 1
            assert sum(validar_otp("usuario", code) for code in codes) == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_emision_concurrente_de_reset_revoca_los_enlaces_previos(tmp_path):
    """Only one reset link remains active after simultaneous requests."""
    database_path = tmp_path / "reset-issuance-race.sqlite"
    application = _crear_app(f"sqlite:///{database_path}", {"connect_args": {"timeout": 30}})
    try:
        barrier = Barrier(2)

        def generar_en_sesion_propia(_):
            with application.app_context():
                database.session.get(User, "usuario")
                database.session.rollback()
                barrier.wait(timeout=10)
                token = generar_token_recuperacion("usuario")
                database.session.commit()
                database.session.remove()
                return token

        with ThreadPoolExecutor(max_workers=2) as executor:
            tokens = list(executor.map(generar_en_sesion_propia, range(2)))

        with application.app_context():
            registros = database.session.execute(database.select(PasswordResetToken)).scalars().all()
            assert len(registros) == 2
            assert sum(not registro.consumed for registro in registros) == 1
            assert sum(validar_token_recuperacion(token, consumir=False) is not None for token in tokens) == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
