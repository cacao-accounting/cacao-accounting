# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1299: CompanyParty conserva la relación y no preferencias inertes.

La compañía y el tercero siguen vinculados con sus datos comerciales; las
preferencias sin consumidores se retiraron del modelo y de los parámetros.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import CompanyParty, Currency, Entity, Party, database
from cacao_accounting.party_settings import (
    PartyCompanySettingsParams,
    build_party_company_settings,
    upsert_party_company_settings,
)

REMOVED_FIELDS = (
    "default_currency",
    "default_income_account_id",
    "default_expense_account_id",
    "default_purchase_account_id",
    "default_advance_account_id",
    "default_bank_name",
    "default_bank_account_no",
    "default_bank_iban",
)

RETAINED_FIELDS = (
    "company",
    "party_id",
    "is_active",
    "credit_limit",
    "payment_terms_id",
    "tax_template_id",
    "default_tax_rule_id",
    "default_price_list_id",
    "allow_purchase_invoice_without_order",
    "allow_purchase_invoice_without_receipt",
    "default_cost_center",
    "default_business_unit",
    "block_overdue",
)


@pytest.fixture
def company_party_scenario():
    """Create one company and one customer party."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Party(
                    code=f"CLI-{suffix}",
                    name="Cliente",
                    is_customer=True,
                    is_active=True,
                ),
            ]
        )
        database.session.commit()
        party_id = database.session.execute(database.select(Party.id)).scalar_one()
        ids = {"party": party_id}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_removed_preferences_are_not_part_of_the_model():
    """The eight inert preferences disappear from the ORM contract."""
    for field in REMOVED_FIELDS:
        assert not hasattr(CompanyParty, field)
    for field in RETAINED_FIELDS:
        assert hasattr(CompanyParty, field)


def test_settings_params_reject_removed_preferences():
    """A caller cannot keep configuring the retired preferences."""
    with pytest.raises(TypeError):
        PartyCompanySettingsParams(
            is_active=True,
            receivable_account_id=None,
            payable_account_id=None,
            tax_template_id=None,
            default_tax_rule_id=None,
            default_price_list_id=None,
            allow_purchase_invoice_without_order=False,
            allow_purchase_invoice_without_receipt=False,
            default_currency="USD",
        )


def test_business_relationship_and_retained_settings_still_work(company_party_scenario):
    """CompanyParty keeps the link, commercial flags and cost dimensions."""
    app, ids = company_party_scenario

    with app.app_context():
        upsert_party_company_settings(
            ids["party"],
            "customer",
            "alpha",
            PartyCompanySettingsParams(
                is_active=True,
                receivable_account_id=None,
                payable_account_id=None,
                tax_template_id=None,
                default_tax_rule_id=None,
                default_price_list_id=None,
                allow_purchase_invoice_without_order=False,
                allow_purchase_invoice_without_receipt=False,
                default_cost_center="CC-1",
                default_business_unit="BU-1",
                block_overdue=True,
            ),
            update_extended=True,
        )
        database.session.commit()
        link = database.session.execute(database.select(CompanyParty).filter_by(party_id=ids["party"])).scalar_one()
        assert link.company == "alpha"
        assert link.default_cost_center == "CC-1"
        assert link.default_business_unit == "BU-1"
        assert link.block_overdue is True

        settings = build_party_company_settings(ids["party"], "alpha", role="customer")
        assert settings.default_cost_center == "CC-1"
        assert settings.default_business_unit == "BU-1"
        assert settings.block_overdue is True
