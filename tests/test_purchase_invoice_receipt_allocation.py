# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1689: la asignación de facturas no puede sobreasignar recepciones concurrentes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import (
    allocate_purchase_invoice_receipt_lines,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseInvoiceReceiptAllocation,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    database,
)


@pytest.fixture
def allocation_scenario(tmp_path: Path):
    """Factura de compra de 10 unidades con tres recepciones candidatas de 6."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'allocation-invoice.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6].upper()
    item_code = f"ITEM-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(Item(code=item_code, name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA"))
        database.session.flush()
        supplier = Party(code=f"SUP-{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        order = PurchaseOrder(
            company="alpha",
            document_no=f"PO-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 1),
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                item_code=item_code,
                item_name="Artículo",
                qty=Decimal("10"),
                qty_in_base_uom=Decimal("10"),
                uom="EA",
                rate=Decimal("10"),
                amount=Decimal("100"),
            )
        )
        receipt_ids: list[str] = []
        for index, qty in enumerate((Decimal("6"), Decimal("6"), Decimal("6")), start=1):
            receipt = PurchaseReceipt(
                company="alpha",
                document_no=f"PR-{suffix}-{index}",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                purchase_order_id=order.id,
                posting_date=date(2026, 5, 1 + index),
                docstatus=1,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
            )
            database.session.add(receipt)
            database.session.flush()
            database.session.add(
                PurchaseReceiptItem(
                    purchase_receipt_id=receipt.id,
                    item_code=item_code,
                    item_name="Artículo",
                    qty=qty,
                    qty_in_base_uom=qty,
                    uom="EA",
                    rate=Decimal("10"),
                    amount=qty * Decimal("10"),
                )
            )
            receipt_ids.append(str(receipt.id))
        invoice = PurchaseInvoice(
            company="alpha",
            document_type="purchase_invoice",
            document_no=f"PI-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            supplier_invoice_no=f"FAC-{suffix}",
            posting_date=date(2026, 5, 12),
            docstatus=1,
            purchase_order_id=order.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code=item_code,
                item_name="Artículo",
                qty=Decimal("10"),
                qty_in_base_uom=Decimal("10"),
                uom="EA",
                rate=Decimal("10"),
                amount=Decimal("100"),
            )
        )
        database.session.flush()
        invoice_id = str(invoice.id)
        invoice_item_id = str(
            database.session.execute(
                select(PurchaseInvoiceItem.id).where(
                    PurchaseInvoiceItem.purchase_invoice_id == invoice.id,
                    PurchaseInvoiceItem.is_superseded.is_(False),
                )
            )
            .scalars()
            .one()
        )
        database.session.commit()

    yield {
        "app": app,
        "invoice_id": invoice_id,
        "invoice_item_id": invoice_item_id,
        "receipt_ids": receipt_ids,
    }

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _allocated_invoice_qty(invoice_item_id: str) -> Decimal:
    """Suma las allocations activas de una línea de factura."""
    value = database.session.execute(
        select(func.coalesce(func.sum(PurchaseInvoiceReceiptAllocation.qty_in_base_uom), 0)).where(
            PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item_id,
            PurchaseInvoiceReceiptAllocation.status == "active",
        )
    ).scalar_one()
    return Decimal(str(value or 0))


def test_invoice_receipt_allocation_respects_invoice_qty(allocation_scenario):
    """Dos recepciones de 6 no pueden sobreasignar una factura de 10 unidades."""
    scenario = allocation_scenario
    with scenario["app"].app_context():
        first = allocate_purchase_invoice_receipt_lines(scenario["receipt_ids"][0], scenario["invoice_id"])
        second = allocate_purchase_invoice_receipt_lines(scenario["receipt_ids"][1], scenario["invoice_id"])
        allocated_total = _allocated_invoice_qty(scenario["invoice_item_id"])

    allocated_first = sum((row.qty_in_base_uom for row in first), Decimal("0"))
    allocated_second = sum((row.qty_in_base_uom for row in second), Decimal("0"))

    assert allocated_first == Decimal("6")
    assert allocated_second == Decimal("4")
    assert allocated_total == Decimal("10")


def test_invoice_receipt_allocation_skips_exhausted_invoice_line(allocation_scenario):
    """Una línea ya agotada no recibe allocations adicionales."""
    scenario = allocation_scenario
    with scenario["app"].app_context():
        first = allocate_purchase_invoice_receipt_lines(scenario["receipt_ids"][0], scenario["invoice_id"])
        second = allocate_purchase_invoice_receipt_lines(scenario["receipt_ids"][1], scenario["invoice_id"])
        third = allocate_purchase_invoice_receipt_lines(scenario["receipt_ids"][2], scenario["invoice_id"])
        allocated_total = _allocated_invoice_qty(scenario["invoice_item_id"])

    assert sum((row.qty_in_base_uom for row in first), Decimal("0")) == Decimal("6")
    assert sum((row.qty_in_base_uom for row in second), Decimal("0")) == Decimal("4")
    assert sum((row.qty_in_base_uom for row in third), Decimal("0")) == Decimal("0")
    assert allocated_total == Decimal("10")


def test_concurrent_receipts_do_not_overallocate_invoice(allocation_scenario):
    """Dos recepciones concurrentes no superan la cantidad de la línea de factura."""
    from concurrent.futures import ThreadPoolExecutor

    scenario = allocation_scenario

    def run(receipt_id: str) -> list[Decimal]:
        with scenario["app"].app_context():
            allocations = allocate_purchase_invoice_receipt_lines(receipt_id, scenario["invoice_id"])
            database.session.commit()
            return [row.qty_in_base_uom for row in allocations]

    with ThreadPoolExecutor(max_workers=2) as workers:
        first_task = workers.submit(run, scenario["receipt_ids"][0])
        second_task = workers.submit(run, scenario["receipt_ids"][1])
        first_task.result(timeout=30)
        second_task.result(timeout=30)

    with scenario["app"].app_context():
        allocated_total = _allocated_invoice_qty(scenario["invoice_item_id"])

    assert allocated_total <= Decimal("10")
