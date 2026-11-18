# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""QA1 #1546 / QA2 B4: los catálogos contables responden 404 homogéneo.

Detalle, edición y borrado de un registro inexistente no deben redirigir con
302; la respuesta es 404 en todos los catálogos.
"""

from __future__ import annotations

import pytest

MISSING_ID = "01J00000000000000000000000"

DETAIL_PATHS = (
    "/accounting/account/{id}",
    "/accounting/account/{id}/edit",
    "/accounting/unit/{id}",
    "/accounting/unit/{id}/edit",
    "/accounting/costs_center/{id}",
    "/accounting/costs_center/{id}/edit",
    "/accounting/project/{id}",
    "/accounting/project/{id}/edit",
)

DELETE_PATHS = (
    "/accounting/unit/delete/{id}",
    "/accounting/costs_center/{id}/delete",
    "/accounting/project/{id}/delete",
)


@pytest.mark.parametrize("template", DETAIL_PATHS)
def test_missing_catalog_record_returns_404(authenticated_client, template):
    """Detail and edit pages answer 404 instead of redirecting."""
    response = authenticated_client().get(template.format(id=MISSING_ID))

    assert response.status_code == 404
    assert response.headers.get("Location") is None


@pytest.mark.parametrize("template", DELETE_PATHS)
def test_missing_catalog_delete_returns_404(authenticated_client, template):
    """Deleting a missing record also answers 404."""
    response = authenticated_client().post(template.format(id=MISSING_ID))

    assert response.status_code == 404
