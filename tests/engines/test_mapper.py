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


def test_payment_mapping_allows_a_fully_withheld_settlement_without_a_bank_line():
    """A zero-cash payment settles the party balance solely through withholding."""
    ctx = CalculationContext(
        company_id="C1",
        document_type="payment_entry",
        event_type="payment_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="supplier",
        party_id="S1",
        currency="NIO",
        company_currency="NIO",
        references=AccountingReferences(party_account="2101", cash_account="1010"),
    )
    settlement = SettlementResult(
        gross_settlement_amount=Decimal("100"),
        cash_amount=Decimal("0"),
        withholding_amount=Decimal("100"),
        settlement_lines=[
            SettlementLine(
                line_id="S1",
                concept="IR",
                type="withholding",
                base_amount=Decimal("100"),
                rate=Decimal("100"),
                amount=Decimal("100"),
                recognition_event="payment",
                accounting_treatment="withholding_payable",
                account_id="2150",
            )
        ],
    )

    proforma = AccountingMapper().map_to_proforma(ctx, settlement=settlement)

    assert proforma.is_balanced
    assert {line.account_id for line in proforma.lines} == {"2101", "2150"}
    assert all(line.account_id != "1010" for line in proforma.lines)


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
                "sales_discount_account_id": "5105",
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


def test_supplier_refund_mapping_reverses_exchange():
    """A supplier refund with carrying value 3600 (AP 100 USD @ 36.0) and cash receipt of 3700 (100 USD @ 37.0)

    should produce a credit of 3600, debit of 3700, and a 100 credit to exchange gain.
    """
    ctx = CalculationContext(
        company_id="C1",
        document_type="payment_entry",
        event_type="refund_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="supplier",
        party_id="S1",
        currency="USD",
        company_currency="NIO",
        exchange_rate=Decimal("36.0"),
        references=AccountingReferences(
            party_account="2101",
            cash_account="1010",
            custom_references={
                "settlement_exchange_rate": Decimal("37.0"),
                "exchange_gain_account_id": "4205",
                "exchange_loss_account_id": "6901",
            },
        ),
    )
    settlement = SettlementResult(
        gross_settlement_amount=Decimal("100"),
        cash_amount=Decimal("100"),
        exchange_difference=Decimal("-100"),  # Normal settlement difference would be loss, but reversed it's a gain of 100
    )

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, settlement=settlement)

    assert proforma.is_balanced
    assert sum(line.debit for line in proforma.lines) == Decimal("3700.00")
    assert sum(line.credit for line in proforma.lines) == Decimal("3700.00")

    payable_line = next(line for line in proforma.lines if line.account_id == "2101")
    bank_line = next(line for line in proforma.lines if line.account_id == "1010")
    gain_line = next(line for line in proforma.lines if line.account_id == "4205")

    assert payable_line.credit == Decimal("3600.0")
    assert bank_line.debit == Decimal("3700.0")
    assert gain_line.credit == Decimal("100.0")


def _invoice_like_context(
    *,
    direction: str,
    event_type: str,
    document_type: str,
    is_credit_note: bool,
) -> CalculationContext:
    """Construye un contexto invoice-like con una linea de bienes y cuenta de impuesto."""
    goods_account = "1101" if direction == "purchase" else "4101"
    goods_side = "debit" if direction == "purchase" else "credit"
    if is_credit_note:
        goods_side = "credit" if direction == "purchase" else "debit"
    return CalculationContext(
        company_id="C1",
        document_type=document_type,
        event_type=event_type,
        transaction_direction=direction,
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="supplier" if direction == "purchase" else "customer",
        party_id="P1",
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
            goods_account=goods_account,
            party_account="2101" if direction == "purchase" else "1105",
            default_tax_accounts={"IVA": "1102"},
            custom_references={
                "account_lines": [
                    {
                        "account_id": goods_account,
                        "amount": "100.00",
                        "side": goods_side,
                        "description": document_type,
                    }
                ]
            },
        ),
    )


def _fiscal_tax_line(base: Decimal, rate: Decimal) -> FiscalResult:
    """Construye un resultado fiscal tipo IVA puro para pruebas del mapper."""
    return FiscalResult(
        tax_lines=[
            FiscalLine(
                line_id="T1",
                concept="IVA",
                type="tax",
                rate=rate,
                calculation_method="percentage",
                base_amount=base,
                amount=base * rate / Decimal("100"),
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


def test_purchase_credit_note_reverses_vat_side():
    """Una nota de credito de compra debe acreditar el IVA (no debitarlo).

    Refs: #786. La linea fiscal del engine no invertia el lado en notas de
    credito: acreditaba el gasto pero mantenia el IVA debitado, dejando AP e
    IVA desbalanceados en el GL.
    """
    ctx = _invoice_like_context(
        direction="purchase",
        event_type="purchase_credit_note_confirmed",
        document_type="purchase_credit_note",
        is_credit_note=True,
    )
    fiscal = _fiscal_tax_line(Decimal("100"), Decimal("15"))

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, fiscal=fiscal)

    vat_line = next(line for line in proforma.lines if line.account_id == "1102")
    party_line = next(line for line in proforma.lines if line.account_id == "2101")

    assert vat_line.credit == Decimal("15.0000")
    assert vat_line.debit == Decimal("0")
    assert proforma.is_balanced
    assert party_line.debit == Decimal("115.0000")
    assert party_line.credit == Decimal("0")


def test_sales_credit_note_reverses_vat_side():
    """Una nota de credito de venta debe debitar el IVA (no acreditarlo).

    Refs: #785. La linea fiscal del engine no invertia el lado en notas de
    credito: debitaba el ingreso pero acreditaba el IVA, dejando AR reducido
    de menos y un IVA por pagar inexistente.
    """
    ctx = _invoice_like_context(
        direction="sales",
        event_type="sales_credit_note_confirmed",
        document_type="sales_credit_note",
        is_credit_note=True,
    )
    fiscal = _fiscal_tax_line(Decimal("100"), Decimal("15"))

    mapper = AccountingMapper()
    proforma = mapper.map_to_proforma(ctx, fiscal=fiscal)

    vat_line = next(line for line in proforma.lines if line.account_id == "1102")
    party_line = next(line for line in proforma.lines if line.account_id == "1105")

    assert vat_line.debit == Decimal("15.0000")
    assert vat_line.credit == Decimal("0")
    assert proforma.is_balanced
    assert party_line.credit == Decimal("115.0000")
    assert party_line.debit == Decimal("0")
