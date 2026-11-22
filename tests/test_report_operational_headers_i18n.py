# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1953: los encabezados de reportes operativos se traducen en ambos idiomas.

Los msgids fuente viven en español. La interfaz española debe mostrar el
término español y la inglesa su traducción del catálogo; un encabezado sin
traducción inglesa vuelve a filtrar español en la UI inglesa.
"""

from __future__ import annotations

from flask_babel import force_locale

from cacao_accounting.i18n import _
from cacao_accounting.reportes.helpers import _COLUMN_LABELS, _column_label


def test_encabezados_citados_se_traducen_en_espanol_e_ingles(app):
    """Los casos reportados usan el término español y su versión inglesa."""
    with app.app_context():
        with force_locale("es"):
            assert _column_label("posting_date", None) == "Fecha de contabilización"
            assert _column_label("item_name", None) == "Nombre del artículo"
        with force_locale("en"):
            assert _column_label("posting_date", None) == "Posting Date"
            assert _column_label("item_name", None) == "Item Name"


def test_todos_los_encabezados_tienen_traduccion_inglesa(app):
    """Ningún msgid del mapa se queda sin traducción al inglés."""
    with app.app_context(), force_locale("en"):
        sin_traduccion = sorted({origen for origen in _COLUMN_LABELS.values() if _(origen) == origen})

    assert sin_traduccion == []
