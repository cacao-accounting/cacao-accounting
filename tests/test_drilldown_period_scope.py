# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1939: el drilldown conserva el rango contable del reporte padre."""

from __future__ import annotations

from cacao_accounting.reportes.helpers import _build_drill_down_url


def test_url_incluye_el_rango_de_periodos(app):
    """El detalle recibe accounting_period_from/to del reporte padre."""
    with app.test_request_context("/"):
        url = _build_drill_down_url(
            {"account_code": "5101"},
            "cacao",
            "DEFAULT_BOOK",
            None,
            "PER-A",
            "PER-B",
        )

    assert url
    assert "accounting_period_from=PER-A" in url
    assert "accounting_period_to=PER-B" in url


def test_sin_rango_no_agrega_parametros(app):
    """Un reporte de un período único no inventa el rango."""
    with app.test_request_context("/"):
        url = _build_drill_down_url({"account_code": "5101"}, "cacao", "DEFAULT_BOOK", "PER-A")

    assert url
    assert "accounting_period=PER-A" in url
    assert "accounting_period_from" not in url
