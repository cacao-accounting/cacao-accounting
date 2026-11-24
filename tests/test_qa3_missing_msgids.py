# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""QA3 2026-11-23: los mensajes devueltos por QA3 tienen traducción inglesa."""

from __future__ import annotations

import gettext
from pathlib import Path

LOCALES = Path(__file__).resolve().parents[1] / "cacao_accounting" / "translations"


def _catalogo_ingles() -> gettext.NullTranslations:
    """Carga el catálogo compilado de inglés."""
    return gettext.translation("messages", localedir=str(LOCALES), languages=["en"])


def test_identificador_de_compania_tiene_traduccion():
    """#1966: el error del importador de líneas no queda sin traducir."""
    catalogo = _catalogo_ingles()

    assert catalogo.gettext("El identificador de compañía no es válido.") == "The company identifier is not valid."


def test_codigo_duplicado_de_plantilla_tiene_traduccion():
    """#1929: el aviso de plantilla duplicada no queda sin traducir."""
    catalogo = _catalogo_ingles()

    assert (
        catalogo.gettext("Ya existe una plantilla con ese código para el tipo documental.")
        == "A template with that code already exists for the document type."
    )


def test_catalogo_devuelve_el_msgid_cuando_falta_la_entrada():
    """Control negativo del mecanismo: una entrada ausente se devuelve cruda."""
    catalogo = _catalogo_ingles()

    assert catalogo.gettext("cadena inexistente qa3 2026-11-23") == "cadena inexistente qa3 2026-11-23"


def test_booleano_invalido_tiene_traduccion():
    """#1197: el error de booleano del importador no queda sin traducir."""
    catalogo = _catalogo_ingles()

    assert (
        catalogo.gettext("El campo %(field)s debe ser un valor booleano válido.")
        == "The %(field)s field must be a valid boolean value."
    )
