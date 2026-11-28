# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1921: la plantilla recurrente conserva el estado enviado tras un error.

El formulario debe ofrecer un submit normal y, si el servicio rechaza el
contenido, re-renderizar con encabezado y líneas enviadas para corregir sin
volver a capturarlas.
"""

from __future__ import annotations

import json
from uuid import uuid4


def test_formulario_tiene_submit_normal(app, authenticated_client, entorno_contable):
    """El formulario renderiza el botón Guardar plantilla como submit."""
    del entorno_contable
    response = authenticated_client("admin").get("/accounting/journal/recurring/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert 'type="submit"' in cuerpo
    assert "Guardar plantilla" in cuerpo


def test_error_del_servicio_conserva_encabezado_y_lineas(app, authenticated_client, entorno_contable):
    """Un desbalance conserva en initialJournal el código y la línea enviada."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    codigo = f"REC-{sufijo}"
    nombre = f"Plantilla conservada {sufijo}"
    items = [
        {
            "account_code": "5101",
            "debit": "10",
            "credit": "0",
            "description": "linea conservada",
        }
    ]

    response = authenticated_client("admin").post(
        "/accounting/journal/recurring/new",
        data={
            "code": codigo,
            "name": nombre,
            "company": "cacao",
            "ledger_id": "DEFAULT_BOOK",
            "start_date": "2026-05-01",
            "end_date": "2026-12-31",
            "frequency": "monthly",
            "currency": "NIO",
            "items_json": json.dumps(items),
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert codigo in cuerpo
    assert nombre in cuerpo
    assert "linea conservada" in cuerpo
    assert '"account_code": "5101"' in cuerpo
