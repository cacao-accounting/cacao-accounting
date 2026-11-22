# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2106: la selección de catálogo respeta país/idioma y el archivo explícito.

`choose_catalog_file()` no debe devolver siempre el catálogo base ES: en inglés
debe resolver `base_en` y con un `catalog_name` explícito debe usar ese archivo
(o devolver `None` si no es válido).
"""

from __future__ import annotations

import os

from cacao_accounting.setup.service import choose_catalog_file


def test_idioma_ingles_usa_el_catalogo_ingles():
    """Para idioma EN se resuelve `base_en.csv`."""
    catalogo = choose_catalog_file("US", "en")
    assert catalogo is not None
    assert os.path.basename(catalogo.file) == "base_en.csv"
    assert catalogo.idioma == "EN"


def test_idioma_espanol_usa_el_catalogo_espanol():
    """Para idioma ES se resuelve `base_es.csv`."""
    catalogo = choose_catalog_file("NI", "es")
    assert catalogo is not None
    assert os.path.basename(catalogo.file) == "base_es.csv"
    assert catalogo.idioma == "ES"


def test_archivo_explicito_se_respeta():
    """Un `catalog_name` válido se usa, no el base por defecto."""
    catalogo = choose_catalog_file("NI", "es", "us_gaap.csv")
    assert catalogo is not None
    assert os.path.basename(catalogo.file) == "us_gaap.csv"
    assert catalogo.pais == "NI"


def test_archivo_explicito_inexistente_devuelve_none():
    """Un `catalog_name` inexistente no cae al catálogo base."""
    assert choose_catalog_file("NI", "es", "no_existe.csv") is None
