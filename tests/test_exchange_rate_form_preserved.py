# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1956: altas y ediciones rechazadas conservan ambas monedas."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.database import ExchangeRate, database

pytestmark = pytest.mark.usefixtures("entorno_contable")


def test_alta_rechazada_conserva_origen_y_destino(authenticated_client):
    """El rechazo por monedas iguales conserva ambos campos enviados."""
    response = authenticated_client("admin").post(
        "/accounting/exchange/new",
        data={"origin": "NIO", "destination": "NIO", "rate": "1", "date": "2026-11-23"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert re.search(r'id="origin"[^>]*value="NIO"', html)
    assert re.search(r'id="destination"[^>]*value="NIO"', html)


def test_edicion_rechazada_conserva_post_y_get_muestra_tasa_actual(app, authenticated_client):
    """GET de edición repuebla datos guardados y POST inválido mantiene lo enviado."""
    rate_date = date(2099, 1, 1)
    with app.app_context():
        rate = ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=rate_date)
        database.session.add(rate)
        database.session.commit()
        rate_id = rate.id

    try:
        client = authenticated_client("admin")
        initial = client.get(f"/accounting/exchange/{rate_id}/edit")
        assert initial.status_code == 200
        initial_html = initial.get_data(as_text=True)
        assert re.search(r'id="origin"[^>]*value="USD"', initial_html)
        assert re.search(r'id="destination"[^>]*value="NIO"', initial_html)

        rejected = client.post(
            f"/accounting/exchange/{rate_id}/edit",
            data={"origin": "NIO", "destination": "NIO", "rate": "37", "date": rate_date.isoformat()},
        )

        assert rejected.status_code == 200
        html = rejected.get_data(as_text=True)
        assert re.search(r'id="origin"[^>]*value="NIO"', html)
        assert re.search(r'id="destination"[^>]*value="NIO"', html)
        with app.app_context():
            persisted = database.session.get(ExchangeRate, rate_id)
            assert persisted is not None
            assert persisted.origin == "USD"
            assert persisted.destination == "NIO"
            assert persisted.rate == Decimal("36")
    finally:
        with app.app_context():
            persisted = database.session.get(ExchangeRate, rate_id)
            if persisted is not None:
                database.session.delete(persisted)
                database.session.commit()
