# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las búsquedas recurrentes eliminan los valores copiados al modelo."""


def test_formulario_recurrente_limpia_los_valores_derivados_del_selector(authenticated_client):
    """El formulario incluye callbacks para limpiar el estado serializado de cada selector."""
    response = authenticated_client().get("/accounting/journal/recurring/new")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for callback in (
        "onClear: function() { header.company = ''; loadBooks(''); }",
        "onClear: function() { header.currency = ''; }",
        "onClear: function() { line.account_code = ''; line.account_label = ''; }",
        "onClear: function() { modalLine.cost_center = ''; }",
        "onClear: function() { modalLine.unit = ''; }",
        "onClear: function() { modalLine.project = ''; }",
        "onClear: function() { modalLine.party_id = ''; }",
    ):
        assert callback in html
