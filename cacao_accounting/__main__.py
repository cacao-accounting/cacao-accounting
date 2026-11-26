# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidad para iniciar la aplicacion como modulo en python."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
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
from cacao_accounting.database.helpers import resolver_credenciales_iniciales
from cacao_accounting.logs import log
from cacao_accounting.server import server


def inicializar_si_hace_falta(app, *, esperar_segundos: int = 15) -> bool:
    """Inicializa la base del entrypoint solo con credenciales seguras.

    Devuelve `True` cuando el servidor debe arrancar. Separado del bloque
    `__main__` para verificar que en producción sin `CACAO_USER`/
    `CACAO_PSWD` el arranque se detiene antes de crear el administrador
    predeterminado (#1602).
    """
    from cacao_accounting.database.helpers import estado_esquema_base_datos, inicia_base_de_datos

    with app.app_context():
        estado = estado_esquema_base_datos()
        if str(estado.get("status")) not in {"empty", "bootstrap_incomplete"}:
            return True
    if esperar_segundos:
        sleep(esperar_segundos)
    with app.app_context():
        estado = estado_esquema_base_datos()
        if str(estado.get("status")) not in {"empty", "bootstrap_incomplete"}:
            return True

    try:
        log.info("Inicializando Cacao Accounting.")
        cacao_user, cacao_passwd = resolver_credenciales_iniciales()
        if cacao_user == "cacao" and cacao_passwd == "cacao":
            log.warning("Se están usando usuario y contraseña predeterminados para el setup inicial.")
        inicia_base_de_datos(app=app, user=cacao_user, passwd=cacao_passwd, with_examples=False)
    except ValueError as exc:
        log.critical(str(exc))
        raise SystemExit(1) from exc
    except ProgrammingError:
        log.warning("No se pudo iniciar Cacao Accounting.")
        return False
    return True


if __name__ == "__main__":
    """Run as module python -m cacao_accounting."""

    app = create_app(ajustes=configuracion)
    app.app_context().push()

    if inicializar_si_hace_falta(app):
        server()
