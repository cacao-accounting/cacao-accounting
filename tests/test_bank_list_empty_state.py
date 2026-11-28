# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2026: el listado de bancos explica el resultado vacío y no pagina en cero."""

from __future__ import annotations


def test_listado_vacio_muestra_estado_y_oculta_paginacion(app, authenticated_client):
    """Sin coincidencias se muestra el mensaje, no 'Página 1 de 0'."""
    html = authenticated_client("admin").get("/cash_management/bank/list?search=no-existe").get_data(as_text=True)

    assert "No se encontraron bancos para los filtros seleccionados." in html
    assert "Página 1 de 0" not in html
