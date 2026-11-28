# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cacao Accounting simple init script."""

import sys

from loguru import logger
from waitress import serve

from cacao_accounting import create_app
from cacao_accounting.config import PORT, THREADS, configuracion
from cacao_accounting.database.helpers import verifica_coneccion_db, verificar_esquema_base_datos

app = create_app(configuracion)

if not verifica_coneccion_db(app=app):
    logger.critical("No se logro conectar a la base de datos.")
    sys.exit(1)

try:
    with app.app_context():
        verificar_esquema_base_datos(permitir_migrar=False)
except Exception as exc:
    logger.critical(str(exc))
    sys.exit(1)

logger.info("Iniciando servidor WSGI en puerto {puerto}.", puerto=PORT)
serve(app, port=int(PORT), threads=int(THREADS))
