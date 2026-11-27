# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1353: condición fiscal por categoría de artículo evaluada por línea.

El motor calcula la base de una regla restringida solo sobre las líneas cuyos
artículos pertenecen a una categoría permitida; un artículo sin categoría no
coincide. La restricción viaja en el snapshot fiscal para eventos posteriores.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.database import Item, ItemCategory, TaxRule, UOM, database
from cacao_accounting.fiscal_persistence_service import (
    build_tax_rule_contexts_from_snapshot,
    load_document_fiscal_lines,
    persist_document_fiscal_snapshot,
)
from cacao_accounting.tax_rule_service import build_tax_rule_contexts, create_tax_rule


def _item(line_id: str, amount: str, category: str | None) -> ItemContext:
    """Build one item line with an optional catalog category."""
    return ItemContext(
        line_id=line_id,
        item_id=f"ITEM-{line_id}",
        description=f"Línea {line_id}",
        quantity=Decimal("1"),
        unit_price=Decimal(amount),
        gross_amount=Decimal(amount),
        net_amount=Decimal(amount),
        item_category=category,
    )


def _context(items: list[ItemContext], rules: list[TaxRuleContext]) -> CalculationContext:
    """Build the minimal engine calculation context."""
    return CalculationContext(
        company_id="cacao",
        document_type="sales_invoice",
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=date(2026, 5, 10),
        posting_date=date(2026, 5, 10),
        party_type="customer",
        party_id="CUSTOMER",
        currency="NIO",
        company_currency="NIO",
        items=items,
        tax_rules=rules,
        references=AccountingReferences(),
    )


def _rule(**overrides) -> TaxRuleContext:
    """Build a percentage rule with optional category restriction."""
    values = {
        "rule_id": f"RULE-{uuid4().hex[:6]}",
        "name": "IVA restringido",
        "concept": "iva",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "rate": Decimal("10"),
        "base_mode": "goods",
    }
    values.update(overrides)
    return TaxRuleContext(**values)


def test_restricted_rule_uses_only_matching_lines_as_base():
    """A 10% rule restricted to category A taxes 100, not the whole 150."""
    result = FiscalEngine().calculate(
        _context([_item("A", "100", "cat-a"), _item("B", "50", "cat-b")], [_rule(allowed_item_categories=["cat-a"])])
    )

    assert result.errors == []
    assert len(result.tax_lines) == 1
    line = result.tax_lines[0]
    assert line.base_amount == Decimal("100")
    assert line.amount == Decimal("10")
    assert line.applies_to_items == ["A"]


def test_unrestricted_rule_keeps_the_document_base():
    """A rule without categories still taxes the full goods total."""
    result = FiscalEngine().calculate(_context([_item("A", "100", "cat-a"), _item("B", "50", "cat-b")], [_rule()]))

    assert result.errors == []
    line = result.tax_lines[0]
    assert line.base_amount == Decimal("150")
    assert line.amount == Decimal("15")
    assert line.applies_to_items == ["A", "B"]


def test_accumulated_rule_applies_exclusions_without_inclusions():
    """An accumulated rule starts from goods when it only excludes concepts."""
    rules = [
        _rule(rule_id="IVA", concept="iva", rate=Decimal("10"), participates_in_next_base=True),
        _rule(
            rule_id="TASA-POSTERIOR",
            concept="tasa_posterior",
            rate=Decimal("5"),
            base_mode="accumulated",
            exclude_concepts=["iva"],
            order=2,
        ),
    ]

    result = FiscalEngine().calculate(_context([_item("A", "100", "cat-a")], rules))

    assert result.errors == []
    assert [line.base_amount for line in result.tax_lines] == [Decimal("100"), Decimal("90")]
    assert [line.amount for line in result.tax_lines] == [Decimal("10"), Decimal("4.5")]


def test_accumulated_rule_counts_each_included_and_excluded_concept_once():
    """Repeated concept names do not multiply an accumulated tax base."""
    rules = [
        _rule(rule_id="IVA", concept="iva", rate=Decimal("10"), participates_in_next_base=True),
        _rule(
            rule_id="TASA-POSTERIOR",
            concept="tasa_posterior",
            rate=Decimal("10"),
            base_mode="accumulated",
            include_concepts=["goods", "goods"],
            exclude_concepts=["iva", "iva"],
            order=2,
        ),
    ]

    result = FiscalEngine().calculate(_context([_item("A", "100", "cat-a")], rules))

    assert result.errors == []
    assert [line.base_amount for line in result.tax_lines] == [Decimal("100"), Decimal("90")]
    assert [line.amount for line in result.tax_lines] == [Decimal("10"), Decimal("9")]


def test_item_without_category_does_not_match_a_restricted_rule():
    """Uncategorized items never satisfy a category condition."""
    result = FiscalEngine().calculate(
        _context([_item("A", "100", None), _item("B", "50", "cat-b")], [_rule(allowed_item_categories=["cat-b"])])
    )

    assert result.errors == []
    line = result.tax_lines[0]
    assert line.base_amount == Decimal("50")
    assert line.amount == Decimal("5")
    assert line.applies_to_items == ["B"]


def test_restricted_rule_without_matching_lines_emits_zero_line():
    """No matching lines yield a zero fiscal line instead of silently disappearing."""
    result = FiscalEngine().calculate(_context([_item("A", "100", "cat-a")], [_rule(allowed_item_categories=["cat-other"])]))

    assert result.errors == []
    assert len(result.tax_lines) == 1
    line = result.tax_lines[0]
    assert line.base_amount == Decimal("0")
    assert line.amount == Decimal("0")
    assert line.applies_to_items == []


def test_multiple_categories_are_supported():
    """A rule may allow more than one catalog category."""
    result = FiscalEngine().calculate(
        _context(
            [_item("A", "100", "cat-a"), _item("B", "50", "cat-b"), _item("C", "20", "cat-c")],
            [_rule(allowed_item_categories=["cat-a", "cat-b"], rate=Decimal("10"))],
        )
    )

    assert result.errors == []
    line = result.tax_lines[0]
    assert line.base_amount == Decimal("150")
    assert line.amount == Decimal("15")
    assert line.applies_to_items == ["A", "B"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"participates_in_next_base": True},
        {"included_in_price": True},
        {"base_mode": "accumulated", "include_concepts": ["goods"]},
    ],
)
def test_restricted_rules_cannot_fragment_the_document_base(overrides):
    """Fail-closed: restricted rules cannot cascade or decompose included taxes."""
    engine = FiscalEngine()
    result = engine.calculate(_context([_item("A", "100", "cat-a")], [_rule(allowed_item_categories=["cat-a"], **overrides)]))

    assert result.errors
    assert result.tax_lines == []
    assert "categorías de artículo permitidas" in result.errors[0]


@pytest.fixture
def persisted_rule(app):
    """Create a real category, item, and restricted tax rule."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        category = ItemCategory(name=f"Insumos-{suffix}", is_active=True)
        uom = UOM(code=f"EA{suffix}"[:20], name="Unidad", is_active=True)
        database.session.add_all([category, uom])
        database.session.flush()
        item = Item(
            code=f"ITEM-CAT-{suffix}",
            name="Artículo categorizado",
            item_type="goods",
            is_stock_item=False,
            item_category_id=category.id,
            default_uom=uom.code,
        )
        database.session.add(item)
        database.session.commit()
        rule = create_tax_rule(
            {
                "name": f"IVA insumos {suffix}",
                "concept": "iva",
                "applies_to": "both",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "15",
                "base_mode": "goods",
                "recognition_event": "invoice",
                "allowed_item_categories": category.id,
                "is_active": "on",
            }
        )
        database.session.commit()
        ids = {"category": category.id, "item": item.code, "rule": rule.id}
    return ids


def test_snapshot_preserves_the_restriction_and_restricted_base(app, persisted_rule):
    """Persisted evidence keeps the category condition and the subset base."""
    with app.app_context():
        context = next(
            rule
            for rule in build_tax_rule_contexts(company=None, applies_to="sales", currency=None)
            if rule.rule_id == persisted_rule["rule"]
        )
        assert context.allowed_item_categories == [persisted_rule["category"]]

        document_id = f"INV-{uuid4().hex[:8]}"
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=document_id,
            currency="NIO",
            tax_lines=[
                {
                    "source_rule_id": persisted_rule["rule"],
                    "concept": "iva",
                    "format": "percentage",
                    "rate": "15",
                    "amount": "15.00",
                }
            ],
            tax_summary={"subtotal": "115", "grand_total": "115"},
            server_subtotal=Decimal("115"),
            category_subtotals={persisted_rule["category"]: Decimal("100")},
        )
        database.session.commit()

        rows = load_document_fiscal_lines(document_type="sales_invoice", document_id=document_id)
        assert len(rows) == 1
        assert rows[0].base_amount == Decimal("100.0000")

        restored = build_tax_rule_contexts_from_snapshot(
            document_type="sales_invoice",
            document_id=document_id,
            recognition_event="settlement",
        )
        assert restored[0].allowed_item_categories == [persisted_rule["category"]]


def test_snapshot_without_category_totals_keeps_the_engine_base(app, persisted_rule):
    """Payment-style events without item data keep the engine-reported base."""
    with app.app_context():
        document_id = f"PAY-{uuid4().hex[:8]}"
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="payment_entry",
            document_id=document_id,
            currency="NIO",
            tax_lines=[
                {
                    "source_rule_id": persisted_rule["rule"],
                    "concept": "iva",
                    "format": "percentage",
                    "rate": "15",
                    "base_amount": "100",
                    "amount": "15.00",
                }
            ],
            tax_summary={"subtotal": "115", "grand_total": "115"},
        )
        database.session.commit()

        rows = load_document_fiscal_lines(document_type="payment_entry", document_id=document_id)
        assert len(rows) == 1
        assert rows[0].base_amount == Decimal("100.0000")


def test_snapshot_reconstructs_accumulated_exclusion_without_inclusions(app):
    """Persisted accumulated bases subtract prior excluded concepts from goods."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        iva_rule = create_tax_rule(
            {
                "name": f"IVA {suffix}",
                "concept": "iva",
                "applies_to": "both",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "10",
                "base_mode": "goods",
                "participates_in_next_base": "on",
                "recognition_event": "invoice",
                "is_active": "on",
            }
        )
        accumulated_rule = create_tax_rule(
            {
                "name": f"Tasa acumulada {suffix}",
                "concept": "tasa_posterior",
                "applies_to": "both",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "5",
                "base_mode": "accumulated",
                "exclude_concepts": "iva",
                "recognition_event": "invoice",
                "is_active": "on",
            }
        )
        database.session.flush()
        document_id = f"INV-{suffix}"

        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=document_id,
            currency="NIO",
            tax_lines=[
                {"source_rule_id": iva_rule.id, "concept": "iva"},
                {"source_rule_id": accumulated_rule.id, "concept": "tasa_posterior"},
            ],
            tax_summary={"subtotal": "100", "grand_total": "114.5"},
            server_subtotal=Decimal("100"),
        )
        database.session.commit()

        rows = load_document_fiscal_lines(document_type="sales_invoice", document_id=document_id)

        assert [row.base_amount for row in rows] == [Decimal("100.0000"), Decimal("90.0000")]
        assert [row.amount for row in rows] == [Decimal("10.0000"), Decimal("4.5000")]


def test_snapshot_acumula_lineas_repetidas_del_mismo_concepto(app):
    """La base acumulada usa la suma de todas las líneas canónicas del concepto."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        reglas = [
            create_tax_rule(
                {
                    "name": f"Tasa fija A {suffix}",
                    "company": "cacao",
                    "concept": "tasa_fija",
                    "applies_to": "both",
                    "level": "transaction",
                    "tax_type": "tax",
                    "calculation_method": "fixed",
                    "rate": "0",
                    "amount": "10",
                    "base_mode": "goods",
                    "participates_in_next_base": "on",
                    "recognition_event": "invoice",
                    "sequence": "10",
                    "is_active": "on",
                }
            ),
            create_tax_rule(
                {
                    "name": f"Tasa fija B {suffix}",
                    "company": "cacao",
                    "concept": "tasa_fija",
                    "applies_to": "both",
                    "level": "transaction",
                    "tax_type": "tax",
                    "calculation_method": "fixed",
                    "rate": "0",
                    "amount": "8",
                    "base_mode": "goods",
                    "participates_in_next_base": "on",
                    "recognition_event": "invoice",
                    "sequence": "20",
                    "is_active": "on",
                }
            ),
            create_tax_rule(
                {
                    "name": f"Tasa posterior {suffix}",
                    "company": "cacao",
                    "concept": "tasa_posterior",
                    "applies_to": "both",
                    "level": "transaction",
                    "tax_type": "tax",
                    "calculation_method": "percentage",
                    "rate": "10",
                    "amount": "0",
                    "base_mode": "accumulated",
                    "include_concepts": "tasa_fija",
                    "recognition_event": "invoice",
                    "sequence": "30",
                    "is_active": "on",
                }
            ),
        ]
        database.session.flush()
        document_id = f"INV-REPEATED-CONCEPT-{suffix}"

        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=document_id,
            currency="NIO",
            tax_lines=[{"source_rule_id": rule.id, "concept": rule.concept} for rule in reglas],
            tax_summary={"subtotal": "100", "grand_total": "119.80"},
            server_subtotal=Decimal("100"),
        )
        database.session.commit()

        rows = load_document_fiscal_lines(document_type="sales_invoice", document_id=document_id)
        summary_total = sum((row.amount for row in rows), Decimal("0")) + Decimal("100")

        assert [row.amount for row in rows] == [Decimal("10.0000"), Decimal("8.0000"), Decimal("1.8000")]
        assert rows[2].base_amount == Decimal("18.0000")
        assert summary_total == Decimal("119.8000")


def test_tax_rule_normalizes_concepts_and_snapshot_handles_legacy_duplicates(app):
    """Rule saves deduplicate concepts and snapshots safely handle legacy repeats."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        iva_rule = create_tax_rule(
            {
                "name": f"IVA {suffix}",
                "concept": "iva",
                "applies_to": "both",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "10",
                "base_mode": "goods",
                "participates_in_next_base": "on",
                "recognition_event": "invoice",
                "is_active": "on",
            }
        )
        accumulated_rule = create_tax_rule(
            {
                "name": f"Tasa acumulada {suffix}",
                "concept": "tasa_posterior",
                "applies_to": "both",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "10",
                "base_mode": "accumulated",
                "include_concepts": "goods, goods",
                "exclude_concepts": "iva, iva",
                "recognition_event": "invoice",
                "is_active": "on",
            }
        )
        database.session.flush()

        assert accumulated_rule.include_concepts == "goods"
        assert accumulated_rule.exclude_concepts == "iva"

        # Existing databases may still contain a duplicate CSV value without a migration.
        accumulated_rule.include_concepts = "goods, goods"
        accumulated_rule.exclude_concepts = "iva, iva"
        database.session.flush()
        document_id = f"INV-{suffix}"
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=document_id,
            currency="NIO",
            tax_lines=[
                {"source_rule_id": iva_rule.id, "concept": "iva"},
                {"source_rule_id": accumulated_rule.id, "concept": "tasa_posterior"},
            ],
            tax_summary={"subtotal": "100", "grand_total": "119"},
            server_subtotal=Decimal("100"),
        )
        database.session.commit()

        rows = load_document_fiscal_lines(document_type="sales_invoice", document_id=document_id)

        assert [row.base_amount for row in rows] == [Decimal("100.0000"), Decimal("90.0000")]
        assert [row.amount for row in rows] == [Decimal("10.0000"), Decimal("9.0000")]


def test_tax_rule_persists_the_category_without_migrations(app, persisted_rule):
    """The ORM schema stores the restriction directly for new databases."""
    with app.app_context():
        rule = database.session.get(TaxRule, persisted_rule["rule"])
        assert rule is not None
        assert rule.allowed_item_categories == persisted_rule["category"]
