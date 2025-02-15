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
from sqlalchemy.exc import OperationalError, InterfaceError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import database
from cacao_accounting.logs import log

MAXIMO_RESULTADOS_EN_CONSULTA_PAGINADA = 10

# <---------------------------------------------------------------------------------------------> #
# Herramientas auxiliares para verificar la ejecución de la base de datos.

if environ.get("CACAO_TEST", None):  # pragma: no cover
    TIEMPO_ESPERA = 0
else:
    TIEMPO_ESPERA = 20


def verifica_coneccion_db(app):  # pragma: no cover
    """Verifica si es posible conentarse a la base de datos."""
    import time

    with app.app_context():
        __inicio = time.time()
        while (time.time() - __inicio) < TIEMPO_ESPERA:
            log.info("Verificando conexión a la base de datos.")
            try:
                from cacao_accounting.database import User

                QUERY = database.session.execute(database.select(User)).first()

                if QUERY:
                    DB_CONN = True
                    log.info("Conexión a la base de datos exitosa.")
                break
            except OperationalError:
                DB_CONN = False
                log.warning("No se pudo establecer conexion a la base de datos.")
                log.info("Reintentando conectar a la base de datos.")
            except InterfaceError:
                DB_CONN = False
                log.warning("No se pudo establecer conexion a la base de datos.")
                log.info("Reintentando conectar a la base de datos.")

            if not environ.get("CACAO_TEST", None):
                time.sleep(2)

        try:
            if not DB_CONN:
                log.warning("No fue imposible establecer una conexión con la base de datos.")
            return DB_CONN
        except UnboundLocalError:
            return False


def entidades_creadas():
    """Verifica si al menos una entidad ha sido creado en el sistema."""
    from cacao_accounting.database import Entity

    try:
        CONSULTA = database.session.execute(database.select(Entity)).first()

        if CONSULTA:
            return True
        else:
            return False

    except:  # noqa: E722
        return False


def usuarios_creados():
    """Verifica si al menos un usuario ha sido creado en el sistema."""
    from cacao_accounting.database import User

    try:
        CONSULTA = database.session.execute(database.select(User)).first()

        if CONSULTA:
            return True
        else:
            return False

    except:  # noqa: E722
        return False


def inicia_base_de_datos(app: Flask, user: str, passwd: str, with_examples: bool) -> bool:  # pragma: no cover
    """Inicia esquema de base datos."""
    from cacao_accounting.datos import base_data, dev_data

    if entidades_creadas():
        pass

    else:
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

        if not with_examples:
            from cacao_accounting.database import CacaoConfig as Config

            config = Config(
                key="SETUP_COMPLETE",
                value="False",
            )

            database.session.add(config)
            database.session.commit()

    return DB_ESQUEMA


def obtener_id_modulo_por_nombre(modulo: Union[str, None]) -> Union[str, None]:
    """Devuelve el UUID de un modulo por su nombre."""
    if modulo:
        from cacao_accounting.database import Modules, database

        MODULO = database.session.execute(database.select(Modules).filter_by(module=modulo)).first()
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
        from cacao_accounting.database import User

        USUARIO = User.query.filter_by(user=usuario).first()
        return USUARIO.id
    else:
        return None


def db_version():  # pragma: no cover
    """Return database version as text."""
    from flask import current_app
    from cacao_accounting.database import database
    from sqlalchemy.sql import text

    with current_app.app_context():
        DABATASE_URI = current_app.config.get("SQLALCHEMY_DATABASE_URI")

        if DABATASE_URI.startswith("mysql+pymysql"):
            Q = database.session.execute(text("SELECT version();"))
            for i in Q:
                db_version = str(i)
        elif DABATASE_URI.startswith("postgresql+pg8000"):
            Q = database.session.execute(text("SELECT VERSION();"))
            for i in Q:
                db_version = str(i)
        else:
            Q = database.session.execute(text("select sqlite_version();"))
            for i in Q:
                db_version = str(i)

    return db_version
