# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1039: las grillas de ventas recorren todas las líneas aunque falte un índice."""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace

from cacao_accounting.ventas import services as ventas
from cacao_accounting.form_lines import form_line_indexes


def _request_con(formulario):
    return SimpleNamespace(form=OrderedDict(formulario))


def test_huecos_y_alias_producen_indices_presentes_unicos(monkeypatch):
    """Los índices intermedios vacíos se omiten y alias como 01 se deduplican."""
    monkeypatch.setattr(
        ventas,
        "request",
        _request_con([("item_code_0", ""), ("item_code_1", "A"), ("item_code_01", "alias"), ("item_code_3", "C")]),
    )
    assert form_line_indexes(ventas.request.form, "item_code") == [0, 1, 3]


def test_sin_lineas_no_produce_indices(monkeypatch):
    """Un formulario sin la familia no produce índices de iteración."""
    monkeypatch.setattr(ventas, "request", _request_con([("otro", "x")]))
    assert form_line_indexes(ventas.request.form, "item_code") == []


def test_sufijo_demasiado_grande_se_ignora(monkeypatch):
    """Un sufijo decimal que Python no puede convertir no rompe el parser."""
    huge_index = "9" * 5000
    monkeypatch.setattr(ventas, "request", _request_con([(f"item_code_{huge_index}", "A")]))
    assert form_line_indexes(ventas.request.form, "item_code") == []
