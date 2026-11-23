# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2041: el listado de pagos explica el resultado vacío."""


def test_listado_de_pagos_sin_coincidencias_muestra_estado(app, authenticated_client):
    """Sin resultados se muestra el mensaje de vacío, no una tabla muda."""
    html = authenticated_client("admin").get("/cash_management/payment/list?search=no-existe").get_data(as_text=True)

    assert "No se encontraron documentos para los filtros seleccionados." in html
