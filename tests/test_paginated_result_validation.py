# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1904: PaginatedResult rechaza metadatos imposibles al construirse."""

from __future__ import annotations

import pytest

from cacao_accounting.query_tools.pagination import PaginatedResult


@pytest.mark.parametrize(
    "kwargs",
    [
        {"page": 0, "page_size": 10, "total_items": 1},
        {"page": 1, "page_size": 0, "total_items": 1},
        {"page": 1, "page_size": -5, "total_items": 1},
        {"page": -1, "page_size": 10, "total_items": 1},
        {"page": 1, "page_size": 10, "total_items": -3},
    ],
)
def test_rechaza_metadatos_invalidos(kwargs):
    """Ninguna página o tamaño no positivo produce metadatos válidos."""
    with pytest.raises(ValueError):
        PaginatedResult(**kwargs)


def test_resultado_valido_calcula_paginas():
    """Un resultado válido sigue calculando total_pages."""
    resultado = PaginatedResult(page=1, page_size=10, total_items=25, items=[])

    assert resultado.total_pages == 3
    assert resultado.has_next_page is True
