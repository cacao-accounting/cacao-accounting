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

"""Utilidad para iniciar el servidor local WSGI usando Waitress."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from waitress import serve  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting import create_app
from cacao_accounting.config import PORT, THREADS, configuracion
from cacao_accounting.logs import log

# <---------------------------------------------------------------------------------------------> #
# Esta es la aplicación por defecto.
# Utiliza la configuración predeterminada, por lo tanto se recomienda establecer los parametros de
# configuracíón desde las variables de entorno.
app = create_app(configuracion)


def server() -> None:
    """Ejecuta la aplicacion con Waitress como servidor WSGI."""
    from cacao_accounting.database.helpers import inicia_base_de_datos, verifica_coneccion_db

    log.info("Iniciando Cacao Accounting.")
    if verifica_coneccion_db(app):
        DATABASE = True
    else:
        from sqlalchemy.exc import OperationalError

        log.warning("No se logro conectar a la base de datos.")
        log.info("Intentando inicializar base de datos.")
        try:
            inicia_base_de_datos(
                app, user=environ.get("CACAO_USER") or "cacao", passwd=environ.get("CACAO_PWD") or "cacao", with_examples=False
            )
            DATABASE = True
        except OperationalError:
            log.error("No se pudo inicilizar la base de datos.")
            DATABASE = False

    if DATABASE:
        try:
            log.info("Iniciando servidor WSGI en puerto {puerto}.", puerto=PORT)
            serve(app, port=PORT, threads=THREADS)
        except OSError:
            log.error("Puerto 8080 actualmente en uso.")
    else:
        log.error("No se logro establecer con la base de datos.")
