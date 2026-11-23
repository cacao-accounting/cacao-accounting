# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2214/#1788: un hueco de índice no descarta las líneas posteriores."""

from __future__ import annotations

from cacao_accounting import create_app
from cacao_accounting.compras.services import form_line_indexes
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
        data={"item_code_0": "", "item_code_1": "A", "item_code_2": "B", "otro": "x"},
    ):
        assert form_line_indexes("item_code") == [0, 1, 2]


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
        assert form_line_indexes("item_code") == []
