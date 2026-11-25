# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1662 y #2268: carga y lector comparten el contrato de delimitadores CSV."""

from __future__ import annotations

import pytest

from cacao_accounting.imports.csv_dialect import (
    CSV_SAMPLE_CHARS,
    ImportCSVFormatError,
    csv_sample_from_bytes,
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


def test_comilla_literal_no_oculta_tabulacion():
    """Una comilla en medio del campo no habilita un citado que oculte la tabulación."""
    contenido = b'cuenta;detalle;credito\n1101;cuenta"rara\tcon tab;0\n'
    assert _valid_csv_fallback(contenido) is False


def test_lector_rechaza_tabulacion_tras_comilla_literal(tmp_path):
    """La carga y el lector coinciden también cuando la comilla es contenido literal."""
    archivo = tmp_path / "comilla_literal.csv"
    archivo.write_text('cuenta;detalle;credito\n1101;cuenta"rara\tcon tab;0\n', encoding="utf-8")
    with pytest.raises(ImportCSVFormatError):
        CSVReader().read(str(archivo))


def test_ventana_multibyte_es_la_misma_en_carga_y_lector(tmp_path):
    """La muestra de bytes cubre los mismos caracteres que lee CSVReader."""
    contenido = f'{"é" * 1100};debito;credito\n1101;100;0\n'
    muestra = csv_sample_from_bytes(contenido.encode("utf-8"))
    assert muestra == contenido[:CSV_SAMPLE_CHARS]
    assert sniff_csv_dialect(muestra).delimiter == ";"
    assert _valid_csv_fallback(contenido.encode("utf-8")) is True

    archivo = tmp_path / "multibyte.csv"
    archivo.write_text(contenido, encoding="utf-8")
    tabla = CSVReader().read(str(archivo))
    assert tabla.columns == ["é" * 1100, "debito", "credito"]
    assert tabla.rows == [["1101", "100", "0"]]


def test_ventana_multibyte_cruza_el_limite_de_bytes(tmp_path):
    """La muestra corta en 8192 bytes sin romper un carácter y conserva 2048."""
    contenido = "😀" * 2047 + ";" + "😀" * 3 + "\na;b\n"
    muestra = csv_sample_from_bytes(contenido.encode("utf-8"))

    with pytest.raises(UnicodeDecodeError):
        contenido.encode("utf-8")[:8192].decode("utf-8")
    assert muestra == contenido[:CSV_SAMPLE_CHARS]
    assert sniff_csv_dialect(muestra).delimiter == ";"
    assert _valid_csv_fallback(contenido.encode("utf-8")) is True

    archivo = tmp_path / "multibyte_limite.csv"
    archivo.write_text(contenido, encoding="utf-8")
    tabla = CSVReader().read(str(archivo))
    assert tabla.columns == ["😀" * 2047, "😀" * 3]
    assert tabla.rows == [["a", "b"]]


def test_campos_citados_consecutivos_conservan_tabulacion_citada(tmp_path):
    """Cerrar un campo citado no impide abrir el siguiente campo citado."""
    contenido = 'h1;"h2";"h3"\n"a\tb";"c";"d\te"\n'
    assert _valid_csv_fallback(contenido.encode("utf-8")) is True

    archivo = tmp_path / "citados_consecutivos.csv"
    archivo.write_text(contenido, encoding="utf-8")
    tabla = CSVReader().read(str(archivo))
    assert tabla.columns == ["h1", "h2", "h3"]
    assert tabla.rows == [["a\tb", "c", "d\te"]]


def test_salto_tras_campo_citado_habilita_cita_en_la_siguiente_fila(tmp_path):
    """El salto que cierra una fila citada deja el inicio de campo listo."""
    contenido = 'h1;"h2"\n"a\tb";"c\td"\n'
    assert _valid_csv_fallback(contenido.encode("utf-8")) is True

    archivo = tmp_path / "cita_tras_salto.csv"
    archivo.write_text(contenido, encoding="utf-8")
    tabla = CSVReader().read(str(archivo))
    assert tabla.columns == ["h1", "h2"]
    assert tabla.rows == [["a\tb", "c\td"]]
