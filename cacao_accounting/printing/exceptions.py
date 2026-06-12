# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Excepciones para el servicio de impresión."""


class PrintingError(Exception):
    """Base exception for printing service."""


class PrintTemplateNotFoundError(PrintingError):
    """Raised when a print template is not found."""


class PrintPermissionError(PrintingError):
    """Raised when a user or company cannot access a print resource."""


class PrintableDocumentNotRegisteredError(PrintingError):
    """Raised when a document type is not registered."""


class TemplateValidationError(PrintingError):
    """Raised when template validation fails."""
