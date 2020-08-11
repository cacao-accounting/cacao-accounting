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

from flask import Flask
from cacao_accounting.admin import admin
from cacao_accounting.app import cacao_app
from cacao_accounting.auth import administrador_sesion, login
from cacao_accounting.bancos import bancos
from cacao_accounting.contabilidad import contabilidad
from cacao_accounting.database import db
from cacao_accounting.compras import compras
from cacao_accounting.inventario import inventario
from cacao_accounting.metadata import DEVELOPMENT
from cacao_accounting.tools import archivos, plantillas
from cacao_accounting.ventas import ventas


def command():
    """
    Interfaz de linea de commandos.
    """
    from flask.cli import main

    main(as_module="cacao_accounting")


def create_app(ajustes=None):
    """
    Aplication factory.

    Referencias:
     - https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/
    """
    app = Flask(__name__, template_folder=plantillas, static_folder=archivos, instance_relative_config=False,)
    if ajustes:
        for i in ajustes:
            app.config[i] = ajustes[i]

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

    @app.cli.command()
    def init-db():
        """Crea el esquema de la base de datos."""

        db.create_all()
        with app.app_context():
            pass

    @app.cli.command()
    def demo-data():
        """Carga datos de prueba en la base de datos."""
        from cacao_accounting.datos import demo_data

        with app.app_context():
            demo_data()

    @app.cli.command()
    def reset-db():
        """Elimina la base de datos, solo disponible para desarrollo."""
        if DEVELOPMENT:
            db.drop_all()

    @app.cli.command()
    def serve():
        """
        Inicio la aplicacion con waitress como servidor WSGI por  defecto.
        """
        from cacao_accounting.__main__ import server

        server()

    @app.cli.command()
    def setup-db():
        """Atajo para reiniciar la base de datos en etapa de desarrollo."""
        if DEVELOPMENT:
            db.drop_all()
            db.create_all()
            with app.app_context():
                demo_data()

    return app
