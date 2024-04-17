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

"""Utilidad para iniciar el servidor local WSGI usando Waitress."""

from waitress import serve  # type: ignore[import]
from cacao_accounting import create_app
from cacao_accounting.config import configuracion, PORT, THREADS
from cacao_accounting.loggin import log

app = create_app(configuracion)


def server() -> None:
    """Ejecuta la aplicacion con Waitress como servidor WSGI."""
    from cacao_accounting.database.helpers import inicia_base_de_datos, requiere_migracion_db, verifica_coneccion_db

    log.info("Iniciando Cacao Accounting.")
    if verifica_coneccion_db(app):
        DATABASE = requiere_migracion_db(app) is False
    else:
        from sqlalchemy.exc import OperationalError

        log.warning("No se logro conectar a la base de datos.")
        log.info("Intentando inicializar base de datos.")
        try:
            inicia_base_de_datos(app)
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
