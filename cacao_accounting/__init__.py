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
from secrets import token_urlsafe
from sqlalchemy.exc import SQLAlchemyError

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
from cacao_accounting.compras import compras
from cacao_accounting.config import (
    DIRECTORIO_ARCHIVOS,
    DIRECTORIO_PLANTILLAS,
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
from cacao_accounting.logs import log
from cacao_accounting.module_badges import module_badge
from cacao_accounting.imports.routes import imports
from cacao_accounting.imports.utils.recovery import recover_crashed_batches
from cacao_accounting.inventario import inventario
from cacao_accounting.printing.routes import printing_public
from cacao_accounting.printing.admin_routes import printing_admin
from cacao_accounting.printing import init_printing
from cacao_accounting.modulos import (
    registrar_modulos_adicionales,
    validar_modulo_activo,
)
from cacao_accounting.reportes import reportes
from cacao_accounting.runtime_mode import force_single_entity, is_cloud_mode, is_desktop_mode
from cacao_accounting.setup import setup_ as setup_wizard
from cacao_accounting.ventas import ventas
from cacao_accounting.version import PRERELEASE
from flask_babel import Babel

alembic = Alembic()
babel = Babel()

DEFAULT_TIMEZONE = "America/Managua"


def command() -> None:  # pragma: no cover
    """Interfaz de linea de commandos."""
    from cacao_accounting.cli import linea_comandos_main

    linea_comandos_main()


def iniciar_extenciones(app: Flask | None = None) -> None:
    """Inicializa extenciones."""
    if app and isinstance(app, Flask):
        from flask_wtf.csrf import CSRFProtect
        from cacao_accounting.limiter import init_limiter
        from cacao_accounting.cache import init_cache
        from flask import has_app_context, has_request_context

        def get_locale():
            if not (has_app_context() or has_request_context()):
                return "es"
            try:
                from cacao_accounting.setup.service import get_setup_value, SETUP_LANGUAGE

                return get_setup_value(SETUP_LANGUAGE, "es")
            except SQLAlchemyError:
                return "es"

        def get_timezone():
            if not (has_app_context() or has_request_context()):
                return DEFAULT_TIMEZONE
            try:
                from cacao_accounting.setup.service import get_setup_value, SETUP_TIMEZONE

                return get_setup_value(SETUP_TIMEZONE, DEFAULT_TIMEZONE)
            except SQLAlchemyError:
                return DEFAULT_TIMEZONE

        csrf = CSRFProtect()
        csrf.init_app(app)
        alembic.init_app(app)
        database.init_app(app)
        administrador_sesion.init_app(app)
        babel.init_app(app, locale_selector=get_locale, timezone_selector=get_timezone)
        init_cache(app)
        init_limiter(app)
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
            app.register_blueprint(imports, url_prefix="/imports")
            app.register_blueprint(printing_public)
            app.register_blueprint(printing_admin)
            init_printing()

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
            app.jinja_env.globals.update(MODO_ESCRITORIO=is_desktop_mode())
            app.jinja_env.globals.update(is_desktop_mode=is_desktop_mode)
            app.jinja_env.globals.update(is_cloud_mode=is_cloud_mode)
            app.jinja_env.globals.update(force_single_entity=force_single_entity)
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
            app.jinja_env.globals.update(module_badge=module_badge)
            app.jinja_env.globals.update(collaboration_active_users=collaboration_active_users)
            app.jinja_env.globals.update(document_collaboration_tasks=document_collaboration_tasks)
            app.jinja_env.globals.update(current_user_open_task_count=current_user_open_task_count)
            app.jinja_env.globals.update(pending_approval_count=pending_approval_count)
            app.jinja_env.globals.update(audit_action_label=audit_action_label)
            from cacao_accounting.document_flow.status import calculate_document_status

            app.jinja_env.globals.update(document_status_info=calculate_document_status)
            # now available globally in templates
            app.jinja_env.globals.update(now=datetime.now)
            if PRERELEASE:
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


def collaboration_active_users() -> list:
    """Return active users for collaboration widgets."""
    if not is_cloud_mode():
        return []
    from cacao_accounting.collaboration_service import active_users

    return active_users()


def document_collaboration_tasks(document_type: str, document_id: str) -> list:
    """Return document tasks for collaboration widgets."""
    if not is_cloud_mode():
        return []
    from cacao_accounting.collaboration_service import list_document_tasks

    return list_document_tasks(document_type, document_id)


def current_user_open_task_count() -> int:
    """Return current user's open cloud task count for navigation badges."""
    if not is_cloud_mode() or not current_user or not current_user.is_authenticated:
        return 0
    from cacao_accounting.collaboration_service import open_task_count

    return open_task_count(str(current_user.id))


def pending_approval_count() -> int:
    """Return count of pending approval requests for the current user."""
    if not is_cloud_mode() or not current_user or not current_user.is_authenticated:
        return 0
    from cacao_accounting.database import ApprovalRequest
    from sqlalchemy import select

    try:
        count = (
            database.session.execute(
                select(ApprovalRequest).filter(
                    ApprovalRequest.status.in_({"Pending Approval", "Pending Cancellation"}),
                )
            )
            .scalars()
            .all()
        )
        return len(count)
    except SQLAlchemyError:
        return 0


def audit_action_label(action: str) -> str:
    """Return display text for audit actions not covered by older template maps."""
    labels = {
        "task_created": _("asignó una tarea"),
        "task_status_changed": _("cambió el estado de una tarea"),
        "task_completed": _("completó una tarea"),
        "task_cancelled": _("canceló una tarea"),
    }
    return labels.get(action, action)


def create_app(ajustes: dict | None = None) -> Flask:
    """Aplication factory."""
    cacao_app = Flask(
        "cacao_accounting",
        template_folder=DIRECTORIO_PLANTILLAS,
        static_folder=DIRECTORIO_ARCHIVOS,
    )

    # Configurar límites por defecto
    cacao_app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    # Configurar cookies de sesión
    cacao_app.config["SESSION_COOKIE_SECURE"] = True
    cacao_app.config["SESSION_COOKIE_HTTPONLY"] = True
    cacao_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    setattr(cacao_app, "wsgi_app", ProxyFix(cacao_app.wsgi_app, x_for=1, x_proto=1, x_host=1))

    if ajustes:
        cacao_app.config.from_mapping(ajustes)

    _configure_app_secret_key(cacao_app)
    _register_app_hooks(cacao_app)

    actualiza_variables_globales_jinja(app=cacao_app)
    iniciar_extenciones(app=cacao_app)
    registrar_blueprints(app=cacao_app)
    registrar_rutas_predeterminadas(app=cacao_app)

    with cacao_app.app_context():
        try:
            recover_crashed_batches()
        except SQLAlchemyError as e:
            log.error("Error al recuperar lotes de importación: {}", e)

    return cacao_app


def _configure_app_secret_key(app: Flask) -> None:
    """Configure a deterministic test secret or a random production key."""
    if app.config.get("SECRET_KEY"):
        return
    if app.config.get("TESTING"):
        app.config["SECRET_KEY"] = "-".join(("test", "secret", "key"))
        return
    app.config["SECRET_KEY"] = token_urlsafe(32)


def _register_app_hooks(app: Flask) -> None:
    """Register request hooks used by the application factory."""

    @app.before_request
    def before_request():  # pragma: no cover
        """Establece un periodo de 30 minutos de valides de la sesión."""
        session.permanent = True
        app.permanent_session_lifetime = timedelta(minutes=30)

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "manifest-src 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Referrer-Policy"] = "same-origin"
        return response


# <---------------------------------------------------------------------------------------------> #
# La logica de negocios se define en cada módulo respectivo.
# <---------------------------------------------------------------------------------------------> #
