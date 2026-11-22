# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Matching configuration writers reject unknown enum values."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from cacao_accounting.control_review_service import _execute
from cacao_accounting.database import PurchaseMatchingConfig, SalesMatchingConfig, database
from cacao_accounting.matching_config_service import update_matching_config

_CONFIG_CASES = (
    ("purchase", PurchaseMatchingConfig, "matching_type", "nonsense-mode"),
    ("purchase", PurchaseMatchingConfig, "price_tolerance_type", "typo-percentage"),
    ("purchase", PurchaseMatchingConfig, "qty_tolerance_type", "nonsense"),
    ("purchase", PurchaseMatchingConfig, "matching_type", ["3-way"]),
    ("sales", SalesMatchingConfig, "matching_type", "nonsense-mode"),
    ("sales", SalesMatchingConfig, "price_tolerance_type", "typo-percentage"),
)


def _config_values(model: str) -> dict[str, object]:
    """Return valid representative values for a matching configuration."""
    values: dict[str, object] = {
        "matching_type": "3-way",
        "price_tolerance_type": "percentage",
        "price_tolerance_value": "0",
        "allow_price_difference": False,
    }
    if model == "purchase":
        values.update(
            qty_tolerance_type="percentage",
            qty_tolerance_value="0",
            require_purchase_order=True,
            bridge_account_required=False,
            auto_reconcile=False,
        )
    else:
        values["require_sales_order"] = True
    return values


@pytest.mark.parametrize("case", _CONFIG_CASES)
@pytest.mark.usefixtures("entorno_contable")
def test_matching_config_rejects_unknown_enum_without_mutation(app, case):
    """Direct writes reject unknown modes before changing persisted configuration."""
    model, config_model, field, invalid_value = case
    previous_desktop = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    company = "cacao"
    try:
        with app.app_context():
            config = database.session.execute(select(config_model).filter_by(company=company)).scalar_one_or_none()
            if config is None:
                config = config_model(company=company)
                database.session.add(config)
                database.session.flush()
            before = {key: getattr(config, key) for key in _config_values(model)}
            values = _config_values(model)
            values[field] = invalid_value

            with pytest.raises(ValueError, match="configuración de matching no es válido"):
                update_matching_config(model, company, values)

            database.session.refresh(config)
            assert {key: getattr(config, key) for key in before} == before
    finally:
        app.config["MODO_ESCRITORIO"] = previous_desktop


@pytest.mark.parametrize("case", _CONFIG_CASES)
@pytest.mark.usefixtures("entorno_contable")
def test_independent_approval_reuses_enum_validation(app, case):
    """Approval execution cannot bypass the shared service's enum allowlist."""
    model, config_model, field, invalid_value = case
    previous_desktop = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    company = "cacao"
    try:
        with app.app_context():
            config = database.session.execute(select(config_model).filter_by(company=company)).scalar_one_or_none()
            if config is None:
                config = config_model(company=company)
                database.session.add(config)
                database.session.flush()
            before = {key: getattr(config, key) for key in _config_values(model)}
            values = _config_values(model)
            values[field] = invalid_value
            request = SimpleNamespace(
                document_type="config_change",
                company_id=company,
                review_payload={"model": model, "after": values, "before": before},
            )
            reviewer = SimpleNamespace(id="independent-reviewer")

            with pytest.raises(ValueError, match="configuración de matching no es válido"):
                _execute(request, reviewer)

            database.session.refresh(config)
            assert {key: getattr(config, key) for key in before} == before
    finally:
        app.config["MODO_ESCRITORIO"] = previous_desktop


@pytest.mark.parametrize(
    ("field", "accepted_values"),
    [
        ("matching_type", ("2-way", "3-way")),
        ("price_tolerance_type", ("percentage", "absolute")),
        ("qty_tolerance_type", ("percentage", "absolute")),
    ],
)
@pytest.mark.usefixtures("entorno_contable")
def test_matching_config_accepts_declared_enum_values(app, field, accepted_values):
    """Every enum option exposed by matching configuration remains accepted."""
    previous_desktop = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    company = "cacao"
    try:
        with app.app_context():
            config = database.session.execute(select(PurchaseMatchingConfig).filter_by(company=company)).scalar_one_or_none()
            if config is None:
                config = PurchaseMatchingConfig(company=company)
                database.session.add(config)
                database.session.flush()
            transaction = database.session.begin_nested()
            try:
                for value in accepted_values:
                    values = _config_values("purchase")
                    values[field] = value
                    update_matching_config("purchase", company, values)
            finally:
                transaction.rollback()
    finally:
        app.config["MODO_ESCRITORIO"] = previous_desktop
