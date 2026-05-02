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

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.modulos import validar_modulo_activo


def modulo_activo(modulo):  # pragma: no cover
    """Verifica si el recurso solicitado pertenece a un modulo activo."""

    def decorator_modulo_activo(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if validar_modulo_activo(modulo):
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
            PERMISOS = Permisos(modulo=obtener_id_modulo_por_nombre(modulo), usuario=current_user.id)
            if PERMISOS.autorizado:
                return func(*args, **kwargs)
            else:
                flash("No se encuentra autorizado a acceder al recurso solicitado.")
                return abort(403)

        return wrapper

    return decorator_verifica_acceso
