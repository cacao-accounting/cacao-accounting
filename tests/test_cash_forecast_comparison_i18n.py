# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El comparativo de pronósticos traduce zonas y estados.

Escenario de negocio (issue #2037): la plantilla imprimía los códigos internos
``Real``/``Current``/``Projected`` y ``Draft``/``Approved``/``Closed``/
``Archived``. Los cálculos y transiciones conservan esos códigos; solo la
presentación debe usar etiquetas gettext.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from flask import render_template
from flask_login import login_user

from cacao_accounting.database import User, database


def _fila(periodo: str, zona: str) -> dict:
    return {
        "period": periodo,
        "zone": zona,
        "base_projected": Decimal("100"),
        "compare_projected": Decimal("120"),
        "variance": Decimal("20"),
        "variance_manual_inflow": Decimal("0"),
        "variance_manual_outflow": Decimal("0"),
    }


def test_el_comparativo_muestra_etiquetas_traducidas(app):
    """Los códigos internos se mapean a etiquetas sin alterar el contrato."""
    with app.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

    with app.test_request_context("/cash_management/cash-forecast/compare"):
        login_user(usuario)
        html = render_template(
            "bancos/cash_forecast_comparar.html",
            companies=[("cacao", "Cacao")],
            selected_company="cacao",
            forecasts=[
                SimpleNamespace(id="b", version="Base", status="Draft"),
                SimpleNamespace(id="c", version="Comparada", status="Archived"),
            ],
            base_id="b",
            compare_id="c",
            base_forecast=SimpleNamespace(version="Base", status="Draft"),
            compare_forecast=SimpleNamespace(version="Comparada", status="Archived"),
            comparison=[
                _fila("Enero", "Real"),
                _fila("Febrero", "Current"),
                _fila("Marzo", "Projected"),
            ],
            titulo="Comparación",
        )

    assert "(Borrador)" in html
    assert "(Archivado)" in html
    assert ">Borrador<" in html
    assert ">Archivado<" in html
    assert ">Real<" in html
    assert ">Actual<" in html
    assert ">Proyectado<" in html
    assert "(Draft)" not in html
    assert "(Archived)" not in html
    assert ">Current<" not in html
    assert ">Projected<" not in html
