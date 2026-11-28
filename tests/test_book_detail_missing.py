# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1787: el detalle de libro responde 404 para un código inexistente."""

from __future__ import annotations


def test_libro_inexistente_responde_404(app, authenticated_client, entorno_contable):
    """Un código que no existe no produce 500."""
    del entorno_contable

    response = authenticated_client("admin").get("/accounting/book/NO-EXISTE")

    assert response.status_code == 404


def test_libro_existente_renderiza_el_codigo(app, authenticated_client, entorno_contable):
    """El control positivo sigue mostrando el libro."""
    del entorno_contable

    response = authenticated_client("admin").get("/accounting/book/DEFAULT_BOOK")

    assert response.status_code == 200
    assert "DEFAULT_BOOK" in response.get_data(as_text=True)
