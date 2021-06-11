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

"""
Modulo para la configuración centralizada de la configuración de la aplicacion.
"""

from os import environ
from os.path import exists, join
from appdirs import user_config_dir, site_config_dir
from flask import current_app
from configobj import ConfigObj
from cacao_accounting.loggin import log
from cacao_accounting.metadata import APPAUTHOR, APPNAME

# < --------------------------------------------------------------------------------------------- >
# URI de conexión a bases de datos por defecto
# Free Open Source Databases
SQLITE = "sqlite:///cacaoaccounting.db"
MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
POSTGRESQL = "postgresql+pg8000://cacao:cacao@localhost:5432/cacao"
# Non Free Databases
MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"


# < --------------------------------------------------------------------------------------------- >
# Permite al usuario establecer cuantos hilos utilizar para ejecutar el servidor WSGI por defecto,
# util para instalaciones en un equipo dedicado, en otros entornos como contenedores se utiliza un
# valor razonable por defecto.
try:
    THREADS = int(environ["CACAO_THREADS"])
except KeyError:
    THREADS = 4

# < --------------------------------------------------------------------------------------------- >
# Permite al usuario establecer en que puerto servir la aplicacion con el servidor WSGI por defecto
try:
    PORT = int(environ["CACAO_PORT"])
except KeyError:
    PORT = 8080

# < --------------------------------------------------------------------------------------------- >
# En entornos de escritorio es util poder establecer la configuracion desde un archivo ubicado en
# una ubicacion predeterminada en el equipo del usuario.
ARCHIVO_CONFIGURACION = "cacaoaccounting.conf"
CONFIGURACION_USUARIO = join(user_config_dir(APPNAME, APPAUTHOR), ARCHIVO_CONFIGURACION)
CONFIGURACION_GLOBAL = join(site_config_dir(APPNAME, APPAUTHOR), ARCHIVO_CONFIGURACION)


if exists(CONFIGURACION_USUARIO):
    configuracion = ConfigObj(CONFIGURACION_USUARIO)
    CONFIGURACION_BASADA_EN_ARCHIVO_LOCAL = True
    log.info("Cargando configuración desde carpeta personal del usuario.")

elif exists(CONFIGURACION_GLOBAL):
    configuracion = ConfigObj(CONFIGURACION_GLOBAL)
    CONFIGURACION_BASADA_EN_ARCHIVO_LOCAL = True
    log.info("Cargando configuración desde carpeta global del sistema.")

else:
    CONFIGURACION_BASADA_EN_ARCHIVO_LOCAL = False

# < --------------------------------------------------------------------------------------------- >
# En entornos de web y de contenedores es un patron recomendado utlizar variables del entorno para
# configurar la aplicacion.


def valida_llave_secreta(llave: str) -> bool:

    CONTIENE_MAYUSCULAS = bool(any(chr.isupper() for chr in llave))
    CONTIENE_MINUSCULAS = bool(any(chr.islower() for chr in llave))
    CONTIENE_NUMEROS = bool(any(chr.isnumeric() for chr in llave))
    CONTIENE_CARACTERES_MINIMOS = bool(len(llave) >= 8)
    try:
        current_app.app_context().push()
        CONFIGURACION_DESARROLLO = current_app.config.get("ENV") == "development"
    except RuntimeError:
        CONFIGURACION_DESARROLLO = False
    if CONFIGURACION_DESARROLLO:
        return True
    else:
        return CONTIENE_MAYUSCULAS and CONTIENE_MINUSCULAS and CONTIENE_NUMEROS and CONTIENE_CARACTERES_MINIMOS


def valida_direccion_base_datos(uri: str) -> bool:
    DIRECCION = str(uri)
    MSSQL_URI = DIRECCION.startswith("mssql")
    MYSQL_URI = DIRECCION.startswith("mysql")
    POSTGRESQL_URI = DIRECCION.startswith("postgresql")
    SQLITE_URI = DIRECCION.startswith("sqlite")
    return MSSQL_URI or MYSQL_URI or POSTGRESQL_URI or SQLITE_URI


def probar_configuracion_por_variables_de_entorno() -> bool:
    """
    Valida que las opciones requeridas para configuración la aplicacion desde variables del entorno
    se encuentran correctamente configuradas.
    """

    try:
        return valida_direccion_base_datos(environ["CACAO_DB"]) and valida_llave_secreta(environ["CACAO_KEY"])
    except KeyError:
        log.info("Configuración por variables de entornos no definida.")
        return False


CONFIGURACION_BASADA_EN_VARIABLES_DE_ENTORNO = probar_configuracion_por_variables_de_entorno()

if not CONFIGURACION_BASADA_EN_ARCHIVO_LOCAL and CONFIGURACION_BASADA_EN_VARIABLES_DE_ENTORNO:
    log.info("Cargando configuracion en base a variables de entorno.")
    configuracion = {}
    configuracion["SQLALCHEMY_DATABASE_URI"] = environ["CACAO_DB"]
    configuracion["SECRET_KEY"] = environ["CACAO_KEY"]
    configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

else:
    log.warning("No se encontro una fuente para la configuración, revise la documentacion")
    log.warning("Utilizando configuración para desarrollo, no apta para uso en producción")
    configuracion = {}
    configuracion["SQLALCHEMY_DATABASE_URI"] = SQLITE
    configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Se evalua posterior al inicio de la aplicacion por lo que sobrescribe el valor establecido como
    # variable de entorno
    configuracion["ENV"] = "development"
    configuracion["SECRET_KEY"] = "dev"
    configuracion["EXPLAIN_TEMPLATE_LOADING"] = True
    configuracion["DEGUG"] = True


def probar_modo_escritorio() -> bool:
    """
    Función utilitaria para establecer nodo de escritorio.
    """

    # Probamos si estamos en un paquete SNAP
    # Referencias
    #  - https://snapcraft.io/docs/environment-variables
    try:
        EJECUTANDO_COMO_SNAP = "SNAP_NAME" in environ
    except KeyError:
        EJECUTANDO_COMO_SNAP = False

    # Probamos si estamos en un paquete FLATPAK
    # Referencias:
    #  - https://www.systutorials.com/docs/linux/man/1-flatpak-run/
    try:
        EJECUTANDO_COMO_FLATPAK = "FLATPAK_ID" in environ
    except KeyError:
        EJECUTANDO_COMO_FLATPAK = False

    # Probamos si se ha establecido la variable de entorno CACAO_DESKTOP
    try:
        EJECUTANDO_COMO_DESKTOP = "CACAO_DESKTOP" in environ
    except KeyError:
        EJECUTANDO_COMO_DESKTOP = False
    # Finalmente probamos si en el archivo de configuración se especificado el
    # modo escritorio.
    if CONFIGURACION_BASADA_EN_ARCHIVO_LOCAL:
        try:
            EJECUTANDO_COMO_DESKTOP = "CACAO_DESKTOP" in configuracion
        except:  # noqa: E722
            EJECUTANDO_COMO_DESKTOP = False
    else:
        EJECUTANDO_COMO_DESKTOP = False
    return EJECUTANDO_COMO_SNAP or EJECUTANDO_COMO_FLATPAK or EJECUTANDO_COMO_DESKTOP


MODO_ESCRITORIO = probar_modo_escritorio()
