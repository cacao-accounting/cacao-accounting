# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2114: el listado de pedidos muestra el total con su moneda."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import SalesRequest, database


def test_listado_de_pedidos_muestra_moneda_transaccional(app, authenticated_client, entorno_contable):
    """Un pedido en USD no se presenta como una cifra sin moneda."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        pedido = SalesRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SR-USD-{suffix}",
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36.5"),
            grand_total=Decimal("100"),
        )
        database.session.add(pedido)
        database.session.commit()

    response = authenticated_client().get(f"/sales/sales-request/list?search=SR-USD-{suffix}")

    assert response.status_code == 200
    assert "USD 100.00" in response.get_data(as_text=True)
