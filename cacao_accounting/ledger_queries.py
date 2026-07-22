"""Predicados compartidos para consultar ledgers contables y de inventario.

Una anulación dentro del mismo período conserva el asiento o movimiento original
y agrega su contrapartida. Los reportes ordinarios deben ocultar ambos lados del
par, mientras que las reconstrucciones deben sumar ambos para obtener el neto.
"""

from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import aliased

from cacao_accounting.database import Book, GLEntry, StockLedgerEntry, database


def primary_ledger_id(company: str) -> str | None:
    """Resolve the deterministic read ledger for non-accounting modules.

    Operational/reporting consumers must never aggregate every active book.
    The accounting module is the only place where a user explicitly selects a
    book; all other consumers use the system default (then primary) active book.
    """
    book = database.session.execute(
        select(Book)
        .where(Book.entity == company, Book.status == "activo")
        .order_by(Book.default.desc(), Book.is_primary.desc(), Book.code.asc())
    ).scalars().first()
    return book.id if book else None


def exclude_cancelled_gl_entries(query: Any) -> Any:
    """Excluye tanto originales anulados como sus reversas del mismo período."""
    return query.where(GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))


def exclude_cancelled_stock_entries(query: Any) -> Any:
    """Excluye todos los movimientos de un voucher de inventario anulado.

    ``StockLedgerEntry`` marca el movimiento original como cancelado y conserva
    el contramovimiento como una fila nueva. Como el modelo no tiene
    ``is_reversal``, la existencia de un movimiento cancelado en el mismo voucher
    identifica el grupo completo que debe ocultarse en reportes operativos.
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
    return query.where(~cancelled_sibling)
