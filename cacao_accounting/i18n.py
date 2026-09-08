# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""i18n y l10n: internacionalización y localización de Cacao Accounting.

Este módulo es la única fuente del helper ``_`` usado para marcar cadenas
visibles (i18n) y de los selectores de idioma y zona horaria que resuelven la
localización (l10n) de cada petición:

- ``_`` traduce contra Flask-Babel cuando el catálogo esta disponible y cae a
  la identidad (cadena sin traducir) en contextos sin Babel, por ejemplo el
  modo desktop sin catálogo instalado.
- ``_get_locale`` resuelve el código de idioma en cascada: idioma del usuario
  autenticado y, en su defecto, el idioma configurado en la instalación.
- ``_get_timezone`` resuelve la zona horaria de la instalación con un valor
  predeterminado en entornos donde el registro de configuración no existe.
"""

from __future__ import annotations

from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

__all__ = ["DEFAULT_TIMEZONE", "_", "_l", "_get_locale", "_get_timezone", "lazy_gettext"]

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel import gettext as _babel_gettext
    from flask_babel import lazy_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        """Devuelve la cadena sin traducir cuando Flask-Babel no esta disponible."""
        return value

    def lazy_gettext(value: str) -> str:
        """Devuelve la cadena sin traducir cuando Flask-Babel no esta disponible."""
        return value

else:

    def _(value: str) -> str:
        """Traduce una cadena visible contra el catalogo activo de Flask-Babel."""
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):
            return value


_l = lazy_gettext


DEFAULT_TIMEZONE = "America/Managua"


def _get_locale() -> str:
    """Retorna el idioma configurado para la aplicacion."""
    from flask import has_app_context, has_request_context

    if not (has_app_context() or has_request_context()):
        return "es"

    try:
        if current_user and current_user.is_authenticated:
            user_lang = getattr(current_user, "language", None)
            if user_lang:
                return user_lang
    except Exception:
        pass

    try:
        from cacao_accounting.setup.service import SETUP_LANGUAGE, get_setup_value

        return get_setup_value(SETUP_LANGUAGE, "es")
    except SQLAlchemyError:
        return "es"


def _get_timezone() -> str:
    """Retorna la zona horaria configurada para la aplicacion."""
    from flask import has_app_context, has_request_context

    if not (has_app_context() or has_request_context()):
        return DEFAULT_TIMEZONE
    try:
        from cacao_accounting.setup.service import SETUP_TIMEZONE, get_setup_value

        return get_setup_value(SETUP_TIMEZONE, DEFAULT_TIMEZONE)
    except SQLAlchemyError:
        return DEFAULT_TIMEZONE
