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
from cacao_accounting.conf import configuracion
from cacao_accounting.loggin import log

app = create_app(configuracion)
if DEVELOPMENT:
    app.config["EXPLAIN_TEMPLATE_LOADING"] = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["DEBUG"] = True


def run():
    """Ejecuta la aplicacion con Waitress como servidor WSGI"""
    try:
        serve(app, port=8080)
        log.info("Servicidor WSGI iniciando correctamente en puerto 8080")
    except OSError:
        log.error("Puerto 8080 actualmente en uso.")


if __name__ == "__main__":
    run()
