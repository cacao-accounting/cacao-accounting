# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidades de autenticación."""

import re
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app, redirect, session, url_for
from jwt import encode

from cacao_accounting.config import MODO_ESCRITORIO
from cacao_accounting.database import CacaoConfig as Config, User, database
from cacao_accounting.logs import log

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
    except VerifyMismatchError:
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
    if not MODO_ESCRITORIO:
        return True
    return identidad.classification == "admin"


def asignar_token_para_usuario(identidad: User) -> None:
    """Genera y asigna el token de autenticación para la API REST."""
    try:
        identidad.token = encode(
            {"user_id": identidad.id},
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        assert identidad.token is not None  # nosec
    except Exception as exc:
        assert exc is not None  # nosec
        log.warning("No se pudo generar auth token.")


def redireccion_despues_de_login():
    """Devuelve la redirección apropiada tras un inicio de sesión exitoso."""
    setup_wizard = database.session.execute(database.select(Config).filter_by(key="SETUP_COMPLETE")).first()

    if setup_wizard and setup_wizard[0].value == "False":
        session["setup_step"] = 1
        return redirect(url_for("setup.setup"))

    return redirect(url_for("cacao_app.pagina_inicio"))
