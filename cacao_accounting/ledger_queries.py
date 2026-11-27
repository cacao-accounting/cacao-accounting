# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Predicados compartidos para consultar ledgers contables y de inventario.

Una anulación dentro del mismo período conserva el asiento o movimiento original
y agrega su contrapartida. Los reportes ordinarios deben ocultar ambos lados del
par, mientras que las reconstrucciones deben sumar ambos para obtener el neto.
"""

from datetime import date
from typing import Any

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased

from cacao_accounting.database import Book, DocumentTransition, GLEntry, StockLedgerEntry, database
from cacao_accounting.i18n import _


class PrimaryLedgerUnavailableError(ValueError):
    """Raised when a balance query has no active accounting book to read."""


def primary_ledger_id(company: str, requested: str | None = None) -> str:
    """Resolve the deterministic read ledger for non-accounting modules.

    Operational/reporting consumers must never aggregate every active book.
    The accounting module is the only place where a user explicitly selects a
    book; all other consumers use the system default (then primary) active book.
    """
    query = select(Book).where(Book.entity == company, Book.status == "activo")
    if requested:
        query = query.where((Book.id == requested) | (Book.code == requested))
    else:
        query = query.order_by(Book.default.desc(), Book.is_primary.desc(), Book.code.asc())
    book = database.session.execute(query).scalars().first()
    if book is None:
        raise PrimaryLedgerUnavailableError(
            _("No existe un libro contable activo para la compañía %(company)s.") % {"company": company}
        )
    return book.id


def exclude_cancelled_gl_entries(query: Any) -> Any:
    """Excluye tanto originales anulados como sus reversas del mismo período."""
    return query.where(GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))


def exclude_cancelled_stock_entries(query: Any, as_of_date: date | None = None) -> Any:
    """Excluye todos los movimientos de un voucher de inventario anulado.

    ``StockLedgerEntry`` marca el movimiento original como cancelado y conserva
    el contramovimiento como una fila nueva. La existencia de un movimiento
    cancelado en el mismo voucher mantiene compatibilidad con datos históricos.

    La política de anulación exige la misma fecha y el mismo período contable
    que el documento original, por lo que el sistema no genera reversas de
    inventario interperíodo (#2263). Las correcciones posteriores se registran
    como operaciones independientes, nunca reescribiendo el corte histórico.
    """
    cancelled = aliased(StockLedgerEntry)
    cancelled_sibling = exists(
        select(cancelled.id).where(
            cancelled.company == StockLedgerEntry.company,
            cancelled.voucher_type == StockLedgerEntry.voucher_type,
            cancelled.voucher_id == StockLedgerEntry.voucher_id,
            cancelled.is_cancelled.is_(True),
        )
    )
    if as_of_date is None:
        return query.where(
            StockLedgerEntry.is_cancelled.is_(False),
            StockLedgerEntry.is_reversal.is_(False),
            ~cancelled_sibling,
        )
    cancellation_after_cutoff = exists(
        select(DocumentTransition.id).where(
            DocumentTransition.company == StockLedgerEntry.company,
            DocumentTransition.source_type == StockLedgerEntry.voucher_type,
            DocumentTransition.source_id == StockLedgerEntry.voucher_id,
            DocumentTransition.transition_type == "cancellation",
            DocumentTransition.posting_date > as_of_date,
        )
    )
    return query.where(
        or_(
            and_(
                StockLedgerEntry.is_cancelled.is_(False),
                StockLedgerEntry.is_reversal.is_(False),
                ~cancelled_sibling,
            ),
            and_(
                StockLedgerEntry.is_cancelled.is_(True),
                StockLedgerEntry.is_reversal.is_(False),
                cancellation_after_cutoff,
            ),
        )
    )
