# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El reporte mensual de retenciones rechaza meses fiscales inválidos.

Escenario de negocio (issues #1350 y #1584): la ruta agrupaba el parseo del
filtro y la generación del reporte en un mismo ``try`` y, ante cualquier
``ValueError``, sustituía el mes solicitado por el mes actual. Una petición a
un período inválido devolvía HTTP 200 con datos de otro período, como si el
filtro se hubiera aplicado. El filtro inválido debe rechazarse de forma
explícita y los errores del generador no deben ocultarse.
"""

from __future__ import annotations

import pytest

MONTHLY_WITHHOLDINGS_URL = "/reports/withholdings/monthly"


@pytest.mark.parametrize(
    "month",
    ["2026-13", "2026-00", "13-2026", "abc", "2026-05-01", "0000-01", "--05", "9999-12"],
)
def test_reporte_rechaza_mes_fiscal_invalido(authenticated_client, month):
    """Un mes fuera de contrato responde 400 y no un reporte de otro período."""
    client = authenticated_client("admin")

    response = client.get(f"{MONTHLY_WITHHOLDINGS_URL}?company=cacao&month={month}")

    assert response.status_code == 400
    assert response.mimetype == "text/html"


def test_reporte_conserva_el_mes_fiscal_solicitado(authenticated_client):
    """Un mes válido se mantiene en el filtro y genera el reporte."""
    client = authenticated_client("admin")

    response = client.get(f"{MONTHLY_WITHHOLDINGS_URL}?company=cacao&month=2026-05")

    assert response.status_code == 200
    assert 'value="2026-05"' in response.get_data(as_text=True)


def test_reporte_acepta_mes_sin_cero_a_la_izquierda(authenticated_client):
    """El parseo conserva la tolerancia previa para meses de un dígito."""
    client = authenticated_client("admin")

    response = client.get(f"{MONTHLY_WITHHOLDINGS_URL}?company=cacao&month=2026-5")

    assert response.status_code == 200


def test_reporte_sin_filtro_usa_el_mes_actual(authenticated_client):
    """Sin ``month`` se conserva el comportamiento predeterminado."""
    client = authenticated_client("admin")

    response = client.get(f"{MONTHLY_WITHHOLDINGS_URL}?company=cacao")

    assert response.status_code == 200


def test_reporte_no_oculta_errores_del_generador(authenticated_client, monkeypatch):
    """Un fallo del servicio no debe convertirse en otro período silencioso."""
    from cacao_accounting.reportes import routes as report_routes

    def _fail(*args, **kwargs):
        raise ValueError("fallo interno de la consulta")

    monkeypatch.setattr(report_routes, "get_monthly_withholding_report", _fail)
    client = authenticated_client("admin")

    with pytest.raises(ValueError, match="fallo interno de la consulta"):
        client.get(f"{MONTHLY_WITHHOLDINGS_URL}?company=cacao&month=2026-05")
