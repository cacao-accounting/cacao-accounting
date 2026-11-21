# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1007/#1010: los valores fiscales no finitos se rechazan como validación.

Una línea manual o una regla fiscal con `NaN`/`Infinity` no debe propagar
totales no finitos ni lanzar una excepción aritmética sin control.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.config import configuracion
from cacao_accounting.fiscal_persistence_service import (
    _decimal_or_none,
    _to_decimal,
    calculate_document_total_with_taxes,
)
from cacao_accounting.fiscal_preview_service import _decimal_value as preview_decimal
from cacao_accounting.tax_rule_service import TaxRuleServiceError
from cacao_accounting.tax_rule_service import _decimal_value as rule_decimal

NON_FINITE = ["NaN", "sNaN", "Infinity", "-Infinity"]


@pytest.fixture
def fiscal_app():
    """Create a minimal app for translated validation messages."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    yield app


@pytest.mark.parametrize("value", NON_FINITE)
def test_persistence_decimal_helpers_reject_non_finite(fiscal_app, value):
    """Canonical persistence helpers cannot store non-finite amounts."""
    with fiscal_app.app_context():
        with pytest.raises(ValueError):
            _decimal_or_none(value)
        with pytest.raises(ValueError):
            _to_decimal(value)


@pytest.mark.parametrize("value", NON_FINITE)
def test_manual_tax_line_rejects_non_finite_amounts(fiscal_app, value):
    """A manipulated manual line fails before changing the document total."""
    document = SimpleNamespace(company="alpha", tax_template_id=None, document_type="sales_invoice")
    payload = [
        {
            "manual": True,
            "source_rule_id": "MANUAL-IVA",
            "concept": "iva",
            "type": "tax",
            "base_amount": "100",
            "rate": value,
            "amount": value,
            "affects_document_total": True,
        }
    ]
    with fiscal_app.app_context():
        with pytest.raises(ValueError):
            calculate_document_total_with_taxes(document, Decimal("100"), [], tax_lines_payload=payload)


@pytest.mark.parametrize("value", NON_FINITE)
def test_preview_rejects_non_finite_amounts(fiscal_app, value):
    """The fiscal preview boundary rejects non-finite payload values."""
    with fiscal_app.app_context():
        with pytest.raises(ValueError):
            preview_decimal(value, default="0")


@pytest.mark.parametrize("value", NON_FINITE)
def test_tax_rule_service_rejects_non_finite_rate(fiscal_app, value):
    """A tax rule cannot be created with a non-finite rate or amount."""
    with fiscal_app.app_context():
        with pytest.raises(TaxRuleServiceError):
            rule_decimal(value, default="0")


@pytest.mark.parametrize("rate", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_fiscal_engine_reports_non_finite_rule_without_polluting_totals(rate):
    """A poisoned rule becomes a calculation error, not a non-finite total."""
    context = CalculationContext(
        company_id="alpha",
        document_type="sales_invoice",
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=date(2026, 5, 10),
        posting_date=date(2026, 5, 10),
        party_type="customer",
        party_id="CUSTOMER",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="line-1",
                item_id="item-1",
                description="Producto",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("100"),
                net_amount=Decimal("100"),
            )
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="RULE-1",
                name="Regla no finita",
                concept="iva",
                tax_type="tax",
                calculation_method="percentage",
                rate=rate,
            )
        ],
    )

    result = FiscalEngine().calculate(context)

    assert result.tax_lines == []
    assert result.errors
    for total in (
        result.net_goods_total,
        result.document_tax_total,
        result.capitalizable_tax_total,
        result.separate_tax_total,
        result.withholding_total,
    ):
        assert total.is_finite()
