# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Verificación de dispositivos, OTP y recuperación de contraseña."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from cacao_accounting.database import (
    OtpVerification,
    PasswordResetToken,
    RecognizedDevice,
    User,
    database,
)
from cacao_accounting.document_flow.status import _
from cacao_accounting.logs import log

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
DEVICE_COOKIE_TTL_DAYS = 30
PASSWORD_RESET_TTL_HOURS = 1
OTP_LENGTH = 6


def _now_utc() -> datetime:
    """Retorna la hora UTC actual como datetime naive para compatibilidad con SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generar_otp(user_id: str, purpose: str = "device_verification") -> str:
    """Genera un código OTP de 6 dígitos y lo persiste en la base de datos.

    Cualquier OTP previo pendiente del mismo usuario y propósito se marca
    como consumido para evitar confusión entre códigos.
    """
    previos = database.session.scalars(
        select(OtpVerification).filter_by(user_id=user_id, purpose=purpose, consumed=False)
    ).all()
    for otp in previos:
        otp.consumed = True

    code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
    registro = OtpVerification(
        user_id=user_id,
        code=code,
        purpose=purpose,
        expires_at=_now_utc() + timedelta(minutes=OTP_TTL_MINUTES),
        attempts=0,
        consumed=False,
    )
    database.session.add(registro)
    database.session.flush()
    log.debug("OTP generated for user %s (purpose=%s)", user_id, purpose)
    return code


def validar_otp(user_id: str, code: str, purpose: str = "device_verification") -> bool:
    """Valida un código OTP.

    Retorna ``True`` solo si el código coincide, no está expirado y no ha
    sido consumido previamente. Incrementa el contador de intentos en cada
    llamada.
    """
    now = _now_utc()
    registro = database.session.scalar(
        select(OtpVerification)
        .filter_by(
            user_id=user_id,
            purpose=purpose,
            consumed=False,
        )
        .order_by(OtpVerification.created.desc())
    )
    if registro is None:
        return False

    if registro.expires_at < now:
        registro.consumed = True
        database.session.flush()
        return False

    if registro.attempts >= OTP_MAX_ATTEMPTS:
        registro.consumed = True
        database.session.flush()
        return False

    registro.attempts += 1

    if not secrets.compare_digest(registro.code, code):
        database.session.flush()
        return False

    registro.consumed = True
    database.session.flush()
    log.debug("OTP validated for user %s", user_id)
    return True


def establecer_cookie_dispositivo(
    user_id: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    """Crea un dispositivo reconocido y retorna el token UUID para la cookie."""
    token = str(uuid.uuid4())
    now = _now_utc()
    registro = RecognizedDevice(
        user_id=user_id,
        token=token,
        user_agent=user_agent[:255] if user_agent else None,
        ip_address=ip_address,
        expires_at=now + timedelta(days=DEVICE_COOKIE_TTL_DAYS),
    )
    database.session.add(registro)
    database.session.flush()
    log.debug("Recognized device created for user %s", user_id)
    return token


def verificar_cookie_dispositivo(user_id: str, token: str) -> bool:
    """Verifica si un token de dispositivo es válido y no está expirado."""
    now = _now_utc()
    registro = database.session.scalar(select(RecognizedDevice).filter_by(user_id=user_id, token=token))
    if registro is None:
        return False
    if registro.expires_at < now:
        return False
    return True


def revocar_dispositivo(device_id: str) -> None:
    """Elimina un dispositivo reconocido por su ID."""
    device = database.session.get(RecognizedDevice, device_id)
    if device:
        database.session.delete(device)
        database.session.flush()
        log.debug("Device %s revoked", device_id)


def listar_dispositivos(user_id: str) -> list[RecognizedDevice]:
    """Lista todos los dispositivos reconocidos de un usuario."""
    return list(
        database.session.scalars(
            select(RecognizedDevice).filter_by(user_id=user_id).order_by(RecognizedDevice.created.desc())
        ).all()
    )


def generar_token_recuperacion(user_id: str) -> str:
    """Genera un token de recuperación de contraseña y lo retorna."""
    previos = database.session.scalars(select(PasswordResetToken).filter_by(user_id=user_id, consumed=False)).all()
    for t in previos:
        t.consumed = True

    token = secrets.token_urlsafe(32)
    registro = PasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=_now_utc() + timedelta(hours=PASSWORD_RESET_TTL_HOURS),
        consumed=False,
    )
    database.session.add(registro)
    database.session.flush()
    log.debug("Password reset token generated for user %s", user_id)
    return token


def validar_token_recuperacion(token: str) -> User | None:
    """Valida un token de recuperación y retorna el usuario asociado.

    Retorna ``None`` si el token no existe, está expirado o ya fue consumido.
    """
    now = _now_utc()
    registro = database.session.scalar(select(PasswordResetToken).filter_by(token=token, consumed=False))
    if registro is None:
        return None
    if registro.expires_at < now:
        registro.consumed = True
        database.session.flush()
        return None

    user = database.session.get(User, registro.user_id)
    if user is None or not user.active:
        registro.consumed = True
        database.session.flush()
        return None

    registro.consumed = True
    database.session.flush()
    return user


def enviar_otp_por_email(user: User, code: str) -> None:
    """Envía un correo con el código OTP de verificación."""
    from cacao_accounting.messaging.email import EmailError, send_email

    if not user.e_mail:
        log.warning("User %s has no email configured", user.user)
        return
    body = (
        f"{'Hola'} {user.name or user.user},\n\n"
        f"{_('Se detectó un intento de inicio de sesión desde un navegador no reconocido.')}\n\n"
        f"{_('Su código de verificación es:')}: {code}\n\n"
        f"{_('Este código expira en')} {OTP_TTL_MINUTES} {'minutos'}.\n\n"
        f"{_('Si usted no solicitó este código, ignore este mensaje.')}"
    )
    try:
        send_email(
            to_email=user.e_mail,
            subject=_("Cacao Accounting - Código de verificación"),
            body=body,
            is_html=False,
        )
    except EmailError as exc:
        log.error("Error sending OTP to %s: %s", user.e_mail, exc)


def enviar_token_recuperacion_email(user: User, token: str) -> None:
    """Envía un correo con el enlace de recuperación de contraseña."""
    from flask import url_for

    from cacao_accounting.messaging.email import EmailError, send_email

    if not user.e_mail:
        log.warning("User %s has no email configured", user.user)
        return
    try:
        reset_url = url_for("login.reset_password", token=token, _external=True)
    except RuntimeError:
        log.error("Cannot generate external URL without application context")
        return

    body = (
        f"{'Hola'} {user.name or user.user},\n\n"
        f"{_('Recibimos una solicitud para restablecer su contraseña.')}\n\n"
        f"{_('Para crear una nueva contraseña, haga clic en el siguiente enlace:')}\n\n"
        f"{reset_url}\n\n"
        f"{_('Este enlace expira en')} {PASSWORD_RESET_TTL_HOURS} {'hora(s)'}.\n\n"
        f"{_('Si usted no solicitó este cambio, ignore este mensaje.')}"
    )
    try:
        send_email(
            to_email=user.e_mail,
            subject=_("Cacao Accounting - Recuperación de contraseña"),
            body=body,
            is_html=False,
        )
    except EmailError as exc:
        log.error("Error sending password reset to %s: %s", user.e_mail, exc)


def usuario_tiene_email(user: User) -> bool:
    """Retorna True si el usuario tiene un correo electrónico válido."""
    return bool(user.e_mail and user.e_mail.strip())
