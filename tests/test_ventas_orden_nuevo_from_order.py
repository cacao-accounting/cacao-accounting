# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2045: residuo legacy del parámetro from_order en la alta de órden de venta."""

from datetime import date

from cacao_accounting.database import SalesOrder, database


def test_alta_orden_ignora_from_order_legacy(app, authenticated_client):
    """El parámetro legacy from_order no se conserva como opción de UI (#2045)."""
    with app.app_context():
        database.session.add(
            SalesOrder(
                company="cacao",
                posting_date=date(2026, 5, 15),
                docstatus=1,
                document_no="SO-2045",
                customer_name="Cliente 2045",
            )
        )
        database.session.commit()
        order_id = database.session.execute(database.select(SalesOrder).filter_by(document_no="SO-2045")).scalar_one().id

    response = authenticated_client().get(f"/sales/sales-order/new?from_order={order_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # El alta no debe presentar la orden legacy como origen ni su cliente.
    assert "SO-2045" not in body
    assert "Cliente 2045" not in body
