# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#759: la capa de valoración conserva la evidencia histórica en todo modo.

La capa mezcla evidencia económica (cantidad, tasa, costo, comprobante y
trazabilidad de capas) con saldos corrientes derivados. La prueba distingue
ambas naturalezas y verifica que los flujos reales de valoración siguen
registrando movimientos compensatorios sin reescribir el histórico.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask_login import login_user
from sqlalchemy import bindparam, text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import (
    _movement_outflow_issue,
    post_stock_entry,
)
from cacao_accounting.database import (
    Accounts,
    Batch,
    CompanyDefaultAccount,
    Currency,
    Entity,
    GLEntry,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import (
    STOCK_VALUATION_BALANCE_FIELDS,
    stock_valuation_balance_transition,
)
from cacao_accounting.inventario.service import (
    update_stock_valuation_layer_balances,
)

IMMUTABLE_FIELDS = (
    "qty",
    "rate",
    "stock_value_difference",
    "voucher_type",
    "voucher_id",
    "posting_date",
    "source_layer_id",
    "company",
    "item_code",
    "warehouse",
    "batch_id",
    "consumed_layers",
)


def _build_app(desktop: bool):
    """Create an isolated app with the structural guards explicitly enabled."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": desktop,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def _layer_snapshot(layer: StockValuationLayer) -> dict[str, object]:
    """Return the persisted values that define the historical layer plus balances."""
    names = IMMUTABLE_FIELDS + tuple(sorted(STOCK_VALUATION_BALANCE_FIELDS))
    return {name: getattr(layer, name) for name in names}


def _seed_layer(app) -> dict[str, object]:
    """Persist one valuation layer with valid company, item, warehouse and batch."""
    suffix = uuid4().hex[:8]
    company = f"C{suffix}"
    company_alt = f"D{suffix}"
    item_code = f"ITEM-{suffix}"
    item_alt = f"ALT-{suffix}"
    warehouse = f"WH-{suffix}"
    warehouse_alt = f"WA-{suffix}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.add_all(
            [
                Entity(
                    code=company,
                    name=f"Compañía valoración {suffix}",
                    company_name=f"Compañía valoración {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code=company_alt,
                    name=f"Compañía alterna {suffix}",
                    company_name=f"Compañía alterna {suffix}",
                    tax_id=f"TAX-ALT-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code=item_code,
                    name="Artículo valorado",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="UND",
                ),
                Item(
                    code=item_alt,
                    name="Artículo alterno",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="UND",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Warehouse(code=warehouse, name="Bodega valorada", company=company),
                Warehouse(code=warehouse_alt, name="Bodega alterna", company=company_alt),
            ]
        )
        database.session.flush()
        batch = Batch(item_code=item_code, batch_no=f"B-{suffix}")
        batch_alt = Batch(item_code=item_code, batch_no=f"BA-{suffix}")
        database.session.add_all([batch, batch_alt])
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
            voucher_id=f"V-{suffix}",
            posting_date=date(2026, 5, 1),
            source_layer_id=f"SRC-{suffix}",
            batch_id=batch.id,
            consumed_layers='[{"layer_id": "SRC", "qty": "1", "rate": "10"}]',
        )
        database.session.add(layer)
        database.session.commit()
        snapshot = _layer_snapshot(layer)
        seed = {
            "id": layer.id,
            "company": company,
            "company_alt": company_alt,
            "item_code": item_code,
            "item_alt": item_alt,
            "warehouse": warehouse,
            "warehouse_alt": warehouse_alt,
            "batch_alt": batch_alt.id,
            "snapshot": snapshot,
        }
    return seed


def _tampered_value(field_name: str, seed: dict[str, object]):
    """Return a different valid-ish value for each protected field."""
    values = {
        "qty": Decimal("999"),
        "rate": Decimal("99"),
        "stock_value_difference": Decimal("999"),
        "voucher_type": "tampered",
        "voucher_id": "tampered",
        "posting_date": date(2030, 1, 1),
        "source_layer_id": "tampered-source",
        "company": seed["company_alt"],
        "item_code": seed["item_alt"],
        "warehouse": seed["warehouse_alt"],
        "batch_id": seed["batch_alt"],
        "consumed_layers": '[{"layer_id": "tampered"}]',
    }
    return values[field_name]


def _assert_persisted_snapshot(app, seed: dict[str, object]) -> None:
    """Reload the layer in a fresh context and compare against the original."""
    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        assert _layer_snapshot(layer) == seed["snapshot"]


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("field_name", IMMUTABLE_FIELDS)
def test_orm_rejects_historical_valuation_rewrite(field_name, desktop):
    """A mapped UPDATE cannot change quantities, costs or traceability."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        setattr(layer, field_name, _tampered_value(field_name, seed))
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("channel", ["core", "textual"])
@pytest.mark.parametrize("field_name", IMMUTABLE_FIELDS)
def test_bulk_rejects_historical_valuation_rewrite(channel, field_name, desktop):
    """Core and textual SQL cannot rewrite historical valuation figures."""
    app = _build_app(desktop)
    seed = _seed_layer(app)
    value = _tampered_value(field_name, seed)

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "core":
                database.session.execute(
                    database.update(StockValuationLayer)
                    .where(StockValuationLayer.id == seed["id"])
                    .values({field_name: value})
                )
            else:
                database.session.execute(
                    text(f"UPDATE stock_valuation_layer SET {field_name} = :value WHERE id = :row_id"),
                    {"value": str(value), "row_id": seed["id"]},
                )
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
def test_delete_of_valuation_layer_is_rejected(channel, desktop):
    """No write path can physically remove a valuation layer."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "orm":
                layer = database.session.get(StockValuationLayer, seed["id"])
                assert layer is not None
                database.session.delete(layer)
            elif channel == "core":
                database.session.execute(database.delete(StockValuationLayer).where(StockValuationLayer.id == seed["id"]))
            else:
                database.session.execute(
                    text("DELETE FROM stock_valuation_layer WHERE id = :row_id"),
                    {"row_id": seed["id"]},
                )
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
def test_orm_bulk_update_cannot_bypass_the_valuation_guard(desktop):
    """Query.update follows the same historical and balance rules as Core SQL."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        with pytest.raises(ValueError):
            database.session.query(StockValuationLayer).filter_by(id=seed["id"]).update(
                {StockValuationLayer.qty: Decimal("99")}
            )
            database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.query(StockValuationLayer).filter_by(id=seed["id"]).update(
                {StockValuationLayer.remaining_qty: Decimal("0")}
            )
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
def test_authorized_scope_allows_query_update_of_balances(desktop):
    """The authorized valuation scope also covers explicit ORM bulk updates."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        with stock_valuation_balance_transition(layer):
            database.session.query(StockValuationLayer).filter_by(id=layer.id).update(
                {
                    StockValuationLayer.remaining_qty: Decimal("2"),
                    StockValuationLayer.remaining_stock_value: Decimal("20"),
                }
            )
            database.session.commit()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        assert layer.remaining_qty == Decimal("2")
        assert layer.remaining_stock_value == Decimal("20")


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
def test_derived_balance_update_requires_authorized_service(channel, desktop):
    """Running balances cannot be changed outside the valuation service scope."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "orm":
                layer = database.session.get(StockValuationLayer, seed["id"])
                assert layer is not None
                layer.remaining_qty = Decimal("0")
                layer.remaining_stock_value = Decimal("0")
            elif channel == "core":
                database.session.execute(
                    database.update(StockValuationLayer)
                    .where(StockValuationLayer.id == seed["id"])
                    .values(remaining_qty=Decimal("0"), remaining_stock_value=Decimal("0"))
                )
            else:
                database.session.execute(
                    text(
                        "UPDATE stock_valuation_layer " "SET remaining_qty = 0, remaining_stock_value = 0 WHERE id = :row_id"
                    ),
                    {"row_id": seed["id"]},
                )
            database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
def test_authorized_service_updates_only_derived_balances(desktop):
    """The authorized service can refresh the running balances of the layer."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        update_stock_valuation_layer_balances(
            layer,
            remaining_qty=Decimal("2"),
            remaining_stock_value=Decimal("20"),
        )
        database.session.commit()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        assert layer.remaining_qty == Decimal("2")
        assert layer.remaining_stock_value == Decimal("20")
        historical = _layer_snapshot(layer)
        for name in IMMUTABLE_FIELDS:
            assert historical[name] == seed["snapshot"][name]


@pytest.mark.parametrize("desktop", [True, False])
def test_authorized_balance_scope_cannot_rewrite_history(desktop):
    """The balance scope never turns into permission to rewrite evidence."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        with pytest.raises(ValueError):
            with stock_valuation_balance_transition(layer):
                layer.remaining_qty = Decimal("2")
                layer.qty = Decimal("99")
                database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)


@pytest.mark.parametrize("desktop", [True, False])
def test_authorized_scope_allows_scoped_core_balance_update(desktop):
    """A scoped Core UPDATE may refresh balances of the authorized layer."""
    app = _build_app(desktop)
    seed = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        with stock_valuation_balance_transition(layer):
            database.session.execute(
                database.update(StockValuationLayer)
                .where(StockValuationLayer.id == layer.id)
                .values(remaining_qty=Decimal("2"), remaining_stock_value=Decimal("20"))
            )
            database.session.commit()

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        assert layer.remaining_qty == Decimal("2")
        assert layer.remaining_stock_value == Decimal("20")


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("authorized_first", [True, False])
def test_authorized_core_update_rejects_mixed_parameter_sets(desktop, authorized_first):
    """An executemany cannot use one authorized ID to update another layer."""
    app = _build_app(desktop)
    seed = _seed_layer(app)
    other_seed = _seed_layer(app)
    parameters = (
        [{"row_id": seed["id"]}, {"row_id": other_seed["id"]}]
        if authorized_first
        else [{"row_id": other_seed["id"]}, {"row_id": seed["id"]}]
    )

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        statement = (
            database.update(StockValuationLayer)
            .where(StockValuationLayer.id == bindparam("row_id"))
            .values(remaining_qty=Decimal("0"), remaining_stock_value=Decimal("0"))
        )
        with pytest.raises(ValueError):
            with stock_valuation_balance_transition(layer):
                database.session.connection().execute(statement, parameters)
                database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, seed)
    _assert_persisted_snapshot(app, other_seed)


@pytest.mark.parametrize("desktop", [True, False])
def test_authorized_core_update_allows_all_authorized_parameter_sets(desktop):
    """A multi-row update remains usable when every layer is authorized."""
    app = _build_app(desktop)
    first = _seed_layer(app)
    second = _seed_layer(app)

    with app.app_context():
        first_layer = database.session.get(StockValuationLayer, first["id"])
        second_layer = database.session.get(StockValuationLayer, second["id"])
        assert first_layer is not None
        assert second_layer is not None
        statement = (
            database.update(StockValuationLayer)
            .where(StockValuationLayer.id == bindparam("row_id"))
            .values(remaining_qty=Decimal("2"), remaining_stock_value=Decimal("20"))
        )
        with stock_valuation_balance_transition(first_layer, second_layer):
            database.session.connection().execute(
                statement,
                [{"row_id": first["id"]}, {"row_id": second["id"]}],
            )
            database.session.commit()

    for layer_id in (first["id"], second["id"]):
        with app.app_context():
            layer = database.session.get(StockValuationLayer, layer_id)
            assert layer is not None
            assert layer.remaining_qty == Decimal("2")
            assert layer.remaining_stock_value == Decimal("20")


def test_balance_scope_requires_persisted_layers():
    """An empty valuation scope cannot authorize any derived-balance update."""
    with pytest.raises(ValueError, match="capas persistidas"):
        with stock_valuation_balance_transition():
            pass


def test_authorized_scope_rejects_unrelated_layers():
    """A balance scope only covers the layers explicitly supplied to it."""
    app = _build_app(desktop=True)
    seed = _seed_layer(app)
    other_seed = _seed_layer(app)

    with app.app_context():
        layer = database.session.get(StockValuationLayer, seed["id"])
        assert layer is not None
        with pytest.raises(ValueError):
            with stock_valuation_balance_transition(layer):
                database.session.execute(
                    database.update(StockValuationLayer)
                    .where(StockValuationLayer.id == other_seed["id"])
                    .values(remaining_qty=Decimal("1"))
                )
                database.session.commit()
        database.session.rollback()

    _assert_persisted_snapshot(app, other_seed)


def _seed_valuation_flow(app, valuation_method: str) -> dict[str, object]:
    """Seed two incoming layers and the bin used by the real valuation service."""
    suffix = uuid4().hex[:8]
    company = f"V{suffix}"
    item_code = f"FLOW-{suffix}"
    warehouse = f"FW-{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=company,
                    name="Compañía flujo",
                    company_name="Compañía flujo",
                    tax_id=f"TAX-FLOW-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                    valuation_method=valuation_method,
                ),
                UOM(code="UND", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code=item_code,
                name="Artículo flujo",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
            )
        )
        database.session.flush()
        database.session.add(Warehouse(code=warehouse, name="Bodega flujo", company=company))
        database.session.flush()
        first = StockValuationLayer(
            item_code=item_code,
            warehouse=warehouse,
            company=company,
            qty=Decimal("2"),
            rate=Decimal("10"),
            stock_value_difference=Decimal("20"),
            remaining_qty=Decimal("2"),
            remaining_stock_value=Decimal("20"),
            voucher_type="stock_entry",
            voucher_id=f"IN-1-{suffix}",
            posting_date=date(2026, 5, 1),
        )
        second = StockValuationLayer(
            item_code=item_code,
            warehouse=warehouse,
            company=company,
            qty=Decimal("3"),
            rate=Decimal("20"),
            stock_value_difference=Decimal("60"),
            remaining_qty=Decimal("3"),
            remaining_stock_value=Decimal("60"),
            voucher_type="stock_entry",
            voucher_id=f"IN-2-{suffix}",
            posting_date=date(2026, 5, 2),
        )
        database.session.add_all([first, second])
        database.session.flush()
        database.session.add(
            StockBin(
                company=company,
                item_code=item_code,
                warehouse=warehouse,
                actual_qty=Decimal("5"),
                stock_value=Decimal("80"),
                valuation_rate=Decimal("16"),
            )
        )
        database.session.commit()
        seed = {
            "company": company,
            "item_code": item_code,
            "warehouse": warehouse,
            "suffix": suffix,
            "first": _layer_snapshot(first),
            "second": _layer_snapshot(second),
        }
    return seed


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize(
    ("valuation_method", "expected_value"),
    [("fifo", Decimal("40")), ("moving_average", Decimal("48"))],
)
def test_valuation_flows_append_layers_without_rewriting_history(desktop, valuation_method, expected_value):
    """FIFO and moving average append the outgoing layer and preserve the inputs."""
    app = _build_app(desktop)
    seed = _seed_valuation_flow(app, valuation_method)
    suffix = seed["suffix"]

    with app.app_context():
        document = SimpleNamespace(
            id=f"SE-{suffix}",
            company=seed["company"],
            posting_date=date(2026, 5, 10),
            purpose="material_issue",
            from_warehouse=seed["warehouse"],
            voucher_type="stock_entry",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        line = SimpleNamespace(
            id=f"LINE-{suffix}",
            item_code=seed["item_code"],
            source_warehouse=seed["warehouse"],
            target_warehouse=None,
            amount=Decimal("0"),
            valuation_rate=Decimal("0"),
            basic_rate=Decimal("0"),
            qty=Decimal("3"),
            batch_id=None,
            serial_no=None,
        )
        movements = _movement_outflow_issue(document, line, Decimal("3"))
        database.session.add_all(movements)
        database.session.commit()

        layers = (
            database.session.execute(
                database.select(StockValuationLayer)
                .filter_by(item_code=seed["item_code"], warehouse=seed["warehouse"])
                .order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
            )
            .scalars()
            .all()
        )
        assert len(layers) == 3
        assert _layer_snapshot(layers[0]) == seed["first"]
        assert _layer_snapshot(layers[1]) == seed["second"]
        outgoing = layers[2]
        assert outgoing.qty == Decimal("-3")
        assert outgoing.stock_value_difference == -expected_value
        assert outgoing.remaining_qty == Decimal("2")
        assert outgoing.remaining_stock_value == Decimal("80") - expected_value
        assert bool(outgoing.consumed_layers) is (valuation_method == "fifo")

        movements = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(item_code=seed["item_code"])).scalars().all()
        )
        assert len(movements) == 1
        assert movements[0].qty_change == Decimal("-3")
        assert movements[0].stock_value_difference == -expected_value
        assert movements[0].stock_value == outgoing.remaining_stock_value


def _post_adjustment(
    app,
    entorno_contable,
    item_code: str,
    warehouse: str,
    purpose: str,
    qty: str,
    amount: str,
) -> StockEntry:
    """Persist and post a positive or negative stock adjustment."""
    entry = StockEntry(
        purpose=purpose,
        company="cacao",
        posting_date=date(2026, 5, 20),
        to_warehouse=warehouse,
        from_warehouse=warehouse,
        document_no=f"ADJ-{uuid4().hex[:8]}",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code=item_code,
            source_warehouse=warehouse,
            target_warehouse=warehouse,
            qty=Decimal(qty),
            uom="UND",
            qty_in_base_uom=Decimal(qty),
            basic_rate=Decimal("10"),
            amount=Decimal(amount),
        )
    )
    database.session.commit()
    with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
        login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
        post_stock_entry(entry)
    return entry


def test_adjustments_keep_valuation_stock_ledger_and_gl_consistent(app, entorno_contable):
    """Posted adjustments reconcile StockValuationLayer, StockLedgerEntry and GL."""
    with app.app_context():
        suffix = uuid4().hex[:6].upper()
        item_code = f"VGL-{suffix}"
        warehouse = f"VGLW-{suffix}"
        database.session.add(
            Item(code=item_code, name="Artículo GL", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code=warehouse, name="Bodega GL", company="cacao"))
        database.session.flush()
        inventory_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="1109")
        ).scalar_one()
        adjustment_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="5201")
        ).scalar_one()
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        for account_id in (inventory_account_id, adjustment_account_id):
            account = database.session.get(Accounts, account_id)
            account.active = True
            account.enabled = True
            account.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=warehouse,
                company="cacao",
                inventory_account_id=inventory_account_id,
            )
        )
        defaults.inventory_adjustment_account_id = adjustment_account_id
        database.session.commit()

        positive = _post_adjustment(app, entorno_contable, item_code, warehouse, "adjustment_positive", "5", "50")
        negative = _post_adjustment(app, entorno_contable, item_code, warehouse, "adjustment_negative", "2", "20")

        layers = database.session.execute(database.select(StockValuationLayer).filter_by(item_code=item_code)).scalars().all()
        movements = database.session.execute(database.select(StockLedgerEntry).filter_by(item_code=item_code)).scalars().all()
        # #1841: retirado el reconstructor físico, cada capa existe porque un asiento vivo la escribió.
        assert layers and movements, "el flujo vivo debe producir capas y asientos"
        comprobantes_vivos = {str(positive.id), str(negative.id)}
        assert {str(layer.voucher_id) for layer in layers} <= comprobantes_vivos
        assert {str(movement.voucher_id) for movement in movements} == {str(layer.voucher_id) for layer in layers}
        entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=negative.id)).scalars().all()
        assert sum((layer.qty for layer in layers), Decimal("0")) == Decimal("3")
        assert sum((movement.qty_change for movement in movements), Decimal("0")) == Decimal("3")
        assert sum((layer.stock_value_difference for layer in layers), Decimal("0")) == Decimal("30")
        assert sum((movement.stock_value_difference for movement in movements), Decimal("0")) == Decimal("30")
        assert entries
        debit = sum((entry.debit for entry in entries), Decimal("0"))
        credit = sum((entry.credit for entry in entries), Decimal("0"))
        assert debit == credit
        by_book: dict[str, Decimal] = {}
        for entry in entries:
            by_book[entry.ledger_id] = by_book.get(entry.ledger_id, Decimal("0")) + Decimal(entry.debit)
        assert set(by_book.values()) == {Decimal("20")}
