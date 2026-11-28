# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1634: una regla fiscal con país solo aplica a ese país."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, TaxRule, database
from cacao_accounting.fiscal_preview_service import fiscal_preview


def _preview_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1634",
                    currency="NIO",
                    country="NI",
                    enabled=True,
                    status="default",
                ),
                TaxRule(
                    company="cacao",
                    name="IVA Honduras",
                    applies_to="sales",
                    concept="IVA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15"),
                    recognition_event="sales_invoice_confirmed",
                    country="HN",
                    is_active=True,
                ),
            ]
        )
        database.session.commit()
    return application


def _item() -> ItemContext:
    return ItemContext(
        line_id="L1",
        item_id="ART01",
        description="Artículo",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        gross_amount=Decimal("100"),
        net_amount=Decimal("100"),
    )


def _regla(rule_id: str, country: str | None, rate: str) -> TaxRuleContext:
    return TaxRuleContext(
        rule_id=rule_id,
        name=rule_id,
        concept=rule_id,
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal(rate),
        recognition_event="sales_invoice_confirmed",
        country=country,
    )


def _context(country: str | None, rules: list[TaxRuleContext]) -> CalculationContext:
    return CalculationContext(
        company_id="cacao",
        document_type="sales_invoice",
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=date(2026, 5, 15),
        posting_date=date(2026, 5, 15),
        party_type="customer",
        party_id="",
        currency="NIO",
        company_currency="NIO",
        items=[_item()],
        tax_rules=rules,
        references=AccountingReferences(country=country),
    )


@pytest.mark.parametrize(
    ("transaction_country", "expected_rules", "expected_total"),
    [
        ("NI", {"GENERAL"}, Decimal("10.00")),
        ("HN", {"GENERAL", "HN-IVA"}, Decimal("25.00")),
        (None, {"GENERAL"}, Decimal("10.00")),
    ],
)
def test_filtra_reglas_por_pais(transaction_country, expected_rules, expected_total):
    """Solo las reglas del país de la transacción o sin país se aplican."""
    rules = [_regla("GENERAL", None, "10"), _regla("HN-IVA", "HN", "15")]

    result = FiscalEngine().calculate(_context(transaction_country, rules))

    assert {line.source_rule_id for line in result.tax_lines} == expected_rules
    assert result.document_tax_total == expected_total


def test_regla_de_otro_pais_no_afecta_al_documento():
    """Un documento sin país tampoco aplica una regla exclusiva de Honduras."""
    result = FiscalEngine().calculate(_context("NI", [_regla("HN-IVA", "HN", "15")]))

    assert result.tax_lines == []
    assert result.document_tax_total == Decimal("0")


def test_preview_omite_reglas_de_otro_pais():
    """El preview usa el país de la compañía y descarta la regla hondureña."""
    application = _preview_app()
    try:
        with application.app_context():
            resultado = fiscal_preview(
                {
                    "document_type": "sales_invoice",
                    "company": "cacao",
                    "posting_date": "2026-05-15",
                    "currency": "NIO",
                    "lines": [{"qty": "1", "rate": "100", "amount": "100"}],
                }
            )

        assert resultado["tax_lines"] == []
        assert resultado["summary"]["document_tax_total"] == "0"
        assert resultado["summary"]["grand_total"] == "100"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
