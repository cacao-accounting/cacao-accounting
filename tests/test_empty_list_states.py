# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los listados vacíos comunican el estado y paginan de forma coherente.

Escenario de negocio (issues #2049, #2048 y #2046): una búsqueda sin
resultados dejaba el cuerpo de la tabla vacío y el paginador mostraba
«Página 1 de 0». La persona usuaria no sabía si la búsqueda falló, si no hay
datos o si carece de alcance sobre la compañía.
"""

from __future__ import annotations

from types import SimpleNamespace


def _assert_estado_vacio(client, url: str, mensaje: str) -> None:
    respuesta = client.get(url)

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert mensaje in html
    assert "0 items encontrados" in html
    assert "Página 1 de 0" not in html


def test_busqueda_de_clientes_sin_resultados(app, authenticated_client):
    """El listado de clientes explica que el filtro no encontró filas."""
    client = authenticated_client("admin")

    _assert_estado_vacio(
        client,
        "/sales/customer/list?search=NO-SUCH-CUSTOMER",
        "No se encontraron clientes para los filtros seleccionados.",
    )


def test_busqueda_de_lotes_sin_resultados(app, authenticated_client):
    """El listado de lotes muestra el estado vacío con mensaje traducible."""
    client = authenticated_client("admin")

    _assert_estado_vacio(
        client,
        "/inventory/batch/list?search=NO-SUCH-BATCH",
        "No se encontraron lotes para los filtros seleccionados.",
    )


def test_lista_de_bodegas_sin_alcance(app, authenticated_client):
    """Una lista de bodegas vacía comunica el alcance y no muestra Página 1 de 0."""
    client = authenticated_client("admin")

    _assert_estado_vacio(
        client,
        "/inventory/warehouse/list",
        "No hay bodegas para los filtros o el alcance de compañía actual.",
    )


def test_la_paginacion_vacia_omite_la_pagina(app):
    """Sin resultados solo se informa el total, sin una página inexistente."""
    with app.test_request_context("/"):
        macro = app.jinja_env.get_template("macros.html").module.rendizar_paginacion
        html = macro(
            consulta=SimpleNamespace(total=0, page=1, pages=0, has_prev=False, has_next=False),
            vista="cacao_app.pagina_inicio",
        )

    assert "0 items encontrados" in html
    assert "Página" not in html
