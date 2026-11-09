# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los encabezados operativos usan msgids en español.

Escenario de negocio (issue #1953): el mapa de columnas usaba msgids en
inglés, por lo que la interfaz en español mostraba encabezados sin traducir.
"""

from __future__ import annotations

from flask_babel import force_locale

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.reportes.helpers import _column_label


def _crear_app():
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def test_encabezados_operativos_en_espanol_e_ingles():
    """#1953: el catálogo español y el inglés reciben su etiqueta."""
    application = _crear_app()
    with application.app_context():
        with force_locale("es"):
            assert _column_label("posting_date", None) == "Fecha de contabilización"
            assert _column_label("item_name", None) == "Nombre del artículo"
        with force_locale("en"):
            assert _column_label("posting_date", None) == "Posting Date"
            assert _column_label("item_name", None) == "Item name"
