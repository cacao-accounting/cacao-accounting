# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidad para iniciar la aplicacion como modulo en python."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ
from time import sleep

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from sqlalchemy.exc import ProgrammingError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database.helpers import usuarios_creados
from cacao_accounting.logs import log
from cacao_accounting.server import server

if __name__ == "__main__":
    """Run as module python -m cacao_accounting."""

    app = create_app(ajustes=configuracion)
    app.app_context().push()

    if usuarios_creados():
        server()

    else:
        # Wait the database 15 senconds
        sleep(15)

        if usuarios_creados():
            server()

        else:

            try:
                from cacao_accounting.database.helpers import inicia_base_de_datos

                log.info("Inicializando Cacao Accounting.")

                cacao_user = environ.get("CACAO_USER") or "cacao"
                cacao_passwd = environ.get("CACAO_PSWD") or "cacao"

                inicia_base_de_datos(app=app, user=cacao_user, passwd=cacao_passwd, with_examples=False)
                server()

            except ProgrammingError:
                log.warning("No se pudo iniciar Cacao Accounting.")
