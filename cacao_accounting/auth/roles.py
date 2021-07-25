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

"""
Definicion de Roles para regular el acceso al sistema de los usuarios.
"""

from cacao_accounting.loggin import log
from cacao_accounting.transaccion import Transaccion
from cacao_accounting.registro import Registro


class RegistroRol(Registro):
    def __init__(self):
        from cacao_accounting.database import Roles

        self.tabla = Roles


# Tipos de acceso:
ACCESO_COMPLETO = [
    "actualizar",
    "anular",
    "autorizar",
    "consultar",
    "cerrar",
    "crear",
    "eliminar",
    "validar",
]

ACCESO_OPERATIVO = [
    "actualizar",
    "anular",
    "autorizar",
    "consultar",
    "cerrar",
    "crear",
    "validar",
]

ACCESO_LECTURA = [
    "consultar",
]

ACCESO_USUARIO = [
    "actualizar",
    "autorizar",
    "consultar",
    "cambiar_estado",
    "crear",
    "validar",
]

ADMINISTRADOR = {
    "name": "admin",
    "detalle": "Administrador del Sistema",
    "allowances": {
        "metadata": ACCESO_COMPLETO,
        "moneda": ACCESO_COMPLETO,
        "tasa_de_cambio": ACCESO_COMPLETO,
        "usuario": ACCESO_COMPLETO,
        "roles": ACCESO_COMPLETO,
        "permisos_rol": ACCESO_COMPLETO,
        "user_role": ACCESO_COMPLETO,
        "modulos": ACCESO_COMPLETO,
        "entidad": ACCESO_COMPLETO,
        "unidad": ACCESO_COMPLETO,
        "cuentas": ACCESO_COMPLETO,
        "centro_costo": ACCESO_COMPLETO,
        "proyecto": ACCESO_COMPLETO,
        "periodo_contable": ACCESO_COMPLETO,
        "cliente": ACCESO_COMPLETO,
        "cliente_direccion": ACCESO_COMPLETO,
        "cliente_contacto": ACCESO_COMPLETO,
        "proveedor": ACCESO_COMPLETO,
        "proveedor_direccion": ACCESO_COMPLETO,
        "proveedor_contacto": ACCESO_COMPLETO,
    },
}

ROLES_PREDETERMINADOS = [ADMINISTRADOR]


def crea_roles_predeterminados() -> None:
    log.debug("Iniciando creacion de Roles predeterminados.")
    for ROL in ROLES_PREDETERMINADOS:
        REGISTRO = RegistroRol()
        REGISTRO.ejecutar_transaccion_a_la_db(
            Transaccion(
                registro="Usuario",
                tipo="principal",
                estatus_actual=None,
                nuevo_estatus=None,
                uuid=None,
                accion="crear",
                datos=ROL,
                datos_detalle=None,
                relaciones=None,
                relacion_id=None,
            )
        )
