# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1882: la importación bancaria conserva solo el asistente compartido.

Se retiró la plantilla obsoleta; la ruta pública sigue redirigiendo al
asistente canónico de importación para no romper enlaces existentes.
"""

from __future__ import annotations

from pathlib import Path


def test_ruta_legacy_redirige_al_asistente_compartido(authenticated_client):
    """El endpoint bancario histórico lleva al asistente canónico."""
    client = authenticated_client("admin")

    response = client.get("/cash_management/bank-statement/import")

    assert response.status_code == 302
    assert "/imports/new" in response.headers["Location"]


def test_plantilla_legacy_de_extracto_fue_retirada():
    """La plantilla huérfana ya no forma parte del paquete."""
    template = (
        Path(__file__).resolve().parents[1] / "cacao_accounting" / "bancos" / "templates" / "bancos" / "extracto_importar.html"
    )
    assert not template.exists()
