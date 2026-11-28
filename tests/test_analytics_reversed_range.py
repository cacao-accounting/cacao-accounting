# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1969: analytics rechaza el rango invertido en vez de devolver vacío."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting.reportes.analytics import (
    get_concentration,
    get_kpi_snapshot,
    get_trend,
    metric_value,
)

INICIO = date(2026, 12, 31)
FIN = date(2026, 1, 1)


@pytest.mark.parametrize(
    "consulta",
    [
        lambda: metric_value("cacao", "income", INICIO, FIN),
        lambda: get_kpi_snapshot("cacao", INICIO, FIN),
        lambda: get_trend("cacao", "income", INICIO, FIN),
        lambda: get_concentration("cacao", "customer", INICIO, FIN),
    ],
)
def test_servicios_de_analytics_rechazan_rango_invertido(app, consulta):
    """La validación ocurre antes de consultar y falla de forma explícita."""
    with app.app_context():
        with pytest.raises(ValueError, match="fecha inicial"):
            consulta()
