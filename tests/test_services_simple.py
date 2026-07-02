# SPDX-License-Identifier: Apache-2.0

"""Tests for tax_pricing_service dataclasses and collaboration constants."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace


class TestTaxPricingServiceDataclasses:
    def test_tax_line_result_can_be_instantiated(self):
        from cacao_accounting.tax_pricing_service import TaxLineResult

        result = TaxLineResult(
            tax_id="tax-1",
            name="IVA 15%",
            account_id="acc-1",
            amount=Decimal("15.0000"),
            behavior="additive",
            is_inclusive=False,
            is_charge=False,
            is_capitalizable=False,
        )
        assert result.tax_id == "tax-1"
        assert result.amount == Decimal("15.0000")

    def test_tax_calculation_result_can_be_instantiated(self):
        from cacao_accounting.tax_pricing_service import TaxCalculationResult, TaxLineResult

        line = TaxLineResult(
            tax_id="tax-1",
            name="IVA",
            account_id="acc-1",
            amount=Decimal("15"),
            behavior="additive",
            is_inclusive=False,
            is_charge=False,
            is_capitalizable=False,
        )
        result = TaxCalculationResult(
            lines=[line],
            additive_total=Decimal("15"),
            deductive_total=Decimal("0"),
            inclusive_total=Decimal("0"),
            payable_delta=Decimal("15"),
        )
        assert len(result.lines) == 1
        assert result.additive_total == Decimal("15")

    def test_price_suggestion_can_be_instantiated(self):
        from cacao_accounting.tax_pricing_service import PriceSuggestion

        suggestion = PriceSuggestion(
            item_code="ITEM001",
            price_list_id="list-1",
            price=Decimal("100.00"),
            currency="NIO",
            uom="UND",
        )
        assert suggestion.item_code == "ITEM001"
        assert suggestion.price == Decimal("100.00")

    def test_price_tolerance_result_can_be_instantiated(self):
        from cacao_accounting.tax_pricing_service import PriceToleranceResult

        result = PriceToleranceResult(
            allowed=True,
            suggested_price=Decimal("100"),
            variance_percentage=Decimal("5.0000"),
            message=None,
        )
        assert result.allowed is True
        assert result.variance_percentage == Decimal("5.0000")


class TestValidatePriceTolerance:
    def test_validate_price_tolerance_allows_within_tolerance(self):
        from cacao_accounting.tax_pricing_service import validate_price_tolerance

        line = SimpleNamespace()
        line.suggested_rate = Decimal("100.0000")
        line.rate = Decimal("105.0000")

        result = validate_price_tolerance("sales_invoice", line)
        assert result.allowed is True
        assert result.variance_percentage < Decimal("10")

    def test_validate_price_tolerance_rejects_outside_tolerance(self):
        from cacao_accounting.tax_pricing_service import validate_price_tolerance

        line = SimpleNamespace()
        line.suggested_rate = Decimal("100.0000")
        line.rate = Decimal("120.0000")

        result = validate_price_tolerance("sales_invoice", line)
        assert result.allowed is False
        assert "tolerancia" in result.message.lower()

    def test_validate_price_tolerance_allows_when_no_suggested_rate(self):
        from cacao_accounting.tax_pricing_service import validate_price_tolerance

        line = SimpleNamespace()
        line.suggested_rate = None
        line.rate = Decimal("100.0000")

        result = validate_price_tolerance("purchase_invoice", line)
        assert result.allowed is True

    def test_validate_price_tolerance_allows_zero_suggested_price(self):
        from cacao_accounting.tax_pricing_service import validate_price_tolerance

        line = SimpleNamespace()
        line.suggested_rate = Decimal("0")
        line.rate = Decimal("100.0000")

        result = validate_price_tolerance("sales_invoice", line)
        assert result.allowed is True


class TestCollaborationConstants:
    def test_task_statuses_are_valid(self):
        from cacao_accounting.collaboration_service import TASK_STATUSES

        assert "open" in TASK_STATUSES
        assert "in_progress" in TASK_STATUSES
        assert "completed" in TASK_STATUSES
        assert "cancelled" in TASK_STATUSES

    def test_task_priorities_are_valid(self):
        from cacao_accounting.collaboration_service import TASK_PRIORITIES

        assert "low" in TASK_PRIORITIES
        assert "normal" in TASK_PRIORITIES
        assert "high" in TASK_PRIORITIES

    def test_collaboration_error_can_be_instantiated(self):
        from cacao_accounting.collaboration_service import CollaborationError

        error = CollaborationError("Test error", 404)
        assert str(error) == "Test error"
        assert error.status_code == 404


class TestModuleBadges:
    def test_module_badge_returns_expected_statuses(self):
        from cacao_accounting.module_badges import module_badge
        from types import SimpleNamespace

        access = SimpleNamespace(access=True, consultar=True, autorizar=True)

        badge = module_badge(access=access, required="access")
        assert badge.status == "ok"

    def test_module_badge_detects_no_access(self):
        from cacao_accounting.module_badges import module_badge
        from types import SimpleNamespace

        no_access = SimpleNamespace(access=False, consultar=False, configurar=False)

        badge = module_badge(access=no_access, required="configurar")
        assert badge.status == "no_access"

    def test_module_badge_detects_view_only(self):
        from cacao_accounting.module_badges import module_badge
        from types import SimpleNamespace

        view_only = SimpleNamespace(access=True, consultar=True, configurar=False)

        badge = module_badge(access=view_only, required="configurar", view_permission="consultar")
        assert badge.status == "view_only"

    def test_module_badge_detects_attention_required(self):
        from cacao_accounting.module_badges import module_badge
        from types import SimpleNamespace

        access = SimpleNamespace(access=True, consultar=True, autorizar=True)

        badge = module_badge(access=access, required="autorizar", requires_attention=True)
        assert badge.status == "attention"


class TestRuntimeModeHelpers:
    def test_is_truthy_handles_strings(self):
        from cacao_accounting.runtime_mode import is_truthy

        assert is_truthy("true") is True
        assert is_truthy("false") is False
        assert is_truthy("1") is True
        assert is_truthy("0") is False
        assert is_truthy("yes") is True
        assert is_truthy("no") is False


class TestPartySettingsDataclass:
    def test_party_company_settings_can_be_instantiated(self):
        from cacao_accounting.party_settings import PartyCompanySettings

        settings = PartyCompanySettings(
            company="test",
            company_label="Test Company",
            is_active=True,
            receivable_account_id="acc-123",
            receivable_account_label="Cuentas por Cobrar",
            payable_account_id=None,
            payable_account_label="",
            tax_template_id="tax-456",
            tax_template_label="IVA General",
            default_tax_rule_id="rule-1",
            default_tax_rule_label="IVA Ventas",
            default_price_list_id="plist-1",
            default_price_list_label="Lista Ventas",
            allow_purchase_invoice_without_order=False,
            allow_purchase_invoice_without_receipt=False,
            default_currency=None,
            default_income_account_id=None,
            default_income_account_label="",
            default_expense_account_id=None,
            default_expense_account_label="",
            default_purchase_account_id=None,
            default_purchase_account_label="",
            default_advance_account_id=None,
            default_advance_account_label="",
            default_cost_center=None,
            default_business_unit=None,
            default_bank_name=None,
            default_bank_account_no=None,
            default_bank_iban=None,
            block_overdue=False,
        )
        assert settings.company == "test"
        assert settings.is_active is True
        assert settings.receivable_account_id == "acc-123"
        assert settings.default_tax_rule_id == "rule-1"
        assert settings.default_price_list_id == "plist-1"
