# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las plantillas recurrentes solo aceptan proyectos de la compañía de la plantilla (#2159).

``_validate_template_projects`` (contabilidad/recurring_journal_service.py) debe rechazar
con ``RecurringJournalError`` cualquier línea cuyo proyecto no pertenezca a la compañía
de la plantilla, y la ruta ``nuevo_comprobante_recurrente`` (contabilidad/routes.py) debe
capturar el error, avisar con un flash y volver al formulario sin persistir nada.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.recurring_journal_service import (
    RecurringJournalError,
    _validate_template_projects,
)
from cacao_accounting.database import Accounts, Project, RecurringJournalItem, RecurringJournalTemplate, database

MENSAJE_PROYECTO_AJENO = "no pertenece a la compañía de la plantilla"


@pytest.fixture
def proyectos_qa(app, entorno_contable, reference_users):
    """Crea un proyecto ajeno (alpha) y uno propio (cacao) con códigos únicos."""
    codigos_plantillas: list[str] = []
    escenario = {
        "ajeno": f"P{uuid4().hex[:6].upper()}",
        "propio": f"P{uuid4().hex[:6].upper()}",
        "plantillas_creadas": codigos_plantillas,
    }
    with app.app_context():
        database.session.add_all(
            [
                Project(code=escenario["ajeno"], name="Proyecto ajeno QA", entity="alpha", enabled=True),
                Project(code=escenario["propio"], name="Proyecto propio QA", entity="cacao", enabled=True),
            ]
        )
        database.session.commit()

    yield escenario

    with app.app_context():
        for codigo in codigos_plantillas:
            plantilla = database.session.execute(
                database.select(RecurringJournalTemplate).filter_by(code=codigo)
            ).scalar_one_or_none()
            if plantilla is not None:
                for linea in database.session.execute(
                    database.select(RecurringJournalItem).filter_by(template_id=plantilla.id)
                ).scalars():
                    database.session.delete(linea)
                database.session.delete(plantilla)
        for codigo in (escenario["ajeno"], escenario["propio"]):
            proyecto = database.session.execute(database.select(Project).filter_by(code=codigo)).scalar_one_or_none()
            if proyecto is not None:
                database.session.delete(proyecto)
        database.session.commit()


def _cuentas_qa(app) -> tuple[str, str]:
    """Devuelve los códigos de las cuentas de cargo y abono sembradas para cacao."""
    with app.app_context():
        cargo = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        abono = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        return str(cargo.code), str(abono.code)


def _datos_plantilla(codigo: str, proyecto: str, cuenta_cargo: str, cuenta_abono: str) -> dict[str, str]:
    """Construye el POST del formulario de plantilla recurrente con líneas balanceadas."""
    lineas = [
        {"account_code": cuenta_cargo, "debit": 100, "credit": 0, "description": "Cargo QA", "project": proyecto},
        {"account_code": cuenta_abono, "debit": 0, "credit": 100, "description": "Abono QA"},
    ]
    return {
        "code": codigo,
        "name": "Plantilla recurrente QA",
        "company": "cacao",
        "ledger_id": "DEFAULT_BOOK",
        "currency": "NIO",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "frequency": "monthly",
        "items_json": json.dumps(lineas),
    }


def test_validador_rechaza_proyecto_ajeno_y_acepta_propio(app, proyectos_qa):
    """El validador del servicio falla con proyectos de otra compañía y pasa con los propios."""
    with app.app_context():
        with pytest.raises(RecurringJournalError, match=MENSAJE_PROYECTO_AJENO):
            _validate_template_projects("cacao", [{"account_code": "1101", "project": proyectos_qa["ajeno"]}])

        _validate_template_projects("cacao", [{"account_code": "1101", "project": proyectos_qa["propio"]}])
        _validate_template_projects("cacao", [{"account_code": "1101"}, {"account_code": "5201", "project": ""}])


def test_ruta_rechaza_proyecto_ajeno_sin_persistir_plantilla(app, authenticated_client, proyectos_qa, entorno_contable):
    """POST con proyecto de alpha vuelve al formulario con flash y no persiste la plantilla."""
    codigo = f"RT{uuid4().hex[:6].upper()}"
    proyectos_qa["plantillas_creadas"].append(codigo)
    cuenta_cargo, cuenta_abono = _cuentas_qa(app)
    datos = _datos_plantilla(codigo, proyectos_qa["ajeno"], cuenta_cargo, cuenta_abono)

    response = authenticated_client().post("/accounting/journal/recurring/new", data=datos)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert b"Internal Server Error" not in response.data
    assert proyectos_qa["ajeno"] in html
    assert MENSAJE_PROYECTO_AJENO in html
    with app.app_context():
        assert (
            database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one_or_none()
            is None
        )


def test_ruta_acepta_proyecto_propio_y_persiste_plantilla(app, authenticated_client, proyectos_qa, entorno_contable):
    """POST con proyecto de cacao persiste la plantilla y su línea asociada al proyecto."""
    codigo = f"RT{uuid4().hex[:6].upper()}"
    proyectos_qa["plantillas_creadas"].append(codigo)
    cuenta_cargo, cuenta_abono = _cuentas_qa(app)
    datos = _datos_plantilla(codigo, proyectos_qa["propio"], cuenta_cargo, cuenta_abono)

    response = authenticated_client().post("/accounting/journal/recurring/new", data=datos)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/accounting/journal/recurring")
    with app.app_context():
        plantilla = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=codigo)).scalar_one()
        assert plantilla.company == "cacao"
        lineas = (
            database.session.execute(database.select(RecurringJournalItem).filter_by(template_id=plantilla.id)).scalars().all()
        )
        assert len(lineas) == 2
        assert [linea.project for linea in lineas if linea.project] == [proyectos_qa["propio"]]
