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


"""
Interface principal de la aplicacion.

Aquí creamos la función que define la "app" que se ejecuta en el servidor
WSGI.
"""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from datetime import timedelta
from os import environ
from typing import Union

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Flask, session
from flask_alembic import Alembic
from flask_login import current_user

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.admin import admin
from cacao_accounting.api import api
from cacao_accounting.app import cacao_app as main_app
from cacao_accounting.auth import administrador_sesion, login
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.bancos import bancos
from cacao_accounting.compras import compras
from cacao_accounting.config import DIRECTORIO_ARCHIVOS, DIRECTORIO_PLANTILLAS, MODO_ESCRITORIO, TESTING_MODE
from cacao_accounting.contabilidad import contabilidad
from cacao_accounting.database import database
from cacao_accounting.database.helpers import entidades_creadas, obtener_id_modulo_por_nombre
from cacao_accounting.exceptions.mensajes import ERROR2
from cacao_accounting.inventario import inventario
from cacao_accounting.modulos import registrar_modulos_adicionales, validar_modulo_activo
from cacao_accounting.ventas import ventas

alembic = Alembic()


def command() -> None:  # pragma: no cover
    """Interfaz de linea de commandos."""
    from cacao_accounting.cli import linea_comandos

    linea_comandos(as_module="cacao_accounting")


def iniciar_extenciones(app: Union[Flask, None] = None) -> None:
    """Inicializa extenciones."""
    if app and isinstance(app, Flask):
        # alembic.init_app(app)
        database.init_app(app)
        administrador_sesion.init_app(app)
    else:
        raise RuntimeError(ERROR2)


def registrar_rutas_predeterminadas(app: Union[Flask, None] = None) -> None:
    """Registra rutas predeterminadas."""
    if app and isinstance(app, Flask):
        from flask import render_template

        @app.errorhandler(404)
        def error_404(error):
            """Pagina personalizada para recursos no encontrados."""
            if error:
                return render_template("404.html"), 404

        @app.errorhandler(403)
        def error_403(error):
            """Pagina personalizada para solicitar acceso a recursos no autorizados."""
            if error:
                return render_template("403.html"), 403

        @app.errorhandler(400)
        def error_400(error):
            """Pagina personalizada para solicitar invalida."""
            if error:
                return render_template("400.html"), 400

    else:
        raise RuntimeError(ERROR2)


def registrar_blueprints(app: Union[Flask, None] = None) -> None:
    """Registra blueprints por defecto."""
    if app and isinstance(app, Flask):
        with app.app_context():
            app.register_blueprint(admin)
            app.register_blueprint(api)
            app.register_blueprint(bancos)
            app.register_blueprint(main_app)
            app.register_blueprint(contabilidad)
            app.register_blueprint(compras)
            app.register_blueprint(inventario)
            app.register_blueprint(login)
            app.register_blueprint(ventas)
            registrar_modulos_adicionales(app)
    else:
        raise RuntimeError(ERROR2)


def actualiza_variables_globales_jinja(app: Union[Flask, None] = None) -> None:
    """Utilidad para asegurar que varios opciones globales esten dispinibles en Jinja2."""
    if app and isinstance(app, Flask):
        with app.app_context():
            app.jinja_env.trim_blocks = True
            app.jinja_env.lstrip_blocks = True
            app.jinja_env.globals.update(validar_modulo_activo=validar_modulo_activo)
            app.jinja_env.globals.update(permisos=Permisos)
            app.jinja_env.globals.update(MODO_ESCRITORIO=MODO_ESCRITORIO)
            app.jinja_env.globals.update(TESTING=TESTING_MODE)
            # En las plantillas no se utiliza el termino permiso para evitar un conflicto de nombre
            # se utiliza "acceso", para ello al inicio de cada plantilla se debe establecer el
            # nivel del permiso de cada usuario agregando la siguiente linea:
            # {% set acceso = permisos(modulo=id_modulo(modulo), usuario=usuario.id)%}
            # donde modulo es uno de "accounting", "cash", "purchases", "inventory", "sales"
            # puede ser que modulos adicionales se encuentren instalados en el sistema, pero esos
            # son los 5 modulos predeterminados del sistema.
            # El sistema de permisos verifica los siguientes accesos predeterminados:
            # "actualizar", "anular", "autorizar", "bi", "cerrar", "configurar", "consultar",
            # "corregir", "crear", "editar", "eliminar", "importar", "listar", "reportes",
            # "solicitar", "validar" y "validar_solicitud"
            app.jinja_env.globals.update(id_modulo=obtener_id_modulo_por_nombre)
            app.jinja_env.globals.update(usuario=current_user)
            app.jinja_env.globals.update(entidades_creadas=entidades_creadas)

    else:
        raise RuntimeError(ERROR2)


def create_app(ajustes: Union[dict, None] = None) -> Flask:
    """Aplication factory."""
    cacao_app = Flask(
        "cacao_accounting",
        template_folder=DIRECTORIO_PLANTILLAS,
        static_folder=DIRECTORIO_ARCHIVOS,
    )

    if ajustes:
        cacao_app.config.from_mapping(ajustes)

    @cacao_app.cli.command()
    def cleandb():  # pragma: no cover
        """Elimina la base de datos, solo disponible para desarrollo."""
        if TESTING_MODE:
            database.drop_all()

    @cacao_app.cli.command()
    def version():  # pragma: no cover
        """Muestra la version actual instalada."""
        from cacao_accounting.version import VERSION

        print(VERSION)

    @cacao_app.cli.command()
    def serve():  # pragma: no cover
        """Inicio la aplicacion con waitress como servidor WSGI por  defecto."""
        from cacao_accounting.server import server

        server()

    @cacao_app.cli.command()
    def setupdb():  # pragma: no cover
        """Define una base de datos de desarrollo nueva."""
        from cacao_accounting.database.helpers import inicia_base_de_datos

        user = environ.get("CACAO_USER") or "cacao"
        passwd = environ.get("CACAO_PWD") or "cacao"

        if TESTING_MODE:
            database.drop_all()
            inicia_base_de_datos(app=cacao_app, user=user, passwd=passwd, with_examples=True)
        else:
            inicia_base_de_datos(app=cacao_app, user=user, passwd=passwd, with_examples=False)

    @cacao_app.before_request
    def before_request():  # pragma: no cover
        session.permanent = True
        cacao_app.permanent_session_lifetime = timedelta(minutes=30)

    actualiza_variables_globales_jinja(app=cacao_app)
    iniciar_extenciones(app=cacao_app)
    registrar_blueprints(app=cacao_app)
    registrar_rutas_predeterminadas(app=cacao_app)

    return cacao_app


# <---------------------------------------------------------------------------------------------> #
# La logica de negocios se define en cada módulo respectivo.
# <---------------------------------------------------------------------------------------------> #
