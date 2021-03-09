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

from waitress import serve
from cacao_accounting import create_app
from cacao_accounting.metadata import DEVELOPMENT
from cacao_accounting.config import configuracion, THREADS
from cacao_accounting.loggin import log
from cacao_accounting.tools import inicia_base_de_datos, verifica_acceso_db, verifica_db_version


app = create_app(configuracion)
if DEVELOPMENT:
    app.config["EXPLAIN_TEMPLATE_LOADING"] = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["DEBUG"] = True


def run():
    """Ejecuta la aplicacion con Waitress como servidor WSGI"""
    log.info("Iniciando Cacao Accounting")

    if verifica_acceso_db(app):
        if verifica_db_version(app):
            log.warning("El esquema de la DB debe ser actualizado para ser compatible con este version de Cacao Accounting.")
            DB_ACCESIBLE = True
        else:
            log.info("Esquema de base de datos compatible.")
    else:
        try:
            log.warning("No se pudo acceder a la base de datos.")
            log.info("Intentando conexión y crear esquema.")
            inicia_base_de_datos(app)
            DB_ACCESIBLE = True
        except:  # noqa: E722
            log.error("No se lo logro establecer conección a la base de datos.")
            DB_ACCESIBLE = False

    if DB_ACCESIBLE:
        try:
            log.info("Iniciando servidor WSGI.")
            serve(app, port="8080", threads=THREADS)
        except OSError:
            log.error("Error al iniciar servidor WSGI, puerto 8080 actualmente en uso.")
    else:
        log.error("Error al iniciar Cacao Accounting, no fue posible establecer conexión a la DB")


if __name__ == "__main__":
    run()
