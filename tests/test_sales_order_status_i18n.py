# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2054: el estado operativo de la orden se muestra traducido en el detalle."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from flask_babel import force_locale
from sqlalchemy import inspect

from cacao_accounting.database import SalesOrder, database

ESTADOS = [
    ("open", "Abierta", "Open"),
    ("partial", "Parcial", "Partial"),
    ("closed", "Cerrada", "Closed"),
    ("cancelled", "Anulada", "Cancelled"),
]


def _orden(status: str) -> str:
    """Crea una orden de venta aprobada con el estado operativo indicado."""
    orden = SalesOrder(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=1,
        status=status,
        document_no=f"SO-2054-{uuid4().hex[:8]}",
        customer_name="Cliente 2054",
    )
    database.session.add(orden)
    database.session.commit()
    return str(orden.id)


def _cliente(escenario):
    """Autentica un cliente sobre la app aislada del escenario."""
    app = escenario.app
    user_id = str(inspect(escenario.admin_user).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return app, client


@pytest.mark.parametrize(("status", "etiqueta_es", "etiqueta_en"), ESTADOS)
def test_detalle_renderiza_el_estado_traducido(entorno_contable_aislado, status, etiqueta_es, etiqueta_en):
    """La ficha muestra la etiqueta legible, no el código persistido, y el catálogo inglés la traduce."""
    app, client = _cliente(entorno_contable_aislado)
    with app.app_context():
        order_id = _orden(status)

    response = client.get(f"/sales/sales-order/{order_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert etiqueta_es in body
    assert f">{status}<" not in body
    with app.app_context(), force_locale("en"):
        from flask_babel import gettext

        assert gettext(etiqueta_es) == etiqueta_en
