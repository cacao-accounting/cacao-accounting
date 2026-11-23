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


def test_payment_references_con_created_igual_se_desempatan_por_id(app, entorno_contable):
    """#2177: con `created` idéntico el orden es determinista por `id`.

    Los ids se insertan en orden inverso al esperado y la referencia de la
    primera fila insertada ordena antes por sus columnas de consulta; así la
    prueba falla tanto con orden de inserción como con orden de índice si se
    retira el desempate `id.asc()` de `_stable_items_query`.
    """
    suffix = uuid4().hex[:6]
    created = datetime(2026, 3, 1, tzinfo=UTC)
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
                    id="Z" * 26,
                    payment_id=entry.id,
                    reference_type="sales_invoice",
                    reference_id=f"AAA-{suffix}",
                    reference_document_no="DOCUMENTO-TARDIO-POR-ID",
                    allocated_amount=Decimal("10"),
                    created=created,
                ),
                PaymentReference(
                    id="A" * 26,
                    payment_id=entry.id,
                    reference_type="sales_invoice",
                    reference_id=f"ZZZ-{suffix}",
                    reference_document_no="DOCUMENTO-TEMPRANO-POR-ID",
                    allocated_amount=Decimal("10"),
                    created=created,
                ),
            ]
        )
        database.session.commit()
        entry_id = entry.id

    context = build_payment_entry_print_context(entry_id, user, "cacao")

    assert [ref["reference_number"] for ref in context["payment"]["references"]] == [
        "DOCUMENTO-TEMPRANO-POR-ID",
        "DOCUMENTO-TARDIO-POR-ID",
    ]


def test_purchase_order_items_con_created_igual_se_desempatan_por_id(app, entorno_contable):
    """#2177: la numeración impresa es determinista aun con `created` igual."""
    created = datetime(2026, 3, 1, tzinfo=UTC)
    with app.app_context():
        user = SimpleNamespace(user="admin", name="Admin")
        order = PurchaseOrder(
            company="cacao",
            document_no="PO-DESEMPATE",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(order)
        database.session.flush()
        database.session.add_all(
            [
                PurchaseOrderItem(
                    id="Z" * 26,
                    purchase_order_id=order.id,
                    item_code="ART01",
                    item_name="Item id tardío",
                    description="SEGUNDA-POR-ID",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal("10"),
                    created=created,
                ),
                PurchaseOrderItem(
                    id="A" * 26,
                    purchase_order_id=order.id,
                    item_code="ART01",
                    item_name="Item id temprano",
                    description="PRIMERA-POR-ID",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal("10"),
                    created=created,
                ),
            ]
        )
        database.session.commit()
        order_id = order.id

    context = build_purchase_order_print_context(order_id, user, "cacao")

    assert [line["description"] for line in context["purchase_order"]["items"]] == ["PRIMERA-POR-ID", "SEGUNDA-POR-ID"]
    assert [line["line_number"] for line in context["purchase_order"]["items"]] == [1, 2]
