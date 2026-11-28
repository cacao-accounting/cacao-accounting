# SPDX-License-Identifier: Apache-2.0
"""#1544 QA2: rutas HTTP publicadas rechazan Infinity/NaN sin 500 ni persistencia."""

from __future__ import annotations


from cacao_accounting.database import PurchaseOrder, SalesRequest, database


def test_sales_request_new_rejects_infinity_via_http(entorno_contable, authenticated_client):
    client = authenticated_client("admin")
    payload = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": "2026-05-15",
        "remarks": "INF-HTTP-SALES",
        "item_code_0": "ART01",
        "qty_0": "1",
        "rate_0": "Infinity",
        "uom_0": "UND",
    }
    resp = client.post("/sales/sales-request/new", data=payload, follow_redirects=False)
    assert resp.status_code in (200, 302)
    assert resp.status_code != 500
    with entorno_contable.app.app_context():
        found = database.session.execute(
            database.select(SalesRequest.id).filter_by(remarks="INF-HTTP-SALES")
        ).scalar_one_or_none()
        assert found is None


def test_purchase_order_new_rejects_infinity_via_http(entorno_contable, authenticated_client):
    client = authenticated_client("admin")
    payload = {
        "company": "cacao",
        "transaction_currency": "NIO",
        "posting_date": "2026-05-15",
        "remarks": "INF-HTTP-PURCHASE",
        "item_code_0": "ART01",
        "qty_0": "1",
        "rate_0": "Infinity",
        "uom_0": "UND",
    }
    resp = client.post("/buying/purchase-order/new", data=payload, follow_redirects=False)
    assert resp.status_code in (200, 302)
    assert resp.status_code != 500
    with entorno_contable.app.app_context():
        found = database.session.execute(
            database.select(PurchaseOrder.id).filter_by(remarks="INF-HTTP-PURCHASE")
        ).scalar_one_or_none()
        assert found is None


def test_purchase_order_new_rejects_nan_via_http(entorno_contable, authenticated_client):
    client = authenticated_client("admin")
    payload = {
        "company": "cacao",
        "transaction_currency": "NIO",
        "posting_date": "2026-05-15",
        "remarks": "NAN-HTTP-PURCHASE",
        "item_code_0": "ART01",
        "qty_0": "NaN",
        "rate_0": "10",
        "uom_0": "UND",
    }
    resp = client.post("/buying/purchase-order/new", data=payload, follow_redirects=False)
    assert resp.status_code in (200, 302)
    assert resp.status_code != 500
    with entorno_contable.app.app_context():
        found = database.session.execute(
            database.select(PurchaseOrder.id).filter_by(remarks="NAN-HTTP-PURCHASE")
        ).scalar_one_or_none()
        assert found is None
