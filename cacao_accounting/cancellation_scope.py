# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Predicados de alcance de anulación para consultas contables.

``ordinary_gl_scope`` excluye los originales anulados y sus contrapartidas
técnicas, mientras que ``cancelled_originals_scope`` devuelve solo los
originales anulados para reconstruir la anulación completa.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def ordinary_gl_scope() -> tuple[Any, Any]:
    """Restricciones GL para la vista ordinaria: excluye originales anulados y contrapartidas."""
    from cacao_accounting.database import GLEntry

    return (GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))


def cancelled_originals_scope(as_of_date: date | None = None) -> tuple[Any, ...]:
    """Muestra solo los originales anulados (no las contrapartidas técnicas)."""
    from sqlalchemy import not_

    from cacao_accounting.database import GLEntry

    scope = [GLEntry.is_cancelled.is_(True)]
    if as_of_date is not None:
        scope.append(not_(_cancellation_after_cutoff(as_of_date)))
    return tuple(scope)


def effective_gl_scope(as_of_date: date | None = None) -> tuple[Any, ...]:
    """Restricciones GL para reportes: originales vivos y reversiones vigentes.

    Excluye originales anulados y conserva las contrapartidas activas cuya
    línea origen pertenece a **otro** período: son el efecto efectivo de una
    reversión interperíodo (#1970). Las contrapartidas del mismo período se
    anulan con su original y quedan fuera.

    Un original cancelado con reversa **posterior** en otro período vuelve a
    entrar: su movimiento estuvo vigente en el corte original y la contrapartida
    ya se contabilizó en el período posterior (#2265). Una reversa fechada antes
    del origen no es válida: se excluyen la contrapartida y el original que
    pretendía revivir. La anulación del mismo período sigue teniendo efecto cero
    y no se muestra en ninguno de los dos lados.
    """
    from sqlalchemy import exists, or_
    from sqlalchemy.orm import aliased

    from cacao_accounting.database import GLEntry

    origen = aliased(GLEntry)
    reversa = aliased(GLEntry)
    reversa_posterior = exists().where(
        reversa.reversal_of == GLEntry.id,
        reversa.is_reversal.is_(True),
        reversa.posting_date > GLEntry.posting_date,
        or_(
            reversa.accounting_period_id != GLEntry.accounting_period_id,
            GLEntry.accounting_period_id.is_(None),
        ),
    )
    reversa_ineficaz = exists().where(
        origen.id == GLEntry.reversal_of,
        or_(
            origen.accounting_period_id == GLEntry.accounting_period_id,
            GLEntry.posting_date <= origen.posting_date,
        ),
    )
    return (
        or_(GLEntry.is_cancelled.is_(False), reversa_posterior, _cancellation_after_cutoff(as_of_date)),
        or_(GLEntry.is_reversal.is_(False), ~reversa_ineficaz),
    )


def _cancellation_after_cutoff(as_of_date: date | None) -> Any:
    """Keep a cancelled original visible before its recorded effective date."""
    from sqlalchemy import exists, select

    from cacao_accounting.database import DocumentTransition, GLEntry

    if as_of_date is None:
        return GLEntry.id.is_(None)
    return exists(
        select(DocumentTransition.id).where(
            DocumentTransition.company == GLEntry.company,
            DocumentTransition.source_type == GLEntry.voucher_type,
            DocumentTransition.source_id == GLEntry.voucher_id,
            DocumentTransition.transition_type == "cancellation",
            DocumentTransition.posting_date > as_of_date,
        )
    )
