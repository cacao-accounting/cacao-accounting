# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""#1876: cancelaci?n de recepci?n no deja lote negativo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.cancellation_service import _consumed_stock_dependencies
from cacao_accounting.database import (
    Batch,
    Currency,
    Entity,
    Item,
    StockBin,
    StockEntry,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    Warehouse,
    database,
)


def _app():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "test-1876",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J1",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad", is_active=True),
            ]
        )
        database.session.commit()
        database.session.add(Warehouse(company="cacao", code="WH1", name="Bodega", is_active=True))
        database.session.add(
            Item(
                code="ITEM-B",
                name="Item Lote",
                default_uom="UND",
                item_type="goods",
                is_stock_item=True,
                has_batch=True,
                allow_negative_stock=False,
            )
        )
        database.session.commit()
        database.session.add_all(
            [
                Batch(item_code="ITEM-B", batch_no="A", is_active=True),
                Batch(item_code="ITEM-B", batch_no="B", is_active=True),
            ]
        )
        database.session.commit()
        app.config["BATCH_A"] = database.session.execute(database.select(Batch.id).filter_by(batch_no="A")).scalar_one()
        app.config["BATCH_B"] = database.session.execute(database.select(Batch.id).filter_by(batch_no="B")).scalar_one()
    return app


def _sle(*, entry_id, qty, value, batch_id, is_cancelled=False, day=date(2026, 5, 1)):
    return StockLedgerEntry(
        posting_date=day,
        item_code="ITEM-B",
        warehouse="WH1",
        company="cacao",
        qty_change=Decimal(str(qty)),
        qty_after_transaction=Decimal("0"),
        valuation_rate=Decimal("10"),
        stock_value_difference=Decimal(str(value)),
        stock_value=Decimal("0"),
        voucher_type="stock_entry",
        voucher_id=entry_id,
        batch_id=batch_id,
        is_cancelled=is_cancelled,
    )


def _movimiento(document_no: str, purpose: str, day: date, warehouse_field: str) -> StockEntry:
    """Crea un movimiento contabilizado del lote para el escenario #2343."""
    entrada = StockEntry(
        company="cacao",
        purpose=purpose,
        posting_date=day,
        document_no=document_no,
        status="submitted",
        docstatus=1,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    setattr(entrada, warehouse_field, "WH1")
    database.session.add(entrada)
    database.session.flush()
    return entrada


def test_validate_stock_reversal_capacity_rechaza_lote_negativo():
    app = _app()
    with app.app_context():
        batch_a = app.config["BATCH_A"]
        batch_b = app.config["BATCH_B"]
        database.session.add(
            StockBin(
                company="cacao",
                item_code="ITEM-B",
                warehouse="WH1",
                actual_qty=Decimal("10"),
                stock_value=Decimal("100"),
                valuation_rate=Decimal("10"),
            )
        )
        database.session.add_all(
            [
                _sle(entry_id="REC-A", qty=5, value=50, batch_id=batch_a),
                _sle(entry_id="ISS-A", qty=-5, value=-50, batch_id=batch_a),
                _sle(entry_id="REC-B", qty=10, value=100, batch_id=batch_b),
            ]
        )
        database.session.commit()

        movement = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id="REC-A")).scalar_one()
        with pytest.raises(posting_service.PostingError, match="lote .* quedar.* con stock negativo"):
            posting_service._validate_stock_reversal_capacity([movement])


def test_consumed_stock_dependencies_detecta_consumo_por_lote_moving_average():
    app = _app()
    with app.app_context():
        batch_a = app.config["BATCH_A"]
        rec_a = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            to_warehouse="WH1",
            document_no="REC-A",
            status="submitted",
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        iss_a = StockEntry(
            company="cacao",
            purpose="material_issue",
            posting_date=date(2026, 5, 1),
            from_warehouse="WH1",
            document_no="ISS-A",
            status="submitted",
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add_all([rec_a, iss_a])
        database.session.flush()

        database.session.add(
            StockValuationLayer(
                item_code="ITEM-B",
                warehouse="WH1",
                company="cacao",
                qty=Decimal("5"),
                rate=Decimal("10"),
                stock_value_difference=Decimal("50"),
                remaining_qty=Decimal("5"),
                remaining_stock_value=Decimal("50"),
                voucher_type="stock_entry",
                voucher_id=rec_a.id,
                posting_date=date(2026, 5, 1),
                batch_id=batch_a,
            )
        )
        database.session.add_all(
            [
                _sle(entry_id=rec_a.id, qty=5, value=50, batch_id=batch_a),
                _sle(entry_id=iss_a.id, qty=-5, value=-50, batch_id=batch_a),
            ]
        )
        database.session.commit()

        deps = _consumed_stock_dependencies(rec_a, "stock_entry", rec_a.id)
        assert any(
            d.kind == "consumo de inventario por lote" and d.identifier == iss_a.id and d.detail == "stock_entry" for d in deps
        )


def test_salida_anterior_no_bloquea_cancelar_ingreso_posterior():
    """#2343: un despacho anterior al segundo ingreso no es su dependencia."""
    app = _app()
    with app.app_context():
        batch_a = app.config["BATCH_A"]
        rec_a = _movimiento("REC-A3", "material_receipt", date(2026, 5, 1), "to_warehouse")
        iss_a = _movimiento("ISS-A3", "material_issue", date(2026, 5, 2), "from_warehouse")
        rec_b = _movimiento("REC-B3", "material_receipt", date(2026, 5, 4), "to_warehouse")
        database.session.add_all(
            [
                _sle(entry_id=rec_a.id, qty=10, value=100, batch_id=batch_a, day=date(2026, 5, 1)),
                _sle(entry_id=iss_a.id, qty=-5, value=-50, batch_id=batch_a, day=date(2026, 5, 2)),
                _sle(entry_id=rec_b.id, qty=10, value=100, batch_id=batch_a, day=date(2026, 5, 4)),
            ]
        )
        database.session.commit()

        deps_b = _consumed_stock_dependencies(rec_b, "stock_entry", rec_b.id)
        assert not any(d.kind == "consumo de inventario por lote" for d in deps_b)


def test_ingreso_anterior_que_dejaria_negativo_sigue_bloqueado():
    """El criterio de saldo diario conserva la protección del lote."""
    app = _app()
    with app.app_context():
        batch_a = app.config["BATCH_A"]
        rec_a = _movimiento("REC-A4", "material_receipt", date(2026, 5, 1), "to_warehouse")
        iss_a = _movimiento("ISS-A4", "material_issue", date(2026, 5, 2), "from_warehouse")
        rec_b = _movimiento("REC-B4", "material_receipt", date(2026, 5, 4), "to_warehouse")
        database.session.add_all(
            [
                _sle(entry_id=rec_a.id, qty=10, value=100, batch_id=batch_a, day=date(2026, 5, 1)),
                _sle(entry_id=iss_a.id, qty=-5, value=-50, batch_id=batch_a, day=date(2026, 5, 2)),
                _sle(entry_id=rec_b.id, qty=10, value=100, batch_id=batch_a, day=date(2026, 5, 4)),
            ]
        )
        database.session.commit()

        deps_a = _consumed_stock_dependencies(rec_a, "stock_entry", rec_a.id)
        assert any(d.kind == "consumo de inventario por lote" and d.identifier == iss_a.id for d in deps_a)


def test_salida_posterior_dependiente_del_ingreso_se_bloquea():
    """Un despacho que deja el lote en negativo sin el ingreso sí es dependencia."""
    app = _app()
    with app.app_context():
        batch_a = app.config["BATCH_A"]
        rec_b = _movimiento("REC-B5", "material_receipt", date(2026, 5, 4), "to_warehouse")
        iss_b = _movimiento("ISS-B5", "material_issue", date(2026, 5, 5), "from_warehouse")
        database.session.add_all(
            [
                _sle(entry_id=rec_b.id, qty=10, value=100, batch_id=batch_a, day=date(2026, 5, 4)),
                _sle(entry_id=iss_b.id, qty=-12, value=-120, batch_id=batch_a, day=date(2026, 5, 5)),
            ]
        )
        database.session.commit()

        deps_b = _consumed_stock_dependencies(rec_b, "stock_entry", rec_b.id)
        assert any(d.kind == "consumo de inventario por lote" and d.identifier == iss_b.id for d in deps_b)


def test_stock_reversal_persiste_batch_en_svl():
    app = _app()
    with app.app_context():
        batch_a = app.config["BATCH_A"]
        database.session.add(
            StockBin(
                company="cacao",
                item_code="ITEM-B",
                warehouse="WH1",
                actual_qty=Decimal("5"),
                stock_value=Decimal("50"),
                valuation_rate=Decimal("10"),
            )
        )
        rec_a = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 1),
            to_warehouse="WH1",
            document_no="REC-A",
            status="submitted",
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(rec_a)
        database.session.flush()
        movement = _sle(entry_id=rec_a.id, qty=5, value=50, batch_id=batch_a)
        database.session.add(movement)
        database.session.commit()

        reversal = posting_service._create_stock_reversal(rec_a, movement, date(2026, 5, 2))
        database.session.add(reversal)
        database.session.flush()
        svl = (
            database.session.execute(database.select(StockValuationLayer).filter_by(voucher_id=rec_a.id, batch_id=batch_a))
            .scalars()
            .all()
        )
        assert len(svl) == 1
        assert Decimal(str(svl[0].qty)) == Decimal("-5")
