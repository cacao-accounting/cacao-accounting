# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2214/#1788: un hueco de índice no descarta las líneas posteriores."""

from __future__ import annotations

from flask import request

from cacao_accounting import create_app
from cacao_accounting.form_lines import form_line_indexes, form_line_items
from cacao_accounting.config import configuracion


def test_indices_con_hueco_intermedio():
    """El primer índice vacío no debe truncar el resto de la grilla."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.test_request_context(
        "/",
        method="POST",
        data={"item_code_0": "", "item_code_1": "A", "item_code_01": "alias", "item_code_2": "B", "otro": "x"},
    ):
        assert form_line_indexes(request.form, "item_code") == [0, 1, 2]


def test_sin_lineas_devuelve_lista_vacia():
    """Un formulario sin la familia de campos no produce índices."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.test_request_context("/", method="POST", data={"otro": "x"}):
        assert form_line_indexes(request.form, "item_code") == []


def test_indices_pueden_leerse_de_un_formulario_explicito():
    """Los validadores que reciben un form pueden usar la misma enumeración robusta."""
    form = {"item_code_0": "A", "item_code_2": "B", "item_code_02": "alias"}
    assert form_line_indexes(form, "item_code") == [0, 2]
    assert form_line_items(form, "item_code") == [(0, "A"), (2, "B")]
