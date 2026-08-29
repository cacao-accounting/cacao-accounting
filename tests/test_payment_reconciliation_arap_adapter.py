"""Contract tests for the payment-reconciliation AR/AP adapter."""

from decimal import Decimal
from types import SimpleNamespace

import pytest


def test_reconciliation_plan_converts_document_amount_to_payment_currency():
    """A USD bank payment can consume an EUR invoice through an explicit rate."""
    from cacao_accounting.document_flow.payment import _plan_reconciliation_allocation

    payment = SimpleNamespace(id="PAY-1", currency="USD")
    document = SimpleNamespace(transaction_currency="EUR")

    line = _plan_reconciliation_allocation(
        raw_line={"payment_exchange_rate": "1.25"},
        payment=payment,
        document=document,
        flow_source_type="sales_invoice",
        document_id="INV-EUR-1",
        outstanding=Decimal("100"),
        allocated=Decimal("80"),
        available=Decimal("100"),
    )

    assert line.document_amount == Decimal("80")
    assert line.document_currency == "EUR"
    assert line.source_amount == Decimal("100.0000")
    assert line.source_currency == "USD"
    assert line.rate == Decimal("1.25")


def test_reconciliation_plan_requires_rate_for_cross_currency_application():
    """Cross-currency reconciliation never guesses an exchange rate."""
    from cacao_accounting.document_flow.payment import _plan_reconciliation_allocation
    from cacao_accounting.document_flow.service import DocumentFlowError

    payment = SimpleNamespace(id="PAY-1", currency="USD")
    document = SimpleNamespace(transaction_currency="EUR")

    with pytest.raises(DocumentFlowError, match="tasa positiva"):
        _plan_reconciliation_allocation(
            raw_line={},
            payment=payment,
            document=document,
            flow_source_type="sales_invoice",
            document_id="INV-EUR-1",
            outstanding=Decimal("100"),
            allocated=Decimal("80"),
            available=Decimal("100"),
        )


def test_reconciliation_plan_preserves_same_currency_legacy_documents():
    """A legacy document without a snapshot remains allocatable one-to-one."""
    from cacao_accounting.document_flow.payment import _plan_reconciliation_allocation

    payment = SimpleNamespace(id="PAY-1", currency="NIO")
    document = SimpleNamespace(transaction_currency=None)

    line = _plan_reconciliation_allocation(
        raw_line={},
        payment=payment,
        document=document,
        flow_source_type="purchase_invoice",
        document_id="INV-LEGACY-1",
        outstanding=Decimal("75"),
        allocated=Decimal("50"),
        available=Decimal("50"),
    )

    assert line.document_currency == "NIO"
    assert line.source_amount == Decimal("50.0000")
