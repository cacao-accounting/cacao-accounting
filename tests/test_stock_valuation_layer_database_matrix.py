# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#759: la política de capas de valoración se aplica en los motores Tier 1.

La matriz usa el motor configurado por la suite (SQLite local o el motor
externo habilitado con ``CHECK_DATABASE``) y conserva el aislamiento por
compañía, artículo y bodega mediante identificadores únicos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    StockValuationLayer,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.inventario.service import update_stock_valuation_layer_balances

pytestmark = pytest.mark.database


def _build_app(tmp_path, desktop: bool):
    """Use the configured engine, falling back to an isolated SQLite file."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'valuation-matrix.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": desktop,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def _seed_layer(app) -> tuple[str, dict[str, object]]:
    """Persist one isolated valuation layer and return its identity and values."""
    suffix = uuid4().hex[:8]
    company = f"M{suffix}"
    item_code = f"MITEM-{suffix}"
    warehouse = f"MHW-{suffix}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía matriz {suffix}",
                company_name=f"Compañía matriz {suffix}",
                tax_id=f"MTAX-{suffix}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        database.session.add(
            Item(code=item_code, name="Artículo matriz", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.flush()
        database.session.add(Warehouse(code=warehouse, name="Bodega matriz", company=company))
        database.session.flush()
        layer = StockValuationLayer(
            item_code=item_code,
            warehouse=warehouse,
            company=company,
            qty=Decimal("5"),
            rate=Decimal("10"),
            stock_value_difference=Decimal("50"),
            remaining_qty=Decimal("5"),
            remaining_stock_value=Decimal("50"),
            voucher_type="stock_entry",
            voucher_id=f"MV-{suffix}",
            posting_date=date(2026, 5, 1),
        )
        database.session.add(layer)
        database.session.commit()
        snapshot = {
            "qty": layer.qty,
            "stock_value_difference": layer.stock_value_difference,
            "remaining_qty": layer.remaining_qty,
            "remaining_stock_value": layer.remaining_stock_value,
        }
        return layer.id, snapshot


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_rejects_historical_rewrite_on_configured_engine(tmp_path, desktop):
    """The mapped guard rejects historical changes on the configured engine."""
    app = _build_app(tmp_path, desktop)
    layer_id, snapshot = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        layer.stock_value_difference = Decimal("999")
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        assert layer.stock_value_difference == snapshot["stock_value_difference"]


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_delete_is_rejected_on_configured_engine(tmp_path, desktop):
    """Deleting valuation evidence through the ORM is rejected."""
    app = _build_app(tmp_path, desktop)
    layer_id, snapshot = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        database.session.delete(layer)
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        assert layer.qty == snapshot["qty"]


@pytest.mark.parametrize("desktop", [True, False])
def test_core_rejects_historical_and_unauthorized_balance_writes(tmp_path, desktop):
    """Core writes cannot rewrite history or balances without the service scope."""
    app = _build_app(tmp_path, desktop)
    layer_id, snapshot = _seed_layer(app)

    with app.app_context():
        with pytest.raises(ValueError):
            database.session.execute(
                database.update(StockValuationLayer).where(StockValuationLayer.id == layer_id).values(qty=Decimal("99"))
            )
            database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.update(StockValuationLayer)
                .where(StockValuationLayer.id == layer_id)
                .values(remaining_qty=Decimal("0"))
            )
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        assert layer.qty == snapshot["qty"]
        assert layer.remaining_qty == snapshot["remaining_qty"]


@pytest.mark.parametrize("desktop", [True, False])
def test_authorized_service_updates_balances_on_configured_engine(tmp_path, desktop):
    """The authorized valuation service refreshes balances on the configured engine."""
    app = _build_app(tmp_path, desktop)
    layer_id, snapshot = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        update_stock_valuation_layer_balances(
            layer,
            remaining_qty=Decimal("2"),
            remaining_stock_value=Decimal("20"),
        )
        database.session.commit()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, layer_id)
        assert layer is not None
        assert layer.remaining_qty == Decimal("2")
        assert layer.remaining_stock_value == Decimal("20")
        assert layer.qty == snapshot["qty"]
