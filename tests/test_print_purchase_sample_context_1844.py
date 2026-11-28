# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1844: los samples de impresión de compras usan proveedor y prefijo propios."""

from __future__ import annotations

import pytest

from cacao_accounting.printing.registry import PRINTABLE_DOCUMENTS, init_printing_registry

SUPPLIER = {
    "code": "SUPP-001",
    "legal_name": "Example Supplier S.A.",
    "commercial_name": "Example Supplier",
    "tax_id": "J0310000000003",
    "address": "Managua, Nicaragua",
    "phone": "+505 7777 0000",
    "email": "supplier@example.com",
}


@pytest.fixture(autouse=True)
def _registry():
    """Reinicia el registro de impresión para cada caso."""
    init_printing_registry()


@pytest.mark.parametrize("document_type", ["purchase_invoice", "purchase_credit_note", "purchase_debit_note"])
def test_facturas_de_compra_usan_sample_de_proveedor(document_type):
    """El preview no reutiliza la factura de venta ni su numeración."""
    definition = PRINTABLE_DOCUMENTS[document_type]
    context = definition["sample_context_builder"]()
    invoice = context["invoice"]

    assert definition["sample_context_builder"].__name__ == "build_purchase_invoice_sample_context"
    assert invoice["number"] == "PI-2026-00001"
    assert invoice["supplier"] == SUPPLIER
    assert "customer" not in invoice


@pytest.mark.parametrize(
    ("document_type", "root_name"),
    [
        ("purchase_order", "purchase_order"),
        ("purchase_request", "purchase_request"),
        ("supplier_quotation", "supplier_quotation"),
        ("request_for_quotation", "request_for_quotation"),
        ("purchase_receipt", "purchase_receipt"),
    ],
)
def test_documentos_de_compra_usan_tercero_proveedor(document_type, root_name):
    """Los samples de compras no identifican al proveedor como cliente."""
    context = PRINTABLE_DOCUMENTS[document_type]["sample_context_builder"]()

    assert context[root_name]["supplier"] == SUPPLIER


def test_sample_de_venta_conserva_cliente_y_prefijo():
    """El cambio de compras no altera el contexto de ventas."""
    context = PRINTABLE_DOCUMENTS["sales_invoice"]["sample_context_builder"]()
    invoice = context["invoice"]

    assert invoice["number"] == "FAC-2026-00001"
    assert invoice["customer"]["code"] == "CUST-001"
    assert invoice["customer"]["legal_name"] == "Example Customer S.A."
    assert "supplier" not in invoice
