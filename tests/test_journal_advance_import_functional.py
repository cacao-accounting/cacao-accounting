# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1197: importación real de comprobantes conserva el indicador de anticipo.

Recorre adaptador → normalizador → persistencia: un CSV con `is_advance=false`
debe guardar líneas con `is_advance=False`, `true` con `True`, y un valor
desconocido debe rechazarse antes de persistir.
"""

from __future__ import annotations

import csv
from io import StringIO
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    ComprobanteContableDetalle,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.imports.services.import_service import ImportService


@pytest.fixture
def journal_import_scenario():
    """Compañía con dos cuentas y libro para importar un comprobante."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name=f"Cacao {suffix}",
                    tax_id=f"T{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            Book(entity="cacao", code="DEFAULT_BOOK", name="Default", status="activo", is_primary=True, currency="NIO")
        )
        admin = User(
            id="admin", user="admin", name="Admin", password=b"x", classification="admin", active=True, company="cacao"
        )
        database.session.add(admin)
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="admin", company_code="cacao"))
        admin_role = Roles(name="admin", note="admin")
        database.session.add(admin_role)
        database.session.flush()
        database.session.add(RolesUser(user_id="admin", role_id=admin_role.id, active=True))
        database.session.add_all(
            [
                Accounts(
                    entity="cacao",
                    code="110101",
                    name="Caja",
                    classification="asset",
                    account_type="cash",
                    group=False,
                    active=True,
                    enabled=True,
                ),
                Accounts(
                    entity="cacao",
                    code="410101",
                    name="Ingresos",
                    classification="revenue",
                    account_type="income",
                    group=False,
                    active=True,
                    enabled=True,
                ),
            ]
        )
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _rows(advance: str) -> list[dict]:
    return [
        {
            "document_ref": "IMP-1",
            "fecha": "2026-05-15",
            "cuenta": "110101",
            "debito": "100",
            "credito": "0",
            "is_advance": advance,
        },
        {
            "document_ref": "IMP-1",
            "fecha": "2026-05-15",
            "cuenta": "410101",
            "debito": "0",
            "credito": "100",
            "is_advance": advance,
        },
    ]


def _import(app, advance: str):
    with app.app_context():
        adapter = JournalEntryAdapter()
        context = {"company_id": "cacao", "accounting_book_id": "DEFAULT_BOOK", "created_by": "admin"}
        document = adapter.build_document(_rows(advance), context)
        adapter.persist_document(document)
        return database.session.execute(database.select(ComprobanteContableDetalle)).scalars().all()


def test_importacion_conserva_false_como_no_anticipo(journal_import_scenario):
    """`false` textual termina persistido como `is_advance=False`."""
    detalles = _import(journal_import_scenario, "false")
    assert len(detalles) == 2
    assert all(detail.is_advance is False for detail in detalles)


def test_importacion_conserva_true_como_anticipo(journal_import_scenario):
    """Control positivo: `true` textual se persiste como `is_advance=True`."""
    detalles = _import(journal_import_scenario, "true")
    assert len(detalles) == 2
    assert all(detail.is_advance is True for detail in detalles)


def test_importacion_rechaza_booleano_desconocido(journal_import_scenario):
    """Un valor no booleano se rechaza antes de persistir líneas."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError

    app = journal_import_scenario
    with app.app_context():
        adapter = JournalEntryAdapter()
        context = {"company_id": "cacao", "accounting_book_id": "DEFAULT_BOOK", "created_by": "admin"}
        document = adapter.build_document(_rows("quizá"), context)
        with pytest.raises(JournalValidationError, match="booleano válido"):
            adapter.persist_document(document)
        database.session.rollback()
        assert database.session.execute(database.select(ComprobanteContableDetalle)).scalars().all() == []


def _csv_rows(advance: str) -> tuple[list[dict[str, str]], list[str]]:
    """Devuelve filas y encabezados leídos por el lector CSV real."""
    contenido = (
        "document_ref,fecha,cuenta,debito,credito,is_advance\n"
        f"IMP-CSV,2026-05-15,110101,100,0,{advance}\n"
        f"IMP-CSV,2026-05-15,410101,0,100,{advance}\n"
    )
    lector = csv.DictReader(StringIO(contenido))
    filas = list(lector)
    encabezados = list(lector.fieldnames or [])
    return filas, encabezados


@pytest.mark.parametrize(("advance", "esperado"), [("false", False), ("true", True)])
def test_csv_real_valida_encabezado_y_conserva_is_advance(journal_import_scenario, advance: str, esperado: bool) -> None:
    """El lector CSV acepta la columna y el valor llega al detalle persistido."""
    app = journal_import_scenario
    with app.app_context():
        filas, encabezados = _csv_rows(advance)
        adapter = JournalEntryAdapter()
        errores = ImportService()._collect_header_errors("batch-csv", encabezados, adapter)
        assert errores == []

        contexto = {"company_id": "cacao", "accounting_book_id": "DEFAULT_BOOK", "created_by": "admin"}
        documento = adapter.build_document(filas, contexto)
        adapter.persist_document(documento)
        detalles = database.session.execute(database.select(ComprobanteContableDetalle)).scalars().all()
        assert len(detalles) == 2
        assert all(detalle.is_advance is esperado for detalle in detalles)


def test_csv_real_rechaza_booleano_desconocido(journal_import_scenario) -> None:
    """Un valor no booleano atraviesa el encabezado y falla al persistir."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError

    app = journal_import_scenario
    with app.app_context():
        filas, encabezados = _csv_rows("quizá")
        adapter = JournalEntryAdapter()
        assert ImportService()._collect_header_errors("batch-csv", encabezados, adapter) == []

        contexto = {"company_id": "cacao", "accounting_book_id": "DEFAULT_BOOK", "created_by": "admin"}
        documento = adapter.build_document(filas, contexto)
        with pytest.raises(JournalValidationError, match="booleano válido"):
            adapter.persist_document(documento)
        database.session.rollback()
        assert database.session.execute(database.select(ComprobanteContableDetalle)).scalars().all() == []
