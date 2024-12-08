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

"""Utilidad para iniciar la aplicacion como modulo en python."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from sqlalchemy.exc import ProgrammingError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.server import server


if __name__ == "__main__":
    """Run as module python -m cacao_accounting."""

    app = create_app(ajustes=configuracion)

    try:
        server()

    except ProgrammingError:
        from cacao_accounting.database.helpers import inicia_base_de_datos

        cacao_user = environ.get("CACAO_USER") or "cacao"
        cacao_passwd = environ.get("CACAO_PSWD") or "cacao"

        inicia_base_de_datos(app=app, user=cacao_user, passwd=cacao_passwd, with_examples=False)

        server()
