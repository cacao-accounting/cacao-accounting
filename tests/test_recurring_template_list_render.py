# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El listado de plantillas recurrentes no renderiza la columna fantasma (#2156).

La columna ``next_application_date`` fue eliminada de
``contabilidad/templates/contabilidad/recurring_journal_lista.html``: el archivo no
debe referenciarla y la página debe responder 200 mostrando las plantillas vigentes.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.recurring_journal_service import create_recurring_template
from cacao_accounting.database import (
    Accounts,
    RecurringJournalApplication,
    RecurringJournalItem,
    RecurringJournalTemplate,
    User,
    database,
)

CAMPO_FANTASMA = "next_application_date"
RAIZ_PAQUETE = Path(__file__).resolve().parents[1] / "cacao_accounting"
PLANTILLA_LISTA = RAIZ_PAQUETE / "contabilidad" / "templates" / "contabilidad" / "recurring_journal_lista.html"


@pytest.fixture
def plantilla_qa(app, entorno_contable):
    """Crea una plantilla recurrente válida mediante el servicio y la elimina al terminar."""
    codigo = f"RL{uuid4().hex[:6].upper()}"
    with app.app_context():
        cargo = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        abono = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        create_recurring_template(
            data={
                "code": codigo,
                "name": "Plantilla listado QA",
                "company": "cacao",
                "ledger_id": None,
                "books": ["DEFAULT_BOOK"],
                "naming_series_id": None,
                "description": "Plantilla para probar el listado recurrente",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "frequency": "monthly",
                "currency": None,
            },
            items=[
                {"account_code": str(cargo.code), "debit": 50, "credit": 0, "description": "Cargo QA"},
                {"account_code": str(abono.code), "debit": 0, "credit": 50, "description": "Abono QA"},
            ],
            user_id=str(admin.id),
        )

    yield codigo

    with app.app_context():
        plantilla = database.session.execute(
            database.select(RecurringJournalTemplate).filter_by(code=codigo)
        ).scalar_one_or_none()
        if plantilla is not None:
            for linea in database.session.execute(
                database.select(RecurringJournalItem).filter_by(template_id=plantilla.id)
            ).scalars():
                database.session.delete(linea)
            database.session.delete(plantilla)
            database.session.commit()


def test_archivo_del_listado_no_referencia_la_columna_fantasma():
    """El HTML fuente de la lista no menciona next_application_date."""
    fuente = PLANTILLA_LISTA.read_text(encoding="utf-8")
    assert fuente.strip(), f"No se pudo leer la plantilla del listado: {PLANTILLA_LISTA}"
    assert CAMPO_FANTASMA not in fuente


def test_ninguna_plantilla_del_arbol_referencia_la_columna_fantasma():
    """Ningún HTML del paquete conserva referencias a la columna eliminada."""
    afectados = [
        str(ruta.relative_to(RAIZ_PAQUETE))
        for ruta in sorted(RAIZ_PAQUETE.rglob("*.html"))
        if CAMPO_FANTASMA in ruta.read_text(encoding="utf-8", errors="ignore")
    ]
    assert afectados == []


def test_listado_renderiza_la_plantilla_sin_la_columna_fantasma(app, authenticated_client, plantilla_qa):
    """GET del listado responde 200, muestra la fila de la plantilla y omite el campo fantasma."""
    response = authenticated_client().get(f"/accounting/journal/recurring?search={plantilla_qa}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert b"Internal Server Error" not in response.data
    assert CAMPO_FANTASMA not in html
    assert plantilla_qa in html
    assert "Plantilla listado QA" in html


def test_listado_y_detalle_traducen_la_frecuencia_interna(app, authenticated_client, plantilla_qa):
    """La frecuencia `monthly` se presenta como «Mensual» en lista y detalle (#2157)."""
    with app.app_context():
        plantilla = database.session.execute(
            database.select(RecurringJournalTemplate).filter_by(code=plantilla_qa)
        ).scalar_one()
        plantilla_id = plantilla.id

    client = authenticated_client()
    listado = client.get(f"/accounting/journal/recurring?search={plantilla_qa}")
    detalle = client.get(f"/accounting/journal/recurring/{plantilla_id}")

    assert listado.status_code == 200
    assert "Mensual" in listado.get_data(as_text=True)
    assert ">monthly<" not in listado.get_data(as_text=True)
    assert detalle.status_code == 200
    assert "Mensual" in detalle.get_data(as_text=True)
    assert ">monthly<" not in detalle.get_data(as_text=True)


def test_historial_recurrente_usa_el_color_de_cada_estado(app, authenticated_client, plantilla_qa):
    """Pendiente, fallida y revertida no se pintan como aplicadas (#2160)."""
    with app.app_context():
        plantilla = database.session.execute(
            database.select(RecurringJournalTemplate).filter_by(code=plantilla_qa)
        ).scalar_one()
        applications = [
            RecurringJournalApplication(
                company="cacao",
                template_id=plantilla.id,
                fiscal_year="2026",
                accounting_period=f"P-{status}",
                application_date=date(2026, 5, 1),
                status=status,
            )
            for status in ("pending", "failed", "reversed", "applied")
        ]
        database.session.add_all(applications)
        database.session.commit()
        application_ids = [application.id for application in applications]
        template_id = plantilla.id

    try:
        response = authenticated_client().get(f"/accounting/journal/recurring/{template_id}")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "text-bg-info" in html
        assert "text-bg-danger" in html
        assert "text-bg-warning" in html
        assert "text-bg-success" in html
        assert "Pendiente" in html
        assert "Fallida" in html
        assert "Revertida" in html
    finally:
        with app.app_context():
            for application in database.session.execute(
                database.select(RecurringJournalApplication).filter(RecurringJournalApplication.id.in_(application_ids))
            ).scalars():
                database.session.delete(application)
            database.session.commit()
