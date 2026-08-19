"""Aplicación determinista de reglas de mapeo entre libros contables."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from cacao_accounting.database import Accounts, Book, GLEntry, LedgerMappingRule, database


class LedgerMappingError(ValueError):
    """Error controlado al transformar una línea para un libro secundario."""


def apply_ledger_mappings(entries: Sequence[GLEntry]) -> list[GLEntry]:
    """Mapea cuentas para libros secundarios usando reglas activas.

    Cada documento genera líneas para todos los libros. Las reglas parten del
    libro primario de la compañía y transforman sólo las líneas generadas para
    el libro destino; los importes y dimensiones se conservan sin cambios.
    """
    if not entries:
        return []
    books = _books_by_id(entries)
    rules = _active_rules(entries, books)
    for entry in entries:
        book = books.get(entry.ledger_id)
        if book is None:
            continue
        target_account_id = rules.get((entry.company, book.code, entry.account_id))
        if target_account_id is None:
            continue
        account = database.session.get(Accounts, target_account_id)
        if account is None or account.entity != entry.company:
            raise LedgerMappingError("La cuenta destino de la regla no pertenece a la compañía del asiento.")
        entry.account_id = account.id
        entry.account_code = account.code
    return list(entries)


def _books_by_id(entries: Sequence[GLEntry]) -> dict[str, Book]:
    """Carga los libros requeridos por las líneas a persistir."""
    ids = {str(entry.ledger_id) for entry in entries if entry.ledger_id}
    if not ids:
        return {}
    books = database.session.execute(select(Book).where(Book.id.in_(ids))).scalars()
    return {str(book.id): book for book in books}


def _active_rules(entries: Sequence[GLEntry], books: dict[str, Book]) -> dict[tuple[str, str, str], str]:
    """Resuelve reglas activas del libro primario al libro destino."""
    companies = {str(entry.company) for entry in entries if entry.company}
    if not companies:
        return {}
    primary_codes = {
        str(book.entity): str(book.code)
        for book in database.session.execute(
            select(Book).where(Book.entity.in_(companies), Book.is_primary.is_(True))
        ).scalars()
    }
    target_codes = {book.code for book in books.values()}
    rules = database.session.execute(
        select(LedgerMappingRule).where(
            LedgerMappingRule.is_active.is_(True),
            LedgerMappingRule.target_book.in_(target_codes),
        )
    ).scalars()
    resolved: dict[tuple[str, str, str], str] = {}
    for rule in rules:
        target_book = next((book for book in books.values() if book.code == rule.target_book), None)
        if target_book is None or primary_codes.get(str(target_book.entity)) != rule.source_book:
            continue
        if not rule.source_account_id or not rule.target_account_id:
            raise LedgerMappingError("La regla de mapeo requiere cuenta origen y destino.")
        key = (str(target_book.entity), str(rule.target_book), str(rule.source_account_id))
        if key in resolved and resolved[key] != str(rule.target_account_id):
            raise LedgerMappingError("Existen reglas de mapeo activas ambiguas para el mismo libro y cuenta.")
        resolved[key] = str(rule.target_account_id)
    return resolved
