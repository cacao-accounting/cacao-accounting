# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Origin protection never falls back to password-only authentication."""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.device_verification import establecer_cookie_dispositivo, generar_otp, validar_otp
from cacao_accounting.config import configuracion
from cacao_accounting.database import CacaoConfig, Currency, Entity, OtpVerification, User, database

PASSWORD = "Session-security-2026!"


def _crear_app(*, security_enabled: bool, smtp_configured: bool):
    """Create an isolated Cloud app with persisted session-security settings."""
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
            "SECRET_KEY": "session-security-fail-closed-test-key",
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                    classification="system",
                    e_mail="admin@example.com",
                ),
                CacaoConfig(key="session_security_enabled", value="true" if security_enabled else "false"),
            ]
        )
        if smtp_configured:
            database.session.add_all(
                [
                    CacaoConfig(key="smtp_server", value="smtp.example.com"),
                    CacaoConfig(key="smtp_from_email", value="noreply@example.com"),
                ]
            )
        database.session.commit()
    return application


def _quitar_smtp_ambiental(monkeypatch) -> None:
    """Ensure the no-SMTP scenario is independent of CI host configuration."""
    for key in (
        "CACAO_SMTP_SERVER",
        "SMTP_SERVER",
        "CACAO_SMTP_FROM_EMAIL",
        "SMTP_FROM_EMAIL",
        "CACAO_SMTP_USER",
        "SMTP_USER",
    ):
        monkeypatch.delenv(key, raising=False)


def test_seguridad_persistida_bloquea_login_si_smtp_no_esta_configurado(monkeypatch):
    """A missing mail service cannot silently disable the required OTP step."""
    _quitar_smtp_ambiental(monkeypatch)
    application = _crear_app(security_enabled=True, smtp_configured=False)
    try:
        client = application.test_client()
        response = client.post(
            "/login",
            data={"usuario": "admin", "acceso": PASSWORD},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        with client.session_transaction() as session:
            assert "_user_id" not in session
            assert "otp_user_id" not in session
            assert any("el correo no está disponible" in message for _, message in session["_flashes"])

        with application.app_context():
            assert database.session.execute(database.select(OtpVerification)).scalars().all() == []
            user = database.session.get(User, "admin")
            assert user is not None and user.token is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_seguridad_persistida_con_smtp_solicita_otp(monkeypatch):
    """Configured SMTP keeps the login in the OTP challenge."""
    sent = []

    def capture_email(user: User, code: str) -> bool:
        sent.append((user.id, user.e_mail, code))
        return True

    from cacao_accounting.auth import device_verification

    monkeypatch.setattr(device_verification, "enviar_otp_por_email", capture_email)
    application = _crear_app(security_enabled=True, smtp_configured=True)
    try:
        client = application.test_client()
        response = client.post("/login", data={"usuario": "admin", "acceso": PASSWORD})

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/auth/verify-otp")
        with client.session_transaction() as session:
            assert session.get("otp_user_id") == "admin"
            assert "_user_id" not in session
        assert len(sent) == 1
        assert sent[0][:2] == ("admin", "admin@example.com")
        assert len(sent[0][2]) == 6

        with application.app_context():
            otp = database.session.execute(database.select(OtpVerification)).scalar_one()
            assert otp.code != sent[0][2]
            assert otp.consumed is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_fallo_de_entrega_otp_revierte_codigo_nuevo_y_conserva_el_anterior(monkeypatch):
    """Failed OTP delivery leaves no unusable challenge and preserves the prior code."""
    from cacao_accounting.messaging.email import EmailError

    application = _crear_app(security_enabled=True, smtp_configured=True)
    try:
        with application.app_context():
            previous_code = generar_otp("admin", purpose="device_verification")
            database.session.commit()

        def fail_email(*_args, **_kwargs) -> None:
            raise EmailError("SMTP no disponible")

        monkeypatch.setattr("cacao_accounting.messaging.email.send_email", fail_email)
        client = application.test_client()
        response = client.post("/login", data={"usuario": "admin", "acceso": PASSWORD})

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        with client.session_transaction() as session:
            assert "_user_id" not in session
            assert "otp_user_id" not in session
            assert any("No se pudo enviar" in message for _, message in session["_flashes"])
        with application.app_context():
            records = database.session.execute(database.select(OtpVerification)).scalars().all()
            assert len(records) == 1
            assert records[0].consumed is False
            assert validar_otp("admin", previous_code, purpose="device_verification") is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_dispositivo_reconocido_permite_login_sin_smtp(monkeypatch):
    """A trusted device can sign in without mail because it needs no new OTP."""
    _quitar_smtp_ambiental(monkeypatch)
    application = _crear_app(security_enabled=True, smtp_configured=False)
    try:
        with application.app_context():
            device_token = establecer_cookie_dispositivo("admin")
            database.session.commit()

        client = application.test_client()
        client.set_cookie("device-id", device_token)
        response = client.post("/login", data={"usuario": "admin", "acceso": PASSWORD})

        assert response.status_code == 302
        with client.session_transaction() as session:
            assert session.get("_user_id") == "admin"
            assert "otp_user_id" not in session
        with application.app_context():
            assert database.session.execute(database.select(OtpVerification)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_login_sin_seguridad_persistida_no_requiere_smtp(monkeypatch):
    """The SMTP requirement applies only when origin protection is enabled."""
    _quitar_smtp_ambiental(monkeypatch)
    application = _crear_app(security_enabled=False, smtp_configured=False)
    try:
        client = application.test_client()
        response = client.post("/login", data={"usuario": "admin", "acceso": PASSWORD})

        assert response.status_code == 302
        with client.session_transaction() as session:
            assert session.get("_user_id") == "admin"
            assert "otp_user_id" not in session
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
