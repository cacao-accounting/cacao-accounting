# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1626/#1627/#1489: presupuesto acepta BOM UTF-8 y rechaza archivos sin filas.

Los escenarios que crean maestros o staging se aíslan limpiando todas las
filas propias (lote, líneas en staging, cuenta y centro de costo) en
`finally`, sin dejar residuos en la base compartida del worker.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.budget_import_service import BudgetError, BudgetImportService
from cacao_accounting.database import (
    Accounts,
    Book,
    Budget,
    BudgetImport,
    BudgetImportLine,
    BudgetLine,
    CostCenter,
    FiscalYear,
    User,
    database,
)


def _presupuesto() -> str:
    sufijo = uuid4().hex[:6]
    libro = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
    anio = database.session.get(FiscalYear, "FY2026")
    presupuesto = Budget(
        company="cacao",
        ledger_id=libro.id,
        fiscal_year_id=anio.id,
        budget_code=f"IMP-{sufijo}",
        name=f"Presupuesto import {sufijo}",
        currency_id="NIO",
        status="draft",
    )
    database.session.add(presupuesto)
    database.session.commit()
    return presupuesto.id


def _usuario() -> str:
    return str(database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one())


def _limpiar(budget_id: str, account_code: str | None = None, cc_code: str | None = None) -> None:
    """Elimina lote, staging, líneas y maestros creados por la prueba."""
    import_ids = list(
        database.session.execute(database.select(BudgetImport.id).where(BudgetImport.budget_id == budget_id)).scalars()
    )
    if import_ids:
        database.session.execute(database.delete(BudgetImportLine).where(BudgetImportLine.import_id.in_(import_ids)))
    database.session.execute(database.delete(BudgetLine).where(BudgetLine.budget_id == budget_id))
    database.session.execute(database.delete(BudgetImport).where(BudgetImport.budget_id == budget_id))
    database.session.execute(database.delete(Budget).where(Budget.id == budget_id))
    if account_code:
        database.session.execute(database.delete(Accounts).where(Accounts.code == account_code))
    if cc_code:
        database.session.execute(database.delete(CostCenter).where(CostCenter.code == cc_code))
    database.session.commit()


def test_parse_csv_normaliza_bom_en_el_encabezado(app, entorno_contable):
    """El BOM UTF-8 no forma parte del nombre de la primera columna."""
    del entorno_contable
    contenido = "\ufeffCuenta,Mayo 2026\n1101,10\n".encode("utf-8")
    with app.app_context():
        filas = BudgetImportService()._parse_csv(contenido)

    assert filas and "Cuenta" in filas[0]
    assert "\ufeffCuenta" not in filas[0]


@pytest.mark.parametrize("contenido", [b"", b"Cuenta,Mayo 2026\n"])
def test_validate_import_rechaza_archivos_sin_filas(app, entorno_contable, contenido):
    """Cero bytes o solo encabezados no crean un lote validado."""
    del entorno_contable
    with app.app_context():
        budget_id = _presupuesto()
        antes = database.session.execute(database.select(database.func.count(BudgetImport.id))).scalar_one()

        try:
            with pytest.raises(BudgetError, match="no contiene filas de datos"):
                BudgetImportService().validate_import(budget_id, "vacio.csv", contenido, _usuario())

            despues = database.session.execute(database.select(database.func.count(BudgetImport.id))).scalar_one()
            assert despues == antes
        finally:
            _limpiar(budget_id)


def test_validate_import_conserva_error_de_presupuesto_inexistente(app, entorno_contable):
    """La validación del presupuesto precede al contenido del archivo."""
    del entorno_contable
    with app.app_context():
        with pytest.raises(BudgetError, match="Presupuesto no encontrado"):
            BudgetImportService().validate_import("presupuesto-inexistente", "vacio.csv", b"", _usuario())


def test_validate_import_acepta_csv_con_bom(app, entorno_contable):
    """Una plantilla válida con BOM se valida y conserva su fila."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    cuenta_code = f"B{sufijo}"
    cc_code = f"ADM{sufijo}"
    contenido = f"\ufeffCuenta,Centro de Costo,Mayo 2026\n{cuenta_code},{cc_code},10\n".encode("utf-8")
    with app.app_context():
        database.session.add(
            Accounts(entity="cacao", code=cuenta_code, name="Cuenta presupuesto", classification="activo", group=False)
        )
        database.session.add(CostCenter(entity="cacao", code=cc_code, name="Centro presupuesto"))
        database.session.commit()
        budget_id = _presupuesto()
        lote_id = None
        try:
            lote = BudgetImportService().validate_import(budget_id, "presupuesto.csv", contenido, _usuario())
            lote_id = lote.id

            assert lote.status == "validated"
            assert lote.rows_read == 1
            assert lote.rows_inserted == 1
            staging = (
                database.session.execute(database.select(BudgetImportLine).where(BudgetImportLine.import_id == lote.id))
                .scalars()
                .all()
            )
            assert len(staging) == 1
        finally:
            _limpiar(budget_id, cuenta_code, cc_code)
            assert database.session.execute(database.select(Accounts).filter_by(code=cuenta_code)).scalar_one_or_none() is None
            assert database.session.execute(database.select(CostCenter).filter_by(code=cc_code)).scalar_one_or_none() is None
            assert (
                database.session.execute(
                    database.select(database.func.count(BudgetImportLine.id)).where(BudgetImportLine.import_id == lote_id)
                ).scalar_one()
                == 0
            )
            assert (
                database.session.execute(
                    database.select(database.func.count(BudgetImport.id)).where(BudgetImport.budget_id == budget_id)
                ).scalar_one()
                == 0
            )


def test_validate_import_rechaza_csv_sin_encabezado_no_crea_lote(app, entorno_contable):
    """#1627 QA: fila sin encabezado no deja lote persistible en sesión."""
    del entorno_contable
    contenido = b"1101,ADM,10\n"
    with app.app_context():
        budget_id = _presupuesto()
        antes = database.session.execute(database.select(database.func.count(BudgetImport.id))).scalar_one()

        try:
            with pytest.raises(BudgetError):
                BudgetImportService().validate_import(budget_id, "sin-header.csv", contenido, _usuario())

            database.session.rollback()
            despues = database.session.execute(database.select(database.func.count(BudgetImport.id))).scalar_one()
            assert despues == antes
        finally:
            _limpiar(budget_id)
