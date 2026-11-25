# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1662 y #2268: carga y lector comparten el contrato de delimitadores CSV."""

from __future__ import annotations

import pytest

from cacao_accounting.imports.csv_dialect import (
    CSV_SAMPLE_CHARS,
    ImportCSVFormatError,
    sniff_csv_dialect,
)
from cacao_accounting.imports.readers.csv_reader import CSVReader
from cacao_accounting.imports.routes import _valid_csv_fallback


def test_fallback_rechaza_tabulaciones_que_el_lector_no_parsea():
    """Un TSV no pasa como CSV si CSVReader solo admite coma y punto y coma."""
    assert _valid_csv_fallback(b"cuenta\tdebito\tcredito\n1101\t100\t0\n") is False


def test_fallback_conserva_coma_y_punto_y_coma():
    """Los delimitadores soportados por CSVReader siguen aceptándose."""
    assert _valid_csv_fallback(b"cuenta,debito,credito\n1101,100,0\n") is True
    assert _valid_csv_fallback(b"cuenta;debito;credito\n1101;100;0\n") is True


def test_fallback_acepta_csv_de_una_sola_columna():
    """Un archivo de una columna no tiene delimitador que Sniffer pueda inferir."""
    assert _valid_csv_fallback(b"codigo\nART01\n") is True
    assert _valid_csv_fallback(b"codigo") is True


def test_fallback_acepta_tabulacion_dentro_de_campo_entrecomillado():
    """La tabulación es contenido válido cuando queda dentro de las comillas."""
    contenido = b'cuenta;detalle;credito\n1101;"cuenta\tcon tab";0\n'
    assert _valid_csv_fallback(contenido) is True


def test_lector_rechaza_tabulacion_fuera_de_comillas(tmp_path):
    """El lector aplica la misma regla que el fallback de MIME."""
    archivo = tmp_path / "tabulado.csv"
    archivo.write_text("cuenta\tdebito\tcredito\n1101\t100\t0\n", encoding="utf-8")
    with pytest.raises(ImportCSVFormatError):
        CSVReader().read(str(archivo))


def test_lector_conserva_tabulacion_dentro_de_comillas(tmp_path):
    """Una tabulación citada llega intacta a las filas del TabularBook."""
    archivo = tmp_path / "citado.csv"
    archivo.write_text('cuenta;detalle;credito\n1101;"cuenta\tcon tab";0\n', encoding="utf-8")
    tabla = CSVReader().read(str(archivo))
    assert tabla.columns == ["cuenta", "detalle", "credito"]
    assert tabla.rows == [["1101", "cuenta\tcon tab", "0"]]


def test_lector_y_fallback_olen_la_misma_muestra(tmp_path):
    """Un delimitador ausente en los primeros 1024 caracteres ya se detecta."""
    contenido = f'"{"h" * 1100}";debito;credito\n1101;100;0\n'
    assert sniff_csv_dialect(contenido[:CSV_SAMPLE_CHARS]).delimiter == ";"
    assert _valid_csv_fallback(contenido.encode("utf-8")) is True

    archivo = tmp_path / "muestra_larga.csv"
    archivo.write_text(contenido, encoding="utf-8")
    tabla = CSVReader().read(str(archivo))
    assert len(tabla.columns) == 3
    assert tabla.rows == [["1101", "100", "0"]]
