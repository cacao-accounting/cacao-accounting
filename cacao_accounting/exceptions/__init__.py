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
