# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""
Interface principal de la aplicacion.

Aquí creamos la función que define la "app" que se ejecuta en el servidor
WSGI.
"""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Flask, session
from flask_alembic import Alembic
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.admin import admin
from cacao_accounting.api import api
from cacao_accounting.app import cacao_app as main_app
from cacao_accounting.auth import administrador_sesion, login
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.bancos import bancos
from cacao_accounting.cache import cache
from cacao_accounting.compras import compras
from cacao_accounting.config import (
    DIRECTORIO_ARCHIVOS,
    DIRECTORIO_PLANTILLAS,
    MODO_ESCRITORIO,
    TESTING_MODE,
)
from cacao_accounting.contabilidad import contabilidad
from cacao_accounting.database import database
from cacao_accounting.database.helpers import (
    entidades_creadas,
    obtener_id_modulo_por_nombre,
)
from cacao_accounting.document_flow.status import _
from cacao_accounting.exceptions.mensajes import ERROR2
from cacao_accounting.inventario import inventario
from cacao_accounting.modulos import (
    registrar_modulos_adicionales,
    validar_modulo_activo,
)
from cacao_accounting.reportes import reportes
from cacao_accounting.setup import setup_ as setup_wizard
from cacao_accounting.ventas import ventas
from cacao_accounting.version import PRERELEASE

alembic = Alembic()


def command() -> None:  # pragma: no cover
    """Interfaz de linea de commandos."""
    from cacao_accounting.cli import linea_comandos

    linea_comandos(as_module="cacao_accounting")


def iniciar_extenciones(app: Flask | None = None) -> None:
    """Inicializa extenciones."""
    if app and isinstance(app, Flask):
        from flask_wtf.csrf import CSRFProtect

        csrf = CSRFProtect()
        csrf.init_app(app)
        # alembic.init_app(app)
        database.init_app(app)
        administrador_sesion.init_app(app)
        cache.init_app(app)
    else:
        raise RuntimeError(ERROR2)


def registrar_rutas_predeterminadas(app: Flask | None = None) -> None:
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


def registrar_blueprints(app: Flask | None = None) -> None:
    """Registra blueprints por defecto."""
    if app and isinstance(app, Flask):
        with app.app_context():
            app.register_blueprint(admin)
            app.register_blueprint(api)
            app.register_blueprint(main_app)
            app.register_blueprint(login)
            registrar_modulos_adicionales(app)
            # Main Modules
            app.register_blueprint(bancos, url_prefix="/cash_management")
            app.register_blueprint(contabilidad, url_prefix="/accounting")
            app.register_blueprint(compras, url_prefix="/buying")
            app.register_blueprint(inventario, url_prefix="/inventory")
            app.register_blueprint(reportes)
            app.register_blueprint(ventas, url_prefix="/sales")
            app.register_blueprint(setup_wizard, url_prefix="/setup")

    else:
        raise RuntimeError(ERROR2)


def actualiza_variables_globales_jinja(app: Flask | None = None) -> None:
    """Utilidad para asegurar que varios opciones globales esten dispinibles en Jinja2."""
    if app and isinstance(app, Flask):
        with app.app_context():
            app.jinja_env.trim_blocks = True
            app.jinja_env.lstrip_blocks = True
            app.jinja_env.globals.update(validar_modulo_activo=validar_modulo_activo)
            app.jinja_env.globals.update(permisos=Permisos)
            app.jinja_env.globals.update(_=_)
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
            app.jinja_env.globals.update(document_currency_code=document_currency_code)
            app.jinja_env.globals.update(format_money_with_currency=format_money_with_currency)
            app.jinja_env.globals.update(format_quantity=format_quantity)
            from cacao_accounting.document_flow.status import calculate_document_status

            app.jinja_env.globals.update(document_status_info=calculate_document_status)
            # now available globally in templates
            app.jinja_env.globals.update(now=datetime.now)
            if PRERELEASE:
                app.jinja_env.globals.update(bdrul=app.config.get("SQLALCHEMY_DATABASE_URI"))
                app.jinja_env.globals.update(development=True)

    else:
        raise RuntimeError(ERROR2)


def document_currency_code(document: object | None) -> str:
    """Return the display currency code for a transactional document."""
    if document is None:
        return ""
    for attr in ("transaction_currency", "currency", "base_currency"):
        value = getattr(document, attr, None)
        if value:
            return str(value)
    company = getattr(document, "company", None) or getattr(document, "entity", None)
    if not company:
        return ""
    from cacao_accounting.database import Entity

    entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalars().first()
    return str(getattr(entity, "currency", "") or "")


def _decimal_for_display(value: object | None) -> Decimal:
    """Normalize template values before numeric formatting."""
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def format_money_with_currency(value: object | None, currency_code: str | None = "") -> str:
    """Format money with thousands separators and optional currency code."""
    amount = f"{_decimal_for_display(value):,.2f}"
    return f"{currency_code} {amount}" if currency_code else amount


def format_quantity(value: object | None) -> str:
    """Format operational quantities with four decimals."""
    return f"{_decimal_for_display(value):,.4f}"


def create_app(ajustes: dict | None = None) -> Flask:
    """Aplication factory."""
    cacao_app = Flask(
        "cacao_accounting",
        template_folder=DIRECTORIO_PLANTILLAS,
        static_folder=DIRECTORIO_ARCHIVOS,
    )

    setattr(cacao_app, "wsgi_app", ProxyFix(cacao_app.wsgi_app, x_for=1, x_proto=1, x_host=1))

    if ajustes:
        cacao_app.config.from_mapping(ajustes)

    if not cacao_app.config.get("SECRET_KEY"):
        if cacao_app.config.get("TESTING"):
            cacao_app.config["SECRET_KEY"] = "test-secret-key"
        else:
            cacao_app.config["SECRET_KEY"] = "dev-secret-key"

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
        passwd = environ.get("CACAO_PSWD") or "cacao"

        if TESTING_MODE:
            database.drop_all()
            inicia_base_de_datos(app=cacao_app, user=user, passwd=passwd, with_examples=True)
        else:
            inicia_base_de_datos(app=cacao_app, user=user, passwd=passwd, with_examples=False)

    @cacao_app.before_request
    def before_request():  # pragma: no cover
        """Establece un periodo de 30 minutos de valides de la sesión."""
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
