# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1936: el selector de período operativo recibe la compañía y su ancla."""

from __future__ import annotations


def test_reporte_expone_el_ancla_de_compania(app, authenticated_client):
    """El formulario renderiza #report-company con el valor de la URL."""
    html = authenticated_client("admin").get("/reports/sales-by-customer?company=cacao").get_data(as_text=True)

    assert 'id="report-company"' in html
    assert 'value="cacao"' in html
