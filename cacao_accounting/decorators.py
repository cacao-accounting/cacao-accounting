# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Funciones auxiliares para usar en las rutas de la aplicación."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from functools import wraps

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import abort, flash
from flask_login import current_user
from werkzeug.exceptions import HTTPException

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.company_context import authorized_company_codes
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.i18n import _
from cacao_accounting.modulos import validar_modulo_activo
from cacao_accounting.runtime_mode import is_desktop_mode


def modulo_activo(modulo):  # pragma: no cover
    """Verifica si el recurso solicitado pertenece a un modulo activo."""
    modulos = [modulo] if isinstance(modulo, str) else list(modulo)

    def decorator_modulo_activo(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if any(validar_modulo_activo(modulo_nombre) for modulo_nombre in modulos):
                return func(*args, **kwargs)
            else:
                flash(_("El módulo que intenta acceder se encuentra inactivo"))
                return abort(404)

        return wrapper

    return decorator_modulo_activo


def verifica_acceso(modulo, accion=None):  # pragma: no cover
    """Comprueba si un usuario tiene acceso a un recurso determinado.

    Con ``accion`` (crear/editar/anular) exige además el permiso de
    acción correspondiente: el acceso sencillo no concede escrituras
    (#1601).
    """

    def decorator_verifica_acceso(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash(_("No se encuentra autorizado a acceder al recurso solicitado."))
                return abort(403)
            module_id = obtener_id_modulo_por_nombre(modulo)
            permisos = Permisos(modulo=module_id, usuario=current_user.id)
            if permisos.autorizado and (accion is None or getattr(permisos, accion, False)):
                return func(*args, **kwargs)
            else:
                flash(_("No se encuentra autorizado a acceder al recurso solicitado."))
                return abort(403)

        return wrapper

    return decorator_verifica_acceso


def verifica_permiso(modulo: str, accion: str):
    """Require a concrete action permission for a state-changing route."""

    def decorator_verifica_permiso(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash(_("No se encuentra autorizado para ejecutar esta acción."))
                return abort(403)
            module_id = obtener_id_modulo_por_nombre(modulo)
            permisos = Permisos(modulo=module_id, usuario=current_user.id)
            if getattr(permisos, accion, False):
                return func(*args, **kwargs)
            flash(_("No se encuentra autorizado para ejecutar esta acción."))
            return abort(403)

        return wrapper

    return decorator_verifica_permiso


def verifica_permiso_cualquiera(modulos: tuple[str, ...], accion: str):
    """Require the action permission in at least one of the given modules."""

    def decorator_verifica_permiso_cualquiera(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash(_("No se encuentra autorizado para ejecutar esta acción."))
                return abort(403)
            for modulo in modulos:
                module_id = obtener_id_modulo_por_nombre(modulo)
                if module_id is None:
                    continue
                permisos = Permisos(modulo=module_id, usuario=current_user.id)
                if getattr(permisos, accion, False):
                    return func(*args, **kwargs)
            flash(_("No se encuentra autorizado para ejecutar esta acción."))
            return abort(403)

        return wrapper

    return decorator_verifica_permiso_cualquiera


def exige_acceso_compania(
    modulo: str, company: str | None, accion: str = "consultar", allow_unauthenticated: bool = False
) -> None:
    """Enforce module/action RBAC and explicit company access.

    Args:
        modulo: Module name (e.g., "sales", "purchases", "accounting")
        company: Company code to check access against
        accion: Action type (consultar, crear, editar, autorizar, anular)
        allow_unauthenticated: If True, allows internal services without authentication.
                               Must be explicitly set; default is False to prevent
                               accidental privilege escalation.
    """
    try:
        is_auth = bool(current_user and getattr(current_user, "is_authenticated", False))
    except Exception:
        is_auth = False

    if not is_auth:
        if not allow_unauthenticated:
            abort(403)
        return
    module_id = obtener_id_modulo_por_nombre(modulo)
    permisos = Permisos(modulo=module_id, usuario=current_user.id)
    if permisos.administrador:
        return
    permission_name = {
        "autorizar": "autorizar",
        "anular": "anular",
        "crear": "crear",
        "editar": "editar",
        "consultar": "consultar",
    }.get(accion, "consultar")
    if getattr(permisos, permission_name, False) and permisos.tiene_acceso_compania(company):
        return
    abort(403)


def exige_acceso_compania_cualquiera(modulos: tuple[str, ...], company: str | None, accion: str = "consultar") -> None:
    """Require company access in at least one of several operational modules."""
    for modulo in modulos:
        try:
            exige_acceso_compania(modulo, company, accion)
            return
        except HTTPException as exc:
            if exc.code != 403:
                raise
    abort(403)


def resolve_required_company(company: str | None, modulo: str) -> str:
    """Resuelve la compañía de una petición que la requiere.

    Cuando la petición trae el código de compañía se devuelve tal cual para que
    la capa de permisos lo valide. En Cloud el parámetro es obligatorio: no se
    asume una compañía aunque el usuario tenga una sola autorizada, porque la
    UI debe enviar siempre la compañía activa (#911). En Desktop se resuelve la
    única compañía autorizada, que es el caso operativo normal.

    Args:
        company: Código de compañía recibido en la petición, o ``None``.
        modulo: Módulo usado para obtener las compañías autorizadas del usuario.

    Returns:
        El código de compañía a utilizar.
    """
    if company:
        return company
    if not is_desktop_mode():
        abort(400, description=_("La compañía es obligatoria."))
    resolved = _single_authorized_company(modulo)
    if resolved is not None:
        return resolved
    abort(400, description=_("La compañía es obligatoria."))


def _single_authorized_company(modulo: str) -> str | None:
    """Devuelve la única compañía autorizada del usuario o ``None``."""
    companies = authorized_company_codes(modulo)
    return companies[0] if len(companies) == 1 else None
