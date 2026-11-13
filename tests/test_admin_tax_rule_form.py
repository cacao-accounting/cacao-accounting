# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Tax-rule administration preserves input and enforces fiscal domains."""

from datetime import date
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.accounting_engine.common.context import CalculationContext, ItemContext
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.database import DocumentTaxLine, DocumentTaxSummary, Modules, TaxRule, database
from cacao_accounting.fiscal_persistence_service import _canonical_tax_rule_amount, persist_document_fiscal_snapshot
from cacao_accounting.tax_rule_service import build_tax_rule_contexts


@pytest.fixture
def active_admin_module(app):
    """Enable the real administration module for this route-level scenario."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            module = Modules(module="admin", default=False, enabled=True)
            database.session.add(module)
            was_created = True
            was_enabled = True
        else:
            was_created = False
            was_enabled = module.enabled
            module.enabled = True
        database.session.commit()

    yield

    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is not None:
            if was_created:
                database.session.delete(module)
            else:
                module.enabled = was_enabled
            database.session.commit()


def test_invalid_tax_rule_reference_rerenders_submitted_business_values(
    app, authenticated_client, entorno_contable, active_admin_module
):
    """An invalid account cannot save a tax rule or erase its submitted values."""
    assert entorno_contable.app is app
    suffix = uuid4().hex[:8]
    rule_name = f"IVA de importación {suffix}"
    data = {
        "name": rule_name,
        "company": "cacao",
        "concept": "impuesto de importación",
        "applies_to": "purchase",
        "level": "transaction",
        "tax_type": "withholding",
        "calculation_method": "percentage",
        "rate": "12.50",
        "account_id": f"MISSING-{suffix}",
        "currency": "NIO",
        "recognition_event": "purchase_invoice_confirmed",
        "sequence": "25",
    }

    response = authenticated_client().post("/settings/tax-rules", data=data)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'value="{rule_name}"' in html
    assert 'name="concept"' in html and 'value="impuesto de importación"' in html
    assert '<option value="purchase" selected>' in html
    assert 'name="rate"' in html and 'value="12.50"' in html
    assert f'value="MISSING-{suffix}"' in html
    with app.app_context():
        assert database.session.execute(database.select(TaxRule).filter_by(name=rule_name)).scalar_one_or_none() is None


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("applies_to", "garbage"),
        ("level", "unknown"),
        ("tax_type", "mystery"),
        ("calculation_method", "mystery"),
        ("calculation_method", "quantity"),
        ("base_mode", "other"),
        ("accounting_treatment", "unknown"),
        ("recognition_event", "whenever"),
    ],
)
def test_invalid_fiscal_domain_is_rejected_before_it_can_change_a_report(
    app, authenticated_client, entorno_contable, active_admin_module, field, invalid_value
):
    """A tampered enum cannot persist a tax rule that builders omit or miscalculate."""
    assert entorno_contable.app is app
    suffix = uuid4().hex[:8]
    rule_name = f"Regla fiscal inválida {suffix}"
    data = {
        "name": rule_name,
        "company": "cacao",
        "concept": "iva",
        "applies_to": "purchase",
        "level": "transaction",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "rate": "15",
        "amount": "0",
        "base_mode": "goods",
        "accounting_treatment": "separate_tax_account",
        "recognition_event": "invoice",
        "currency": "NIO",
        "sequence": "10",
        field: invalid_value,
    }

    client = authenticated_client()
    response = client.post("/settings/tax-rules", data=data)

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(TaxRule).filter_by(name=rule_name)).scalar_one_or_none() is None

    valid_data = {
        **data,
        field: {
            "applies_to": "purchase",
            "level": "transaction",
            "tax_type": "tax",
            "calculation_method": "percentage",
            "base_mode": "goods",
            "accounting_treatment": "separate_tax_account",
            "recognition_event": "invoice",
        }[field],
        "is_active": "on",
        "affects_document_total": "on",
    }
    assert client.post("/settings/tax-rules", data=valid_data).status_code == 302
    with app.app_context():
        rule = database.session.execute(database.select(TaxRule).filter_by(name=rule_name)).scalar_one()
        rule_id = rule.id

    update_response = client.post(f"/settings/tax-rules/{rule_id}/edit", data=data)

    assert update_response.status_code == 200
    with app.app_context():
        database.session.expire_all()
        persisted_rule = database.session.get(TaxRule, rule_id)
        assert persisted_rule is not None
        assert getattr(persisted_rule, field) == valid_data[field]


def test_valid_fiscal_domains_reach_context_and_calculate_capitalized_tax(
    app, authenticated_client, entorno_contable, active_admin_module
):
    """The selected purchase event and treatment survive persistence and affect the fiscal result."""
    assert entorno_contable.app is app
    rule_name = f"Arancel capitalizable {uuid4().hex[:8]}"
    response = authenticated_client().post(
        "/settings/tax-rules",
        data={
            "name": rule_name,
            "company": "cacao",
            "concept": "arancel",
            "applies_to": "purchase",
            "level": "item",
            "tax_type": "charge",
            "calculation_method": "fixed",
            "rate": "0",
            "amount": "5",
            "base_mode": "accumulated",
            "accounting_treatment": "capitalizable_inventory_cost",
            "recognition_event": "purchase_invoice_confirmed",
            "currency": "NIO",
            "sequence": "10",
            "is_active": "on",
            "affects_document_total": "on",
        },
    )
    assert response.status_code == 302

    credit_note_rules = {
        "purchase_credit_note_confirmed": ("purchase", f"NC compra {uuid4().hex[:8]}"),
        "sales_credit_note_confirmed": ("sales", f"NC venta {uuid4().hex[:8]}"),
    }
    client = authenticated_client()
    for event, (direction, name) in credit_note_rules.items():
        credit_response = client.post(
            "/settings/tax-rules",
            data={
                "name": name,
                "company": "cacao",
                "concept": "nota_credito",
                "applies_to": direction,
                "level": "transaction",
                "tax_type": "tax",
                "calculation_method": "fixed",
                "rate": "0",
                "amount": "5",
                "base_mode": "goods",
                "accounting_treatment": "separate_tax_account",
                "recognition_event": event,
                "currency": "NIO",
                "sequence": "10",
                "is_active": "on",
                "affects_document_total": "on",
            },
        )
        assert credit_response.status_code == 302

    with app.app_context():
        contexts = build_tax_rule_contexts(
            company="cacao",
            applies_to="purchase",
            currency="NIO",
            recognition_event="purchase_invoice_confirmed",
        )
        contexts = [rule for rule in contexts if rule.name == rule_name]
        assert len(contexts) == 1
        invoice_rules = build_tax_rule_contexts(
            company="cacao", applies_to="purchase", currency="NIO", recognition_event="invoice"
        )
        assert all(rule.name != rule_name for rule in invoice_rules)
        for event, (direction, name) in credit_note_rules.items():
            matching_rules = build_tax_rule_contexts(
                company="cacao",
                applies_to=direction,
                currency="NIO",
                recognition_event=event,
            )
            assert [rule.name for rule in matching_rules if rule.name == name] == [name]
            assert all(
                rule.name != name
                for rule in build_tax_rule_contexts(
                    company="cacao",
                    applies_to=direction,
                    currency="NIO",
                    recognition_event="invoice",
                )
            )

    calculation = CalculationContext(
        company_id="cacao",
        document_type="purchase_invoice",
        event_type="purchase_invoice_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 1),
        posting_date=date(2026, 5, 1),
        party_type="supplier",
        party_id="SUPPLIER",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="line-1",
                item_id="item-1",
                description="Material importado",
                quantity=Decimal("3"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("300"),
                net_amount=Decimal("300"),
            )
        ],
        tax_rules=contexts,
    )
    result = FiscalEngine().calculate(calculation)

    assert result.errors == []
    assert result.capitalizable_tax_total == Decimal("5.0000")
    assert result.tax_lines[0].recognition_event == "purchase_invoice_confirmed"
    assert result.tax_lines[0].accounting_treatment == "capitalizable_inventory_cost"
    assert result.tax_lines[0].affects_inventory is True

    unsupported_rule = replace(contexts[0], calculation_method="quantity")
    unsupported_result = FiscalEngine().calculate(replace(calculation, tax_rules=[unsupported_rule]))
    assert unsupported_result.tax_lines == []
    assert any("método de cálculo fiscal no está soportado" in error for error in unsupported_result.errors)
    with pytest.raises(ValueError, match="método de cálculo fiscal no está soportado"):
        _canonical_tax_rule_amount(TaxRule(calculation_method="quantity", amount=Decimal("0")), Decimal("300"), Decimal("5"))


def test_unsupported_manual_method_preserves_existing_fiscal_snapshot(app, entorno_contable):
    """Reject a forged manual method before replacing the document's persisted fiscal evidence."""
    assert entorno_contable.app is app
    document_type = "sales_invoice"
    document_id = uuid4().hex[:26]
    valid_line = {
        "manual": True,
        "source_rule_id": f"MANUAL-{document_id}",
        "concept": "cargo manual",
        "type": "charge",
        "calculation_method": "manual",
        "base_amount": "100",
        "rate": "0",
        "amount": "5",
        "accounting_treatment": "separate_tax_account",
        "affects_document_total": True,
    }

    with app.app_context():
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type=document_type,
            document_id=document_id,
            currency="NIO",
            tax_lines=[valid_line],
            tax_summary={"subtotal": "100", "grand_total": "105"},
            server_subtotal=Decimal("100"),
            server_total=Decimal("105"),
        )
        database.session.commit()
        original_summary = database.session.execute(
            database.select(DocumentTaxSummary).filter_by(document_type=document_type, document_id=document_id)
        ).scalar_one()
        original_line = database.session.execute(
            database.select(DocumentTaxLine).filter_by(document_tax_summary_id=original_summary.id)
        ).scalar_one()
        summary_id = original_summary.id
        line_id = original_line.id

        invalid_line = {**valid_line, "calculation_method": "quantity"}
        with pytest.raises(ValueError, match="método de cálculo fiscal no está soportado"):
            persist_document_fiscal_snapshot(
                company="cacao",
                document_type=document_type,
                document_id=document_id,
                currency="NIO",
                tax_lines=[invalid_line],
                tax_summary={"subtotal": "100", "grand_total": "105"},
                server_subtotal=Decimal("100"),
                server_total=Decimal("105"),
            )

        database.session.expire_all()
        persisted_summary = database.session.get(DocumentTaxSummary, summary_id)
        persisted_line = database.session.get(DocumentTaxLine, line_id)
        assert persisted_summary is not None
        assert persisted_line is not None
        assert persisted_line.calculation_method == "manual"
        assert persisted_line.amount == Decimal("5.0000")

        database.session.delete(persisted_summary)
        database.session.commit()
