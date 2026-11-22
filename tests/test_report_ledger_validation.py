# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2194: un libro inexistente, inactivo o ajeno no produce un reporte vacío.

El contrato exige fallar de forma controlada (400) en lugar de responder 200
con un reporte sin filas, indistinguible de un período sin movimientos.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Book, Currency, Entity, database
from cacao_accounting.reportes.helpers import _validate_requested_ledger


def _company(app) -> None:
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )
        if database.session.execute(database.select(Entity).filter_by(code="cafe")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="cafe",
                    name="Cafe",
                    company_name="Cafe SA",
                    tax_id=f"JE{uuid4().hex[:8].upper()}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                )
            )
        database.session.commit()
        if database.session.execute(database.select(Book).filter_by(code="LOCAL1")).scalar_one_or_none() is None:
            database.session.add(Book(entity="cafe", code="LOCAL1", name="Libro Cafe", status="activo", currency="NIO"))
            database.session.commit()


def test_libro_inexistente_se_rechaza(app, entorno_contable):
    """Un código que no existe responde 400, no un reporte vacío."""
    _company(app)
    with app.test_request_context("/"):
        with app.app_context():
            from werkzeug.exceptions import HTTPException

            try:
                _validate_requested_ledger("cacao", "NOEXISTE")
            except HTTPException as error:
                assert error.code == 400
            else:
                raise AssertionError("Un libro inexistente no se rechazó")


def test_libro_de_otra_compania_se_rechaza(app, entorno_contable):
    """Un libro de otra compañía responde 400."""
    _company(app)
    with app.test_request_context("/"):
        with app.app_context():
            from werkzeug.exceptions import HTTPException

            try:
                _validate_requested_ledger("cacao", "LOCAL1")
            except HTTPException as error:
                assert error.code == 400
            else:
                raise AssertionError("Un libro ajeno no se rechazó")


def test_libro_propio_activo_se_acepta(app, entorno_contable):
    """Control positivo: un libro activo de la compañía pasa la validación."""
    _company(app)
    with app.test_request_context("/"):
        with app.app_context():
            _validate_requested_ledger("cacao", "DEFAULT_BOOK")
