# SPDX-License-Identifier: Apache-2.0
"""Pruebas unitarias para el servicio de correo electrónico y su configuración."""

from __future__ import annotations

import os
import sys
from unittest import mock

# Mock email_validator module to avoid environment dependency errors in WTForms Email validator
sys.modules["email_validator"] = mock.MagicMock()

import pytest
from flask import Flask

from cacao_accounting import create_app
from cacao_accounting.database import CacaoConfig, User, database
from cacao_accounting.messaging.email import (
    EmailError,
    get_smtp_setting,
    send_email,
    set_smtp_setting,
)
from z_func import init_test_db


@pytest.fixture(scope="module")
def app_instance():
    """Instancia de aplicación Flask con base de datos en memoria para pruebas."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "email_test_secret_key",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "MODO_ESCRITORIO": False,  # Cloud mode by default for email tests
        }
    )
    with _app.app_context():
        init_test_db(_app)
        cacao_user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one_or_none()
        if cacao_user:
            cacao_user.classification = "admin"
            database.session.commit()
    return _app


def test_get_smtp_setting_defaults(app_instance):
    """Prueba que se obtienen los valores por defecto cuando no hay DB ni variables de entorno."""
    with app_instance.app_context():
        # Asegurarse de limpiar DB para pruebas aisladas
        database.session.execute(database.delete(CacaoConfig))
        database.session.commit()

        # Limpiar env
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_smtp_setting("smtp_server") is None
            assert get_smtp_setting("smtp_port", "587") == "587"
            assert get_smtp_setting("smtp_use_tls", "true") == "true"


def test_get_smtp_setting_env_fallback(app_instance):
    """Prueba que el recuperador de configuración SMTP usa las variables de entorno de fallback."""
    with app_instance.app_context():
        database.session.execute(database.delete(CacaoConfig))
        database.session.commit()

        env_mock = {
            "CACAO_SMTP_SERVER": "smtp.env.test",
            "SMTP_PORT": "465",
            "CACAO_SMTP_USER": "env_user",
        }
        with mock.patch.dict(os.environ, env_mock, clear=True):
            assert get_smtp_setting("smtp_server") == "smtp.env.test"
            assert get_smtp_setting("smtp_port") == "465"
            assert get_smtp_setting("smtp_user") == "env_user"


def test_get_smtp_setting_db_priority(app_instance):
    """Prueba que la configuración en base de datos tiene prioridad sobre las variables de entorno."""
    with app_instance.app_context():
        database.session.execute(database.delete(CacaoConfig))
        set_smtp_setting("smtp_server", "smtp.db.test")
        database.session.commit()

        env_mock = {
            "CACAO_SMTP_SERVER": "smtp.env.test",
        }
        with mock.patch.dict(os.environ, env_mock, clear=True):
            assert get_smtp_setting("smtp_server") == "smtp.db.test"


def test_smtp_password_encryption_decryption(app_instance):
    """Prueba que la contraseña de SMTP se guarda cifrada en base de datos y se descifra al recuperarse."""
    with app_instance.app_context():
        database.session.execute(database.delete(CacaoConfig))
        set_smtp_setting("smtp_password", "SuperSecretSMTPPassword123")
        database.session.commit()

        # Verificar que el valor real guardado en la base de datos está cifrado (y no es el texto plano)
        record = database.session.execute(database.select(CacaoConfig).filter_by(key="smtp_password")).scalar_one()
        assert record.value != "SuperSecretSMTPPassword123"

        # Verificar que se descifra correctamente al recuperarse
        assert get_smtp_setting("smtp_password") == "SuperSecretSMTPPassword123"


def test_send_email_desktop_mode_error(app_instance, monkeypatch):
    """Prueba que en modo Escritorio el envío de correos levanta un error."""
    with app_instance.app_context():
        app_instance.config["MODO_ESCRITORIO"] = True
        try:
            with pytest.raises(EmailError) as exc_info:
                send_email("test@example.com", "Subject", "Body")
            assert "no está disponible en modo DESKTOP" in str(exc_info.value)
        finally:
            app_instance.config["MODO_ESCRITORIO"] = False


def test_send_email_missing_config_errors(app_instance):
    """Prueba errores cuando faltan datos obligatorios de SMTP."""
    with app_instance.app_context():
        database.session.execute(database.delete(CacaoConfig))
        database.session.commit()

        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EmailError) as exc_info:
                send_email("test@example.com", "Subject", "Body")
            assert "smtp_server" in str(exc_info.value)

            set_smtp_setting("smtp_server", "smtp.test.com")
            database.session.commit()

            with pytest.raises(EmailError) as exc_info:
                send_email("test@example.com", "Subject", "Body")
            assert "smtp_from_email" in str(exc_info.value)


@mock.patch("smtplib.SMTP")
def test_send_email_success_standard_port(mock_smtp, app_instance):
    """Prueba el envío exitoso de correo con puerto estándar (STARTTLS)."""
    with app_instance.app_context():
        database.session.execute(database.delete(CacaoConfig))
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_port", "587")
        set_smtp_setting("smtp_user", "myuser")
        set_smtp_setting("smtp_password", "mypass")
        set_smtp_setting("smtp_use_tls", "true")
        database.session.commit()

        # Mock smtp instances
        instance = mock_smtp.return_value

        send_email("recipient@example.com", "Test Subject", "Test Body")

        mock_smtp.assert_called_once_with("smtp.test.com", 587, timeout=10)
        instance.ehlo.assert_called()
        instance.starttls.assert_called_once()
        instance.login.assert_called_once_with("myuser", "mypass")
        instance.sendmail.assert_called_once()
        instance.quit.assert_called_once()


@mock.patch("smtplib.SMTP_SSL")
def test_send_email_success_ssl_port(mock_smtp_ssl, app_instance):
    """Prueba el envío exitoso de correo con puerto SSL (465) y validación de contexto SSL."""
    with app_instance.app_context():
        database.session.execute(database.delete(CacaoConfig))
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_port", "465")
        set_smtp_setting("smtp_user", "myuser")
        set_smtp_setting("smtp_password", "mypass")
        database.session.commit()

        instance = mock_smtp_ssl.return_value

        send_email("recipient@example.com", "Test Subject", "Test Body")

        # Asegurarse de que se pasó un objeto de contexto SSL
        called_args, called_kwargs = mock_smtp_ssl.call_args
        assert called_args[0] == "smtp.test.com"
        assert called_args[1] == 465
        assert "context" in called_kwargs
        assert called_kwargs["timeout"] == 10

        instance.login.assert_called_once_with("myuser", "mypass")
        instance.sendmail.assert_called_once()
        instance.quit.assert_called_once()


def test_email_settings_admin_view_cloud(app_instance):
    """Prueba la vista de configuración SMTP en modo Cloud."""
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/email")
        assert response.status_code == 200
        assert b"Ajustes del Servidor SMTP" in response.data

        # POST save config
        response2 = client.post(
            "/settings/email",
            data={
                "smtp_server": "smtp.web.test",
                "smtp_port": "587",
                "smtp_user": "webuser",
                "smtp_password": "webpassword",
                "smtp_use_tls": "on",
                "smtp_from_email": "webfrom@example.com",
            },
            follow_redirects=True,
        )
        assert response2.status_code == 200
        assert b"Configuraci" in response2.data and b"guardada correctamente" in response2.data

        with app_instance.app_context():
            assert get_smtp_setting("smtp_server") == "smtp.web.test"
            assert get_smtp_setting("smtp_user") == "webuser"
            assert get_smtp_setting("smtp_password") == "webpassword"
            assert get_smtp_setting("smtp_from_email") == "webfrom@example.com"


@mock.patch("cacao_accounting.messaging.email.send_email")
def test_email_settings_admin_test_action(mock_send_email, app_instance):
    """Prueba la acción de enviar correo de prueba desde la vista de administración."""
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # POST test_email action without recipient
        response = client.post(
            "/settings/email",
            data={
                "action": "test_email",
                "test_recipient": "",
            },
            follow_redirects=True,
        )
        assert b"Debe especificar un correo destinatario" in response.data

        # POST test_email success
        response2 = client.post(
            "/settings/email",
            data={
                "action": "test_email",
                "test_recipient": "test_dest@example.com",
            },
            follow_redirects=True,
        )
        assert b"Correo de prueba enviado correctamente" in response2.data
        mock_send_email.assert_called_once_with(
            to_email="test_dest@example.com",
            subject="Correo de prueba de Cacao Accounting",
            body="Este es un correo de prueba para verificar la configuración de SMTP en Cacao Accounting.",
            is_html=False,
        )


def test_email_settings_admin_view_desktop_forbidden(app_instance):
    """Prueba que la vista de configuración SMTP está prohibida en modo Desktop."""
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        app_instance.config["MODO_ESCRITORIO"] = True
        try:
            response = client.get("/settings/email")
            assert response.status_code == 403
        finally:
            app_instance.config["MODO_ESCRITORIO"] = False
