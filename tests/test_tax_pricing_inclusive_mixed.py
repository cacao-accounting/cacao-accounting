# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1026: los impuestos inclusivos y aditivos respetan su base configurada."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.database import Tax, TaxTemplate, TaxTemplateItem, database
from cacao_accounting.tax_pricing_service import TaxPricingError, calculate_taxes


def _legacy_template(items: list[tuple[str, str, bool, str]], suffix: str) -> str:
    """Create an isolated sales template from (tax type, rate, inclusive, base) tuples."""
    template = TaxTemplate(
        name=f"Plantilla mixta {suffix}",
        company="cacao",
        template_type="selling",
        currency="NIO",
        is_active=True,
    )
    database.session.add(template)
    database.session.flush()
    for sequence, (tax_type, rate, inclusive, calculation_base) in enumerate(items, start=1):
        tax_id = f"TAX-1026-{suffix}-{sequence}"
        database.session.add(
            Tax(
                id=tax_id,
                name=f"Impuesto {sequence}",
                rate=Decimal(rate),
                tax_type=tax_type,
                applies_to="sales",
                is_active=True,
            )
        )
        database.session.add(
            TaxTemplateItem(
                tax_template_id=template.id,
                tax_id=tax_id,
                sequence=sequence * 10,
                calculation_base=calculation_base,
                behavior="additive",
                is_inclusive=inclusive,
            )
        )
    database.session.flush()
    return template.id


def _document(displayed_total: str) -> SimpleNamespace:
    """Create a minimal legacy document with its user-entered item price."""
    return SimpleNamespace(
        company="cacao",
        _tax_items=[SimpleNamespace(amount=Decimal(displayed_total))],
    )


@pytest.mark.parametrize("inclusive_first", [True, False])
def test_legacy_aditivo_net_document_usa_precio_neto_tras_extraer_inclusivo(entorno_contable_aislado, inclusive_first):
    """A 10% additive charge uses 100 net from the displayed 115 including 15% VAT."""
    with entorno_contable_aislado.app.app_context():
        taxes = [("percentage", "15", True, "net_document"), ("percentage", "10", False, "net_document")]
        if not inclusive_first:
            taxes.reverse()
        template_id = _legacy_template(taxes, uuid4().hex[:8])

        result = calculate_taxes(_document("115"), template_id)

        assert {line.is_inclusive: line.amount for line in result.lines} == {
            True: Decimal("15.0000"),
            False: Decimal("10.0000"),
        }
        assert result.inclusive_total == Decimal("15.0000")
        assert result.additive_total == Decimal("10.0000")
        assert result.payable_delta == Decimal("10.0000")


@pytest.mark.parametrize(
    ("rates", "expected"),
    [
        (["10", "5"], [Decimal("8.6580"), Decimal("4.7619")]),
        (["5", "10"], [Decimal("4.3290"), Decimal("9.0909")]),
    ],
)
def test_legacy_inclusivos_previous_total_respetan_orden_y_redondeo(entorno_contable_aislado, rates, expected):
    """Sequential included percentages are decomposed in reverse sequence."""
    with entorno_contable_aislado.app.app_context():
        template_id = _legacy_template(
            [("percentage", rate, True, "previous_total") for rate in rates],
            uuid4().hex[:8],
        )

        result = calculate_taxes(_document("100"), template_id)

        assert [line.amount for line in result.lines] == expected
        assert result.inclusive_total == sum(expected, Decimal("0"))
        assert Decimal("100") - result.inclusive_total == Decimal("86.5801")


def test_legacy_inclusivos_previous_total_reconstruyen_impuesto_fijo(entorno_contable_aislado):
    """A fixed included charge precedes and contributes to a sequential percentage base."""
    with entorno_contable_aislado.app.app_context():
        template_id = _legacy_template(
            [("fixed", "10", True, "previous_total"), ("percentage", "10", True, "previous_total")],
            uuid4().hex[:8],
        )

        result = calculate_taxes(_document("121"), template_id)

        assert [line.amount for line in result.lines] == [Decimal("10.0000"), Decimal("11.0000")]
        assert result.inclusive_total == Decimal("21.0000")


def test_legacy_inclusivos_net_document_comparten_base_independiente_del_orden(entorno_contable_aislado):
    """Two included rates decompose gross 130 into net 100 and taxes 10 and 20."""
    with entorno_contable_aislado.app.app_context():
        taxes = [
            ("percentage", "10", True, "net_document"),
            ("percentage", "20", True, "net_document"),
            ("percentage", "10", False, "net_document"),
        ]
        template_id = _legacy_template(taxes, uuid4().hex[:8])

        result = calculate_taxes(_document("130"), template_id)

        assert [line.amount for line in result.lines] == [
            Decimal("10.0000"),
            Decimal("20.0000"),
            Decimal("10.0000"),
        ]
        assert result.inclusive_total == Decimal("30.0000")
        assert result.additive_total == Decimal("10.0000")

        reversed_template_id = _legacy_template([taxes[1], taxes[0], taxes[2]], uuid4().hex[:8])
        reversed_result = calculate_taxes(_document("130"), reversed_template_id)
        assert [line.amount for line in reversed_result.lines] == [
            Decimal("20.0000"),
            Decimal("10.0000"),
            Decimal("10.0000"),
        ]
        assert reversed_result.inclusive_total == result.inclusive_total
        assert reversed_result.additive_total == result.additive_total


def test_legacy_rechaza_base_cero_al_descomponer_impuesto_inclusivo(entorno_contable_aislado):
    """A rate that makes sequential inclusive reconstruction singular fails clearly."""
    with entorno_contable_aislado.app.app_context():
        template_id = _legacy_template(
            [("percentage", "-100", True, "previous_total")],
            uuid4().hex[:8],
        )

        with pytest.raises(TaxPricingError, match="base nula o negativa"):
            calculate_taxes(_document("100"), template_id)


def test_fiscal_engine_mixed_taxes_use_shared_inclusive_base_and_reconstructed_net():
    """Two included rules share gross 130; the additive rule uses the resulting net 100."""
    item = ItemContext(
        line_id="line-1",
        item_id="item-1",
        description="Producto gravado",
        quantity=Decimal("1"),
        unit_price=Decimal("130"),
        gross_amount=Decimal("130"),
        net_amount=Decimal("130"),
    )
    rules = [
        TaxRuleContext(
            rule_id="included-10",
            name="IVA incluido 10%",
            concept="iva_a",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("10"),
            base_mode="accumulated",
            include_concepts=["goods"],
            order=10,
            included_in_price=True,
        ),
        TaxRuleContext(
            rule_id="included-20",
            name="IVA incluido 20%",
            concept="iva_b",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("20"),
            base_mode="accumulated",
            include_concepts=["goods"],
            order=20,
            included_in_price=True,
        ),
        TaxRuleContext(
            rule_id="additive-10",
            name="Cargo aditivo 10%",
            concept="servicio",
            tax_type="charge",
            calculation_method="percentage",
            rate=Decimal("10"),
            base_mode="goods",
            order=30,
        ),
    ]
    context = CalculationContext(
        company_id="cacao",
        document_type="sales_invoice",
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=None,
        posting_date=None,
        party_type="customer",
        party_id="customer-1",
        currency="NIO",
        company_currency="NIO",
        items=[item],
        tax_rules=rules,
        references=AccountingReferences(),
    )

    result = FiscalEngine().calculate(context)

    assert result.errors == []
    amounts = {line.source_rule_id: line.amount for line in result.tax_lines}
    bases = {line.source_rule_id: line.base_amount for line in result.tax_lines}
    assert amounts == {"included-10": Decimal("10.00"), "included-20": Decimal("20.00"), "additive-10": Decimal("10.00")}
    assert bases == {"included-10": Decimal("130"), "included-20": Decimal("130"), "additive-10": Decimal("100")}
    assert result.net_goods_total == Decimal("100")
    assert result.document_tax_total == Decimal("10.00")

    reordered_rules = [replace(rules[1], order=10), replace(rules[0], order=20), rules[2]]
    reordered_result = FiscalEngine().calculate(replace(context, tax_rules=reordered_rules))
    reordered_amounts = {line.source_rule_id: line.amount for line in reordered_result.tax_lines}
    assert reordered_amounts == amounts
