# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio central de envío de correos electrónicos."""

from __future__ import annotations

import base64
import logging
import os
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

from cacao_accounting.database import CacaoConfig, database
from cacao_accounting.runtime_mode import is_desktop_mode


class EmailError(Exception):
    """Excepción para errores relacionados con el envío de correos electrónicos."""


LOGGER = logging.getLogger(__name__)
SMTP_PASSWORD_SALT_KEY = "smtp_password_salt"


def _get_encryption_key(salt: bytes) -> bytes:
    """Derive a Fernet key from the application secret using PBKDF2-HMAC."""
    key_base = ""
    if has_app_context():
        key_base = current_app.config.get("SECRET_KEY", "")
    if not key_base:
        key_base = os.environ.get("CACAO_SECRET_KEY") or os.environ.get("SECRET_KEY") or ""

    if not key_base:
        raise EmailError("Configure SECRET_KEY o CACAO_SECRET_KEY para proteger la contraseña SMTP.")

    key_derivation = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=210_000,
    )
    return base64.urlsafe_b64encode(key_derivation.derive(key_base.encode("utf-8")))


def _get_or_create_password_salt() -> bytes:
    """Load the persistent SMTP-password salt, creating it on first use."""
    if not has_app_context():
        raise EmailError("La contraseña SMTP requiere un contexto de aplicación para cifrarse.")
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=SMTP_PASSWORD_SALT_KEY)).scalar_one_or_none()
    if record and record.value:
        try:
            return base64.urlsafe_b64decode(record.value.encode("ascii"))
        except ValueError as exc:
            raise EmailError("La sal de cifrado SMTP almacenada no es válida.") from exc
    salt = os.urandom(16)
    database.session.add(CacaoConfig(key=SMTP_PASSWORD_SALT_KEY, value=base64.urlsafe_b64encode(salt).decode("ascii")))
    database.session.flush()
    return salt


def encrypt_smtp_pass(plaintext: str) -> str:
    """Cifra la contraseña utilizando Fernet."""
    if not plaintext:
        return ""
    try:
        return Fernet(_get_encryption_key(_get_or_create_password_salt())).encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EmailError(f"Error al cifrar contraseña: {exc}") from exc


def decrypt_smtp_pass(ciphertext: str) -> str:
    """Descifra la contraseña utilizando Fernet."""
    if not ciphertext:
        return ""
    try:
        return Fernet(_get_encryption_key(_get_or_create_password_salt())).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        LOGGER.error("No se pudo descifrar la contraseña SMTP; revise SECRET_KEY y su rotación.")
        raise EmailError("No se pudo descifrar la contraseña SMTP configurada.") from exc
    except (TypeError, ValueError) as exc:
        raise EmailError("La contraseña SMTP almacenada no es válida.") from exc


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
    except SQLAlchemyError:
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


def _build_message(to_email: str, subject: str, body: str, from_email: str, is_html: bool) -> str:
    """Build and serialize an email message for SMTP delivery."""
    if is_html:
        message: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
        message.attach(MIMEText(body, "html", "utf-8"))
    else:
        message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    return message.as_string()


def _send_smtp_message(
    smtp_config: dict[str, Any],
    message: str,
) -> None:
    """Open an SMTP connection and send one serialized message."""
    context = ssl.create_default_context()
    smtp: Any
    if smtp_config["port"] == 465:
        smtp = smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"], context=context, timeout=10)
    else:
        smtp = smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=10)
        if smtp_config["use_tls"]:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
    if smtp_config["user"] and smtp_config["password"]:
        smtp.login(smtp_config["user"], smtp_config["password"])
    smtp.sendmail(smtp_config["from_email"], [smtp_config["to_email"]], message)
    smtp.quit()


def retry_email_queue_item(queue_id: str) -> Any:
    """Reintenta el envío de un correo fallido desde la cola de correos."""
    from datetime import datetime, timezone
    from cacao_accounting.database import EmailQueue

    if is_desktop_mode():
        raise EmailError("El reintento de envío de correos no está disponible en modo DESKTOP.")

    item = database.session.get(EmailQueue, queue_id)
    if not item:
        raise EmailError("El registro de correo no existe.")

    item.attempts = (item.attempts or 0) + 1
    try:
        send_email(to_email=item.recipient, subject=item.subject, body=item.body, is_html=False)
        item.status = "sent"
        item.error_message = None
        item.sent_at = datetime.now(timezone.utc)

        if item.document_type and item.document_id:
            try:
                from cacao_accounting.document_flow.repository import get_document
                from cacao_accounting.audit_trail_service import log_email_sent

                doc = get_document(item.document_type, item.document_id)
                if doc:
                    log_email_sent(
                        doc,
                        recipients=item.recipient,
                        subject=item.subject,
                        comment=f"correo reintentado y enviado exitosamente a {item.recipient}",
                    )
            except Exception as audit_exc:
                LOGGER.warning("No se pudo registrar auditoría en reintento: %s", audit_exc)

        database.session.commit()
        return item
    except Exception as exc:
        item.status = "failed"
        item.error_message = str(exc)
        database.session.commit()
        raise EmailError(f"Error al reintentar envío: {exc}") from exc


def can_send_transaction_emails() -> bool:
    """Verifica si el envío de correos desde transacciones operativas está habilitado y configurado."""
    if is_desktop_mode():
        return False
    server = get_smtp_setting("smtp_server")
    from_email = get_smtp_setting("smtp_from_email")
    if not server or not from_email:
        return False
    disabled = _get_db_value("disable_transaction_emails")
    if disabled and disabled.lower() in ("true", "1", "yes", "y", "on"):
        return False
    return True


def get_document_default_recipient_email(document_type: str, document_id: str) -> str:
    """Obtiene la dirección de correo del proveedor/cliente o tercero asociado al documento."""
    if not has_app_context():
        return ""
    try:
        from cacao_accounting.document_flow.repository import get_document
        from cacao_accounting.database import Party, database

        doc = get_document(document_type, document_id)
        if not doc:
            return ""

        party_id = (
            getattr(doc, "supplier_id", None)
            or getattr(doc, "customer_id", None)
            or getattr(doc, "client_id", None)
            or getattr(doc, "party_id", None)
            or getattr(doc, "entity_id", None)
        )
        if not party_id:
            return ""

        tercero = database.session.execute(
            database.select(Party).where((Party.id == str(party_id)) | (Party.code == str(party_id)))
        ).scalar_one_or_none()

        if tercero:
            email = (tercero.primary_email or tercero.legal_representative_email or "").strip()
            if email:
                return email
    except Exception:
        pass
    return ""


def send_email(to_email: str, subject: str, body: str, is_html: bool = False) -> None:
    """Envía un correo electrónico utilizando la configuración SMTP activa (Cloud-Only)."""
    if is_desktop_mode():
        raise EmailError("La capacidad de envío de correos electrónicos no está disponible en modo DESKTOP.")

    server_host = get_smtp_setting("smtp_server")
    port_str = get_smtp_setting("smtp_port") or "587"
    user = get_smtp_setting("smtp_user")
    smtp_pass = get_smtp_setting("smtp_password")
    use_tls_str = get_smtp_setting("smtp_use_tls") or "true"
    from_email = get_smtp_setting("smtp_from_email")

    if not server_host:
        raise EmailError("El servidor SMTP (smtp_server) no está configurado.")
    if not from_email:
        raise EmailError("El remitente (smtp_from_email) no está configurado.")

    try:
        port = int(port_str)
    except ValueError as exc:
        raise EmailError(f"Puerto SMTP no válido: {port_str}") from exc

    use_tls = use_tls_str.lower() in ("true", "1", "yes", "y", "on")

    message = _build_message(to_email, subject, body, from_email, is_html)
    smtp_config = {
        "host": server_host,
        "port": port,
        "user": user,
        "password": smtp_pass,
        "use_tls": use_tls,
        "from_email": from_email,
        "to_email": to_email,
    }

    try:
        _send_smtp_message(smtp_config, message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise EmailError(f"Error al enviar correo electrónico: {exc}") from exc
