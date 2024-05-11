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

"""Datos básicos para iniciar el sistema."""

from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import crea_roles_predeterminados, asigna_rol_a_usuario
from cacao_accounting.loggin import log
from cacao_accounting.modulos import _init_modulos
from cacao_accounting.transaccion import Transaccion

# pylint: disable=import-outside-toplevel


def registra_monedas(carga_rapida=False):
    """Carga de monedas al sistema."""
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
        MONEDA.ejecutar_transaccion(nio)
        MONEDA.ejecutar_transaccion(usd)
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
            MONEDA.ejecutar_transaccion(moneda)
    log.debug("Monedas cargadas Correctamente")


def crea_usuario_admin(user: str, passwd: str):
    """
    Crea el usuario administrador.

    Si no se encuentra definido a nivel de variables de entorno se crea utilizando valores
    predeterminados, no se recomienda utilizar los valores predeterminados si la instancia va
    a estar expuesta de forma publica a la internet.
    """
    from flask import current_app
    from cacao_accounting.auth import proteger_passwd
    from cacao_accounting.database import Usuario, database

    log.info("Creando Usuario Administrador")

    with current_app.app_context():
        usuario = Usuario(usuario=user, clave_acceso=proteger_passwd(passwd))
        database.session.add(usuario)
        database.session.commit()
        asigna_rol_a_usuario(usuario=user, rol="admin")


def __cargar_roles_al_sistema() -> None:
    """Carga roles de desarrollo a la base de datos."""
    crea_roles_predeterminados()


def base_data(user, passwd, carga_rapida=False):
    """Definición de metodo para cargar información base al sistema."""
    log.debug("Iniciando carga de datos base al sistema.")
    _init_modulos()
    __cargar_roles_al_sistema()
    cargar_permisos_predeterminados()
    crea_usuario_admin(user, passwd)
    registra_monedas(carga_rapida=carga_rapida)
    log.debug("Batos base cargados en la base de datos.")
