# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1977: los selectores de año fiscal usan el doctype registrado.

Las plantillas de presupuesto declaraban ``fiscal_year``, que no existe en el
registro de search-select; el doctype autorizado para contabilidad es
``fiscal_year_id``. La regresión cubre alta, reporte y el endpoint real.
"""

from __future__ import annotations

import os

import pytest

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
