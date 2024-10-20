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
"""Modulo para la configuración centralizada de la configuración de la aplicacion."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ, name, path
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
DIRECTORIO_APP = path.abspath(path.dirname(__file__))
DIRECTORIO_PRINCICIPAL = Path(DIRECTORIO_APP).parent.absolute()
DIRECTORIO_PLANTILLAS = path.join(DIRECTORIO_APP, "templates")
DIRECTORIO_ARCHIVOS = path.join(DIRECTORIO_APP, "static")

# < --------------------------------------------------------------------------------------------- >
# URI de conexión a bases de datos por defecto
# Free Open Source Databases
if name == "nt":
    SQLITE = "sqlite:///" + str(DIRECTORIO_PRINCICIPAL) + "\\cacaoaccounting.db"
else:
    SQLITE = "sqlite:///" + str(DIRECTORIO_PRINCICIPAL) + "/cacaoaccounting.db"

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

DATABASE_URL = environ.get("CACAO_DATABASE_URL") or environ.get("DATABASE_URL")
SECRET_KEY = environ.get("CACAO_SECRET_KEY") or environ.get("CACAO_KEY") or environ.get("SECRET_KEY")


def valida_llave_secreta(llave: str) -> bool:
    """Valida requisitos minimos para aceptar una contraseña."""
    CONTIENE_MAYUSCULAS = bool(any(chr.isupper() for chr in llave))
    CONTIENE_MINUSCULAS = bool(any(chr.islower() for chr in llave))
    CONTIENE_NUMEROS = bool(any(chr.isnumeric() for chr in llave))
    CONTIENE_CARACTERES_MINIMOS = bool(len(llave) >= 8)
    CONFIGURACION_DESARROLLO = environ.get("ENV") == "development"
    if CONFIGURACION_DESARROLLO:
        return True
    else:
        VALIDACION = CONTIENE_MAYUSCULAS and CONTIENE_MINUSCULAS and CONTIENE_NUMEROS and CONTIENE_CARACTERES_MINIMOS
        if VALIDACION:
            log.debug("Clave secreta valida.")
            return True
        else:
            log.warning("Clave secreta insegura.")
            log.info("Establesca una clave secreta más segura.")
            return False


def valida_direccion_base_datos(uri: str) -> bool:
    """Verifica que la URI de la database este en el formato correcto."""
    DIRECCION = str(uri)
    MYSQL_URI = DIRECCION.startswith("mysql+pymysql")
    MARIADB_URI = DIRECCION.startswith("mariadb+mariadbconnector")
    POSTGRESQL_URI = DIRECCION.startswith("postgresql+pg8000") or DIRECCION.startswith("postgresql+psycopg2")
    SQLITE_URI = DIRECCION.startswith("sqlite")
    VALIDACION = MYSQL_URI or POSTGRESQL_URI or SQLITE_URI or MARIADB_URI
    if VALIDACION:
        log.debug("URL de Acceso a db validada correctamente.")
        if MARIADB_URI:
            log.warning("El soporte a MariaDB es expimental.")
    else:
        log.warning("Favor revise la configuración de acceso a la base de datos.")
    return VALIDACION


def probar_configuracion_por_variables_de_entorno() -> bool:
    """Valida que las variables del entorno se encuentran correctamente configuradas."""
    if DATABASE_URL and SECRET_KEY:
        VALIDACION = valida_direccion_base_datos(DATABASE_URL) and valida_llave_secreta(SECRET_KEY)
        if VALIDACION:
            log.info("Configuracion valida obtenida de variables de entorno")
        else:
            log.warning("No se encontro configuración valida.")
        return VALIDACION
    else:
        return False


configuracion = {}

if probar_configuracion_por_variables_de_entorno():
    log.debug("Cargando configuracion en base a variables de entorno.")
    configuracion["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    configuracion["SECRET_KEY"] = SECRET_KEY
    configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = "False"

else:
    log.debug("Utilizando configuración preterminada.")
    configuracion["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or SQLITE  # Always prefer CACAO_DB
    configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = "False"
    configuracion["ENV"] = "development"
    configuracion["SECRET_KEY"] = SECRET_KEY or "dev"  # nosec
    configuracion["DEGUG"] = "True"
    configuracion["TEMPLATES_AUTO_RELOAD"] = "True"

if environ.get("CACHE_REDIS_URL"):
    configuracion["CACHE_TYPE"] = "RedisCache"
    configuracion["CACHE_REDIS_URL"] = environ.get("CACHE_REDIS_URL")
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
    elif environ.get("CACAO_ACCOUNTING_DESKTOP", default=False):
        return True

    else:
        return False


MODO_ESCRITORIO = probar_modo_escritorio()

TESTING_MODE = environ.get("CACAO_TEST", False) or environ.get("CI", False) or environ.get("PYTEST_VERSION") is not None
