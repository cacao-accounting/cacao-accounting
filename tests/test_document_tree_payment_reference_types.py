# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Payment trees preserve the logical type stored on each reference (#1408, #1615)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.document_flow.registry import get_document_type
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    SalesInvoice,
    database,
)
from cacao_accounting.document_flow.tree import build_document_flow_tree


@pytest.fixture(name="payment_reference_tree")
def payment_reference_tree_fixture():
    """Create credit/debit notes and a return referenced from matching payment records."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    references = (
        ("sales_credit_note", "sales_invoice", "pay", "customer"),
        ("sales_debit_note", "sales_invoice", "receive", "customer"),
        ("sales_return", "sales_invoice", "pay", "customer"),
        ("purchase_credit_note", "purchase_invoice", "receive", "supplier"),
        ("purchase_debit_note", "purchase_invoice", "pay", "supplier"),
        ("sales_invoice", "sales_invoice", "receive", "customer"),
    )

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                *[Modules(module=name, default=False, enabled=True) for name in ("sales", "purchases", "cash")],
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()

        payment_ids = {}
        for index, (logical_type, physical_type, payment_type, party_type) in enumerate(references):
            invoice_model = PurchaseInvoice if party_type == "supplier" else SalesInvoice
            doc_no = f"DOC-{index}-{suffix}"
            invoice = invoice_model(
                company="alpha",
                posting_date=date(2026, 5, 10),
                docstatus=1,
                document_no=doc_no,
                document_type=logical_type,
                grand_total=Decimal("100"),
                **({"supplier_name": "Proveedor"} if party_type == "supplier" else {"customer_name": "Cliente"}),
            )
            payment = PaymentEntry(
                company="alpha",
                posting_date=date(2026, 5, 10),
                docstatus=1,
                document_no=f"PAY-{index}-{suffix}",
                payment_type=payment_type,
                party_type=party_type,
                party_name="Proveedor" if party_type == "supplier" else "Cliente",
                paid_amount=Decimal("100"),
            )
            database.session.add_all([invoice, payment])
            database.session.flush()
            database.session.add(
                PaymentReference(
                    payment_id=payment.id,
                    reference_type=physical_type,
                    flow_source_type=None if logical_type == "sales_invoice" else logical_type,
                    reference_id=invoice.id,
                    reference_document_no=doc_no,
                    company="alpha",
                    allocated_amount=Decimal("100"),
                )
            )
            payment_ids[payment.id] = (invoice.id, logical_type, doc_no)

        database.session.commit()

    yield app, payment_ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_payment_tree_uses_logical_type_and_falls_back_for_legacy_references(payment_reference_tree):
    """Modern notes/returns keep their logical identity; old rows use physical type."""
    app, payment_ids = payment_reference_tree

    with app.app_context():
        for payment_id, (invoice_id, expected_type, doc_no) in payment_ids.items():
            tree = build_document_flow_tree("payment_entry", payment_id, direction="downstream")
            node = next(item for item in tree["downstream"] if item.get("document_id") == invoice_id)

            assert node["document_type"] == expected_type
            assert node["document_no"] == doc_no
            assert node["status"] is not None
            assert node["label"] == str(get_document_type(expected_type).label)
