# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1399: la prevalidación de conciliación compara el tercero seleccionado.

Una hoja coherente entre pago y factura, pero de otro cliente, no debe mostrarse
como válida si la pantalla tiene seleccionado un tercero distinto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.api.line_import import (
    _payment_reconciliation_party_context,
    _validate_payment_reconciliation_row,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Party,
    PaymentEntry,
    SalesInvoice,
    database,
)


@pytest.fixture
def payment_import_party_scenario():
    """Create a payment and invoice for Alice plus a Bob party."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="cash", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        alice = Party(code=f"ALICE-{suffix}", name="Alice", is_customer=True, is_active=True)
        bob = Party(code=f"BOB-{suffix}", name="Bob", is_customer=True, is_active=True)
        database.session.add_all([alice, bob])
        database.session.flush()
        payment = PaymentEntry(
            company="alpha",
            payment_type="receive",
            party_type="customer",
            party_id=alice.id,
            party_name="Alice",
            currency="NIO",
            paid_amount=Decimal("100"),
            base_paid_amount=Decimal("100"),
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        invoice = SalesInvoice(
            company="alpha",
            document_type="sales_invoice",
            document_no="INV-ALICE",
            customer_id=alice.id,
            customer_name="Alice",
            transaction_currency="NIO",
            base_currency="NIO",
            posting_date=date(2026, 5, 9),
            docstatus=1,
            total=Decimal("100"),
            grand_total=Decimal("100"),
        )
        database.session.add_all([payment, invoice])
        database.session.commit()
        ids = {
            "payment": payment.id,
            "invoice": invoice.id,
            "alice": alice.id,
            "bob": bob.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _row(ids) -> dict[str, str]:
    """Build one reconciliation import row."""
    return {
        "payment_id": ids["payment"],
        "reference_type": "sales_invoice",
        "reference_id": ids["invoice"],
        "allocated_amount": "10",
    }


def test_row_rejects_selected_party_that_differs_from_payment(payment_import_party_scenario):
    """A row from Alice is invalid when the screen selects Bob."""
    app, ids = payment_import_party_scenario

    with app.app_context():
        errors: list[dict[str, object]] = []
        _validate_payment_reconciliation_row(_row(ids), 1, "alpha", errors, party_type="customer", party_id=ids["bob"])

    assert any("tercero seleccionado" in str(error["message"]) for error in errors)


def test_row_accepts_selected_party_matching_payment(payment_import_party_scenario):
    """The same row is valid for its own party and for the legacy empty filter."""
    app, ids = payment_import_party_scenario

    with app.app_context():
        matching_errors: list[dict[str, object]] = []
        _validate_payment_reconciliation_row(
            _row(ids), 1, "alpha", matching_errors, party_type="customer", party_id=ids["alice"]
        )
        legacy_errors: list[dict[str, object]] = []
        _validate_payment_reconciliation_row(_row(ids), 1, "alpha", legacy_errors)

    assert matching_errors == []
    assert legacy_errors == []


def test_party_context_rejects_unknown_selected_type(payment_import_party_scenario):
    """The validation context only accepts customer or supplier filters."""
    app, _ids = payment_import_party_scenario

    with app.app_context():
        party_type, party_id, error = _payment_reconciliation_party_context(
            "payment_reconciliation", {"filters": {"party_type": "debtor", "party_id": "X"}}
        )

    assert (party_type, party_id) == ("", "")
    assert error is not None
    assert error[1] == 400
