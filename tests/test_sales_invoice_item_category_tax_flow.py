# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1353: flujo completo de una regla fiscal restringida por categoría.

Una factura de venta con dos líneas —una categorizada y otra sin categoría—
calcula el impuesto solo sobre el subtotal que coincide, persiste ese base en
el snapshot fiscal y conserva la condición para eventos posteriores.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.accounting_engine.document_builders import build_calculation_context
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.database import Item, ItemCategory, Party, SalesInvoice, SalesInvoiceItem, database
from cacao_accounting.fiscal_persistence_service import (
    build_tax_rule_contexts_from_snapshot,
    document_item_category_subtotals,
    load_document_fiscal_lines,
    persist_document_fiscal_snapshot,
)
from cacao_accounting.tax_rule_service import create_tax_rule


def _category(name: str) -> ItemCategory:
    """Create one catalog category."""
    return ItemCategory(name=f"{name}-{uuid4().hex[:6]}", is_active=True)


def _line_payload(line) -> dict:
    """Serialize an engine fiscal line like the form submits it."""
    payload = asdict(line)
    for field in ("rate", "base_amount", "amount"):
        payload[field] = str(payload[field])
    return payload


def _item(code: str, category_id: str | None) -> Item:
    """Create one sale item, optionally categorized."""
    return Item(
        code=code,
        name=f"Artículo {code}",
        item_type="goods",
        is_stock_item=False,
        is_sale_item=True,
        default_uom="UND",
        item_category_id=category_id,
    )


def test_sales_invoice_taxes_only_the_matching_category_and_persists_it(app, entorno_contable):
    """End-to-end: engine base, snapshot base, and restored condition agree."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        category = _category("Calzado")
        database.session.add(category)
        database.session.flush()
        categorized = _item(f"CAL-{suffix}", category.id)
        uncategorized = _item(f"GEN-{suffix}", None)
        database.session.add_all([categorized, uncategorized])
        database.session.flush()
        customer = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            customer_id=customer.id,
            customer_name=customer.name,
        )
        database.session.add(invoice)
        database.session.flush()
        items = [
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=categorized.code,
                item_name=categorized.name,
                qty=Decimal("1"),
                rate=Decimal("100"),
                amount=Decimal("100"),
                uom="UND",
            ),
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=uncategorized.code,
                item_name=uncategorized.name,
                qty=Decimal("1"),
                rate=Decimal("50"),
                amount=Decimal("50"),
                uom="UND",
            ),
        ]
        database.session.add_all(items)
        rule = create_tax_rule(
            {
                "name": f"IVA calzado {suffix}",
                "company": "cacao",
                "concept": "iva",
                "applies_to": "sales",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "10",
                "base_mode": "goods",
                "recognition_event": "sales_invoice_confirmed",
                "currency": "NIO",
                "allowed_item_categories": category.id,
                "is_active": "on",
            }
        )
        database.session.commit()

        context = build_calculation_context(invoice)
        assert context is not None
        result = FiscalEngine().calculate(context)
        assert result.errors == []
        tax_line = next(line for line in result.tax_lines if line.source_rule_id == rule.id)
        assert tax_line.base_amount == Decimal("100")
        assert tax_line.amount == Decimal("10")
        assert tax_line.applies_to_items == [items[0].id]

        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=invoice.id,
            currency="NIO",
            tax_lines=[_line_payload(tax_line)],
            tax_summary={"subtotal": "150", "grand_total": "160"},
            server_subtotal=Decimal("150"),
            category_subtotals=document_item_category_subtotals(items),
        )
        database.session.commit()

        rows = load_document_fiscal_lines(document_type="sales_invoice", document_id=invoice.id)
        assert len(rows) == 1
        assert rows[0].base_amount == Decimal("100.0000")
        assert rows[0].amount == Decimal("10.0000")

        restored = build_tax_rule_contexts_from_snapshot(
            document_type="sales_invoice",
            document_id=invoice.id,
            recognition_event="sales_invoice_confirmed",
        )
        assert [rule.allowed_item_categories for rule in restored] == [[category.id]]


def test_category_subtotals_group_only_categorized_lines(app, entorno_contable):
    """The server-side subtotal map excludes uncategorized lines entirely."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        category = _category("Servicios")
        database.session.add(category)
        database.session.flush()
        categorized = _item(f"SER-{suffix}", category.id)
        uncategorized = _item(f"SIN-{suffix}", None)
        database.session.add_all([categorized, uncategorized])
        database.session.flush()
        customer = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            customer_id=customer.id,
            customer_name=customer.name,
        )
        database.session.add(invoice)
        database.session.flush()
        items = [
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=categorized.code,
                qty=Decimal("1"),
                rate=Decimal("120"),
                amount=Decimal("120"),
                uom="UND",
            ),
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=uncategorized.code,
                qty=Decimal("1"),
                rate=Decimal("80"),
                amount=Decimal("80"),
                uom="UND",
            ),
        ]
        database.session.add_all(items)
        database.session.commit()

        totals = document_item_category_subtotals(items)

        assert totals == {category.id: Decimal("120")}


def test_restricted_rule_ignores_other_categories_in_a_multi_line_invoice(app, entorno_contable):
    """A second categorized line outside the allowed category is not taxed."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        allowed_category = _category("Alimentos")
        other_category = _category("Tecnología")
        database.session.add_all([allowed_category, other_category])
        database.session.flush()
        allowed_item = _item(f"ALI-{suffix}", allowed_category.id)
        other_item = _item(f"TEC-{suffix}", other_category.id)
        database.session.add_all([allowed_item, other_item])
        database.session.flush()
        customer = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            customer_id=customer.id,
            customer_name=customer.name,
        )
        database.session.add(invoice)
        database.session.flush()
        items = [
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=allowed_item.code,
                qty=Decimal("2"),
                rate=Decimal("30"),
                amount=Decimal("60"),
                uom="UND",
            ),
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=other_item.code,
                qty=Decimal("1"),
                rate=Decimal("200"),
                amount=Decimal("200"),
                uom="UND",
            ),
        ]
        database.session.add_all(items)
        rule = create_tax_rule(
            {
                "name": f"IVA alimentos {suffix}",
                "company": "cacao",
                "concept": "iva",
                "applies_to": "sales",
                "level": "item",
                "tax_type": "tax",
                "calculation_method": "percentage",
                "rate": "10",
                "base_mode": "goods",
                "recognition_event": "sales_invoice_confirmed",
                "currency": "NIO",
                "allowed_item_categories": allowed_category.id,
                "is_active": "on",
            }
        )
        database.session.commit()

        context = build_calculation_context(invoice)
        assert context is not None
        result = FiscalEngine().calculate(context)
        assert result.errors == []
        tax_line = next(line for line in result.tax_lines if line.source_rule_id == rule.id)
        assert tax_line.base_amount == Decimal("60")
        assert tax_line.amount == Decimal("6")
        assert tax_line.applies_to_items == [items[0].id]
