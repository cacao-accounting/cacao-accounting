# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Matching configuration writers reject unknown enum values."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from cacao_accounting.control_review_service import _execute
from cacao_accounting.database import Modules, PurchaseMatchingConfig, SalesMatchingConfig, User, database
from cacao_accounting.matching_config_service import update_matching_config

_CONFIG_CASES = (
    ("purchase", PurchaseMatchingConfig, "matching_type", "nonsense-mode"),
    ("purchase", PurchaseMatchingConfig, "price_tolerance_type", "typo-percentage"),
    ("purchase", PurchaseMatchingConfig, "qty_tolerance_type", "nonsense"),
    ("purchase", PurchaseMatchingConfig, "matching_type", ["3-way"]),
    ("sales", SalesMatchingConfig, "matching_type", "nonsense-mode"),
    ("sales", SalesMatchingConfig, "price_tolerance_type", "typo-percentage"),
)
_NUMERIC_CASES = (
    ("purchase", PurchaseMatchingConfig, "price_tolerance_value", "-1"),
    ("purchase", PurchaseMatchingConfig, "qty_tolerance_value", "Infinity"),
    ("purchase", PurchaseMatchingConfig, "price_tolerance_value", "1.23456"),
    ("sales", SalesMatchingConfig, "price_tolerance_value", "NaN"),
    ("sales", SalesMatchingConfig, "price_tolerance_value", "1000000"),
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


def _matching_config_admin_client(app, user_id: str):
    """Authenticate an isolated client as the configured system administrator."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _matching_config_post_values(model: str, company: str, field: str, value: str) -> dict[str, object]:
    """Build a complete valid admin payload with one overridden value."""
    values = _config_values(model)
    values.update(company=company, config_form="complete")
    for key, actual in tuple(values.items()):
        if isinstance(actual, bool):
            values[key] = "on" if actual else "_no"
    values[field] = value
    return values


def _assert_invalid_matching_admin_post(app, path: str, case: tuple[str, type, str, str]) -> None:
    """Check an invalid admin payload redirects and leaves its config unchanged."""
    model, config_model, field, invalid_value = case
    previous_desktop = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    company = "cacao"
    try:
        with app.app_context():
            if database.session.execute(select(Modules).filter_by(module="admin")).scalar_one_or_none() is None:
                database.session.add(Modules(module="admin", default=False, enabled=True))
                database.session.commit()
            config = database.session.execute(select(config_model).filter_by(company=company)).scalar_one_or_none()
            original_value = getattr(config, field) if config is not None else None
            admin_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        response = _matching_config_admin_client(app, admin_id).post(
            path, data=_matching_config_post_values(model, company, field, invalid_value)
        )
        assert response.status_code == 302
        with app.app_context():
            config = database.session.execute(select(config_model).filter_by(company=company)).scalar_one_or_none()
            if original_value is None:
                assert config is None
            else:
                assert getattr(config, field) == original_value
    finally:
        app.config["MODO_ESCRITORIO"] = previous_desktop


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


@pytest.mark.parametrize("case", _NUMERIC_CASES)
@pytest.mark.usefixtures("entorno_contable")
def test_matching_config_rejects_invalid_numeric_tolerance_without_mutation(app, case):
    """Tolerance bounds reject negative, non-finite, and unrepresentable values."""
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
            original_value = getattr(config, field)
            values = _config_values(model)
            values[field] = invalid_value

            with pytest.raises(ValueError):
                update_matching_config(model, company, values)

            database.session.refresh(config)
            assert getattr(config, field) == original_value
    finally:
        app.config["MODO_ESCRITORIO"] = previous_desktop


@pytest.mark.parametrize("case", _NUMERIC_CASES)
@pytest.mark.usefixtures("entorno_contable")
def test_matching_config_approval_rejects_invalid_numeric_tolerance(app, case):
    """Independent approval cannot bypass tolerance domain validation."""
    model, config_model, field, invalid_value = case
    previous_desktop = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    values = _config_values(model)
    values[field] = invalid_value
    request = SimpleNamespace(
        document_type="config_change",
        company_id="cacao",
        review_payload={"model": model, "after": values, "before": _config_values(model)},
    )
    reviewer = SimpleNamespace(id="independent-reviewer")
    try:
        with app.app_context():
            config = database.session.execute(select(config_model).filter_by(company="cacao")).scalar_one_or_none()
            if config is None:
                database.session.add(config_model(company="cacao"))
                database.session.flush()
            with pytest.raises(ValueError):
                _execute(request, reviewer)
    finally:
        app.config["MODO_ESCRITORIO"] = previous_desktop


@pytest.mark.parametrize(
    ("path", "case"),
    [
        ("/settings/purchase-reconciliation", ("purchase", PurchaseMatchingConfig, "price_tolerance_value", "-1")),
        ("/settings/purchase-reconciliation", ("purchase", PurchaseMatchingConfig, "qty_tolerance_value", "Infinity")),
        ("/settings/sales-matching", ("sales", SalesMatchingConfig, "price_tolerance_value", "NaN")),
    ],
)
@pytest.mark.usefixtures("entorno_contable")
def test_matching_config_admin_post_rejects_invalid_numeric_value(app, path, case):
    """The real admin POST translates numeric failures to a redirect, not HTTP 500."""
    _assert_invalid_matching_admin_post(app, path, case)
