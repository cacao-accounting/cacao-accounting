# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Resolución y persistencia de la compañía activa del usuario.

La compañía activa es una preferencia de interfaz: decide qué compañía usan los
dashboards de módulo al construir enlaces a reportes. Se guarda en una cookie del
navegador (sin depender de la caché) y siempre se valida contra las compañías
autorizadas del usuario antes de usarse. Solo aplica en modo cloud; en modo
desktop existe una única compañía y no se muestra selector.
"""

from __future__ import annotations

from flask import Response, g, has_request_context, request
from flask_login import current_user

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.runtime_mode import is_desktop_mode

ACTIVE_COMPANY_COOKIE = "cacao_active_company"
ACTIVE_COMPANY_MODULE = "accounting"
ACTIVE_COMPANY_COOKIE_MAX_AGE = 365 * 24 * 3600


def authorized_company_codes(modulo: str = ACTIVE_COMPANY_MODULE) -> list[str]:
    """Devuelve los códigos de compañía autorizados del usuario actual.

    Args:
        modulo: Módulo usado para evaluar los permisos del usuario.

    Returns:
        Lista de códigos de compañía autorizados (vacía si no hay sesión).
    """
    try:
        is_auth = bool(current_user and getattr(current_user, "is_authenticated", False))
    except Exception:
        is_auth = False
    if not is_auth:
        return []

    cache_key = f"_ca_authorized_companies_{modulo}_{current_user.id}"
    if has_request_context():
        cached = getattr(g, cache_key, None)
        if cached is not None:
            return cached

    module_id = obtener_id_modulo_por_nombre(modulo)
    permisos = Permisos(modulo=module_id, usuario=current_user.id)
    codes = list(permisos.obtener_companias_autorizadas())

    if has_request_context():
        setattr(g, cache_key, codes)
    return codes


def get_active_company(requested: str | None = None) -> str | None:
    """Resuelve la compañía activa del usuario.

    Prioridad: compañía solicitada en la petición, cookie del navegador y, por
    último, la primera compañía autorizada. Todo valor se valida contra las
    compañías autorizadas del usuario; un valor inválido se descarta.

    Args:
        requested: Código de compañía recibido en la petición, o ``None``.

    Returns:
        El código de compañía activa, o ``None`` si el usuario no tiene ninguna.
    """
    companies = authorized_company_codes()
    if not companies:
        return None
    if requested and requested in companies:
        return requested
    cookie_value = request.cookies.get(ACTIVE_COMPANY_COOKIE) if has_request_context() else None
    if cookie_value and cookie_value in companies:
        return cookie_value
    return companies[0]


def set_active_company(response: Response, code: str | None) -> bool:
    """Valida y guarda la compañía activa en la cookie del navegador.

    Args:
        response: Respuesta sobre la que escribir la cookie.
        code: Código de compañía elegido.

    Returns:
        ``True`` si el usuario tiene acceso a la compañía y se guardó.
    """
    if not code or code not in authorized_company_codes():
        return False
    response.set_cookie(
        ACTIVE_COMPANY_COOKIE,
        code,
        max_age=ACTIVE_COMPANY_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not is_desktop_mode(),
    )
    return True
