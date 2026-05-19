# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Additional robust test cases for imports and complex scenarios."""

import pytest
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator


@pytest.fixture
def orchestrator():
    return BusinessEventOrchestrator()


def test_import_landed_cost_three_items_by_value(orchestrator):
    """
    Caso 1: importación con 3 ítems, prorrateo por valor.
    Ítem A: 500.00, Ítem B: 600.00, Ítem C: 400.00. Total FOB: 1500.00.
    Flete: 180, Seguro: 45, Aduana: 75, Transporte: 120. Total Capitalizable Base: 420.00.
    DAI: 5%, ISC: 3%, IVA: 15%.
    """
    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="import_landed_cost_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="USD",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="A",
                item_id="I1",
                description="A",
                quantity=Decimal("10"),
                unit_price=Decimal("50"),
                gross_amount=Decimal("500"),
                net_amount=Decimal("500"),
            ),
            ItemContext(
                line_id="B",
                item_id="I2",
                description="B",
                quantity=Decimal("5"),
                unit_price=Decimal("120"),
                gross_amount=Decimal("600"),
                net_amount=Decimal("600"),
            ),
            ItemContext(
                line_id="C",
                item_id="I3",
                description="C",
                quantity=Decimal("20"),
                unit_price=Decimal("20"),
                gross_amount=Decimal("400"),
                net_amount=Decimal("400"),
            ),
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R1",
                name="Flete",
                concept="Flete",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("180"),
                order=1,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R2",
                name="Seguro",
                concept="Seguro",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("45"),
                order=2,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R3",
                name="Aduana",
                concept="Aduana",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("75"),
                order=3,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R4",
                name="Transporte",
                concept="Transporte",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("120"),
                order=4,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R5",
                name="DAI",
                concept="DAI",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("5"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "Transporte"],
                order=5,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R6",
                name="ISC",
                concept="ISC",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("3"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "Transporte", "DAI"],
                order=6,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R7",
                name="IVA",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "Transporte", "DAI", "ISC"],
                order=7,
                accounting_treatment="separate_tax_account",
            ),
        ],
    )

    results = orchestrator.handle_event(context)
    fiscal = results["fiscal"]
    lc = results["landed_cost"]

    assert fiscal.get_amount("DAI").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("96.00")
    assert fiscal.get_amount("ISC").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("60.48")
    assert fiscal.get_amount("IVA").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("311.47")

    assert lc.inventory_value_total.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("2076.48")

    # Check individual allocations (allowing for small rounding differences in 4th decimal)
    assert lc.get_allocation("A").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("692.16")
    assert lc.get_allocation("B").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("830.59")
    assert lc.get_allocation("C").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("553.73")


def test_import_with_non_capitalizable_local_transport(orchestrator):
    """
    Caso 2: importación con 4 ítems, transporte local no capitalizable.
    Transporte local: gasto separado, no capitalizable.
    """
    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="import_landed_cost_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="USD",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="A",
                item_id="I1",
                description="A",
                quantity=Decimal("100"),
                unit_price=Decimal("8"),
                gross_amount=Decimal("800"),
                net_amount=Decimal("800"),
            ),
            ItemContext(
                line_id="B",
                item_id="I2",
                description="B",
                quantity=Decimal("50"),
                unit_price=Decimal("12"),
                gross_amount=Decimal("600"),
                net_amount=Decimal("600"),
            ),
            ItemContext(
                line_id="C",
                item_id="I3",
                description="C",
                quantity=Decimal("30"),
                unit_price=Decimal("20"),
                gross_amount=Decimal("600"),
                net_amount=Decimal("600"),
            ),
            ItemContext(
                line_id="D",
                item_id="I4",
                description="D",
                quantity=Decimal("10"),
                unit_price=Decimal("50"),
                gross_amount=Decimal("500"),
                net_amount=Decimal("500"),
            ),
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R1",
                name="Flete",
                concept="Flete",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("250"),
                order=1,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R2",
                name="Seguro",
                concept="Seguro",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("100"),
                order=2,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R3",
                name="Aduana",
                concept="Aduana",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("150"),
                order=3,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R4",
                name="DAI",
                concept="DAI",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("10"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana"],
                order=4,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R5",
                name="ISC",
                concept="ISC",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("5"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "DAI"],
                order=5,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R6",
                name="Transporte",
                concept="Transporte",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("200"),
                order=6,
                accounting_treatment="separate_expense_account",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R7",
                name="IVA",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "DAI", "ISC", "Transporte"],
                order=7,
                accounting_treatment="separate_tax_account",
            ),
        ],
    )

    results = orchestrator.handle_event(context)
    fiscal = results["fiscal"]
    lc = results["landed_cost"]

    assert fiscal.get_amount("DAI") == Decimal("300.00")
    assert fiscal.get_amount("ISC") == Decimal("165.00")
    assert fiscal.get_amount("IVA").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("549.75")
    assert fiscal.get_amount("Transporte") == Decimal("200.00")

    assert lc.inventory_value_total == Decimal("3465.00")

    assert lc.get_allocation("A").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("1108.80")
    assert lc.get_allocation("B").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("831.60")
    assert lc.get_allocation("C").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("831.60")
    assert lc.get_allocation("D").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("693.00")


def test_import_with_mixed_allocation_methods_by_weight_and_value(orchestrator):
    """
    Caso 3: importación con flete fijo, seguro porcentual y prorrateo por peso.
    Flete (400) prorrateado por PESO.
    Seguro (40) prorrateado por VALOR.
    Aduana (100) prorrateado por VALOR.
    """
    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="import_landed_cost_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="USD",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="A",
                item_id="I1",
                description="A",
                quantity=Decimal("1"),
                unit_price=Decimal("1000"),
                gross_amount=Decimal("1000"),
                net_amount=Decimal("1000"),
                weight=Decimal("100"),
            ),
            ItemContext(
                line_id="B",
                item_id="I2",
                description="B",
                quantity=Decimal("1"),
                unit_price=Decimal("500"),
                gross_amount=Decimal("500"),
                net_amount=Decimal("500"),
                weight=Decimal("300"),
            ),
            ItemContext(
                line_id="C",
                item_id="I3",
                description="C",
                quantity=Decimal("1"),
                unit_price=Decimal("500"),
                gross_amount=Decimal("500"),
                net_amount=Decimal("500"),
                weight=Decimal("100"),
            ),
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R1",
                name="Flete",
                concept="Flete",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("400"),
                order=1,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
                allocation_method="by_weight",
            ),
            TaxRuleContext(
                rule_id="R2",
                name="Seguro",
                concept="Seguro",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("40"),
                order=2,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
                allocation_method="by_value",
            ),
            TaxRuleContext(
                rule_id="R3",
                name="Aduana",
                concept="Aduana",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("100"),
                order=3,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
                allocation_method="by_value",
            ),
            TaxRuleContext(
                rule_id="R4",
                name="DAI",
                concept="DAI",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("5"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana"],
                order=4,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
                allocation_method="by_current_value",
            ),
            TaxRuleContext(
                rule_id="R5",
                name="ISC",
                concept="ISC",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("3"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "DAI"],
                order=5,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
                allocation_method="by_current_value",
            ),
            TaxRuleContext(
                rule_id="R6",
                name="IVA",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                base_mode="accumulated",
                include_concepts=["goods", "Flete", "Seguro", "Aduana", "DAI", "ISC"],
                order=6,
                accounting_treatment="separate_tax_account",
            ),
        ],
    )

    results = orchestrator.handle_event(context)
    fiscal = results["fiscal"]
    lc = results["landed_cost"]

    assert fiscal.get_amount("DAI").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("127.00")
    assert fiscal.get_amount("ISC").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("80.01")
    assert fiscal.get_amount("IVA").quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("412.05")

    assert lc.inventory_value_total.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("2747.01")

    # Costo final esperado:
    # A: 1243.73
    # B: 838.16
    # C: 665.12
    assert lc.get_allocation("A").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("1243.73")
    assert lc.get_allocation("B").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("838.16")
    assert lc.get_allocation("C").final_inventory_cost.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("665.12")


def test_vat_is_excluded_from_inventory_cost(orchestrator):
    """Caso 4: Validar que IVA no se capitaliza."""
    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="purchase_invoice_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="A",
                item_id="I1",
                description="A",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("100"),
                net_amount=Decimal("100"),
            )
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R1",
                name="IVA",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                order=1,
                accounting_treatment="separate_tax_account",
            )
        ],
    )
    results = orchestrator.handle_event(context)
    assert results["fiscal"].get_amount("IVA") == Decimal("15.00")
    assert results["landed_cost"].inventory_value_total == Decimal("100.00")
    assert results["landed_cost"].inventory_value_total < (Decimal("100") + results["fiscal"].document_tax_total)
