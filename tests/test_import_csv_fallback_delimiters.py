# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1662: el fallback CSV acepta solo delimitadores que el lector soporta."""

from __future__ import annotations

from cacao_accounting.imports.routes import _valid_csv_fallback


def test_fallback_rechaza_tabulaciones_que_el_lector_no_parsea():
    """Un TSV no pasa como CSV si CSVReader solo admite coma y punto y coma."""
    assert _valid_csv_fallback(b"cuenta\tdebito\tcredito\n1101\t100\t0\n") is False


def test_fallback_conserva_coma_y_punto_y_coma():
    """Los delimitadores soportados por CSVReader siguen aceptándose."""
    assert _valid_csv_fallback(b"cuenta,debito,credito\n1101,100,0\n") is True
    assert _valid_csv_fallback(b"cuenta;debito;credito\n1101;100;0\n") is True
