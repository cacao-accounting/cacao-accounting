# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2070: la política AR/AP exige `enabled` booleano."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("enabled", ["false", "true", 1, 0, None])
def test_enabled_no_booleano_responde_400(authenticated_client, enabled):
    """Cadenas y números no se coercionan silenciosamente a bool."""
    response = authenticated_client().post(
        "/api/accounting/arap-reconciliation",
        json={"company": "cacao", "enabled": enabled},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "El campo enabled debe ser booleano."


def test_enabled_false_se_conserva(authenticated_client):
    """El booleano JSON false deshabilita realmente la política."""
    response = authenticated_client().post(
        "/api/accounting/arap-reconciliation",
        json={"company": "cacao", "enabled": False},
    )

    assert response.status_code == 200
    assert response.get_json()["enabled"] is False
