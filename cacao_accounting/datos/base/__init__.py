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
Datos básicos para iniciar el sistema.
"""

from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import crea_roles_predeterminados, asigna_rol_a_usuario
from cacao_accounting.loggin import log
from cacao_accounting.modulos import _init_modulos
from cacao_accounting.transaccion import Transaccion

# pylint: disable=import-outside-toplevel


def registra_monedas(carga_rapida=False):
    from teritorio import Currencies
    from cacao_accounting.contabilidad.registros.moneda import RegistroMoneda

    log.debug("Iniciando carga de base monedas a la base de datos.")
    MONEDA = RegistroMoneda()
    if carga_rapida:

        nio = Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={"codigo": "NIO", "nombre": "Cordobas Oro", "decimales": 2},
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
        usd = Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={"codigo": "USD", "nombre": "Dolares de los Estados Unidos", "decimales": 2},
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
        MONEDA.ejecutar_transaccion_a_la_db(nio)
        MONEDA.ejecutar_transaccion_a_la_db(usd)
    else:
        for currency in Currencies():
            moneda = Transaccion(
                registro="Moneda",
                tipo="principal",
                estatus_actual=None,
                nuevo_estatus=None,
                uuid=None,
                accion="crear",
                datos={"codigo": currency.code, "nombre": currency.name, "decimales": currency.minor_units},
                datos_detalle=None,
                relaciones=None,
                relacion_id=None,
            )
            MONEDA.ejecutar_transaccion_a_la_db(moneda)
    log.debug("Monedas cargadas Correctamente")


def crea_usuario_admin():
    from os import environ
    from cacao_accounting.auth import proteger_passwd
    from cacao_accounting.auth.registros import RegistroUsuario

    log.info("Creando Usuario Administrador")
    USUARIO = RegistroUsuario()
    USER = environ.get("CACAO_USER", None) or "cacao"
    PWD = environ.get("CACAO_PWD", None) or "cacao"
    if environ.get("CACAO_USER", None) and environ.get("CACAO_PWD", None):
        log.info("Creando Usuario Administrador desde variables de entorno")
    else:
        log.warning("No se encontrato valores para usuario administrador, usando predeterminados")
    usuario = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": USER,
            "clave_acceso": proteger_passwd(PWD),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion_a_la_db(usuario)
    asigna_rol_a_usuario(USER, "admin")


def base_data(carga_rapida=False):
    """
    Definición de metodo para cargar información base al sistema.
    """
    log.debug("Iniciando carga de datos base al sistema.")
    crea_roles_predeterminados()
    cargar_permisos_predeterminados()
    crea_usuario_admin()
    registra_monedas(carga_rapida=carga_rapida)
    _init_modulos()
    log.debug("Batos base cargados en la base de datos.")
