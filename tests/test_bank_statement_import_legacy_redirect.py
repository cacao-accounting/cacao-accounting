# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1882: la importación bancaria usa solo el asistente compartido.

Se retiraron la plantilla obsoleta, la ruta de redirección y el enlace legacy;
el dashboard de Bancos apunta al asistente canónico.
"""

from __future__ import annotations

from pathlib import Path


def test_dashboard_enlaza_al_asistente_canonico(authenticated_client):
    """El enlace de importación apunta directamente al asistente compartido."""
    client = authenticated_client("admin")

    response = client.get("/cash_management/bancos")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/imports/new" in body
    assert "/bank-statement/import" not in body


def test_ruta_legacy_de_importacion_bancaria_fue_retirada(authenticated_client):
    """El endpoint de redirección ya no existe."""
    client = authenticated_client("admin")

    response = client.get("/cash_management/bank-statement/import")

    assert response.status_code == 404


def test_plantilla_legacy_de_extracto_fue_retirada():
    """La plantilla huérfana ya no forma parte del paquete."""
    template = (
        Path(__file__).resolve().parents[1] / "cacao_accounting" / "bancos" / "templates" / "bancos" / "extracto_importar.html"
    )
    assert not template.exists()
