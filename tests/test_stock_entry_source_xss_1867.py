# SPDX-License-Identifier: Apache-2.0
"""#1867: source_id no debe inyectarse en JS/HTML del formulario de StockEntry."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting.database import Entity, PurchaseReceipt, database
from cacao_accounting.inventario.services import _source_context


def _allow_inventory_companies(monkeypatch):
    from cacao_accounting import decorators

    def _allow(*_modules, company_code=None, **_kwargs):
        if company_code:
            company = database.session.get(Entity, company_code)
            if company is not None:
                return company
        from flask import abort

        abort(403)

    monkeypatch.setattr(decorators, "exige_acceso_compania_cualquiera", _allow)


def _create_receipt(company="cacao", warehouse="BOD01"):
    receipt = PurchaseReceipt(
        company=company,
        posting_date=date(2026, 5, 15),
        docstatus=1,
        document_no="RC-XSS-1867",
        transaction_currency="NIO",
    )
    database.session.add(receipt)
    database.session.commit()
    return receipt.id


def test_source_api_url_rejects_unsafe_source_id(app, entorno_contable, monkeypatch, authenticated_client):
    _allow_inventory_companies(monkeypatch)
    with app.app_context():
        _create_receipt()
    payload = "x');alert(document.domain);//"
    resp = authenticated_client().get(f"/inventory/stock-entry/new?source_type=purchase_receipt&source_id={payload}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "alert(document.domain)" not in html
    assert "x&#39;);alert" not in html
    assert "/api/buying/purchase-receipt/" not in html


def test_source_api_url_accepts_safe_source_id(app, entorno_contable, authenticated_client):
    """With authenticated admin, a safe ID must render a safe tojson API URL."""
    with app.app_context():
        rid = _create_receipt()
    resp = authenticated_client("admin").get(f"/inventory/stock-entry/new?source_type=purchase_receipt&source_id={rid}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert f"/api/buying/purchase-receipt/{rid}/items" in html
    assert "fetchSource" in html
    assert "Recepci\\u00f3n de Compra" in html
    assert "Remisi\\u00f3n de Mercader\\u00eda Vendida" in html
    assert "recepci?n de compra" not in html
    assert "remisi?n de mercader?a" not in html


@pytest.mark.parametrize(
    ("source_type", "prefijo", "etiqueta"),
    [
        ("purchase_receipt", "/api/buying/purchase-receipt/", "recepción de compra"),
        ("delivery_note", "/api/sales/delivery-note/", "remisión de mercadería vendida"),
    ],
)
def test_source_context_conserva_etiquetas_legibles(source_type, prefijo, etiqueta):
    """El contexto seguro conserva la URL y la etiqueta visible del origen."""
    url, etiqueta_visible = _source_context(source_type, "ID_SEGURO")

    assert url == f"{prefijo}ID_SEGURO/items"
    assert etiqueta_visible == etiqueta
