# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Protección contra credential stuffing por cuenta de usuario.

Implementa cooldown temporal exponencial con auto-unlock para cuentas
que exceden un umbral de intentos de inicio de sesión fallidos.

Política de bloqueo:
    1-4  intentos → sin restricción
    5    intentos → lock 1 minuto
    6    intentos → lock 5 minutos
    7    intentos → lock 15 minutos
    8+   intentos → lock 30 minutos
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from cacao_accounting.database import User, database
from cacao_accounting.document_flow.status import _
from cacao_accounting.logs import log

LOCKOUT_THRESHOLDS: list[tuple[int, int]] = [
    (5, 1),
    (6, 5),
    (7, 15),
    (8, 30),
]

THRESHOLD_DEFAULT_MINUTES = 30
LOCKOUT_COUNT_RESET = 0


def _now_utc() -> datetime:
    """Retorna la hora UTC actual como datetime naive para compatibilidad con SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lockout_minutes(failed_count: int) -> int:
    """Retorna los minutos de bloqueo según el número de intentos fallidos."""
    for threshold, minutes in reversed(LOCKOUT_THRESHOLDS):
        if failed_count >= threshold:
            return minutes
    return 0


def esta_bloqueada(usuario: User) -> bool:
    """Retorna True si la cuenta está bloqueada temporalmente."""
    if usuario.lockout_until is None:
        return False
    ahora = _now_utc()
    if usuario.lockout_until > ahora:
        return True
    _desbloquear_cuenta(usuario)
    return False


def registrar_intento_fallido(usuario: User) -> int:
    """Registra un intento fallido y retorna el nuevo conteo de intentos.

    Aplica el cooldown temporal exponencial cuando se alcanza el umbral.
    """
    from cacao_accounting.audit_trail_service import log_login_failed

    usuario.failed_login_count = (usuario.failed_login_count or 0) + 1
    usuario.last_failed_login = _now_utc()

    minutos = _lockout_minutes(usuario.failed_login_count)
    if minutos > 0:
        usuario.lockout_until = _now_utc() + timedelta(minutes=minutos)
        log.warning(
            "Account %s locked for %d minutes after %d failed attempts",
            usuario.user,
            minutos,
            usuario.failed_login_count,
        )

    try:
        log_login_failed(usuario.id, usuario.user, usuario.failed_login_count)
    except Exception:
        log.debug("Could not log failed login to audit trail")

    database.session.flush()
    log.debug("Failed login recorded for %s (count=%d)", usuario.user, usuario.failed_login_count)
    return usuario.failed_login_count


def registrar_intento_exitoso(usuario: User) -> None:
    """Resetea el contador de intentos fallidos tras un login exitoso."""
    if usuario.failed_login_count and usuario.failed_login_count > 0:
        usuario.failed_login_count = 0
        usuario.lockout_until = None
        database.session.flush()
        log.debug("Login counters reset for %s", usuario.user)


def _desbloquear_cuenta(usuario: User) -> None:
    """Desbloquea una cuenta cuyo lockout ya expiró."""
    usuario.lockout_until = None
    database.session.flush()


def desbloquear_cuenta(usuario: User) -> None:
    """Desbloqueo manual de cuenta por administrador."""
    from cacao_accounting.audit_trail_service import log_account_unlocked

    usuario.failed_login_count = 0
    usuario.lockout_until = None
    database.session.flush()
    try:
        log_account_unlocked(usuario.id, usuario.user, "admin")
    except Exception:
        log.debug("Could not log account unlock to audit trail")
    log.info("Account %s manually unlocked", usuario.user)


def tiempo_restante_bloqueo(usuario: User) -> int | None:
    """Retorna los segundos restantes de bloqueo, o None si no está bloqueado."""
    if usuario.lockout_until is None:
        return None
    ahora = _now_utc()
    delta = usuario.lockout_until - ahora
    if delta.total_seconds() <= 0:
        _desbloquear_cuenta(usuario)
        return None
    return int(delta.total_seconds())


def listar_cuentas_bloqueadas() -> list[tuple[User, int]]:
    """Retorna usuarios bloqueados con sus segundos restantes de lockout."""
    resultado: list[tuple[User, int]] = []
    usuarios = database.session.scalars(select(User).filter(User.lockout_until.isnot(None))).all()
    ahora = _now_utc()
    for u in usuarios:
        if u.lockout_until and u.lockout_until > ahora:
            segundos = int((u.lockout_until - ahora).total_seconds())
            resultado.append((u, segundos))
    return resultado


def notificar_intento_fallido(usuario: User) -> None:
    """Envía correo de alerta al usuario tras intentos fallidos."""
    from cacao_accounting.messaging.email import EmailError, send_email

    if not usuario.e_mail:
        return

    intentos = usuario.failed_login_count or 0
    minutos = _lockout_minutes(intentos)

    if minutos > 0:
        asunto = _("Cacao Accounting - Cuenta bloqueada temporalmente")
        cuerpo = (
            f"{'Hola'} {usuario.name or usuario.user},\n\n"
            f"{_('Se detectaron múltiples intentos fallidos de inicio de sesión en su cuenta.')}\n\n"
            f"{_('Su cuenta ha sido bloqueada temporalmente por')} {minutos} "
            f"{'minuto(s)'}.\n\n"
            f"{_('Si usted no realizó estos intentos, cambie su contraseña y contacte al administrador.')}"
        )
    else:
        asunto = _("Cacao Accounting - Alerta de seguridad")
        cuerpo = (
            f"{'Hola'} {usuario.name or usuario.user},\n\n"
            f"{_('Se detectó un intento fallido de inicio de sesión en su cuenta.')}\n\n"
            f"{_('Si usted no realizó este intente, cambie su contraseña.')}"
        )

    try:
        send_email(
            to_email=usuario.e_mail,
            subject=str(asunto),
            body=cuerpo,
            is_html=False,
        )
    except EmailError as exc:
        log.error("Error sending failed login notification to %s: %s", usuario.e_mail, exc)
