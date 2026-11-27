# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La idempotencia recurrente sobrevive al renombrado del período (#1815)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.recurring_journal_service import (
    RecurringJournalError,
    apply_recurring_template,
    approve_recurring_template,
    create_recurring_template,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    ComprobanteContable,
    RecurringJournalApplication,
    RecurringJournalItem,
    RecurringJournalTemplate,
    User,
    database,
)


def _nueva_plantilla() -> tuple[str, str]:
    """Crea una plantilla mensual balanceada y devuelve su código y usuario."""
    cargo = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
    abono = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    codigo = f"RP{uuid4().hex[:6].upper()}"
    plantilla = create_recurring_template(
        data={
            "code": codigo,
            "name": "Plantilla idempotencia",
            "company": "cacao",
            "ledger_id": None,
            "books": ["DEFAULT_BOOK"],
            "naming_series_id": None,
            "description": "Regresión #1815",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "frequency": "monthly",
            "currency": None,
        },
        items=[
            {"account_code": str(cargo.code), "debit": 100, "credit": 0},
            {"account_code": str(abono.code), "debit": 0, "credit": 100},
        ],
        user_id=str(admin.id),
    )
    approve_recurring_template(plantilla.id, str(admin.id))
    return codigo, str(admin.id)


def _nuevo_periodo() -> AccountingPeriod:
    """Crea un período abierto aislado para la prueba."""
    sufijo = uuid4().hex[:6].upper()
    periodo = AccountingPeriod(
        id=f"PER-{sufijo}",
        entity="cacao",
        fiscal_year_id="FY2026",
        name=f"Período {sufijo}",
        start=date(2026, 6, 1),
        end=date(2026, 6, 30),
        enabled=True,
        is_closed=False,
    )
    database.session.add(periodo)
    database.session.commit()
    return periodo


def _aplicaciones_de(codigo: str) -> list[RecurringJournalApplication]:
    """Lista las aplicaciones persistidas de una plantilla."""
    plantilla = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one()
    return list(
        database.session.execute(database.select(RecurringJournalApplication).filter_by(template_id=plantilla.id)).scalars()
    )


def _limpia(codigo: str, periodo_id: str | None = None) -> None:
    """Elimina los artefactos creados por la prueba, incluido su período."""
    plantilla = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one_or_none()
    if plantilla is not None:
        lineas = list(
            database.session.execute(database.select(RecurringJournalItem).filter_by(template_id=plantilla.id)).scalars()
        )
        for aplicacion in _aplicaciones_de(codigo):
            if aplicacion.journal_id:
                comprobante = database.session.get(ComprobanteContable, aplicacion.journal_id)
                if comprobante is not None:
                    database.session.delete(comprobante)
            database.session.delete(aplicacion)
        for linea in lineas:
            database.session.delete(linea)
        database.session.delete(plantilla)
    if periodo_id is not None:
        periodo = database.session.get(AccountingPeriod, periodo_id)
        if periodo is not None:
            database.session.delete(periodo)
    database.session.commit()


def test_renombrar_periodo_no_duplica_la_aplicacion(entorno_contable_aislado):
    """Un per?odo renombrado sigue siendo el mismo para la idempotencia."""
    app = entorno_contable_aislado.app
    with app.app_context():
        codigo, admin = _nueva_plantilla()
        plantilla = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one()
        periodo = _nuevo_periodo()
        nombre_original = periodo.name
        apply_recurring_template(plantilla.id, "FY2026", nombre_original, date(2026, 6, 30), admin, company="cacao")
        periodo.name = "Junio renombrado"
        database.session.commit()

        segunda = apply_recurring_template(
            plantilla.id, "FY2026", "Junio renombrado", date(2026, 6, 30), admin, company="cacao"
        )

        aplicaciones = _aplicaciones_de(codigo)
        assert len(aplicaciones) == 1
        assert aplicaciones[0].accounting_period_id == periodo.id
        assert aplicaciones[0].accounting_period == nombre_original
        assert segunda.id == aplicaciones[0].id


def test_reintento_identico_no_crea_segundo_comprobante(entorno_contable_aislado):
    """#1776: reintento idempotente devuelve la aplicaci?n existente."""
    app = entorno_contable_aislado.app
    with app.app_context():
        codigo, admin = _nueva_plantilla()
        plantilla = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one()
        periodo = _nuevo_periodo()
        primera = apply_recurring_template(plantilla.id, "FY2026", periodo.name, date(2026, 6, 30), admin, company="cacao")
        segunda = apply_recurring_template(plantilla.id, "FY2026", periodo.name, date(2026, 6, 30), admin, company="cacao")
        aplicaciones = _aplicaciones_de(codigo)

        assert len(aplicaciones) == 1
        assert segunda.id == primera.id
        assert aplicaciones[0].journal_id == primera.journal_id


def test_nombre_inequivoco_es_requerido(app, entorno_contable):
    """La resolución ausente falla cerrado sin aplicar la plantilla."""
    del entorno_contable
    codigo, admin = _nueva_plantilla()
    try:
        with app.app_context():
            plantilla = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one()
            with pytest.raises(RecurringJournalError, match="Periodo no encontrado"):
                apply_recurring_template(
                    plantilla.id, "FY2026", "Periodo inexistente", date(2026, 6, 30), admin, company="cacao"
                )
            assert not _aplicaciones_de(codigo)
    finally:
        with app.app_context():
            _limpia(codigo)
