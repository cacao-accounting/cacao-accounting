# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2069: el precio de catálogo rechaza cantidades inválidas."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("qty", ["abc", "NaN", "Infinity", "-Infinity", "0", "-1"])
def test_cantidad_invalida_responde_400(authenticated_client, qty):
    """Texto, no finitos y no positivos no llegan a la búsqueda de precio."""
    response = authenticated_client().get(f"/api/sales/catalog-price?company=cacao&item_code=ART01&qty={qty}")

    assert response.status_code == 400
