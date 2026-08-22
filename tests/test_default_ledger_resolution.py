# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Pruebas de regresión de la resolución unificada del libro contable por defecto.

Cubre el fix ``fix(reports): unify default ledger resolution``: ``primary_ledger_id``
(``ledger_queries``) y ``_resolve_ledger`` (``reportes.services``) deben compartir:

1. El predicado de libros activos, que es fail-closed: una fila legacy con
   ``status=NULL`` ya no se interpreta como activa.
2. La misma precedencia de selección: ``default DESC, is_primary DESC, code ASC``.
3. La exclusión de libros inactivos.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicación Flask aislada con una compañía sin libros pre-cargados."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"))
        database.session.commit()
        yield app


def _add_book(code: str, *, default: bool = False, primary: bool = False, status: str | None = "activo"):
    """Agrega un libro contable a la compañía de prueba."""
    from cacao_accounting.database import Book, database

    book = Book(
        code=code,
        name=f"Libro {code}",
        entity="cacao",
        currency="NIO",
        default=default,
        is_primary=primary,
        status=status,
    )
    database.session.add(book)
    database.session.commit()
    if status is None:
        # El default del modelo activa libros sin estado explícito; una fila
        # legacy con NULL solo se obtiene mediante actualización directa.
        database.session.execute(database.update(Book).where(Book.code == code).values(status=None))
        database.session.commit()
    database.session.expire(book)
    return book


def test_primary_ledger_id_excludes_legacy_null_status_book(app_ctx):
    """Una fila legacy sin estado (NULL) ya no se interpreta como activa."""
    from cacao_accounting.ledger_queries import primary_ledger_id

    _add_book("LEGACY", status=None)
    assert primary_ledger_id("cacao") is None

    active = _add_book("ACT1")
    assert primary_ledger_id("cacao") == active.id


def test_primary_ledger_id_excludes_inactive_books(app_ctx):
    """Los libros inactivos nunca se resuelven como libro por defecto."""
    from cacao_accounting.ledger_queries import primary_ledger_id

    _add_book("INACT", status="inactivo")
    assert primary_ledger_id("cacao") is None

    active = _add_book("ACT1")
    assert primary_ledger_id("cacao") == active.id


def test_primary_ledger_id_prefers_default_over_primary(app_ctx):
    """El libro marcado como default gana sobre el primario."""
    from cacao_accounting.ledger_queries import primary_ledger_id

    _add_book("PRIM", primary=True)
    default_book = _add_book("DEFA", default=True)
    assert primary_ledger_id("cacao") == default_book.id


def test_primary_ledger_id_resolves_requested_by_code_or_id(app_ctx):
    """La resolución explícita acepta tanto id como código."""
    from cacao_accounting.ledger_queries import primary_ledger_id

    other = _add_book("OTRO")
    _add_book("DEFA", default=True)

    assert primary_ledger_id("cacao", requested=other.code) == other.id
    assert primary_ledger_id("cacao", requested=other.id) == other.id
    # Un libro solicitado pero inactivo no se resuelve.
    inactive = _add_book("INACT", status="inactivo")
    assert primary_ledger_id("cacao", requested=inactive.code) is None


def test_resolve_ledger_prefers_default_over_primary(app_ctx):
    """_resolve_ledger usa la misma precedencia: default antes que primary."""
    from cacao_accounting.reportes.services import _resolve_ledger

    _add_book("ZUL", primary=True)
    default_book = _add_book("AAA", default=True)

    resolved = _resolve_ledger("cacao", None)
    assert resolved is not None
    assert resolved.id == default_book.id


def test_resolve_ledger_falls_back_to_primary_then_code_order(app_ctx):
    """Sin default gana el primario; sin primario desempata el código menor."""
    from cacao_accounting.reportes.services import _resolve_ledger

    first = _add_book("BBB")
    _add_book("AAA")
    resolved = _resolve_ledger("cacao", None)
    assert resolved is not None
    assert resolved.code == min(first.code, "AAA")

    primary_book = _add_book("MMM", primary=True)
    resolved = _resolve_ledger("cacao", None)
    assert resolved is not None
    assert resolved.id == primary_book.id


def test_resolve_ledger_excludes_inactive_and_legacy_null_status(app_ctx):
    """_resolve_ledger comparte el predicado de actividad fail-closed."""
    from cacao_accounting.ledger_queries import primary_ledger_id
    from cacao_accounting.reportes.services import _resolve_ledger

    _add_book("OLD1", status=None, primary=True)
    _add_book("INAC", status="inactivo")

    # Sin libros activos no hay resolución, aunque existan filas legacy.
    assert _resolve_ledger("cacao", None) is None
    assert primary_ledger_id("cacao") is None

    active = _add_book("ACT1")
    resolved = _resolve_ledger("cacao", None)
    assert resolved is not None
    assert resolved.id == active.id
    assert primary_ledger_id("cacao") == resolved.id

    # Solicitado por código inactivo o legacy -> sin resultado.
    assert _resolve_ledger("cacao", "INAC") is None
    assert _resolve_ledger("cacao", "OLD1") is None


def test_both_resolvers_agree_on_the_same_book(app_ctx):
    """Contrato central del fix: ambos resolutores eligen el mismo libro."""
    from cacao_accounting.ledger_queries import primary_ledger_id
    from cacao_accounting.reportes.services import _resolve_ledger

    _add_book("FISC", primary=True)
    default_book = _add_book("IFRS", default=True)

    resolved = _resolve_ledger("cacao", None)
    assert resolved is not None
    assert primary_ledger_id("cacao") == resolved.id
    assert default_book.id == primary_ledger_id("cacao")
