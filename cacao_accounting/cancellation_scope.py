# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Predicados de alcance de anulación para consultas contables.

``ordinary_gl_scope`` excluye los originales anulados y sus contrapartidas
técnicas, mientras que ``cancelled_originals_scope`` devuelve solo los
originales anulados para reconstruir la anulación completa.
"""

from __future__ import annotations

from typing import Any


def ordinary_gl_scope() -> tuple[Any, Any]:
    """Restricciones GL para la vista ordinaria: excluye originales anulados y contrapartidas."""
    from cacao_accounting.database import GLEntry

    return (GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))


def cancelled_originals_scope() -> tuple[Any]:
    """Muestra solo los originales anulados (no las contrapartidas técnicas)."""
    from cacao_accounting.database import GLEntry

    return (GLEntry.is_cancelled.is_(True),)
