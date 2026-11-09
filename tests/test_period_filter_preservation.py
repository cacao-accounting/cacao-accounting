# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cambiar el período conserva la búsqueda y el estado.

Escenario de negocio (issue #2155): ``list_filters`` conservaba compañía y
período, pero el formulario de ``period_list_filters`` no enviaba search ni
status. Al cambiar compañía o período se perdían los filtros vigentes.
"""

from __future__ import annotations

from types import SimpleNamespace


def test_el_formulario_de_periodo_conserva_busqueda_y_estado(app):
    """El GET de período incluye los filtros activos como campos ocultos."""
    consulta = SimpleNamespace(
        periods=[1],
        selected_company="cacao",
        period_from="",
        period_to="",
        period_from_label="",
        period_to_label="",
    )

    with app.test_request_context("/cash_management/payment/list?search=ABC&status=paid"):
        html = app.jinja_env.get_template("macros.html").module.period_list_filters(consulta)

    assert 'name="search" value="ABC"' in html
    assert 'name="status" value="paid"' in html
