# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1977: los selectores de año fiscal usan el doctype registrado.

Las plantillas de presupuesto declaraban ``fiscal_year``, que no existe en el
registro de search-select; el doctype autorizado para contabilidad es
``fiscal_year_id``. La regresión cubre alta, reporte y el endpoint real.
"""

from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import Entity, FiscalYear, User, UserCompanyAccess, database

DOCTYPES_VALIDOS = ('doctype: "fiscal_year_id"', '"doctype": "fiscal_year_id"')
DESKTOP = os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"}


def _assert_doctype_valido(cuerpo: str) -> None:
    """El HTML usa fiscal_year_id y nunca el doctype inexistente."""
    assert any(fragmento in cuerpo for fragmento in DOCTYPES_VALIDOS)
    assert 'doctype: "fiscal_year"' not in cuerpo
    assert '"doctype": "fiscal_year"' not in cuerpo


@pytest.mark.skipif(DESKTOP, reason="El formulario de presupuesto no aplica en modo escritorio.")
def test_alta_de_presupuesto_usa_el_doctype_registrado(app, authenticated_client, entorno_contable):
    """El formulario de alta apunta al doctype que el API registra y no filtra Jinja."""
    del entorno_contable
    response = authenticated_client("admin").get("/accounting/presupuestos/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    _assert_doctype_valido(cuerpo)
    assert 'placeholder="ej. PPTO-2026-BASE"' in cuerpo
    assert "{{ _(" not in cuerpo


@pytest.mark.skipif(DESKTOP, reason="El reporte de presupuesto no aplica en modo escritorio.")
def test_reporte_real_vs_presupuesto_usa_el_doctype_registrado(app, authenticated_client, entorno_contable):
    """El filtro del reporte usa el mismo doctype registrado."""
    del entorno_contable
    response = authenticated_client("admin").get("/accounting/presupuestos/report/real-vs-budget?company=cacao")

    assert response.status_code == 200
    _assert_doctype_valido(response.get_data(as_text=True))


def test_search_select_atiende_fiscal_year_id(app, authenticated_client, entorno_contable):
    """El endpoint registrado responde para cacao, no 404."""
    del entorno_contable
    response = authenticated_client("admin").get(
        "/api/search-select",
        query_string={"doctype": "fiscal_year_id", "company": "cacao", "q": "2026"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert "Tipo de seleccion no registrado" not in str(payload)


def test_search_select_fiscal_year_aisla_compania(app, authenticated_client, entorno_contable):
    """El selector devuelve los años de la compañía consultada y excluye los ajenos."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    codigo = f"B{sufijo}"
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        database.session.add(
            Entity(
                code=codigo,
                name="Beta",
                company_name=f"Beta {sufijo}",
                tax_id=f"T-{sufijo}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.flush()
        database.session.add(
            FiscalYear(
                id=f"FY-{sufijo}",
                entity=codigo,
                name="2099",
                year_start_date=date(2099, 1, 1),
                year_end_date=date(2099, 12, 31),
                is_closed=False,
            )
        )
        database.session.add(UserCompanyAccess(user_id=admin.id, company_code=codigo))
        database.session.commit()

    client = authenticated_client("admin")
    try:
        cacao = client.get(
            "/api/search-select",
            query_string={"doctype": "fiscal_year_id", "company": "cacao", "q": "20"},
        )
        beta = client.get(
            "/api/search-select",
            query_string={"doctype": "fiscal_year_id", "company": codigo, "q": "20"},
        )

        cacao_text = " ".join(str(opcion) for opcion in cacao.get_json()["results"])
        beta_text = " ".join(str(opcion) for opcion in beta.get_json()["results"])
        assert "2026" in cacao_text
        assert "2099" not in cacao_text
        assert "2099" in beta_text
        assert "2026" not in beta_text
    finally:
        with app.app_context():
            anio = database.session.get(FiscalYear, f"FY-{sufijo}")
            if anio is not None:
                database.session.delete(anio)
            database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.company_code == codigo))
            entidad = database.session.get(Entity, codigo)
            if entidad is not None:
                database.session.delete(entidad)
            database.session.commit()
