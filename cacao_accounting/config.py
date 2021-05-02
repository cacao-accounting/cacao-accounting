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
from configobj import ConfigObj
from cacao_accounting.loggin import log
from cacao_accounting.metadata import DEVELOPMENT, APPAUTHOR, APPNAME

# < --------------------------------------------------------------------------------------------- >
# URI de conexión a bases de datos por defecto
# Free Open Source Databases
SQLITE = "sqlite:///cacaoaccounting.db"
MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
POSTGRESQL = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"
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


def probar_configuracion_por_variables_de_entorno():
    """
    Valida que las opciones requeridas para configuración la aplicacion desde variables del entorno
    se encuentran correctamente configuradas.
    """
    if "CACAO_DB" in environ and "CACAO_KEY" in environ:
        try:
            URI = environ["CACAO_DB"]
            KEY = environ["CACAO_KEY"]
            URI, KEY
            return True
        except KeyError:
            return False
    else:
        return False


CONFIGURACION_BASADA_EN_VARIABLES_DE_ENTORNO = probar_configuracion_por_variables_de_entorno()

if not CONFIGURACION_BASADA_EN_ARCHIVO_LOCAL and CONFIGURACION_BASADA_EN_VARIABLES_DE_ENTORNO:
    log.info("Cargando configuracion en base a variables de entorno.")
    configuracion = {}
    configuracion["SQLALCHEMY_DATABASE_URI"] = environ["CACAO_DB"]
    configuracion["SECRET_KEY"] = environ["CACAO_KEY"]
    configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

elif DEVELOPMENT:
    log.warning("Utilizando configuración predeterminada para desarrollo, no apta para producción")
    configuracion = {}
    configuracion["SQLALCHEMY_DATABASE_URI"] = SQLITE
    configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    configuracion["ENV"] = "development"
    configuracion["SECRET_KEY"] = "dev"
    configuracion["EXPLAIN_TEMPLATE_LOADING"] = True
    configuracion["DEGUG"] = True

else:
    log.warning("No se pudo encontrar una fuente para la configuración de la aplicacion, revise la documentacion")
    configuracion = None
