# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidades de autenticación."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import current_app, redirect, session, url_for
from jwt import encode
from jwt.exceptions import PyJWTError

from cacao_accounting.database import CacaoConfig as Config, User, database
from cacao_accounting.logs import log
from cacao_accounting.runtime_mode import is_desktop_mode

ph = PasswordHasher()


def obtener_usuario(usuario: str) -> Optional[User]:
    """Busca un usuario activo por nombre de usuario."""
    consulta = database.session.execute(database.select(User).filter_by(user=usuario)).first()
    return consulta[0] if consulta else None


def autenticar_usuario(usuario: str, clave: str) -> Optional[User]:
    """Devuelve el usuario si las credenciales son válidas."""
    registro = obtener_usuario(usuario)

    if registro is None or not registro.active:
        return None

    try:
        ph.verify(registro.password, clave)
        return registro
    except InvalidHashError:
        log.warning("Hash de contraseña inválido para el usuario {}", registro.id)
        return None
    except VerifyMismatchError:
        return None
    except VerificationError:
        # Un hash con encabezado Argon2 reconocible pero cuerpo ilegible no es
        # una credencial válida: se trata como intento fallido, sin 500 (#1965).
        log.warning("Hash de contraseña ilegible para el usuario {}", registro.id)
        return None


def validar_acceso(usuario: str, clave: str) -> bool:
    """Verifica si las credenciales provistas pertenecen a un usuario activo."""
    return autenticar_usuario(usuario, clave) is not None


def validar_clave_segura(clave: str) -> bool:
    """Verifica que la contraseña cumpla con reglas básicas de seguridad."""
    checks = {
        "min_len": len(clave) >= 8,
        "upper": bool(re.search(r"[A-Z]", clave)),
        "lower": bool(re.search(r"[a-z]", clave)),
        "digit": bool(re.search(r"\d", clave)),
        "special": bool(re.search(r"[^A-Za-z0-9]", clave)),
    }
    for rule, passed in checks.items():
        match rule:
            case "min_len" | "upper" | "lower" | "digit" | "special":
                if not passed:
                    return False
            case _:
                return False
    return True


def puede_iniciar_en_escritorio(identidad: User) -> bool:
    """Determina si el usuario puede iniciar sesión en modo escritorio."""
    if is_desktop_mode():
        if identidad.classification in {"customer", "supplier"}:
            return False
        return identidad.classification == "admin"
    return True


def _utcnow() -> datetime:
    """Devuelve el instante UTC actual para la emisión del token."""
    return datetime.now(timezone.utc)


def asignar_token_para_usuario(identidad: User) -> str | None:
    """Genera, asigna y devuelve el token de autenticación de la API REST.

    El valor se devuelve para que una emisión explícita pueda mostrarlo una
    única vez sin depender de la caché, que es opcional. La huella persistida
    en ``api_token_hash`` sigue siendo la autoridad de validación.
    """
    token: str | None = None
    try:
        ahora = _utcnow()
        payload = {
            "user_id": identidad.id,
            "auth_version": identidad.auth_version,
            "iat": ahora,
            "nbf": ahora,
            "exp": ahora + timedelta(hours=8),
            # Un identificador único evita que dos emisiones en el mismo
            # segundo produzcan el mismo JWT y reactiven uno revocado.
            "jti": uuid4().hex,
        }
        token = encode(
            payload,
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        identidad.token = token
        # La huella persistida es la autoridad cuando la caché no está disponible.
        database.session.commit()
    except (KeyError, PyJWTError) as exc:
        assert exc is not None  # nosec
        log.warning("No se pudo generar auth token.")
        return None
    return token


def revocar_credenciales_usuario(identidad: User) -> None:
    """Invalidate every browser session and API token issued to a user."""
    identidad.auth_version = User.auth_version + 1
    identidad.token = None


def redireccion_despues_de_login():
    """Devuelve la redirección apropiada tras un inicio de sesión exitoso."""
    setup_wizard = database.session.execute(database.select(Config).filter_by(key="SETUP_COMPLETE")).first()

    if setup_wizard and setup_wizard[0].value == "False":
        session["setup_step"] = 1
        return redirect(url_for("setup.setup"))

    from flask_login import current_user

    if current_user.is_authenticated:
        from cacao_accounting.portal import portal_home_for_user

        portal_home = portal_home_for_user()
        if portal_home:
            return redirect(portal_home)

    return redirect(url_for("cacao_app.pagina_inicio"))
