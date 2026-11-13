# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Tax-rule administration preserves user input when a reference is invalid."""

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, TaxRule, database


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
