# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1746/#2108: valida números de configuración antes de persistirlos."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.admin.services import _approval_rule_from_form
from cacao_accounting.database import ApprovalMatrix, Item, SalesMatchingConfig, User, database
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    ItemParams,
    create_item_with_uoms,
    update_item_with_uoms,
)
from cacao_accounting.matching_config_service import update_matching_config


@pytest.mark.parametrize(
    ("min_amount", "max_amount", "approval_level", "message"),
    [
        ("500", "100", "1", "mayor o igual"),
        ("-1", "", "1", "no puede ser negativo"),
        ("0", "-1", "1", "no puede ser negativo"),
        ("Infinity", "", "1", "número finito"),
        ("abc", "", "1", "número válido"),
        ("0", "", "0", "nivel de aprobación"),
        ("0", "", "no-int", "nivel de aprobación"),
    ],
)
def test_approval_rule_rejects_invalid_ranges_and_levels(
    app, entorno_contable, min_amount, max_amount, approval_level, message
):
    """El writer de reglas rechaza valores inválidos antes de crear el modelo."""
    with app.app_context():
        original_rule_ids = {row.id for row in database.session.execute(select(ApprovalMatrix)).scalars()}
        user = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context(
            "/settings/approval-matrix",
            method="POST",
            data={
                "user_id": user.id,
                "document_type": "sales_invoice",
                "min_amount": min_amount,
                "max_amount": max_amount,
                "approval_level": approval_level,
            },
        ):
            with pytest.raises(ValueError, match=message):
                _approval_rule_from_form("cacao")

        current_rule_ids = {row.id for row in database.session.execute(select(ApprovalMatrix)).scalars()}
        assert current_rule_ids == original_rule_ids


def test_approval_rule_accepts_finite_ordered_range(app, entorno_contable):
    """Una regla con límites válidos conserva exactos sus valores decimales."""
    with app.app_context():
        user = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context(
            "/settings/approval-matrix",
            method="POST",
            data={
                "user_id": user.id,
                "document_type": "sales_invoice",
                "min_amount": "0.1250",
                "max_amount": "100.2500",
                "approval_level": "1",
            },
        ):
            rule = _approval_rule_from_form("cacao")

    assert rule.min_amount == Decimal("0.1250")
    assert rule.max_amount == Decimal("100.2500")
    assert rule.approval_level == 1


def test_sales_matching_rejects_negative_price_tolerance_without_mutation(app, entorno_contable):
    """La tolerancia negativa no se guarda ni se convierte en revisión pendiente."""
    with app.app_context():
        transaction = database.session.begin_nested()
        try:
            config = database.session.execute(select(SalesMatchingConfig).filter_by(company="cacao")).scalar_one_or_none()
            if config is None:
                config = SalesMatchingConfig(
                    company="cacao",
                    matching_type="3-way",
                    price_tolerance_type="percentage",
                    price_tolerance_value=Decimal("0"),
                    require_sales_order=True,
                    allow_price_difference=False,
                )
                database.session.add(config)
                database.session.flush()
            original_tolerance = config.price_tolerance_value

            with pytest.raises(ValueError, match="no puede ser negativa"):
                update_matching_config(
                    "sales",
                    "cacao",
                    {
                        "matching_type": "3-way",
                        "price_tolerance_type": "percentage",
                        "price_tolerance_value": "-1",
                        "require_sales_order": True,
                        "allow_price_difference": False,
                    },
                )

            database.session.refresh(config)
            assert config.price_tolerance_value == original_tolerance
        finally:
            transaction.rollback()


@pytest.mark.parametrize("rate", [Decimal("-1"), Decimal("-0.01")])
def test_item_service_rejects_negative_standard_rate_without_mutating_item(app, entorno_contable, rate):
    """El writer de artículos no guarda una tarifa que luego viola el contrato de ventas."""
    with app.app_context():
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        original_rate = item.standard_rate
        params = ItemParams(name=item.name, default_uom=item.default_uom, standard_rate=rate)

        with pytest.raises(InventoryServiceError, match="no puede ser negativo"):
            update_item_with_uoms(item.code, params)

        database.session.refresh(item)
        assert item.standard_rate == original_rate


def test_item_update_accepts_zero_standard_rate(app, entorno_contable):
    """El límite permitido es no negativo; una tarifa gratuita sigue siendo válida."""
    with app.app_context():
        transaction = database.session.begin_nested()
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        updated = update_item_with_uoms(
            item.code,
            ItemParams(
                name=item.name,
                item_type=item.item_type,
                is_stock_item=item.is_stock_item,
                is_purchase_item=item.is_purchase_item,
                is_sale_item=item.is_sale_item,
                default_uom=item.default_uom,
                standard_rate=Decimal("0"),
            ),
        )
        assert updated.standard_rate == Decimal("0")
        transaction.rollback()


def test_item_create_rejects_negative_standard_rate_before_persisting(app, entorno_contable):
    """El writer de alta valida la tarifa antes de insertar el artículo."""
    with app.app_context():
        code = "NEG" + uuid4().hex[:8].upper()
        params = ItemParams(name="Artículo inválido", standard_rate=Decimal("-0.01"))

        with pytest.raises(InventoryServiceError, match="no puede ser negativo"):
            create_item_with_uoms(params, code=code)

        assert database.session.execute(select(Item).filter_by(code=code)).scalar_one_or_none() is None
