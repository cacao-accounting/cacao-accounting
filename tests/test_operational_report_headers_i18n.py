# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1953: los encabezados de reportes operativos respetan el locale."""

from __future__ import annotations

from flask_babel import force_locale

from cacao_accounting.reportes.helpers import _column_label


def test_encabezado_en_espanol(app):
    """Con locale es el encabezado está en español."""
    with app.test_request_context("/"):
        with force_locale("es"):
            assert _column_label("posting_date", None) == "Fecha de contabilización"


def test_encabezado_en_ingles(app):
    """Con locale en el mismo encabezado se traduce."""
    with app.test_request_context("/"):
        with force_locale("en"):
            etiqueta = _column_label("posting_date", None)
            assert etiqueta != "Fecha de contabilización"
            assert etiqueta
