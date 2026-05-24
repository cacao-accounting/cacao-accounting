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
