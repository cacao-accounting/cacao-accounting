# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2163: el listado de tasas muestra la precisión persistida."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import ExchangeRate, database


def test_listado_de_tasas_conserva_los_decimales_almacenados(app, entorno_contable, authenticated_client):
    """La tasa no se redondea a cuatro decimales al listarla."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        rate = ExchangeRate(
            origin="USD",
            destination="NIO",
            rate=Decimal("37.123456789"),
            date=date(2026, 5, 15) + timedelta(days=int(suffix, 16) % 300),
        )
        database.session.add(rate)
        database.session.commit()

    response = authenticated_client().get("/accounting/exchange")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "37.123456789" in html
    assert "37.1235" not in html
