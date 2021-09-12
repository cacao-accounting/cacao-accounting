# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes

"""Funciones auxiliares para usar en las rutas de la aplicación."""

from functools import wraps
from flask import flash, abort
from flask_login import current_user
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.modulos import validar_modulo_activo


def modulo_activo(modulo):
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


def verifica_acceso(modulo):
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
