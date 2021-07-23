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
Definicion de base de datos.
El objetivo es que el sistema contable pueda ser desplegado sin tener que depender
de una base de datos especifica, la prioridad en soportar Postresql como base de datos
primaria para entornos multiusuarios y Sqlite como base de datos para entornos de un
solo usuario.
Mysql en su versión comunitaria es una opción secundaria, Mariadb no es un opción debido
a que por el momento no soportan el tipo de datos JSON.
Referencia:
 - https://mariadb.com/kb/en/json-data-type/
"""

# pylint: disable=too-few-public-methods

from os import environ
from typing import Union
from flask import Flask
from sqlalchemy_paginator import Paginator
from cacao_accounting.database import db, DBVERSION, Metadata
from cacao_accounting.exceptions import DataError, OperationalError
from cacao_accounting.exceptions.mensajes import ERROR1, ERROR4
from cacao_accounting.loggin import log
from cacao_accounting.transaccion import Transaccion


# <---------------------------------------------------------------------------------------------> #
# Herramientas auxiliares para verificar la ejecución de la base de datos.
def requiere_migracion_db(app):
    """
    Utilidad para realizar migraciones en la base de datos.
    """
    from cacao_accounting.version import VERSION

    with app.app_context():
        meta = Metadata.query.all()

    migrardb = False
    while migrardb is False:
        for i in meta:
            if (i.dbversion == DBVERSION) and (i.cacaoversion == VERSION):
                pass
            else:
                log.info("Se requiere actualizar esquema de base de datos.")
                migrardb = True
        break
    return migrardb


if environ.get("CACAO_TEST", None) or environ.get("CACAO_TEST", None):
    TIEMPO_ESPERA = 2
else:
    TIEMPO_ESPERA = 20


def verifica_coneccion_db(app):
    """
    Verifica si es posible conentarse a la base de datos.
    """
    import time

    with app.app_context():
        __inicio = time.time()
        while (time.time() - __inicio) < TIEMPO_ESPERA:
            log.info("Verificando conexión a la base de datos.")
            try:
                Metadata.query.all()
                DB_CONN = True
                log.info("Conexión a la base de datos exitosa.")
                break
            except:  # noqa: E722
                DB_CONN = False
                log.warning("No se pudo establecer conexion a la base de datos.")
                log.info("Reintentando conectar a la base de datos.")
            time.sleep(3)

    return DB_CONN


def db_metadata(app: Union[Flask, None] = None) -> None:
    """
    Actualiza metadatos en la base de datos.
    """
    from cacao_accounting.version import VERSION

    if app and isinstance(app, Flask):
        with app.app_context():
            METADATOS = Metadata(
                cacaoversion=VERSION,
                dbversion=DBVERSION,
            )
            db.session.add(METADATOS)
            db.session.commit()


def inicia_base_de_datos(app):
    """
    Inicia esquema de base datos.
    """
    from flask import current_app
    from cacao_accounting.datos import base_data, dev_data

    with app.app_context():
        log.info("Intentando inicializar base de datos.")
        try:
            db.create_all()
            if current_app.config.get("ENV") == "development" or "CACAO_TEST" in environ:

                base_data(carga_rapida=True)
                dev_data()
                db_metadata(app=app)
                DB_ESQUEMA = True
            else:
                base_data(carga_rapida=False)
                db_metadata(app=app)
                DB_ESQUEMA = True
        except:  # noqa: E722
            log.error("No se pudo iniciliazar esquema de base de datos.")
            DB_ESQUEMA = False
    return DB_ESQUEMA


MAXIMO_RESULTADOS_EN_CONSULTA_PAGINADA = 15


def paginar_consulta(tabla=None, elementos=None):
    """
    Toma una consulta simple y la devuel como una consulta paginada.
    """
    if tabla:
        items = elementos or MAXIMO_RESULTADOS_EN_CONSULTA_PAGINADA
        consulta = db.session.query(tabla).order_by(tabla.id)
        consulta_paginada = Paginator(consulta, items)
        return consulta_paginada
    else:
        raise DataError(ERROR1)


def obtener_registro_desde_uuid(tipo=None, tabla=None, tabla_detalle=None, uuid=None) -> Transaccion:
    if tabla:
        REGISTRO = tabla.query.filter_by(id=uuid).first()
        TRANSACCION = Transaccion(
            registro="Entidad",
            tipo="principal",
            accion="consultar",
            estatus_actual=REGISTRO.status,
            nuevo_estatus=None,
            uuid=REGISTRO.id,
            relaciones=None,
            relacion_id=None,
            datos=REGISTRO,
            datos_detalle=None,
        )
        return TRANSACCION
    else:
        raise OperationalError(ERROR4)
