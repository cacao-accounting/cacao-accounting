# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Reyes Reyes

"""Tests for Accounting Mapper."""

from datetime import date
from decimal import Decimal

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    FiscalLine,
    FiscalResult,
    ItemContext,
    SettlementLine,
    SettlementResult,
)
from cacao_accounting.accounting_engine.orchestrator.mapper import AccountingMapper


def test_basic_purchase_mapping():
    """A purchase invoice should debit goods/taxes and credit the supplier."""
    ctx = CalculationContext(
        company_id="C1",
        document_type="purchase_invoice",
        event_type="purchase_invoice_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="supplier",
        party_id="S1",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L1",
                item_id="I1",
                description="Item 1",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("100"),
                net_amount=Decimal("100"),
            )
        ],
        references=AccountingReferences(
            goods_account="1101",
            party_account="2101",
            default_tax_accounts={"IVA": "1102"},
        ),
    )

    fiscal = FiscalResult(
        tax_lines=[
            FiscalLine(
                line_id="T1",
                concept="IVA",
                type="tax",
                rate=Decimal("15"),
                calculation_method="percentage",
                base_amount=Decimal("100"),
                amount=Decimal("15"),
                recognition_event="invoice",
                accounting_treatment="separate",
                affects_inventory=False,
                affects_document_total=True,
                included_in_price=False,
                source_rule_id="R1",
                applies_to_items=["L1"],
                depends_on=[],
                participates_in_next_base=False,
            )
        ]
    )

    settlement = SettlementResult(gross_settlement_amount=Decimal("115"))

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, fiscal=fiscal, settlement=settlement)

    assert proforma.is_balanced
    assert len(proforma.lines) == 3
    assert sum(line.debit for line in proforma.lines) == Decimal("115")
    assert sum(line.credit for line in proforma.lines) == Decimal("115")
    assert all(line.transaction_currency == "NIO" for line in proforma.lines)
    assert all(line.company_currency == "NIO" for line in proforma.lines)


def test_payment_mapping_uses_bank_withholding_and_exchange_loss():
    """A supplier payment should map payable, bank, withholding and exchange loss."""
    ctx = CalculationContext(
        company_id="C1",
        document_type="payment_entry",
        event_type="payment_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="supplier",
        party_id="S1",
        currency="USD",
        company_currency="NIO",
        exchange_rate=Decimal("36.5"),
        references=AccountingReferences(
            party_account="2101",
            cash_account="1010",
            custom_references={
                "settlement_exchange_rate": Decimal("36.8"),
                "exchange_loss_account_id": "6901",
            },
        ),
    )
    settlement = SettlementResult(
        gross_settlement_amount=Decimal("100"),
        cash_amount=Decimal("98"),
        withholding_amount=Decimal("2"),
        exchange_difference=Decimal("-30"),
        settlement_lines=[
            SettlementLine(
                line_id="S1",
                concept="IR",
                type="withholding",
                base_amount=Decimal("100"),
                rate=Decimal("2"),
                amount=Decimal("2"),
                recognition_event="payment",
                accounting_treatment="withholding_payable",
                account_id="2150",
            )
        ],
    )

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, settlement=settlement)

    assert proforma.is_balanced
    assert sum(line.debit for line in proforma.lines) == Decimal("3680.00")
    assert sum(line.credit for line in proforma.lines) == Decimal("3680.00")
    payable_line = next(line for line in proforma.lines if line.account_id == "2101")
    bank_line = next(line for line in proforma.lines if line.account_id == "1010")
    withholding_line = next(line for line in proforma.lines if line.account_id == "2150")
    loss_line = next(line for line in proforma.lines if line.account_id == "6901")
    assert payable_line.debit == Decimal("3650.0")
    assert payable_line.amount_transaction_currency == Decimal("100")
    assert payable_line.exchange_rate_used == Decimal("36.5")
    assert bank_line.credit == Decimal("3606.4")
    assert bank_line.exchange_rate_used == Decimal("36.8")
    assert withholding_line.credit == Decimal("73.6")
    assert loss_line.debit == Decimal("30")
    assert loss_line.amount_transaction_currency == Decimal("0")


def test_collection_mapping_uses_bank_withholding_and_exchange_gain():
    """A customer collection should map bank, withholding receivable and exchange gain."""
    ctx = CalculationContext(
        company_id="C1",
        document_type="payment_entry",
        event_type="collection_confirmed",
        transaction_direction="sales",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="customer",
        party_id="C1",
        currency="USD",
        company_currency="NIO",
        exchange_rate=Decimal("36.5"),
        references=AccountingReferences(
            party_account="1105",
            cash_account="1010",
            custom_references={
                "settlement_exchange_rate": Decimal("36.8"),
                "exchange_gain_account_id": "4205",
            },
        ),
    )
    settlement = SettlementResult(
        gross_settlement_amount=Decimal("100"),
        cash_amount=Decimal("98"),
        withholding_amount=Decimal("2"),
        exchange_difference=Decimal("30"),
        settlement_lines=[
            SettlementLine(
                line_id="S1",
                concept="RET",
                type="withholding",
                base_amount=Decimal("100"),
                rate=Decimal("2"),
                amount=Decimal("2"),
                recognition_event="collection",
                accounting_treatment="withholding_receivable",
                account_id="1130",
            )
        ],
    )

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, settlement=settlement)

    assert proforma.is_balanced
    assert sum(line.debit for line in proforma.lines) == Decimal("3680.00")
    assert sum(line.credit for line in proforma.lines) == Decimal("3680.00")
    receivable_line = next(line for line in proforma.lines if line.account_id == "1105")
    bank_line = next(line for line in proforma.lines if line.account_id == "1010")
    withholding_line = next(line for line in proforma.lines if line.account_id == "1130")
    gain_line = next(line for line in proforma.lines if line.account_id == "4205")
    assert receivable_line.credit == Decimal("3650.0")
    assert bank_line.debit == Decimal("3606.4")
    assert withholding_line.debit == Decimal("73.6")
    assert gain_line.credit == Decimal("30")


def test_collection_mapping_includes_discount_and_unrealized_revaluation():
    """Collections should map discounts plus the unrealized revaluation offset."""
    ctx = CalculationContext(
        company_id="C1",
        document_type="payment_entry",
        event_type="collection_confirmed",
        transaction_direction="sales",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="customer",
        party_id="C1",
        currency="USD",
        company_currency="NIO",
        exchange_rate=Decimal("36.5"),
        references=AccountingReferences(
            party_account="1105",
            cash_account="1010",
            custom_references={
                "settlement_exchange_rate": Decimal("36.8"),
                "payment_discount_account_id": "5105",
                "unrealized_exchange_gain_account_id": "4206",
            },
        ),
    )
    settlement = SettlementResult(
        gross_settlement_amount=Decimal("100"),
        cash_amount=Decimal("98"),
        payment_discount_amount=Decimal("2"),
        exchange_difference=Decimal("30"),
        unrealized_exchange_difference=Decimal("30"),
        settlement_lines=[],
    )

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, settlement=settlement)

    assert proforma.is_balanced
    discount_line = next(line for line in proforma.lines if line.account_id == "5105")
    unrealized_line = next(line for line in proforma.lines if line.account_id == "4206")
    unrealized_offset = next(
        line for line in proforma.lines if line.account_id == "1105" and line.description.startswith("Unrealized")
    )
    assert discount_line.debit == Decimal("73.6")
    assert unrealized_line.credit == Decimal("30")
    assert unrealized_offset.debit == Decimal("30")
