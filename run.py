# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cacao Accounting simple init scritp."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from os import environ
import sys

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

flask_env = (environ.get("FLASK_ENV") or "").lower()
env = (environ.get("ENV") or "").lower()

# Se asume modo desarrollo si alguna variable de entorno está explícitamente en "dev" o "development"
is_dev = flask_env in ("dev", "development") or env in ("dev", "development")

user = environ.get("CACAO_USER")
passwd = environ.get("CACAO_PSWD")

if not user or not passwd:
    if not is_dev:
        logger.critical("CACAO_USER and CACAO_PSWD must be set in environment")
        sys.exit(1)
    else:
        user = user or "cacao"
        passwd = passwd or "cacao"

if verifica_coneccion_db(app=app):
    with app.app_context():

        if not usuarios_creados():
            if user == "cacao" and passwd == "cacao":
                logger.warning("Se están usando usuario y contraseña predeterminados para el setup inicial.")
            try:
                inicia_base_de_datos(app=app, user=user, passwd=passwd, with_examples=False)
                db = True
            except OperationalError:
                logger.warning("Hubo un error al inicializar la base de datos.")
                db = False
        else:
            db = True
else:
    with app.app_context():
        try:
            if not usuarios_creados():
                if user == "cacao" and passwd == "cacao":
                    logger.warning("Se están usando usuario y contraseña predeterminados para el setup inicial.")
            inicia_base_de_datos(app=app, user=user, passwd=passwd, with_examples=False)
            db = True
        except OperationalError:
            logger.warning("Hubo un error al inicializar la base de datos.")
            db = False


if not db:
    logger.warning("No se pudo iniciar el servicio.")
else:
    logger.info("Iniciando servidor WSGI en puerto {puerto}.", puerto=PORT)
    serve(app, port=int(PORT), threads=int(THREADS))
