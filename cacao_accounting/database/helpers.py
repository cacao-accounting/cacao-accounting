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

"""Funciones auxiliares relacionadas a la base de datos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ
from typing import Union

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Flask
from sqlalchemy.exc import OperationalError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import database
from cacao_accounting.logs import log

MAXIMO_RESULTADOS_EN_CONSULTA_PAGINADA = 10


# <---------------------------------------------------------------------------------------------> #
# Herramientas auxiliares para verificar la ejecución de la base de datos.

if environ.get("CACAO_TEST", None):
    TIEMPO_ESPERA = 2
else:
    TIEMPO_ESPERA = 20


def verifica_coneccion_db(app):
    """Verifica si es posible conentarse a la base de datos."""
    import time

    with app.app_context():
        __inicio = time.time()
        while (time.time() - __inicio) < TIEMPO_ESPERA:
            log.info("Verificando conexión a la base de datos.")
            try:
                from cacao_accounting.database import Usuario

                QUERY = database.session.execute(database.select(Usuario)).first()

                if QUERY:
                    DB_CONN = True
                    log.info("Conexión a la base de datos exitosa.")
                break
            except OperationalError:
                DB_CONN = False
                log.warning("No se pudo establecer conexion a la base de datos.")
                log.info("Reintentando conectar a la base de datos.")
            time.sleep(3)

        if not DB_CONN:
            log.warning("No fue imposible establecer una conexión con la base de datos.")

    return DB_CONN


def inicia_base_de_datos(app: Flask, user: str, passwd: str, with_examples: bool) -> bool:
    """Inicia esquema de base datos."""
    from cacao_accounting.datos import base_data, dev_data

    log.info("Intentando inicializar base de datos.")

    with app.app_context():
        try:
            database.create_all()
            log.info("Esquema de base de datos creado correctamente.")
            if with_examples:
                log.trace("Creando datos de prueba.")
                base_data(user, passwd, carga_rapida=False)
                dev_data()
            else:
                base_data(user, passwd, carga_rapida=True)
            DB_ESQUEMA = True
        except OperationalError:
            log.error("No se pudo iniciliazar esquema de base de datos.")
            DB_ESQUEMA = False
    return DB_ESQUEMA


def obtener_id_modulo_por_nombre(modulo: Union[str, None]) -> Union[str, None]:
    """Devuelve el UUID de un modulo por su nombre."""
    if modulo:
        from cacao_accounting.database import Modulos, database

        MODULO = database.session.execute(database.select(Modulos).filter_by(modulo=modulo)).first()
        return MODULO[0].id
    else:
        return None


def obtener_id_rol_por_monbre(rol: str) -> str:
    """Devuelve el UUID de un rol en base a su nombre."""
    from cacao_accounting.database import Roles

    ROL = Roles.query.filter_by(name=rol).first()
    return ROL.id


def obtener_id_usuario_por_nombre(usuario: Union[str, None]) -> Union[str, None]:
    """Devuelve el UUID de un usuario en base a su id."""
    if usuario:
        from cacao_accounting.database import Usuario

        USUARIO = Usuario.query.filter_by(usuario=usuario).first()
        return USUARIO.id
    else:
        return None


def entidades_creadas():
    """Verifica si al menos una entidad ha sido creado en el sistema."""
    from cacao_accounting.database import Entidad

    CONSULTA = database.session.execute(database.select(Entidad)).first()
    log.warning(CONSULTA[0])

    if CONSULTA:
        return True
    else:
        return False
