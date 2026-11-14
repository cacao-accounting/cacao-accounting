# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2027: el breadcrumb del listado de bancos usa un nombre accesible real.

``banco_lista.html`` debe anunciar la navegación con
``aria-label="Ruta de navegación"`` en lugar del valor genérico en inglés
``aria-label="breadcrumb"``.
"""

from __future__ import annotations


def test_banco_lista_nombra_la_ruta_de_navegacion(authenticated_client):
    """El listado de bancos no usa aria-label="breadcrumb" y sí la etiqueta traducida."""
    respuesta = authenticated_client().get("/cash_management/bank/list")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert 'aria-label="breadcrumb"' not in html, "La etiqueta genérica en inglés no debe usarse como nombre accesible."
    assert '<nav aria-label="Ruta de navegación">' in html, "El nav del breadcrumb debe anunciar su nombre accesible."
    assert '<ol class="breadcrumb' in html, "El listado sigue siendo un breadcrumb visual."
