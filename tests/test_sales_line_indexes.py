# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1039: las grillas de ventas recorren todas las líneas aunque falte un índice."""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace

from cacao_accounting.ventas import services as ventas


def _request_con(formulario):
    return SimpleNamespace(form=OrderedDict(formulario))


def test_hueco_intermedio_no_trunca_el_maximo():
    """Con índices 0 vacío, 1 y 3 con datos, el máximo es 3."""
    original = ventas.request
    ventas.request = _request_con([("item_code_0", ""), ("item_code_1", "A"), ("item_code_3", "C")])
    try:
        assert ventas._max_line_index("item_code") == 3
    finally:
        ventas.request = original


def test_sin_lineas_el_maximo_es_menos_uno():
    """Un formulario sin la familia no produce ninguna iteración."""
    original = ventas.request
    ventas.request = _request_con([("otro", "x")])
    try:
        assert ventas._max_line_index("item_code") == -1
    finally:
        ventas.request = original
