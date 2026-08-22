"""Regression coverage for sales-invoice company immutability."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.ventas.services import _handle_sales_invoice_edit_post


def test_draft_sales_invoice_rejects_company_change() -> None:
    """Editing a draft cannot move its identifier and fiscal context to another company."""
    app = create_app({**configuracion, "TESTING": True, "SECRET_KEY": "test"})
    invoice = SimpleNamespace(id="SALES-1", company="company-a")

    with app.test_request_context("/sales/invoice/SALES-1", method="POST", data={"company": "company-b"}):
        response = _handle_sales_invoice_edit_post(invoice)

    assert response.status_code == 302
    assert invoice.company == "company-a"
