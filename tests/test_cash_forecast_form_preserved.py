# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1951: un rechazo del pronóstico conserva los datos enviados."""


def test_rechazo_conserva_version_descripcion_y_anio(app, authenticated_client):
    """Falta periodicidad: el formulario vuelve con lo capturado."""
    datos = {
        "company": "cacao",
        "fiscal_year_id": "FY-1951",
        "version": "Q3-2026",
        "description": "Escenario pesimista",
    }

    respuesta = authenticated_client("admin").post("/cash_management/cash-forecast/new", data=datos)

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert 'value="Q3-2026"' in html
    assert "Escenario pesimista" in html
