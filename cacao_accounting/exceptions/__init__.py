# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Definición central de errores del sistema."""


class CacaoAccountingException(Exception):
    """Clase base para generar errores locales."""

    _safe_for_display = True


class DataError(CacaoAccountingException):
    """Clase para generar errores de datos."""


class IntegrityError(CacaoAccountingException):
    """Clase para generar errores de Integridad."""


class TransactionError(CacaoAccountingException):
    """Clase para generar errores en transacciones."""


class OperationalError(CacaoAccountingException):
    """Clase para generar errores operativos."""


class AccessDenied(CacaoAccountingException):
    """Clase para generar errores de acceso."""


def flash_error(exc, category="danger"):
    """Log the exception details and flash a generic localized error message to the user.

    This function logs the full exception safely, but displays a generic message
    unless the exception is a known safe domain/validation exception.

    Exceptions are considered safe for display when they define the class attribute
    ``_safe_for_display = True``. Built-in exception types are checked by name as
    a fallback since they cannot be modified directly.
    """
    from flask import flash
    from cacao_accounting.logs import log
    from cacao_accounting.document_flow.status import _

    log.error("Error en operación: {}", exc)

    _SAFE_BUILTIN_NAMES = frozenset(
        {
            "ValueError",
            "ArithmeticError",
            "HTTPException",
        }
    )

    is_safe = False
    for base in type(exc).__mro__:
        if getattr(base, "_safe_for_display", False):
            is_safe = True
            break
        if base.__name__ in _SAFE_BUILTIN_NAMES:
            is_safe = True
            break

    if is_safe:
        flash(_(str(exc)), category)
    else:
        flash(_("Error interno al procesar la solicitud."), category)
