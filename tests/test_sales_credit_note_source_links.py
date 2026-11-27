# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1224: sales notes must use the source invoice's flow and currency."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Currency, DeliveryNote, Party, SalesInvoice, SalesOrder, database
from cacao_accounting.ventas import services


@pytest.fixture
def sales_note_sources(entorno_contable_aislado, monkeypatch):
    """Create one invoice flow and unrelated sources matching customer and company."""
    app = entorno_contable_aislado.app
    monkeypatch.setattr(services, "exige_acceso_compania", lambda *args, **kwargs: None)
    suffix = uuid4().hex[:8]
    with app.app_context():
        customer = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        for code in ("USD", "EUR"):
            currency = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
            if currency is None:
                database.session.add(Currency(code=code, name=code, decimals=2, active=True, default=False))
        database.session.flush()
        source_order = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 1),
            docstatus=1,
            document_no=f"SO-NOTE-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_order = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 1),
            docstatus=1,
            document_no=f"SO-OTHER-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        database.session.add_all([source_order, unrelated_order])
        database.session.flush()
        source_delivery = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 5),
            docstatus=1,
            document_no=f"DN-NOTE-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            sales_order_id=source_order.id,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_usd_delivery = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 6),
            docstatus=1,
            document_no=f"DN-USD-OTHER-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_eur_delivery = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 6),
            docstatus=1,
            document_no=f"DN-EUR-OTHER-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="EUR",
            base_currency="NIO",
        )
        database.session.add_all([source_delivery, unrelated_usd_delivery, unrelated_eur_delivery])
        database.session.flush()
        source_invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"SI-NOTE-{suffix}",
            document_type="sales_invoice",
            customer_id=customer.id,
            customer_name=customer.name,
            sales_order_id=source_order.id,
            delivery_note_id=source_delivery.id,
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36.5"),
            grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        database.session.add(source_invoice)
        database.session.commit()
        return {
            "app": app,
            "customer_id": str(customer.id),
            "invoice_id": str(source_invoice.id),
            "order_id": str(source_order.id),
            "unrelated_order_id": str(unrelated_order.id),
            "delivery_id": str(source_delivery.id),
            "unrelated_usd_delivery_id": str(unrelated_usd_delivery.id),
            "unrelated_eur_delivery_id": str(unrelated_eur_delivery.id),
        }


def _credit_note_form(sources: dict[str, str], **overrides: str) -> dict[str, str]:
    """Return the smallest form payload for a sales credit note."""
    data = {
        "company": "cacao",
        "customer_id": sources["customer_id"],
        "posting_date": "2026-05-20",
        "document_type": "sales_credit_note",
        "from_invoice": sources["invoice_id"],
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("delivery_key", ["unrelated_eur_delivery_id", "unrelated_usd_delivery_id"])
def test_rejects_delivery_from_another_invoice_flow(sales_note_sources, delivery_key):
    """Equal or foreign currencies do not make a different delivery part of the source flow."""
    sources = sales_note_sources
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/sales/sales-invoice/new",
            method="POST",
            data=_credit_note_form(sources, from_note=sources[delivery_key]),
        ),
    ):
        before = database.session.execute(database.select(SalesInvoice.id)).scalars().all()
        with pytest.raises(ValueError, match="no pertenece al flujo de la factura origen"):
            services._prepare_sales_invoice_creation()
        after = database.session.execute(database.select(SalesInvoice.id)).scalars().all()

    assert after == before


def test_rejects_order_from_another_invoice_flow(sales_note_sources):
    """A matching-currency order from another flow is rejected before invoice creation."""
    sources = sales_note_sources
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/sales/sales-invoice/new",
            method="POST",
            data=_credit_note_form(sources, from_order=sources["unrelated_order_id"]),
        ),
    ):
        before = database.session.execute(database.select(SalesInvoice.id)).scalars().all()
        with pytest.raises(ValueError, match="no pertenece al flujo de la factura origen"):
            services._prepare_sales_invoice_creation()
        after = database.session.execute(database.select(SalesInvoice.id)).scalars().all()

    assert after == before


def test_valid_source_flow_uses_invoice_currency_and_rate(sales_note_sources):
    """A valid note inherits its reversal invoice currency and exchange rate."""
    sources = sales_note_sources
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/sales/sales-invoice/new",
            method="POST",
            data=_credit_note_form(sources, from_order=sources["order_id"], from_note=sources["delivery_id"]),
        ),
    ):
        context = services._prepare_sales_invoice_creation()
        note = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 20),
            document_type="sales_credit_note",
            transaction_currency="USD",
        )
        services._set_sales_invoice_totals(note, Decimal("25"), Decimal("25"), context["reversal_invoice"])

    assert context["reversal_invoice"].id == sources["invoice_id"]
    assert note.transaction_currency == "USD"
    assert note.exchange_rate == Decimal("36.5")


def test_rejects_note_currency_that_differs_from_reversal_invoice(sales_note_sources):
    """The outstanding comparison cannot silently use another transaction currency."""
    sources = sales_note_sources
    app = sources["app"]
    with app.app_context():
        invoice = database.session.get(SalesInvoice, sources["invoice_id"])
        assert invoice is not None
        note = SalesInvoice(
            company="cacao",
            customer_id=sources["customer_id"],
            document_type="sales_credit_note",
            transaction_currency="EUR",
            reversal_of=invoice.id,
            sales_order_id=sources["order_id"],
            delivery_note_id=sources["delivery_id"],
        )
        with pytest.raises(ValueError, match="deben usar la misma moneda"):
            services._validate_sales_reversal_document(note)
