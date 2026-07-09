# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Pruebas de validaciones pre-submit para documentos transaccionales."""

from datetime import date

import pytest

from cacao_accounting.document_flow.validation import validate_submit_prerequisites


class MockRegistro:
    def __init__(self, company=None, posting_date=None, supplier_id=None, customer_id=None):
        self.company = company
        self.posting_date = posting_date
        self.supplier_id = supplier_id
        self.customer_id = customer_id


class MockItem:
    def __init__(self, qty=1, warehouse=None, item_code=None):
        self.qty = qty
        self.warehouse = warehouse
        self.item_code = item_code


class TestValidateSubmitPrerequisites:
    def test_valid_document_passes(self):
        items = [MockItem(qty=1)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        validate_submit_prerequisites(registro, items=items, require_party=True)

    def test_valid_document_no_party_required_passes(self):
        items = [MockItem(qty=1)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8))
        validate_submit_prerequisites(registro, items=items, require_party=False)

    def test_valid_document_with_customer_passes(self):
        items = [MockItem(qty=1)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), customer_id="CUST-001")
        validate_submit_prerequisites(registro, items=items, require_party=True)

    def test_rejects_missing_company(self):
        items = [MockItem(qty=1)]
        registro = MockRegistro(company=None, posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="compania"):
            validate_submit_prerequisites(registro, items=items)

    def test_rejects_missing_posting_date(self):
        items = [MockItem(qty=1)]
        registro = MockRegistro(company="cacao", posting_date=None, supplier_id="SUP-001")
        with pytest.raises(ValueError, match="fecha"):
            validate_submit_prerequisites(registro, items=items)

    def test_rejects_missing_party_when_required(self):
        items = [MockItem(qty=1)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8))
        with pytest.raises(ValueError, match="cliente o proveedor"):
            validate_submit_prerequisites(registro, items=items, require_party=True)

    def test_rejects_empty_lines(self):
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="linea"):
            validate_submit_prerequisites(registro, items=[], require_lines=True)

    def test_rejects_none_lines(self):
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="linea"):
            validate_submit_prerequisites(registro, items=None, require_lines=True)

    def test_rejects_zero_qty(self):
        items = [MockItem(qty=0)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="cero"):
            validate_submit_prerequisites(registro, items=items, require_qty_positive=True)

    def test_rejects_negative_qty(self):
        items = [MockItem(qty=-1)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="cero"):
            validate_submit_prerequisites(registro, items=items, require_qty_positive=True)

    def test_skips_line_validation_when_disabled(self):
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        validate_submit_prerequisites(registro, items=None, require_lines=False)

    def test_skips_qty_validation_when_disabled(self):
        items = [MockItem(qty=0)]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        validate_submit_prerequisites(registro, items=items, require_qty_positive=False)

    def test_rejects_missing_warehouse_when_required(self):
        items = [MockItem(qty=1, warehouse=None, item_code="ITEM-001")]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="almacen"):
            validate_submit_prerequisites(registro, items=items, require_warehouse=True)

    def test_passes_with_warehouse_when_required(self):
        items = [MockItem(qty=1, warehouse="WH-001", item_code="ITEM-001")]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        validate_submit_prerequisites(registro, items=items, require_warehouse=True)

    def test_skips_warehouse_validation_when_disabled(self):
        items = [MockItem(qty=1, warehouse=None, item_code="ITEM-001")]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        validate_submit_prerequisites(registro, items=items, require_warehouse=False)

    def test_rejects_one_item_without_warehouse_among_many(self):
        items = [
            MockItem(qty=1, warehouse="WH-001", item_code="ITEM-001"),
            MockItem(qty=1, warehouse=None, item_code="ITEM-002"),
        ]
        registro = MockRegistro(company="cacao", posting_date=date(2026, 7, 8), supplier_id="SUP-001")
        with pytest.raises(ValueError, match="ITEM-002"):
            validate_submit_prerequisites(registro, items=items, require_warehouse=True)
