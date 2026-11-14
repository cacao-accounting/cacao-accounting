# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2037: el comparativo de pronósticos etiqueta zonas y estados sin códigos crudos.

``cash_forecast_comparar.html`` define ``zone_labels`` y
``forecast_status_labels`` con gettext y respaldo ``.get(x, x)``. La página
nunca debe mostrar los códigos internos "Current"/"Projected" ni los estados
"Draft"/"Approved" sin traducir.
"""

from __future__ import annotations

import os

import re
from urllib.parse import urlsplit
from uuid import uuid4

ETIQUETAS_ZONA_TRADUCIDAS = {"Real", "Actual", "Proyectado"}
INSIGNIA_ZONA = re.compile(r'badge bg-light text-dark small ms-1">([^<]+)</span>')
INSIGNIA_ESTADO = re.compile(r'badge bg-secondary d-inline-block">([^<]+)</span>')


def _crear_pronostico(cliente, version: str) -> str:
    """Crea un pronóstico por la ruta real y devuelve su identificador."""
    respuesta = cliente.post(
        "/cash_management/cash-forecast/new",
        data={
            "company": "cacao",
            "version": version,
            "description": f"Escenario {version}",
            "fiscal_year_id": "FY2026",
            "periodicity": "monthly",
        },
    )
    assert respuesta.status_code in (302, 303), "La creación del pronóstico debe redirigir al detalle."
    ruta = urlsplit(respuesta.headers["Location"]).path
    return ruta.rsplit("/", 1)[-1]


def test_comparativo_muestra_estados_y_zonas_traducidos(app, authenticated_client, entorno_contable):
    """El comparativo usa Borrador/Aprobado y zonas traducidas, nunca códigos crudos."""
    if os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"}:
        import pytest

        pytest.skip("El comparativo de pronósticos no aplica en modo escritorio.")
    sufijo = uuid4().hex[:8]
    cliente = authenticated_client()

    borrador_id = _crear_pronostico(cliente, f"base-{sufijo}")
    aprobado_id = _crear_pronostico(cliente, f"escenario-{sufijo}")
    aprobacion = cliente.post(f"/cash_management/cash-forecast/{aprobado_id}/approve")
    assert aprobacion.status_code in (302, 303), "El pronóstico borrador debe poder aprobarse."

    # Cliente nuevo: sin mensajes flash de la aprobación en la página comparada.
    respuesta = authenticated_client().get(
        f"/cash_management/cash-forecast/compare?company=cacao&base_id={borrador_id}&compare_id={aprobado_id}"
    )

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)

    # Los estados del escenario base y del comparado se renderizan con su etiqueta.
    estados = INSIGNIA_ESTADO.findall(html)
    assert "Borrador" in estados, "El escenario base debe mostrar la etiqueta Borrador."
    assert "Aprobado" in estados, "El escenario comparado debe mostrar la etiqueta Aprobado."
    # El selector de escenarios también anuncia el estado de cada pronóstico.
    assert "(Borrador)" in html and "(Aprobado)" in html

    # Las zonas de la comparación solo pueden ser etiquetas traducidas.
    zonas = INSIGNIA_ZONA.findall(html)
    assert zonas, "La tabla de comparación debe renderizar la zona de cada período."
    assert set(zonas) <= ETIQUETAS_ZONA_TRADUCIDAS, f"Zonas sin traducir: {sorted(set(zonas) - ETIQUETAS_ZONA_TRADUCIDAS)}"

    # Ningún código interno llega al HTML como etiqueta.
    for codigo in ("Current", "Projected", "Draft", "Approved"):
        assert codigo not in html, f"El código crudo {codigo} no debe aparecer en el comparativo."
