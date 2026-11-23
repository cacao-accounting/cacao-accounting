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


def effective_gl_scope() -> tuple[Any, ...]:
    """Restricciones GL para reportes: originales vivos y reversiones vigentes.

    Excluye originales anulados y conserva las contrapartidas activas cuya
    línea origen pertenece a **otro** período: son el efecto efectivo de una
    reversión interperíodo (#1970). Las contrapartidas del mismo período se
    anulan con su original y quedan fuera.
    """
    from sqlalchemy import exists, or_
    from sqlalchemy.orm import aliased

    from cacao_accounting.database import GLEntry

    origen = aliased(GLEntry)
    mismo_periodo = exists().where(
        origen.id == GLEntry.reversal_of,
        origen.accounting_period_id == GLEntry.accounting_period_id,
    )
    return (
        GLEntry.is_cancelled.is_(False),
        or_(GLEntry.is_reversal.is_(False), ~mismo_periodo),
    )
