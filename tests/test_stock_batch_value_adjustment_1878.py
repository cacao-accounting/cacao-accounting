# SPDX-License-Identifier: Apache-2.0
"""#1878: ajuste de solo valor por lote no debe dejar valor de lote negativo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import PostingError, _movement_outflow_issue
from cacao_accounting.database import (
    AccountingPeriod,
    Batch,
    Book,
    Currency,
    Entity,
    FiscalYear,
    Item,
    StockBin,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)


@pytest.fixture
def app_1878():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J1",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add(Book(entity="cacao", code="B1", name="B1", currency="NIO", status="activo", is_primary=True))
        fy = FiscalYear(
            entity="cacao",
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fy)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                fiscal_year_id=fy.id,
                entity="cacao",
                name="2026-05",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                is_closed=False,
                enabled=True,
            )
        )
        database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.commit()
        database.session.add(
            Item(
                code="IT-1878",
                name="Item 1878",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                allow_negative_stock=False,
            )
        )
        database.session.add(Warehouse(code="WH-1878", name="Bodega 1878", company="cacao"))
        database.session.commit()
        database.session.add_all(
            [
                Batch(id="LOT-A", item_code="IT-1878", batch_no="LOT-A"),
                Batch(id="LOT-B", item_code="IT-1878", batch_no="LOT-B"),
            ]
        )
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_value_only_negative_adjustment_cannot_make_batch_value_negative(app_1878):
    with app_1878.app_context():
        database.session.add(
            StockBin(
                company="cacao",
                item_code="IT-1878",
                warehouse="WH-1878",
                actual_qty=Decimal("2"),
                stock_value=Decimal("101"),
                valuation_rate=Decimal("50.5"),
            )
        )
        database.session.add_all(
            [
                StockLedgerEntry(
                    posting_date=date(2026, 5, 1),
                    company="cacao",
                    item_code="IT-1878",
                    warehouse="WH-1878",
                    qty_change=Decimal("1"),
                    stock_value_difference=Decimal("1"),
                    valuation_rate=Decimal("1"),
                    qty_after_transaction=Decimal("1"),
                    stock_value=Decimal("1"),
                    voucher_type="stock_entry",
                    voucher_id="SE-A",
                    batch_id="LOT-A",
                    is_cancelled=False,
                ),
                StockLedgerEntry(
                    posting_date=date(2026, 5, 1),
                    company="cacao",
                    item_code="IT-1878",
                    warehouse="WH-1878",
                    qty_change=Decimal("1"),
                    stock_value_difference=Decimal("100"),
                    valuation_rate=Decimal("100"),
                    qty_after_transaction=Decimal("2"),
                    stock_value=Decimal("101"),
                    voucher_type="stock_entry",
                    voucher_id="SE-B",
                    batch_id="LOT-B",
                    is_cancelled=False,
                ),
            ]
        )
        database.session.commit()

        doc = SimpleNamespace(
            company="cacao",
            base_currency="NIO",
            transaction_currency="NIO",
            exchange_rate=Decimal("1"),
            from_warehouse="WH-1878",
        )
        line = SimpleNamespace(
            item_code="IT-1878",
            source_warehouse="WH-1878",
            amount=Decimal("10"),
            valuation_rate=Decimal("0"),
            basic_rate=Decimal("0"),
            batch_id="LOT-A",
        )

        with pytest.raises(PostingError, match="lote.*debajo de cero"):
            _movement_outflow_issue(doc, line, Decimal("0"))


def test_ajustes_concurrentes_del_mismo_lote_se_serializan(tmp_path, monkeypatch):
    """#1878: dos ajustes de 8 contra un lote de 10 no pueden confirmar ambos."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, BrokenBarrierError
    from uuid import uuid4

    from cacao_accounting.contabilidad import posting_service

    uri = f"sqlite:///{tmp_path / 'batch-value-1878.sqlite'}"
    settings = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    }
    writer = create_app(settings)
    reader = create_app(settings)
    with writer.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J1",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.add(Warehouse(code="WH-1878", name="Bodega 1878", company="cacao"))
        database.session.flush()
        database.session.add(
            Item(
                code="IT-1878",
                name="Item 1878",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                allow_negative_stock=False,
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                Batch(id="LOT-A", item_code="IT-1878", batch_no="LOT-A"),
                Batch(id="LOT-B", item_code="IT-1878", batch_no="LOT-B"),
            ]
        )
        database.session.commit()
        database.session.add(
            StockBin(
                company="cacao",
                item_code="IT-1878",
                warehouse="WH-1878",
                actual_qty=Decimal("2"),
                stock_value=Decimal("101"),
                valuation_rate=Decimal("50.5"),
            )
        )
        database.session.add_all(
            [
                StockLedgerEntry(
                    posting_date=date(2026, 5, 1),
                    company="cacao",
                    item_code="IT-1878",
                    warehouse="WH-1878",
                    qty_change=Decimal("1"),
                    stock_value_difference=Decimal("10"),
                    valuation_rate=Decimal("10"),
                    qty_after_transaction=Decimal("10"),
                    stock_value=Decimal("10"),
                    voucher_type="stock_entry",
                    voucher_id="SE-A",
                    batch_id="LOT-A",
                    is_cancelled=False,
                ),
                StockLedgerEntry(
                    posting_date=date(2026, 5, 1),
                    company="cacao",
                    item_code="IT-1878",
                    warehouse="WH-1878",
                    qty_change=Decimal("1"),
                    stock_value_difference=Decimal("100"),
                    valuation_rate=Decimal("100"),
                    qty_after_transaction=Decimal("2"),
                    stock_value=Decimal("110"),
                    voucher_type="stock_entry",
                    voucher_id="SE-B",
                    batch_id="LOT-B",
                    is_cancelled=False,
                ),
            ]
        )
        database.session.commit()

    def _fake_movement(document, line, warehouse, qty_change, valuation_rate, value_change, **kwargs):
        del document, warehouse, qty_change, valuation_rate, kwargs
        try:
            movement_barrier.wait(timeout=0.2)
        except BrokenBarrierError:
            pass
        database.session.add(
            StockLedgerEntry(
                posting_date=date(2026, 5, 2),
                company="cacao",
                item_code=line.item_code,
                warehouse="WH-1878",
                qty_change=Decimal("0"),
                stock_value_difference=value_change,
                valuation_rate=Decimal("0"),
                qty_after_transaction=Decimal("2"),
                stock_value=Decimal("101") + value_change,
                voucher_type="stock_entry",
                voucher_id=f"ADJ-{uuid4().hex[:8]}",
                batch_id=line.batch_id,
                is_cancelled=False,
            )
        )
        database.session.flush()
        return []

    monkeypatch.setattr(posting_service, "_create_stock_movement", _fake_movement)
    movement_barrier = Barrier(2, timeout=10)
    doc = SimpleNamespace(
        company="cacao",
        base_currency="NIO",
        transaction_currency="NIO",
        exchange_rate=Decimal("1"),
        from_warehouse="WH-1878",
    )
    line = SimpleNamespace(
        item_code="IT-1878",
        source_warehouse="WH-1878",
        amount=Decimal("8"),
        valuation_rate=Decimal("0"),
        basic_rate=Decimal("0"),
        batch_id="LOT-A",
    )
    barrier = Barrier(2, timeout=30)

    def _adjust(app) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                _movement_outflow_issue(doc, line, Decimal("0"))
                database.session.commit()
                return "ajustado"
            except PostingError:
                database.session.rollback()
                return "rechazado"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = [workers.submit(_adjust, writer), workers.submit(_adjust, reader)]
        outcomes = sorted(future.result(timeout=30) for future in results)

    assert outcomes == ["ajustado", "rechazado"]
    with writer.app_context():
        database.session.expire_all()
        batch_value = database.session.execute(
            database.select(database.func.coalesce(database.func.sum(StockLedgerEntry.stock_value_difference), 0)).where(
                StockLedgerEntry.company == "cacao",
                StockLedgerEntry.item_code == "IT-1878",
                StockLedgerEntry.warehouse == "WH-1878",
                StockLedgerEntry.batch_id == "LOT-A",
                StockLedgerEntry.is_cancelled.is_(False),
            )
        ).scalar_one()
        assert Decimal(str(batch_value)) == Decimal("2")
        database.session.remove()
        database.engine.dispose()
    with reader.app_context():
        database.session.remove()
        database.engine.dispose()
