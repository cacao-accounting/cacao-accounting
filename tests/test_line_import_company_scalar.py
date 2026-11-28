# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1966: company_id no escalar es payload inválido, no 500."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("company_id", [["cacao"], {"code": "cacao"}, 123, True])
def test_company_id_no_textual_responde_400(app, authenticated_client, company_id):
    """Un contexto que no usa el código textual no llega al filtro SQL."""
    respuesta = authenticated_client("admin").post(
        "/api/line-import/validate",
        json={"doctype": "sales_invoice", "context": {"company_id": company_id}, "rows": [{}]},
    )

    assert respuesta.status_code == 400, respuesta.get_data(as_text=True)
