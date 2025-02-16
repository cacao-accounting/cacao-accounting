# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from loguru import logger
from waitress import serve

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting import create_app
from cacao_accounting.config import PORT, THREADS, configuracion
from cacao_accounting.database.helpers import inicia_base_de_datos


app = create_app(configuracion)
user = environ.get("CACAO_USER") or "cacao"
passwd = environ.get("CACAO_PSWD") or "cacao"

with app.app_context():
    inicia_base_de_datos(app=app, user=user, passwd=passwd, with_examples=False)
    logger.info("Iniciando servidor WSGI en puerto {puerto}.", puerto=PORT)
    serve(app, port=int(PORT), threads=int(THREADS))
