# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Definición central de errores del sistema."""


class CacaoAccountingException(Exception):
    """Clase base para generar errores locales."""


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
    """Log the exception details and flash a generic localized error message to the user,

    unless the exception is a known safe domain/validation exception.
    """
    from flask import flash
    from cacao_accounting.logs import log
    from cacao_accounting.document_flow.status import _

    log.error("Error en operación: {}", exc)

    safe_exception_names = {
        "ValueError",
        "ArithmeticError",
        "CacaoAccountingException",
        "RecurringJournalError",
        "BudgetError",
        "QueryToolError",
        "PrintingError",
        "HTTPException",
    }

    is_safe = False
    for base in type(exc).__mro__:
        if base.__name__ in safe_exception_names:
            is_safe = True
            break

    if is_safe:
        flash(_(str(exc)), category)
    else:
        flash(_("Error interno al procesar la solicitud."), category)
