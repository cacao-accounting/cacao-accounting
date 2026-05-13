# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Repositorio para comprobantes contables manuales."""

from __future__ import annotations

from sqlalchemy import select

from cacao_accounting.database import ComprobanteContable, ComprobanteContableDetalle, database

JOURNAL_TRANSACTION_TYPE = "journal_entry"


def add_journal(journal: ComprobanteContable, lines: list[ComprobanteContableDetalle]) -> ComprobanteContable:
    """Persiste un comprobante contable manual y sus lineas."""
    database.session.add(journal)
    database.session.flush()
    for line in lines:
        line.transaction = JOURNAL_TRANSACTION_TYPE
        line.transaction_id = journal.id
    database.session.add_all(lines)
    database.session.commit()
    return journal


def get_journal(journal_id: str) -> ComprobanteContable | None:
    """Obtiene un comprobante manual por ID."""
    return database.session.get(ComprobanteContable, journal_id)


def list_journals() -> list[ComprobanteContable]:
    """Lista comprobantes manuales recientes."""
    return list(
        database.session.execute(
            select(ComprobanteContable)
            .where(ComprobanteContable.is_fiscal_year_closing.is_(False))
            .order_by(ComprobanteContable.date.desc(), ComprobanteContable.created.desc())
        )
        .scalars()
        .all()
    )


def list_journal_lines(journal_id: str) -> list[ComprobanteContableDetalle]:
    """Lista lineas del comprobante en orden de captura."""
    return list(
        database.session.execute(
            select(ComprobanteContableDetalle)
            .filter_by(transaction=JOURNAL_TRANSACTION_TYPE, transaction_id=journal_id)
            .order_by(ComprobanteContableDetalle.order, ComprobanteContableDetalle.id)
        )
        .scalars()
        .all()
    )


def replace_journal_lines(journal: ComprobanteContable, lines: list[ComprobanteContableDetalle]) -> ComprobanteContable:
    """Reemplaza las lineas capturadas de un comprobante manual."""
    existing_lines = list_journal_lines(journal.id)
    for line in existing_lines:
        database.session.delete(line)
    database.session.flush()

    for line in lines:
        line.transaction = JOURNAL_TRANSACTION_TYPE
        line.transaction_id = journal.id

    database.session.add(journal)
    database.session.add_all(lines)
    database.session.commit()
    return journal
