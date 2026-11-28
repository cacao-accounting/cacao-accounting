# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El reporte financiero rechaza formatos de exportación no soportados.

Escenario de negocio (issue #2192): un ``export`` desconocido se ignoraba y la
ruta devolvía la vista HTML con HTTP 200, como si la exportación hubiera
ocurrido. El contraste correcto es un HTTP 400 explícito.
"""

from __future__ import annotations

import pytest

FINANCIAL_REPORT_ROUTES = (
    "/reports/trial-balance",
    "/reports/account-summary",
    "/reports/income-statement",
)


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
@pytest.mark.parametrize("export_format", ["bogus", "docx", "CSV", "xls"])
def test_reporte_rechaza_formato_de_exportacion_desconocido(authenticated_client, route, export_format):
    """Cualquier valor fuera de {csv,xlsx,pdf} responde 400 y no HTML."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&export={export_format}")

    assert response.status_code == 400


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_exporta_csv_con_su_mimetype(authenticated_client, route):
    """CSV sigue siendo una descarga con el mimetype esperado."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&export=csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_exporta_xlsx_con_su_mimetype(authenticated_client, route):
    """XLSX sigue siendo una descarga con el mimetype esperado."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao&export=xlsx")

    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.parametrize("route", FINANCIAL_REPORT_ROUTES)
def test_reporte_sin_export_devuelve_la_vista_html(authenticated_client, route):
    """La vista normal conserva HTML cuando no se pide exportación."""
    client = authenticated_client("admin")

    response = client.get(f"{route}?apply_filters=1&company=cacao")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
