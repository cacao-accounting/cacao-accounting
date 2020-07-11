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

import click
from flask import Flask
from cacao_accounting.database import db
from cacao_accounting.app import cacao_app
from cacao_accounting.auth import administrador_sesion, login
from cacao_accounting.bancos import bancos
from cacao_accounting.contabilidad import contabilidad
from cacao_accounting.compras import compras
from cacao_accounting.inventario import inventario


__name__ = "Cacao Accounting"
__license__ = "Apache Software License "
__version__ = "0.0.1"

DEVELOPMENT = True


def create_app(ajustes=None):
    """Aplication factory"""
    app = Flask(
        __name__,
        template_folder="cacao_accounting/templates",
        static_folder="cacao_accounting/static",
        instance_relative_config=False,
        )
    if ajustes:
        for i in ajustes:
            app.config[i] = ajustes[i]

    db.init_app(app)
    administrador_sesion.init_app(app)
    with app.app_context():
        app.register_blueprint(login)
        app.register_blueprint(cacao_app)
        app.register_blueprint(contabilidad)
        app.register_blueprint(bancos)
        app.register_blueprint(compras)
        app.register_blueprint(inventario)

    @app.cli.command("init-db")
    def crear_db():
        from cacao_accounting.datos import cargar_datos, demo_data
        "Crea el esquema de la base de datos."
        db.create_all()
        with app.app_context():
            cargar_datos()
            demo_data()

    @app.cli.command("reset-db")
    def eliminar_db():
        "Elimina la base de datos, solo disponible para desarrollo."
        if DEVELOPMENT:
            db.drop_all()

    return app
