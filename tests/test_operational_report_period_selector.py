# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1936: el selector de período operativo recibe la compañía y su ancla."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("path", ("/reports/kardex", "/reports/bank-movement"))
def test_kardex_y_bancos_solo_exponen_filtros_de_periodos_completos(authenticated_client, entorno_contable, path):
    """Kardex y movimientos bancarios no ofrecen fechas parciales que el servidor rechaza."""
    del entorno_contable
    response = authenticated_client("admin").get(
        f"{path}?company=cacao&accounting_period_from=P2026-05&accounting_period_to=P2026-05"
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="accounting_period_from"' in html
    assert 'name="accounting_period_to"' in html
    assert 'name="date_from"' not in html
    assert 'name="date_to"' not in html


@pytest.mark.parametrize("path", ("/reports/kardex", "/reports/bank-movement"))
def test_kardex_y_bancos_rechazan_fechas_diarias_aunque_sean_enviadas(authenticated_client, entorno_contable, path):
    """Las rutas conservan el guard de rangos parciales aunque se envíe una URL manual."""
    del entorno_contable
    response = authenticated_client("admin").get(
        f"{path}?company=cacao&accounting_period_from=P2026-05&accounting_period_to=P2026-05&date_from=2026-05-15"
    )

    assert response.status_code == 400


def test_reporte_expone_el_ancla_de_compania(authenticated_client):
    """El formulario renderiza #report-company con el valor de la URL."""
    html = authenticated_client("admin").get("/reports/sales-by-customer?company=cacao").get_data(as_text=True)

    assert 'id="report-company"' in html
    assert 'value="cacao"' in html
