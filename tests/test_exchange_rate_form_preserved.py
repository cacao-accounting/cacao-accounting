# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1956: rechazar una tasa manual conserva las monedas elegidas."""


def test_rechazo_conserva_origen_y_destino(app, authenticated_client, entorno_contable):
    """Misma moneda de origen y destino: el formulario vuelve con los valores."""
    datos = {"origin": "NIO", "destination": "NIO", "rate": "1"}

    respuesta = authenticated_client("admin").post("/accounting/exchange/new", data=datos)

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    import re

    assert re.search(r'id="origin"[^>]*value="NIO"', html)
