# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidad para iniciar el servidor local WSGI usando Waitress."""

# ---------------------------------------------------------------------------------------
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
    from cacao_accounting.database.helpers import (
        inicia_base_de_datos,
        resolver_credenciales_iniciales,
        verifica_coneccion_db,
    )

    log.info("Iniciando Cacao Accounting.")
    if verifica_coneccion_db(app):
        DATABASE = True
    else:
        from sqlalchemy.exc import OperationalError

        log.warning("No se logro conectar a la base de datos.")
        log.info("Intentando inicializar base de datos.")
        try:
            user, passwd = resolver_credenciales_iniciales()
            if user == "cacao" and passwd == "cacao":
                log.warning("Se están usando usuario y contraseña predeterminados para el setup inicial.")
            with app.app_context():
                inicia_base_de_datos(app, user=user, passwd=passwd, with_examples=False)
            DATABASE = True
        except ValueError as exc:
            log.critical(str(exc))
            raise SystemExit(1) from exc
        except OperationalError:
            log.error("No se pudo inicilizar la base de datos.")
            DATABASE = False

    if DATABASE:
        try:
            log.info("Iniciando servidor WSGI en puerto {puerto}.", puerto=PORT)
            serve(app, port=int(PORT), threads=int(THREADS))
        except OSError:
            log.error("Puerto {PORT} actualmente en uso.")
    else:
        log.error("No se logro establecer con la base de datos.")
