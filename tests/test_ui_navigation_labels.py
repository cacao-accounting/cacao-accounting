# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2145/#2199: navegación localizada y enlace de chat correcto."""

from __future__ import annotations

import pytest
from flask import render_template_string

from cacao_accounting.runtime_mode import is_desktop_mode


def test_compras_breadcrumb_usa_nombre_accesible_traducido(authenticated_client):
    """El `aria-label` del breadcrumb no queda en inglés fijo (#2145)."""
    response = authenticated_client().get("/buying/")

    assert response.status_code == 200
    assert 'aria-label="Ruta de navegación"' in response.get_data(as_text=True)


def test_macro_de_entidad_enlaza_a_la_sala_de_chat(app):
    """El botón Sala de Chat apunta a Gitter, no al manual (#2199)."""
    if is_desktop_mode():
        pytest.skip("El macro de entidad solo publica enlaces de comunidad en Cloud.")
    with app.test_request_context("/"):
        html = render_template_string("{% import 'macros.html' as m %}{{ m.crear_nueva_entidad() }}")

    assert "https://gitter.im/cacao-accounting/community" in html
    assert html.count("https://cacao-accounting-manual.readthedocs.io/es/latest/") == 1
