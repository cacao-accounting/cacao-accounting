# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio administrativo de seguridad de sesión."""

from __future__ import annotations

from flask import request
from sqlalchemy import select

from cacao_accounting.database import CacaoConfig, RecognizedDevice, User, database
from cacao_accounting.messaging.email import get_smtp_setting

SESSION_SECURITY_KEY = "session_security_enabled"


def smtp_is_configured() -> bool:
    """Retorna True si SMTP está configurado con servidor y remitente."""
    server = (get_smtp_setting("smtp_server") or "").strip()
    from_email = (get_smtp_setting("smtp_from_email") or "").strip()
    return bool(server and from_email)


def is_session_security_enabled() -> bool:
    """Retorna True si la protección de orígenes está activada."""
    registro = database.session.execute(select(CacaoConfig).filter_by(key=SESSION_SECURITY_KEY)).scalar_one_or_none()
    return registro is not None and registro.value == "true"


def set_session_security_enabled(enabled: bool) -> None:
    """Activa o desactiva la protección de orígenes."""
    valor = "true" if enabled else "false"
    registro = database.session.execute(select(CacaoConfig).filter_by(key=SESSION_SECURITY_KEY)).scalar_one_or_none()
    if registro:
        registro.value = valor
    else:
        database.session.add(CacaoConfig(key=SESSION_SECURITY_KEY, value=valor))
    database.session.flush()


def listar_dispositivos_usuario(user_id: str) -> list[RecognizedDevice]:
    """Lista dispositivos reconocidos de un usuario específico."""
    return list(
        database.session.scalars(
            select(RecognizedDevice).filter_by(user_id=user_id).order_by(RecognizedDevice.created.desc())
        ).all()
    )


def listar_todos_dispositivos() -> list[tuple[RecognizedDevice, str]]:
    """Lista todos los dispositivos reconocidos con el nombre del usuario."""
    rows = database.session.execute(
        select(RecognizedDevice, User.user)
        .join(User, RecognizedDevice.user_id == User.id)
        .order_by(RecognizedDevice.created.desc())
    ).all()
    return [(device, username) for device, username in rows]


def revocar_dispositivo(device_id: str) -> bool:
    """Revoca un dispositivo. Retorna True si existía."""
    device = database.session.get(RecognizedDevice, device_id)
    if device is None:
        return False
    database.session.delete(device)
    database.session.flush()
    return True


def usuario_actual_ip() -> str:
    """Retorna la IP del cliente actual."""
    if request and request.remote_addr:
        return request.remote_addr
    return "unknown"


def listar_cuentas_bloqueadas() -> list[tuple[User, int]]:
    """Retorna usuarios bloqueados con sus segundos restantes de lockout."""
    from cacao_accounting.auth.account_throttling import listar_cuentas_bloqueadas as _listar

    return _listar()


def desbloquear_cuenta_usuario(user_id: str) -> bool:
    """Desbloquea una cuenta de usuario. Retorna True si existía y estaba bloqueada."""
    from cacao_accounting.auth.account_throttling import desbloquear_cuenta

    usuario = database.session.get(User, user_id)
    if usuario is None:
        return False
    if not usuario.lockout_until and (not usuario.failed_login_count or usuario.failed_login_count == 0):
        return False
    desbloquear_cuenta(usuario)
    database.session.flush()
    return True
