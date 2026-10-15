# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Fachada de compatibilidad para los servicios de contabilización."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cacao_accounting.contabilidad import posting_service as _posting_service

if TYPE_CHECKING:
    # Re-export the public symbols so static analyzers resolve their real types.
    # Runtime lookups still go through ``__getattr__`` for backwards compatibility.
    from cacao_accounting.contabilidad.posting_service import (  # noqa: F401
        GLEntryParams,
        PostingError,
        _add_entries,
        _create_gl_entry,
        _document_contexts,
        _lookup_exchange_rate,
        cancel_document,
        post_comprobante_contable,
        submit_document,
    )

JOURNAL_TRANSACTION_TYPE = "journal_entry"
_ERROR_INVENTARIO_REQUIERE_ALMACEN = "La linea de inventario requiere almacen."
_ERROR_YA_TIENE_ENTRADAS_GL = "Este documento ya tiene entradas GL contabilizadas."
_DOCUMENTO_YA_CONTABILIZADO_MSG = "Este documento ya tiene asientos contables activos; no se puede contabilizar dos veces."
_REMARKS_CUENTA_BANCARIA_PAGO = "Cuenta bancaria de pago"


def __getattr__(name: str) -> Any:
    """Devuelve un símbolo histórico desde su implementación extraída."""
    try:
        return getattr(_posting_service, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__() -> list[str]:
    """Enumera símbolos propios y los mantenidos por compatibilidad."""
    return sorted(set(globals()) | set(dir(_posting_service)))
