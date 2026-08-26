# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Funciones auxiliares para usar en las rutas de la aplicación."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from functools import wraps

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import abort, flash
from flask_login import current_user
from werkzeug.exceptions import HTTPException

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.modulos import validar_modulo_activo


def modulo_activo(modulo):  # pragma: no cover
    """Verifica si el recurso solicitado pertenece a un modulo activo."""
    modulos = [modulo] if isinstance(modulo, str) else list(modulo)

    def decorator_modulo_activo(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if any(validar_modulo_activo(modulo_nombre) for modulo_nombre in modulos):
                return func(*args, **kwargs)
            else:
                flash("El modulo que intenta acceder se encuentra inactivo")
                return abort(404)

        return wrapper

    return decorator_modulo_activo


def verifica_acceso(modulo):  # pragma: no cover
    """Comprueba si un usuario tiene acceso a un recurso determinado."""

    def decorator_verifica_acceso(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("No se encuentra autorizado a acceder al recurso solicitado.")
                return abort(403)
            module_id = obtener_id_modulo_por_nombre(modulo)
            permisos = Permisos(modulo=module_id, usuario=current_user.id)
            if permisos.autorizado:
                return func(*args, **kwargs)
            else:
                flash("No se encuentra autorizado a acceder al recurso solicitado.")
                return abort(403)

        return wrapper

    return decorator_verifica_acceso


def verifica_permiso(modulo: str, accion: str):
    """Require a concrete action permission for a state-changing route."""

    def decorator_verifica_permiso(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("No se encuentra autorizado para ejecutar esta acción.")
                return abort(403)
            module_id = obtener_id_modulo_por_nombre(modulo)
            permisos = Permisos(modulo=module_id, usuario=current_user.id)
            if getattr(permisos, accion, False):
                return func(*args, **kwargs)
            flash("No se encuentra autorizado para ejecutar esta acción.")
            return abort(403)

        return wrapper

    return decorator_verifica_permiso


def exige_acceso_compania(
    modulo: str, company: str | None, accion: str = "consultar", allow_unauthenticated: bool = False
) -> None:
    """Enforce module/action RBAC and explicit company access.

    Args:
        modulo: Module name (e.g., "sales", "purchases", "accounting")
        company: Company code to check access against
        accion: Action type (consultar, crear, editar, autorizar, anular)
        allow_unauthenticated: If True, allows internal services without authentication.
                               Must be explicitly set; default is False to prevent
                               accidental privilege escalation.
    """
    try:
        is_auth = bool(current_user and getattr(current_user, "is_authenticated", False))
    except Exception:
        is_auth = False

    if not is_auth:
        if not allow_unauthenticated:
            abort(403)
        return
    module_id = obtener_id_modulo_por_nombre(modulo)
    permisos = Permisos(modulo=module_id, usuario=current_user.id)
    if permisos.administrador:
        return
    permission_name = {
        "autorizar": "autorizar",
        "anular": "anular",
        "crear": "crear",
        "editar": "editar",
        "consultar": "consultar",
    }.get(accion, "consultar")
    if getattr(permisos, permission_name, False) and permisos.tiene_acceso_compania(company):
        return
    abort(403)


def exige_acceso_compania_cualquiera(modulos: tuple[str, ...], company: str | None, accion: str = "consultar") -> None:
    """Require company access in at least one of several operational modules."""
    for modulo in modulos:
        try:
            exige_acceso_compania(modulo, company, accion)
            return
        except HTTPException as exc:
            if exc.code != 403:
                raise
    abort(403)
