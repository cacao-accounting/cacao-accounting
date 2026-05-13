# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Modulo para la configuración centralizada de la configuración de la aplicacion."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ, name
from pathlib import Path

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.logs import log

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# < --------------------------------------------------------------------------------------------- >
# Directorios de la aplicacion
DIRECTORIO_APP = Path(__file__).parent
DIRECTORIO_PRINCIPAL = DIRECTORIO_APP.parent
DIRECTORIO_PLANTILLAS = str(DIRECTORIO_APP / "templates")
DIRECTORIO_ARCHIVOS = str(DIRECTORIO_APP / "static")

# < --------------------------------------------------------------------------------------------- >
# URI de conexión a bases de datos por defecto
if name == "nt":
    SQLITE = f"sqlite:///{DIRECTORIO_PRINCIPAL}\\cacaoaccounting.db"
else:
    SQLITE = f"sqlite:///{DIRECTORIO_PRINCIPAL}/cacaoaccounting.db"

# < --------------------------------------------------------------------------------------------- >
# Permite al usuario establecer cuantos hilos utilizar para ejecutar el servidor WSGI por defecto,
# util para instalaciones en un equipo dedicado, en otros entornos como contenedores se utiliza un
# valor razonable por defecto.
THREADS = environ.get("CACAO_THREADS") or environ.get("THREADS") or 4

# < --------------------------------------------------------------------------------------------- >
# Permite al usuario establecer en que puerto servir la aplicacion con el servidor WSGI por defecto
PORT = environ.get("CACAO_PORT") or environ.get("PORT") or 8080

# < --------------------------------------------------------------------------------------------- >
# En entornos de web y de contenedores es un patron recomendado utlizar variables del entorno para
# configurar la aplicacion.

DATABASE_URL = environ.get("CACAO_DATABASE_URL") or environ.get("CACAO_DB") or environ.get("DATABASE_URL") or SQLITE
SECRET_KEY = environ.get("CACAO_SECRET_KEY") or environ.get("CACAO_KEY") or environ.get("SECRET_KEY")


def valida_direccion_base_datos(uri: str) -> bool:
    """Verifica que la URI de la database este en el formato correcto."""
    direccion = str(uri)
    match direccion:
        case _ if direccion.startswith("mysql+pymysql"):
            return True
        case _ if direccion.startswith("mariadb+mariadbconnector"):
            log.warning("El soporte a MariaDB es expimental.")
            return True
        case _ if direccion.startswith("postgresql+pg8000") or direccion.startswith("postgresql+psycopg2"):
            return True
        case _ if direccion.startswith("sqlite"):
            return True
        case _:
            log.warning("Favor revise la configuración de acceso a la base de datos.")
            return False


configuracion: dict[str, str] = {}

if valida_direccion_base_datos(DATABASE_URL):
    configuracion["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
configuracion["SECRET_KEY"] = SECRET_KEY or ""
configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = "False"

if environ.get("CACAO_TEST"):
    configuracion["DEGUG"] = "True"
    configuracion["TEMPLATES_AUTO_RELOAD"] = "True"

if environ.get("CACHE_REDIS_URL"):
    configuracion["CACHE_TYPE"] = "RedisCache"
    configuracion["CACHE_REDIS_URL"] = environ.get("CACHE_REDIS_URL") or ""
else:
    configuracion["CACHE_TYPE"] = "SimpleCache"


def probar_modo_escritorio() -> bool:
    """Función utilitaria para establecer nodo de escritorio."""
    # Probamos si estamos en un paquete SNAP
    # Referencias
    #  - https://snapcraft.io/docs/environment-variables
    if environ.get("SNAP_NAME", default=False):
        return True

    # Probamos si estamos en un paquete FLATPAK
    # Referencias:
    #  - https://www.systutorials.com/docs/linux/man/1-flatpak-run/
    elif environ.get("FLATPAK_ID", default=False):
        return True

    # Probamos si se ha establecido la variable de entorno CACAO_ACCOUNTING-DESKTOP
    # En el codigo fuente de la distribución de escritorio se establece esta opción
    # previo a importar la aplicación principal.
    elif str(environ.get("CACAO_ACCOUNTING_DESKTOP", "False")).lower() == "true":
        return True

    else:
        return False


MODO_ESCRITORIO = probar_modo_escritorio()

TESTING_MODE = environ.get("CACAO_TEST", False) or environ.get("CI", False) or environ.get("PYTEST_VERSION") is not None
