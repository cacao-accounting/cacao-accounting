# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El reporte financiero rechaza libros inexistentes, inactivos o ajenos.

Escenario de negocio (issue #2194): solicitar un libro que no existe, que está
inactivo o que pertenece a otra compañía devolvía HTTP 200 con un reporte vacío,
indistinguible de un período sin movimientos.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from cacao_accounting.database import Book, Entity, database

FINANCIAL_REPORT_ROUTES = (
    "/reports/trial-balance",
    "/reports/account-summary",
    "/reports/income-statement",
)


def _ensure_entity(code: str) -> None:
    entity = database.session.execute(select(Entity).filter_by(code=code)).scalar_one_or_none()
    if entity is None:
        database.session.add(
            Entity(
                code=code,
                name=code.title(),
                company_name=f"{code.title()} SA",
                tax_id=f"TEST-{code.upper()}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()


def _ensure_book(code: str, entity_code: str, status: str = "activo") -> Book:
    book = database.session.execute(select(Book).filter_by(code=code)).scalar_one_or_none()
    if book is None:
        book = Book(
            code=code,
            entity=entity_code,
            name=f"Libro {code}",
            status=status,
            is_primary=False,
            currency="NIO",
        )
        database.session.add(book)
        database.session.flush()
    return book


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_rechaza_libro_inexistente(app, authenticated_client, route):
    """Un código de libro que no existe no puede resolver un reporte vacío."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&ledger=NO-EXISTE")

    assert response.status_code == 400


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_rechaza_libro_de_otra_compania(app, authenticated_client, route):
    """Un libro de otra compañía no se acepta aunque el usuario tenga acceso a la solicitada."""
    with app.app_context():
        _ensure_entity("zeta")
        _ensure_book("ZETA_BOOK", "zeta")
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&ledger=ZETA_BOOK")

    assert response.status_code == 400


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_rechaza_libro_inactivo(app, authenticated_client, route):
    """Un libro inactivo de la compañía tampoco es una fuente válida del reporte."""
    with app.app_context():
        _ensure_book("CACAO_BOOK_INACTIVO", "cacao", status="inactivo")
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&ledger=CACAO_BOOK_INACTIVO")

    assert response.status_code == 400


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_acepta_libro_valido_por_codigo_e_id(app, authenticated_client, route):
    """El libro activo de la compañía se resuelve tanto por código como por id."""
    with app.app_context():
        book_id = database.session.execute(select(Book.id).where(Book.code == "DEFAULT_BOOK")).scalar_one()
    client = authenticated_client("admin")

    by_code = client.get(f"{route}?apply_filters=1&company=cacao&ledger=DEFAULT_BOOK")
    by_id = client.get(f"{route}?apply_filters=1&company=cacao&ledger={book_id}")

    assert by_code.status_code == 200
    assert by_id.status_code == 200


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_sin_libro_explicito_conserva_el_libro_por_defecto(app, authenticated_client, entorno_contable, route):
    """Omitir el parámetro mantiene la resolución del libro primario."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao")

    assert response.status_code == 200
