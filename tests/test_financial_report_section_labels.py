# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las secciones del estado de flujo se presentan con su etiqueta localizada.

Escenario de negocio (issue #2193): las filas de detalle de operación usan
``section="operating"`` y ``_format_cell`` no tenía entrada para ese token, por
lo que la columna mostraba el identificador interno en inglés mientras
inversión y financiamiento sí aparecían traducidos.
"""

from __future__ import annotations

import pytest

from cacao_accounting.i18n import _
from cacao_accounting.reportes.helpers import _format_cell


@pytest.mark.parametrize("section", ["operating", "investing", "financing"])
def test_secciones_de_flujo_no_muestran_el_token_interno(app, section):
    """Ningún token de detalle del estado de flujo se presenta sin etiqueta."""
    with app.app_context(), app.test_request_context("/reports/cash-flow"):
        assert _format_cell("section", section, "NIO") != section


def test_operacion_usa_la_etiqueta_localizada(app):
    """La sección de operación comparte la etiqueta usada en la configuración."""
    with app.app_context(), app.test_request_context("/reports/cash-flow"):
        assert _format_cell("section", "operating", "NIO") == _("Operación")
