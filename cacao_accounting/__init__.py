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
Interface principal de la aplicacion.

Aquí creamos la función que define la "app" que se ejecuta en el servidor
WSGI.
"""

from sys import version_info
from typing import Union
from configobj import ConfigObj
from flask import Flask
from flask import current_app
from flask_alembic import Alembic
from flask_talisman import Talisman
from cacao_accounting.admin import admin
from cacao_accounting.ajax import ajax
from cacao_accounting.app import cacao_app as main_app
from cacao_accounting.auth import administrador_sesion, login
from cacao_accounting.bancos import bancos
from cacao_accounting.contabilidad import contabilidad
from cacao_accounting.database import db
from cacao_accounting.config import MODO_ESCRITORIO
from cacao_accounting.compras import compras
from cacao_accounting.exception import ERROR2
from cacao_accounting.inventario import inventario
from cacao_accounting.modulos import registrar_modulos_adicionales, validar_modulo_activo
from cacao_accounting.tools import DIRECTORIO_ARCHIVOS, DIRECTORIO_PLANTILLAS
from cacao_accounting.ventas import ventas


alembic = Alembic()
talisman = Talisman()


def command() -> None:
    """
    Interfaz de linea de commandos.
    """
    from cacao_accounting.cli import linea_comandos

    linea_comandos(as_module="cacao_accounting")


def verifica_version_de_python() -> None:
    """
    Requerimos al menos python 3.6 para la aplicación.
    """
    # pylint: disable=W0612
    if version_info >= (3, 6):
        pass
    else:
        raise RuntimeError("Python >= 3.6 requerido.")


def iniciar_extenciones(app: Union[Flask, None] = None) -> None:
    """
    Inicializa extenciones.
    """
    if app and isinstance(app, Flask):
        alembic.init_app(app)
        db.init_app(app)
        administrador_sesion.init_app(app)
        with app.app_context():
            if not current_app.config.get("ENV") == "development":
                talisman.init_app(app)
    else:
        raise RuntimeError(ERROR2)


def registrar_rutas_predeterminadas(app: Union[Flask, None] = None) -> None:
    """
    Registra rutas predeterminadas.
    """
    if app and isinstance(app, Flask):
        from flask import render_template

        @app.errorhandler(404)
        def page_not_found(error):  # pylint: disable=W0613
            return render_template("404.html"), 404

    else:
        raise RuntimeError(ERROR2)


def registrar_blueprints(app: Union[Flask, None] = None) -> None:
    """
    Registra blueprints por defecto.
    """
    if app and isinstance(app, Flask):
        with app.app_context():
            app.register_blueprint(admin)
            app.register_blueprint(bancos)
            app.register_blueprint(main_app)
            app.register_blueprint(contabilidad)
            app.register_blueprint(compras)
            app.register_blueprint(inventario)
            app.register_blueprint(login)
            app.register_blueprint(ventas)
            app.register_blueprint(ajax)
            registrar_modulos_adicionales(app)
    else:
        raise RuntimeError(ERROR2)


def actualiza_variables_globales_jinja(app: Union[Flask, None] = None) -> None:
    """
    Utilidad para asegurar que varios opciones globales esten dispinibles en Jinja2.
    """

    if app and isinstance(app, Flask):
        with app.app_context():
            app.jinja_env.trim_blocks = True
            app.jinja_env.lstrop_blocks = True
            app.jinja_env.globals.update(validar_modulo_activo=validar_modulo_activo)
            app.jinja_env.globals.update(DEVELOPMENT=current_app.config.get("ENV"))
            app.jinja_env.globals.update(MODO_ESCRITORIO=MODO_ESCRITORIO)
    else:
        raise RuntimeError(ERROR2)


def create_app(ajustes: Union[ConfigObj, dict, None] = None) -> Flask:
    """
    Aplication factory.

    Referencias:
     - https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/
    """
    # pylint: disable=W0612
    verifica_version_de_python()
    CACAO_APP = Flask(
        "cacao_accounting",
        template_folder=DIRECTORIO_PLANTILLAS,
        static_folder=DIRECTORIO_ARCHIVOS,
    )

    if ajustes:
        CACAO_APP.config.from_mapping(ajustes)

    @CACAO_APP.cli.command()
    def initdb():
        """Crea el esquema de la base de datos."""

        from cacao_accounting.database import inicia_base_de_datos

        inicia_base_de_datos(CACAO_APP)

    @CACAO_APP.cli.command()
    def cleandb():
        """Elimina la base de datos, solo disponible para desarrollo."""
        if current_app.config.get("ENV") == "development":
            db.drop_all()

    @CACAO_APP.cli.command()
    def version():
        """Muestra la version actual instalada."""
        from cacao_accounting.version import VERSION

        print(VERSION)

    @CACAO_APP.cli.command()
    def serve():
        """
        Inicio la aplicacion con waitress como servidor WSGI por  defecto.
        """
        from cacao_accounting.server import server

        server()

    @CACAO_APP.cli.command()
    def setupdb():
        """
        Define una base de datos de desarrollo nueva.
        """
        from cacao_accounting.database import inicia_base_de_datos

        if current_app.config.get("ENV") == "development":
            db.drop_all()
            inicia_base_de_datos(CACAO_APP)

    actualiza_variables_globales_jinja(app=CACAO_APP)
    iniciar_extenciones(app=CACAO_APP)
    registrar_blueprints(app=CACAO_APP)
    registrar_rutas_predeterminadas(app=CACAO_APP)
    return CACAO_APP
