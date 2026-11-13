# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Verificación de dispositivos, OTP y recuperación de contraseña."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from flask import current_app
from sqlalchemy import case, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cacao_accounting.database import (
    AuthSecretIssuanceLock,
    OtpVerification,
    PasswordResetToken,
    RecognizedDevice,
    User,
    database,
)
from cacao_accounting.logs import log

from cacao_accounting.i18n import _

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
DEVICE_COOKIE_TTL_DAYS = 30
PASSWORD_RESET_TTL_HOURS = 1
OTP_LENGTH = 6


def _now_utc() -> datetime:
    """Return the current UTC time with timezone information preserved."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize database timestamps to aware UTC for cross-database comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _secret_digest(secret_type: str, user_id: str, secret: str, purpose: str = "") -> bytes:
    """Return a keyed, non-reversible digest bound to its auth context."""
    key = current_app.secret_key
    if not current_app.config.get("AUTH_TOKEN_KEY_STABLE", False):
        raise RuntimeError("A stable Flask SECRET_KEY is required to protect authentication secrets")
    if isinstance(key, str):
        key = key.encode("utf-8")
    if not isinstance(key, bytes) or not key:
        raise RuntimeError("A Flask SECRET_KEY is required to protect authentication secrets")
    payload = "\0".join((secret_type, user_id, purpose, secret)).encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).digest()


def _otp_digest(user_id: str, purpose: str, code: str) -> str:
    """Encode an OTP digest into the existing six-character storage field."""
    digest = _secret_digest("otp", user_id, code, purpose)
    encoded = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"${encoded[:5]}"


def _device_digest(user_id: str, token: str) -> str:
    """Encode a device-token digest into the existing 36-character field."""
    digest = _secret_digest("device", user_id, token)
    encoded = base64.urlsafe_b64encode(digest[:27]).decode("ascii")
    return f"${encoded[:35]}"


def _reset_token_digest(token: str) -> str:
    """Return the indexed HMAC stored for a reset token."""
    return f"${_secret_digest('password-reset', '', token).hex()[:63]}"


def _secret_issuance_statement(dialect: str, lock_table: Any, user_id: str) -> Any:
    """Build a dialect-specific write that serializes secret issuance."""
    statement: Any
    if dialect == "sqlite":
        statement = sqlite_insert(lock_table).values(user_id=user_id)
        statement = statement.on_conflict_do_update(
            index_elements=[lock_table.c.user_id],
            set_={"user_id": user_id},
        )
    elif dialect == "postgresql":
        statement = postgresql_insert(lock_table).values(user_id=user_id)
        statement = statement.on_conflict_do_update(
            index_elements=[lock_table.c.user_id],
            set_={"user_id": user_id},
        )
    elif dialect in {"mysql", "mariadb"}:
        statement = mysql_insert(lock_table).values(user_id=user_id)
        statement = statement.on_duplicate_key_update(user_id=user_id)
    else:
        raise RuntimeError(f"Auth secret issuance locking is unsupported for database dialect {dialect}")
    return statement


def _lock_secret_issuance(user_id: str) -> None:
    """Serialize issuance and revocation of temporary secrets for one account."""
    lock_table = AuthSecretIssuanceLock.__table__
    dialect = database.session.get_bind().dialect.name
    statement = _secret_issuance_statement(dialect, lock_table, user_id)
    database.session.execute(statement)


def generar_otp(user_id: str, purpose: str = "device_verification") -> str:
    """Genera un código OTP de 6 dígitos y lo persiste en la base de datos.

    Cualquier OTP previo pendiente del mismo usuario y propósito se marca
    como consumido para evitar confusión entre códigos.
    """
    code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
    code_digest = _otp_digest(user_id, purpose, code)
    _lock_secret_issuance(user_id)
    previos = database.session.scalars(
        select(OtpVerification).filter_by(user_id=user_id, purpose=purpose, consumed=False).with_for_update()
    ).all()
    for otp in previos:
        otp.consumed = True

    registro = OtpVerification(
        user_id=user_id,
        code=code_digest,
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
    registro_id = database.session.scalar(
        select(OtpVerification.id)
        .filter_by(
            user_id=user_id,
            purpose=purpose,
            consumed=False,
        )
        .order_by(OtpVerification.created.desc())
        .with_for_update()
    )
    if registro_id is None:
        return False

    code_digest = _otp_digest(user_id, purpose, code)
    filtros_activo = (
        OtpVerification.id == registro_id,
        OtpVerification.consumed.is_(False),
    )

    database.session.execute(
        update(OtpVerification)
        .where(
            *filtros_activo,
            or_(OtpVerification.expires_at < now, OtpVerification.attempts >= OTP_MAX_ATTEMPTS),
        )
        .values(consumed=True)
        .execution_options(synchronize_session=False)
    )

    reclamo_correcto = cast(
        CursorResult,
        database.session.execute(
            update(OtpVerification)
            .where(
                *filtros_activo,
                OtpVerification.expires_at >= now,
                OtpVerification.attempts < OTP_MAX_ATTEMPTS,
                OtpVerification.code == code_digest,
            )
            .values(attempts=OtpVerification.attempts + 1, consumed=True)
            .execution_options(synchronize_session=False)
        ),
    )
    if reclamo_correcto.rowcount == 1:
        database.session.flush()
        log.debug("OTP validated for user %s", user_id)
        return True

    registro_fallido = cast(
        CursorResult,
        database.session.execute(
            update(OtpVerification)
            .where(
                *filtros_activo,
                OtpVerification.expires_at >= now,
                OtpVerification.attempts < OTP_MAX_ATTEMPTS,
                OtpVerification.code != code_digest,
            )
            .values(
                attempts=OtpVerification.attempts + 1,
                consumed=case((OtpVerification.attempts + 1 >= OTP_MAX_ATTEMPTS, True), else_=False),
            )
            .execution_options(synchronize_session=False)
        ),
    )
    if registro_fallido.rowcount == 1:
        database.session.flush()
        return False

    database.session.flush()
    return False


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
        token=_device_digest(user_id, token),
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
    registro = database.session.scalar(
        select(RecognizedDevice).filter_by(user_id=user_id, token=_device_digest(user_id, token))
    )
    if registro is None:
        return False
    if _as_utc(registro.expires_at) < now:
        return False
    return True


def revocar_dispositivo(device_id: str) -> None:
    """Elimina un dispositivo reconocido por su ID."""
    device = database.session.get(RecognizedDevice, device_id)
    if device:
        database.session.delete(device)
        database.session.flush()
        log.debug("Device %s revoked", device_id)


def generar_token_recuperacion(user_id: str) -> str:
    """Genera un token de recuperación de contraseña y lo retorna."""
    token = secrets.token_urlsafe(32)
    token_digest = _reset_token_digest(token)
    _lock_secret_issuance(user_id)
    previos = database.session.scalars(
        select(PasswordResetToken).filter_by(user_id=user_id, consumed=False).with_for_update()
    ).all()
    for t in previos:
        t.consumed = True

    registro = PasswordResetToken(
        user_id=user_id,
        token=token_digest,
        expires_at=_now_utc() + timedelta(hours=PASSWORD_RESET_TTL_HOURS),
        consumed=False,
    )
    database.session.add(registro)
    database.session.flush()
    log.debug("Password reset token generated for user %s", user_id)
    return token


def validar_token_recuperacion(token: str, consumir: bool = True) -> User | None:
    """Valida un token de recuperación y retorna el usuario asociado.

    Retorna ``None`` si el token no existe, está expirado o ya fue consumido.
    ``consumir=False`` permite validar el enlace antes de mostrar el formulario;
    el token se marca como usado cuando se procesa el cambio de contraseña.
    """
    now = _now_utc()
    # Resolve the indexed digest without querying by the raw bearer token.
    registro = database.session.scalar(select(PasswordResetToken).filter_by(token=_reset_token_digest(token), consumed=False))
    if registro is None:
        return None
    if _as_utc(registro.expires_at) < now:
        registro.consumed = True
        database.session.flush()
        return None

    user = database.session.get(User, registro.user_id)
    if user is None or not user.active:
        registro.consumed = True
        database.session.flush()
        return None

    if consumir:
        claim = cast(
            CursorResult,
            database.session.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.id == registro.id,
                    PasswordResetToken.consumed.is_(False),
                    PasswordResetToken.expires_at >= now,
                )
                .values(consumed=True)
                .execution_options(synchronize_session=False)
            ),
        )
        if claim.rowcount != 1:
            return None
        database.session.expire(registro, ["consumed"])
        database.session.flush()
    return user


def enviar_otp_por_email(user: User, code: str) -> bool:
    """Envía un código OTP y reporta si el servidor aceptó la entrega."""
    from cacao_accounting.messaging.email import EmailError, send_email

    if not user.e_mail:
        log.warning("User %s has no email configured", user.user)
        return False
    body = (
        f"{_('Hola')} {user.name or user.user},\n\n"
        f"{_('Se detectó un intento de inicio de sesión desde un navegador no reconocido.')}\n\n"
        f"{_('Su código de verificación es:')}: {code}\n\n"
        f"{_('Este código expira en')} {OTP_TTL_MINUTES} {_('minutos')}.\n\n"
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
        return False
    return True


def enviar_token_recuperacion_email(user: User, token: str) -> bool:
    """Envía el enlace de recuperación y retorna si la entrega fue aceptada."""
    from flask import url_for

    from cacao_accounting.messaging.email import EmailError, send_email

    if not user.e_mail:
        log.warning("User %s has no email configured", user.user)
        return False
    try:
        reset_url = url_for("login.reset_password", token=token, _external=True)
    except RuntimeError:
        log.error("Cannot generate external URL without application context")
        return False

    body = (
        f"{_('Hola')} {user.name or user.user},\n\n"
        f"{_('Recibimos una solicitud para restablecer su contraseña.')}\n\n"
        f"{_('Para crear una nueva contraseña, haga clic en el siguiente enlace:')}\n\n"
        f"{reset_url}\n\n"
        f"{_('Este enlace expira en')} {PASSWORD_RESET_TTL_HOURS} {_('hora(s)')}.\n\n"
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
        return False
    return True


def usuario_tiene_email(user: User) -> bool:
    """Retorna True si el usuario tiene un correo electrónico válido."""
    return bool(user.e_mail and user.e_mail.strip())
