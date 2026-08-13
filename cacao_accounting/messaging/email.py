# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio central de envío de correos electrónicos."""

from __future__ import annotations

import base64
import hashlib
import os
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from cryptography.fernet import Fernet
from flask import current_app, has_app_context

from cacao_accounting.database import CacaoConfig, database
from cacao_accounting.runtime_mode import is_desktop_mode


class EmailError(Exception):
    """Excepción para errores relacionados con el envío de correos electrónicos."""


def _get_encryption_key() -> bytes:
    """Deriva una clave Fernet válida de 32 bytes a partir de la variable SECRET_KEY."""
    key_base = ""  # nosonar
    if has_app_context():
        key_base = current_app.config.get("SECRET_KEY", "")
    if not key_base:
        key_base = os.environ.get("CACAO_SECRET_KEY") or os.environ.get("SECRET_KEY") or ""

    if not key_base:
        # Generar una clave temporal y aleatoria si no hay ninguna configurada
        key_base = "temp_fallback_key_" + str(os.urandom(16).hex())

    # Derivar una clave segura de 32 bytes usando SHA256
    key_hash = hashlib.sha256(key_base.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key_hash)


def encrypt_smtp_pass(plaintext: str) -> str:
    """Cifra la contraseña utilizando Fernet."""
    if not plaintext:
        return ""
    try:
        f = Fernet(_get_encryption_key())
        return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise EmailError(f"Error al cifrar contraseña: {e}")


def decrypt_smtp_pass(ciphertext: str) -> str:
    """Descifra la contraseña utilizando Fernet."""
    if not ciphertext:
        return ""
    try:
        f = Fernet(_get_encryption_key())
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        # Retornar vacío si falla el descifrado (por ejemplo, si cambia la clave secreta)
        return ""


def _get_db_value(key: str) -> str | None:
    if not has_app_context():
        return None
    try:
        record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
        if record and record.value:
            val = str(record.value).strip()
            if key == "smtp_password":
                return decrypt_smtp_pass(val)
            return val
    except Exception:
        # Evitar fallos si la base de datos no está inicializada o las tablas no existen
        pass
    return None


def get_smtp_setting(key: str, default: str | None = None) -> str | None:
    """Obtiene un parámetro de configuración SMTP desde la base de datos o variables de entorno."""
    val = _get_db_value(key)
    if val is not None:
        return val

    env_keys = {
        "smtp_server": ["CACAO_SMTP_SERVER", "SMTP_SERVER"],
        "smtp_port": ["CACAO_SMTP_PORT", "SMTP_PORT"],
        "smtp_user": ["CACAO_SMTP_USER", "SMTP_USER"],
        "smtp_password": ["CACAO_SMTP_PASSWORD", "SMTP_PASSWORD"],
        "smtp_use_tls": ["CACAO_SMTP_USE_TLS", "SMTP_USE_TLS"],
        "smtp_from_email": ["CACAO_SMTP_FROM_EMAIL", "SMTP_FROM_EMAIL"],
    }

    for env_key in env_keys.get(key, []):
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val.strip()

    if key == "smtp_from_email":
        user_val = get_smtp_setting("smtp_user")
        if user_val:
            return user_val

    return default


def set_smtp_setting(key: str, value: str) -> None:
    """Guarda un parámetro de configuración SMTP en la base de datos (con cifrado para la contraseña)."""
    if key == "smtp_password":
        value = encrypt_smtp_pass(value)
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    if record is None:
        database.session.add(CacaoConfig(key=key, value=value))
    else:
        record.value = value


def send_email(to_email: str, subject: str, body: str, is_html: bool = False) -> None:
    """Envía un correo electrónico utilizando la configuración SMTP activa (Cloud-Only)."""
    if is_desktop_mode():
        raise EmailError("La capacidad de envío de correos electrónicos no está disponible en modo DESKTOP.")

    server_host = get_smtp_setting("smtp_server")
    port_str = get_smtp_setting("smtp_port") or "587"
    user = get_smtp_setting("smtp_user")
    smtp_pass = get_smtp_setting("smtp_password")  # nosonar
    use_tls_str = get_smtp_setting("smtp_use_tls") or "true"
    from_email = get_smtp_setting("smtp_from_email")

    if not server_host:
        raise EmailError("El servidor SMTP (smtp_server) no está configurado.")
    if not from_email:
        raise EmailError("El remitente (smtp_from_email) no está configurado.")

    try:
        port = int(port_str)
    except ValueError:
        raise EmailError(f"Puerto SMTP no válido: {port_str}")

    use_tls = use_tls_str.lower() in ("true", "1", "yes", "y", "on")

    msg: MIMEMultipart | MIMEText
    if is_html:
        html_msg = MIMEMultipart("alternative")
        html_msg.attach(MIMEText(body, "html", "utf-8"))
        msg = html_msg
    else:
        msg = MIMEText(body, "plain", "utf-8")

    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        smtp: Any
        if port == 465:  # nosonar
            smtp = smtplib.SMTP_SSL(server_host, port, context=context, timeout=10)  # nosonar
        else:  # nosonar
            smtp = smtplib.SMTP(server_host, port, timeout=10)  # nosonar
            if use_tls:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()

        if user and smtp_pass:
            smtp.login(user, smtp_pass)

        smtp.sendmail(from_email, [to_email], msg.as_string())
        smtp.quit()
    except Exception as e:
        raise EmailError(f"Error al enviar correo electrónico: {e}") from e
