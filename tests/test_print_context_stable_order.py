# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2177: los contextos de impresión conservan un orden estable de líneas."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.database import PaymentEntry, PaymentReference, PurchaseOrder, PurchaseOrderItem, database
from cacao_accounting.printing.context import (
    build_payment_entry_print_context,
    build_purchase_order_print_context,
)


def test_payment_references_are_ordered_by_creation(app, entorno_contable):
    """Las referencias impresas no dependen del orden incidental de la base."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        user = SimpleNamespace(user="admin", name="Admin")
        entry = PaymentEntry(
            company="cacao",
            payment_type="pay",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal("20"),
            received_amount=Decimal("20"),
            currency="NIO",
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add_all(
            [
                PaymentReference(
                    payment_id=entry.id,
                    reference_type="sales_invoice",
                    reference_id=f"LATE-{suffix}",
                    reference_document_no="LATE",
                    allocated_amount=Decimal("10"),
                    created=datetime(2026, 1, 2, tzinfo=UTC),
                ),
                PaymentReference(
                    payment_id=entry.id,
                    reference_type="sales_invoice",
                    reference_id=f"EARLY-{suffix}",
                    reference_document_no="EARLY",
                    allocated_amount=Decimal("10"),
                    created=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        database.session.commit()
        entry_id = entry.id

    context = build_payment_entry_print_context(entry_id, user, "cacao")

    assert [ref["reference_number"] for ref in context["payment"]["references"]] == ["EARLY", "LATE"]


def test_purchase_order_lines_are_ordered_by_creation(app, entorno_contable):
    """La numeración impresa sigue la creación de las líneas."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        user = SimpleNamespace(user="admin", name="Admin")
        order = PurchaseOrder(
            company="cacao",
            document_no=f"PO-{suffix}",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(order)
        database.session.flush()
        database.session.add_all(
            [
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    item_code="ART01",
                    item_name="Última",
                    description="LATE",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal("10"),
                    created=datetime(2026, 1, 2, tzinfo=UTC),
                ),
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    item_code="ART01",
                    item_name="Primera",
                    description="EARLY",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal("10"),
                    created=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        database.session.commit()
        order_id = order.id

    context = build_purchase_order_print_context(order_id, user, "cacao")

    assert [line["description"] for line in context["purchase_order"]["items"]] == ["EARLY", "LATE"]
    assert [line["line_number"] for line in context["purchase_order"]["items"]] == [1, 2]
