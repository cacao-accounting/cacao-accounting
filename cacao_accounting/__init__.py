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
from flask import Flask
from flask_alembic import Alembic
from cacao_accounting.admin import admin
from cacao_accounting.app import cacao_app
from cacao_accounting.auth import administrador_sesion, login
from cacao_accounting.bancos import bancos
from cacao_accounting.contabilidad import contabilidad
from cacao_accounting.database import db
from cacao_accounting.compras import compras
from cacao_accounting.inventario import inventario
from cacao_accounting.metadata import DEVELOPMENT
from cacao_accounting.modulos import registrar_modulos_adicionales
from cacao_accounting.tools import archivos, plantillas
from cacao_accounting.ventas import ventas


alembic = Alembic()


def command():
    """
    Interfaz de linea de commandos.
    """
    from cacao_accounting.cli import main

    main(as_module="cacao_accounting")


def create_app(ajustes=None):
    """
    Aplication factory.

    Referencias:
     - https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/
    """
    # pylint: disable=W0612
    if version_info >= (3, 6):
        pass
    else:
        raise RuntimeError("Python >= 3.6 requerido.")
    app = Flask(
        __name__,
        template_folder=plantillas,
        static_folder=archivos,
        instance_relative_config=False,
    )
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrop_blocks = True
    if ajustes:
        for i in ajustes:
            app.config[i] = ajustes[i]

    alembic.init_app(app)
    db.init_app(app)
    administrador_sesion.init_app(app)
    with app.app_context():
        app.register_blueprint(admin)
        app.register_blueprint(bancos)
        app.register_blueprint(cacao_app)
        app.register_blueprint(contabilidad)
        app.register_blueprint(compras)
        app.register_blueprint(inventario)
        app.register_blueprint(login)
        app.register_blueprint(ventas)
        registrar_modulos_adicionales(app)

    from cacao_accounting.modulos import validar_modulo_activo

    app.jinja_env.globals.update(validar_modulo_activo=validar_modulo_activo)
    app.jinja_env.globals.update(DEVELOPMENT=DEVELOPMENT)

    @app.cli.command()
    def initdb():
        """Crea el esquema de la base de datos."""
        from cacao_accounting.datos.base import base_data

        db.create_all()
        with app.app_context():
            if DEVELOPMENT:
                from cacao_accounting.datos import demo_data

                base_data(carga_rapida=True)
                demo_data()
            else:
                base_data(carga_rapida=False)

    @app.cli.command()
    def cleandb():
        """Elimina la base de datos, solo disponible para desarrollo."""
        if DEVELOPMENT:
            db.drop_all()

    @app.cli.command()
    def serve():
        """
        Inicio la aplicacion con waitress como servidor WSGI por  defecto.
        """
        from cacao_accounting.__main__ import run

        run()

    return app
