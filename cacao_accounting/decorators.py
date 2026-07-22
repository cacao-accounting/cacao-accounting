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
from flask import abort, flash, request
from flask_login import current_user

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
            libros = _libros_contables_solicitados(modulo)
            permisos = Permisos(modulo=module_id, usuario=current_user.id)
            if permisos.autorizado and _tiene_acceso_a_libros(module_id, libros):
                return func(*args, **kwargs)
            else:
                flash("No se encuentra autorizado a acceder al recurso solicitado.")
                return abort(403)

        return wrapper

    return decorator_verifica_acceso


def verifica_permiso(modulo: str, accion: str):  # pragma: no cover
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
    """Enforce module/action access to at least one book of a company.

    Operational documents carry a company but not a user-specific company
    ACL. Company access is therefore derived from the user's authorized books;
    administrators retain global access.

    Args:
        modulo: Module name (e.g., "sales", "purchases", "accounting")
        company: Company code to check access against
        accion: Action type (consultar, crear, editar, autorizar, anular)
        allow_unauthenticated: If True, allows internal services without authentication.
                               Must be explicitly set; default is False to prevent
                               accidental privilege escalation.
    """
    if not current_user.is_authenticated:
        if not allow_unauthenticated:
            abort(403)
        return
    module_id = obtener_id_modulo_por_nombre(modulo)
    permisos = Permisos(modulo=module_id, usuario=current_user.id)
    if permisos.administrador:
        return
    granular_action = {
        "autorizar": "can_approve",
        "anular": "can_cancel",
        "crear": "can_write",
        "editar": "can_write",
        "consultar": "can_read",
    }.get(accion, "can_read")
    if permisos.autorizado and permisos.obtener_libros_autorizados(granular_action, company=company):
        return
    abort(403)


def _libros_contables_solicitados(modulo: str) -> list[str]:
    """Extrae libros de la peticion solo para rutas del modulo contable."""
    if modulo != "accounting":
        return []
    form_books = request.form.getlist("books") if request.method == "POST" else []
    candidates = [
        request.args.get("ledger"),
        request.form.get("ledger"),
        request.form.get("ledger_id"),
        *form_books,
    ]
    return [book for book in candidates if book]


def _tiene_acceso_a_libros(module_id: str | None, libros: list[str]) -> bool:
    """Valida acceso de lectura a todos los libros contables solicitados."""
    if not libros:
        return True
    return all(Permisos(modulo=module_id, usuario=current_user.id, libro=libro).autorizado for libro in libros)
