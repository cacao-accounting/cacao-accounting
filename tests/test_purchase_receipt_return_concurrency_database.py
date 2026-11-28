# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2311: dos devoluciones concurrentes no exceden la recepción original."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import create_purchase_receipt_return_allocations
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Party,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    Warehouse,
    database,
)

pytestmark = pytest.mark.database

FECHA = date(2026, 5, 12)


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        pytest.skip("La carrera requiere bloqueo de fila real.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2311",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str) -> tuple[str, str, list[str]]:
    company = f"R{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        supplier = Party(code=f"PRV{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        uom = UOM(code=f"U{suffix}", name="Unidad", is_active=True)
        database.session.add_all([supplier, uom])
        database.session.flush()
        item = Item(code=f"IT{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom=uom.code)
        warehouse = Warehouse(code=f"W{suffix}", name="Bodega", company=company)
        database.session.add_all([item, warehouse])
        database.session.flush()
        original = PurchaseReceipt(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PR{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency=f"C{suffix}",
            base_currency=f"C{suffix}",
            exchange_rate=Decimal("1"),
        )
        database.session.add(original)
        database.session.flush()
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=original.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("4"),
                qty_in_base_uom=Decimal("4"),
                uom=uom.code,
                rate=Decimal("10"),
                amount=Decimal("40"),
                base_amount=Decimal("40"),
                warehouse=warehouse.code,
            )
        )
        returns = []
        for index in (1, 2):
            ret = PurchaseReceipt(
                company=company,
                posting_date=FECHA,
                docstatus=0,
                document_no=f"PRR{suffix}-{index}",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                is_return=True,
                reversal_of=original.id,
                transaction_currency=f"C{suffix}",
                base_currency=f"C{suffix}",
                exchange_rate=Decimal("1"),
            )
            database.session.add(ret)
            database.session.flush()
            database.session.add(
                PurchaseReceiptItem(
                    purchase_receipt_id=ret.id,
                    item_code=item.code,
                    item_name=item.name,
                    qty=Decimal("3"),
                    qty_in_base_uom=Decimal("3"),
                    uom=uom.code,
                    rate=Decimal("10"),
                    amount=Decimal("30"),
                    base_amount=Decimal("30"),
                    warehouse=warehouse.code,
                )
            )
            returns.append(ret.id)
        database.session.commit()
        result = (company, original.id, returns)
        database.session.remove()
        return result


def test_dos_devoluciones_concurrentes_no_exceden_lo_recibido(tmp_path):
    """Solo una devolución de 3 puede asignarse contra una recepción de 4."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    _company, _original_id, return_ids = _seed(app, suffix)
    barrier = Barrier(2, timeout=30)

    def return_items(return_id: str) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                create_purchase_receipt_return_allocations(return_id)
                database.session.commit()
                return "asignada"
            except Exception:
                database.session.rollback()
                return "rechazada"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(return_items, return_ids))
        assert sorted(results) == ["asignada", "rechazada"], results
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
