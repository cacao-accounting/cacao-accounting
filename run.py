# Copyright 2025 William José Moreno Reyes
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

"""Cacao Accounting simple init scritp."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from loguru import logger
from waitress import serve
from sqlalchemy.exc import OperationalError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting import create_app
from cacao_accounting.config import PORT, THREADS, configuracion
from cacao_accounting.database.helpers import verifica_coneccion_db, usuarios_creados
from cacao_accounting.database.helpers import inicia_base_de_datos


app = create_app(configuracion)
user = environ.get("CACAO_USER") or "cacao"
passwd = environ.get("CACAO_PSWD") or "cacao"

if verifica_coneccion_db(app=app):
    with app.app_context():

        if not usuarios_creados():
            try:
                inicia_base_de_datos(app=app, user=user, passwd=passwd, with_examples=False)
                db = True
            except OperationalError:
                logger.warning("Hubo un error al inicializar la base de datos.")
                db = False
        else:
            db = True


if not db:
    logger.warning("No se pudo iniciar el servicio.")
else:
    logger.info("Iniciando servidor WSGI en puerto {puerto}.", puerto=PORT)
    serve(app, port=int(PORT), threads=int(THREADS))
