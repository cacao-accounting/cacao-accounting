# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests for Rule Resolver dynamic conditions."""

from decimal import Decimal
from datetime import date
from cacao_accounting.accounting_engine.common.context import TaxRuleContext, CalculationContext, AccountingReferences
from cacao_accounting.accounting_engine.fiscal.resolver import RuleResolver

def test_rule_date_validity():
    resolver = RuleResolver()
    rule = TaxRuleContext(
        rule_id="R1", name="Vat", concept="IVA",
        tax_type="tax", calculation_method="percentage",
        valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)
    )

    ctx_in = CalculationContext(
        company_id="C1", document_type="invoice", event_type="confirm",
        transaction_direction="sales", transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1), party_type="customer", party_id="P1",
        currency="NIO", company_currency="NIO",
        references=AccountingReferences()
    )

    ctx_out = CalculationContext(
        company_id="C1", document_type="invoice", event_type="confirm",
        transaction_direction="sales", transaction_date=date(2026, 1, 1),
        posting_date=date(2026, 1, 1), party_type="customer", party_id="P1",
        currency="NIO", company_currency="NIO",
        references=AccountingReferences()
    )

    assert len(resolver.resolve([], [], [], [rule], ctx_in)) == 1
    assert len(resolver.resolve([], [], [], [rule], ctx_out)) == 0

def test_rule_currency_validity():
    resolver = RuleResolver()
    rule = TaxRuleContext(
        rule_id="R1", name="Vat", concept="IVA",
        tax_type="tax", calculation_method="percentage",
        allowed_currencies=["USD"]
    )

    ctx_nio = CalculationContext(
        company_id="C1", document_type="invoice", event_type="confirm",
        transaction_direction="sales", transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1), party_type="customer", party_id="P1",
        currency="NIO", company_currency="NIO",
        references=AccountingReferences()
    )

    ctx_usd = CalculationContext(
        company_id="C1", document_type="invoice", event_type="confirm",
        transaction_direction="sales", transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1), party_type="customer", party_id="P1",
        currency="USD", company_currency="NIO",
        references=AccountingReferences()
    )

    assert len(resolver.resolve([], [], [], [rule], ctx_nio)) == 0
    assert len(resolver.resolve([], [], [], [rule], ctx_usd)) == 1
