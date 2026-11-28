# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1197: comprobantes normalizan booleanos textuales en importación."""

from __future__ import annotations

import pytest

from cacao_accounting.contabilidad.journal_service import JournalValidationError, _normalize_line
from cacao_accounting.numbers import coerce_boolean


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
        (None, False),
        ("true", True),
        ("1", True),
        ("si", True),
        ("on", True),
        (True, True),
        (False, False),
    ],
)
def test_coerce_boolean_acepta_representaciones_inequivocas(value, expected):
    """Booleanos nativos y textos aceptados se resuelven sin asumir verdadero."""
    assert coerce_boolean(value, "is_advance") is expected


def test_coerce_boolean_rechaza_valor_desconocido():
    """Un valor no booleano es un error, no un anticipo silencioso."""
    with pytest.raises(ValueError, match="booleano válido"):
        coerce_boolean("quizá", "is_advance")


def test_normalize_line_interpreta_texto_false_como_anticipo_falso():
    """El adaptador de importación entrega cadenas; `false` no debe ser True."""
    line = _normalize_line(
        {"account": "110101", "debit": "10", "credit": "0", "is_advance": "false"},
        1,
    )
    assert line.is_advance is False


def test_normalize_line_acepta_true_textual():
    line = _normalize_line({"account": "110101", "debit": "10", "credit": "0", "is_advance": "true"}, 1)
    assert line.is_advance is True


def test_normalize_line_rechaza_booleano_invalido():
    with pytest.raises(JournalValidationError, match="booleano válido"):
        _normalize_line({"account": "110101", "debit": "10", "credit": "0", "is_advance": "quizá"}, 1)
