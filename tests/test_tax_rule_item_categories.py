# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1353: condición fiscal opcional por categoría de artículo.

Una regla con ``allowed_item_categories`` solo aplica a líneas cuyos artículos
pertenecen a una categoría permitida. La condición se persiste como ULID del
catálogo existente ``ItemCategory``, se canonicaliza para snapshots estables y
se valida en backend, sin depender de controles de interfaz.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import ItemCategory, Modules, TaxRule, database
from cacao_accounting.tax_rule_service import (
    TaxRuleServiceError,
    build_tax_rule_contexts,
    create_tax_rule,
    update_tax_rule,
)


def _category(name: str, *, active: bool = True) -> ItemCategory:
    """Create one catalog category with a unique name."""
    return ItemCategory(name=f"{name}-{uuid4().hex[:6]}", is_active=active)


def _rule_values(**overrides: str | None) -> dict[str, str | None]:
    """Build a minimal global tax rule payload."""
    values: dict[str, str | None] = {
        "name": f"IVA restringido {uuid4().hex[:6]}",
        "concept": "iva",
        "applies_to": "both",
        "level": "item",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "rate": "15",
        "sequence": "10",
        "recognition_event": "invoice",
        "is_active": "on",
    }
    values.update(overrides)
    return values


@pytest.fixture
def item_categories(app):
    """Seed active and inactive categories in the shared test database."""
    with app.app_context():
        active_a = _category("Bienes", active=True)
        active_b = _category("Servicios", active=True)
        inactive = _category("Descontinuada", active=False)
        database.session.add_all([active_a, active_b, inactive])
        database.session.commit()
        ids = {
            "active_a": active_a.id,
            "active_b": active_b.id,
            "inactive": inactive.id,
            "missing": f"MISSING-{uuid4().hex[:10]}",
        }
    return ids


def test_rule_persists_canonical_item_categories_and_exposes_them(app, item_categories):
    """The condition is persisted deduplicated/sorted and reaches the engine context."""
    with app.app_context():
        rule = create_tax_rule(
            _rule_values(allowed_item_categories=f"{item_categories['active_b']}, {item_categories['active_a']}")
        )
        database.session.commit()

        assert rule.allowed_item_categories == ", ".join(sorted([item_categories["active_a"], item_categories["active_b"]]))
        contexts = build_tax_rule_contexts(company=None, applies_to="purchase", currency=None)
        context = next(item for item in contexts if item.rule_id == rule.id)
        assert context.allowed_item_categories == sorted([item_categories["active_a"], item_categories["active_b"]])


def test_duplicate_item_categories_are_deduplicated(app, item_categories):
    """Submitting the same category twice stores it once."""
    category = item_categories["active_a"]
    with app.app_context():
        rule = create_tax_rule(_rule_values(allowed_item_categories=f"{category},{category},{category}"))
        database.session.commit()

        assert rule.allowed_item_categories == category


def test_rule_without_categories_stays_unrestricted(app):
    """An empty condition remains optional and yields an empty context list."""
    with app.app_context():
        rule = create_tax_rule(_rule_values(allowed_item_categories="  ,  "))
        database.session.commit()

        assert rule.allowed_item_categories is None
        contexts = build_tax_rule_contexts(company=None, applies_to="sales", currency=None)
        context = next(item for item in contexts if item.rule_id == rule.id)
        assert context.allowed_item_categories == []


def test_unknown_item_category_is_rejected_before_persisting(app, item_categories):
    """A category outside the catalog cannot be stored."""
    with app.app_context():
        with pytest.raises(TaxRuleServiceError, match="no existe"):
            create_tax_rule(_rule_values(allowed_item_categories=item_categories["missing"]))
        database.session.rollback()
        assert (
            database.session.execute(
                database.select(TaxRule).where(TaxRule.allowed_item_categories == item_categories["missing"])
            ).scalar_one_or_none()
            is None
        )


def test_inactive_item_category_is_rejected_before_persisting(app, item_categories):
    """An inactive category cannot be used as a fiscal condition."""
    with app.app_context():
        with pytest.raises(TaxRuleServiceError, match="no está activa"):
            create_tax_rule(_rule_values(allowed_item_categories=item_categories["inactive"]))
        database.session.rollback()


def test_update_replaces_the_item_category_condition(app, item_categories):
    """Updating a rule can add or clear the restriction."""
    with app.app_context():
        rule = create_tax_rule(_rule_values())
        database.session.commit()

        update_tax_rule(rule, _rule_values(allowed_item_categories=item_categories["active_a"]))
        database.session.commit()
        assert rule.allowed_item_categories == item_categories["active_a"]

        update_tax_rule(rule, _rule_values(allowed_item_categories=""))
        database.session.commit()
        assert rule.allowed_item_categories is None


@pytest.fixture
def admin_module_enabled(app):
    """Enable the administration module for the route-level case."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        previous = module.enabled if module is not None else None
        if module is None:
            module = Modules(module="admin", default=False, enabled=True)
            database.session.add(module)
        else:
            module.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is not None:
            if previous is None:
                database.session.delete(module)
            else:
                module.enabled = previous
            database.session.commit()


def test_admin_form_persists_the_item_category_condition(app, authenticated_client, admin_module_enabled, item_categories):
    """The condition is saved from the admin surface, not only through the service."""
    name = f"Regla por categoría {uuid4().hex[:6]}"
    data = _rule_values(name=name, allowed_item_categories=item_categories["active_a"])

    response = authenticated_client().post("/settings/tax-rules", data=data, follow_redirects=False)

    assert response.status_code in {302, 303}
    with app.app_context():
        rule = database.session.execute(database.select(TaxRule).filter_by(name=name)).scalar_one()
        assert rule.allowed_item_categories == item_categories["active_a"]


def test_admin_form_rejects_unknown_category_and_preserves_input(
    app, authenticated_client, admin_module_enabled, item_categories
):
    """An invalid category re-renders the form with the submitted value."""
    name = f"Regla inválida {uuid4().hex[:6]}"
    data = _rule_values(name=name, allowed_item_categories=item_categories["missing"])

    response = authenticated_client().post("/settings/tax-rules", data=data)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'value="{item_categories["missing"]}"' in html
    with app.app_context():
        assert database.session.execute(database.select(TaxRule).filter_by(name=name)).scalar_one_or_none() is None
