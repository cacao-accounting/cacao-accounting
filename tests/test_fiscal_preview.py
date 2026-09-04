"""Pruebas de preview fiscal unificado para formularios MVP."""

from __future__ import annotations

import os
import sys
import importlib
from decimal import Decimal

import pytest
from flask import url_for

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_func import init_test_db

from cacao_accounting import create_app
from cacao_accounting.api import _require_fiscal_preview_company_access
from cacao_accounting.fiscal_persistence_service import calculate_document_total_with_taxes

app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)


def test_document_total_ignores_tax_summary_without_template():
    """No permite que el resumen fiscal del navegador altere el subtotal."""
    total = calculate_document_total_with_taxes(
        type("Document", (), {"tax_template_id": None})(),
        Decimal("100"),
        [],
        '{"grand_total": "115.00"}',
    )
    assert total == Decimal("100")


def test_document_total_uses_canonical_manual_tax_lines_without_template():
    """A persisted manual tax changes AR totals even without a tax template."""
    total = calculate_document_total_with_taxes(
        type("Document", (), {"tax_template_id": None, "company": "cacao"})(),
        Decimal("100"),
        [],
        tax_lines_payload=[
            {
                "manual": True,
                "concept": "IVA",
                "type": "tax",
                "base_amount": "100",
                "rate": "16",
                "amount": "16",
                "affects_document_total": True,
                "included_in_price": False,
            }
        ],
    )
    assert total == Decimal("116")


@pytest.mark.parametrize(
    ("document_type", "expected_module", "expected_modules"),
    [
        ("purchase_invoice", "purchases", None),
        ("sales_invoice", "sales", None),
        ("purchase_receipt", None, ("purchases", "inventory")),
        ("purchase_order", None, ("purchases", "inventory")),
        ("delivery_note", None, ("sales", "inventory")),
        ("payment_entry", "cash", None),
    ],
)
def test_fiscal_preview_requires_company_access_for_its_operational_module(
    monkeypatch, document_type, expected_module, expected_modules
):
    """El preview no puede cargar reglas fiscales de una compañía ajena."""
    captured = []
    captured_shared = []
    api_module = importlib.import_module("cacao_accounting.api")
    monkeypatch.setattr(
        api_module,
        "exige_acceso_compania",
        lambda module, company, action: captured.append((module, company, action)),
    )
    monkeypatch.setattr(
        api_module,
        "exige_acceso_compania_cualquiera",
        lambda modules, company, action: captured_shared.append((modules, company, action)),
    )

    _require_fiscal_preview_company_access({"document_type": document_type, "company": "other-company"})

    if expected_modules:
        assert captured == []
        assert captured_shared == [(expected_modules, "other-company", "consultar")]
    else:
        assert captured == [(expected_module, "other-company", "consultar")]
        assert captured_shared == []


@pytest.fixture(scope="module", autouse=True)
def setupdb(request):
    """Inicializa la base de datos para las pruebas lentas."""
    if request.config.getoption("--slow") == "True":
        with app.app_context():
            init_test_db(app)


def test_api_fiscal_preview_purchase_invoice(request):
    """Valida que la API de preview fiscal responda para factura de compra."""
    if request.config.getoption("--slow") != "True":
        return
    with app.app_context():
        with app.test_client() as client:
            client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
            response = client.post(
                "/api/fiscal/preview",
                json={
                    "document_type": "purchase_invoice",
                    "company": "cacao",
                    "currency": "NIO",
                    "posting_date": "2026-05-19",
                    "party_type": "supplier",
                    "party_id": "SUPP-DEMO",
                    "lines": [
                        {"uid": "L-1", "item_code": "ITEM-1", "item_name": "Item 1", "qty": 2, "rate": 10, "amount": 20}
                    ],
                },
            )
            assert response.status_code == 200
            payload = response.get_json()
            assert payload is not None
            assert payload["profile"]["document_type"] == "purchase_invoice"
            assert "summary" in payload
            assert "tax_lines" in payload


def test_forms_render_tax_charges_block(request):
    """Valida que formularios MVP rendericen el bloque de impuestos y cargos."""
    if request.config.getoption("--slow") != "True":
        return
    with app.app_context():
        with app.test_client() as client:
            client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
            with app.test_request_context():
                invoice_new_url = url_for("compras.compras_factura_compra_nuevo")
                payment_new_url = url_for("bancos.bancos_pago_nuevo")

            purchase_invoice_form = client.get(invoice_new_url)
            assert purchase_invoice_form.status_code == 200
            html_invoice = purchase_invoice_form.get_data(as_text=True)
            assert "Impuestos y Cargos" in html_invoice
            assert "taxChargeDetailModal" in html_invoice

            payment_form = client.get(payment_new_url)
            assert payment_form.status_code == 200
            html_payment = payment_form.get_data(as_text=True)
            assert "Impuestos y Cargos" in html_payment
            assert "Añadir impuesto/cargo" in html_payment
            assert "Recalcular" in html_payment
            assert "taxChargeDetailModal" in html_payment
            assert "Método de cálculo" in html_payment
            assert "Referencias del Pago" in html_payment
            assert "referenceLineDetailModal" in html_payment
            assert "Monto sin asignar" in html_payment
