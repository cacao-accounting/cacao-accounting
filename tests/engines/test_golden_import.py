# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Golden Test for the import reference case."""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.accounting_engine.landed_cost.engine import LandedCostEngine


def test_golden_import_case():
    """
    Reference Case:
    Mercadería: 1000.00
    DAI 5% sobre mercadería = 50.00
    Subtotal acumulado = 1050.00
    ISC 3% sobre mercadería + DAI = 31.50
    Subtotal acumulado = 1081.50
    IVA 15% sobre mercadería + DAI + ISC = 162.23 (rounded from 162.225)

    Expected results:
    DAI = 50.00
    ISC = 31.50
    IVA = 162.23
    Costo inventariable = 1081.50
    Total factura = 1243.73
    """

    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="purchase_invoice_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="USD",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L001",
                item_id="ITEM-001",
                description="Mercadería",
                quantity=Decimal("10"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("1000"),
                net_amount=Decimal("1000"),
            )
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R001",
                name="DAI 5%",
                concept="DAI",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("5"),
                base_mode="goods",
                order=1,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R002",
                name="ISC 3%",
                concept="ISC",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("3"),
                base_mode="accumulated",
                include_concepts=["goods", "DAI"],
                order=2,
                accounting_treatment="capitalizable_inventory_cost",
                participates_in_next_base=True,
            ),
            TaxRuleContext(
                rule_id="R003",
                name="IVA 15%",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                base_mode="accumulated",
                include_concepts=["goods", "DAI", "ISC"],
                order=3,
                accounting_treatment="separate_tax_account",
                participates_in_next_base=False,
            ),
        ],
    )

    fiscal_engine = FiscalEngine()
    fiscal_result = fiscal_engine.calculate(context)

    dai = fiscal_result.get_amount("DAI")
    isc = fiscal_result.get_amount("ISC")
    iva = fiscal_result.get_amount("IVA")

    assert dai.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("50.00")
    assert isc.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("31.50")
    assert iva.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("162.23")

    landed_cost_engine = LandedCostEngine()
    capitalizable_lines = [l for l in fiscal_result.tax_lines if l.accounting_treatment == "capitalizable_inventory_cost"]
    landed_cost_result = landed_cost_engine.calculate(context.items, capitalizable_lines)

    assert landed_cost_result.inventory_value_total.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("1081.50")
    total_factura = context.items[0].net_amount + dai + isc + iva
    assert total_factura.quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("1243.73")


if __name__ == "__main__":
    test_golden_import_case()
    print("Golden test passed!")
