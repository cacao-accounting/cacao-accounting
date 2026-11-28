# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1076: un replay de idempotencia debe pertenecer a la misma factura.

La clave es única en `PurchaseReconciliation`; reutilizarla con otra factura
debe fallar como conflicto y no devolver la evidencia económica de la primera.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import (
    PurchaseReconciliationError,
    _find_reconciliation_by_idempotency_key,
    reconcile_purchase_invoice,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Party,
    PurchaseInvoice,
    PurchaseReconciliation,
    database,
)


@pytest.fixture
def reconciliation_idempotency_scenario():
    """Create two invoices and one reconciliation registered under a key."""
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
        supplier = Party(code=f"SUP-{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        invoice_a = PurchaseInvoice(
            company="alpha",
            document_type="purchase_invoice",
            document_no=f"PI-A-{suffix}",
            supplier_id=supplier.id,
            supplier_name="Proveedor",
            supplier_invoice_no=f"A-{suffix}",
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        invoice_b = PurchaseInvoice(
            company="alpha",
            document_type="purchase_invoice",
            document_no=f"PI-B-{suffix}",
            supplier_id=supplier.id,
            supplier_name="Proveedor",
            supplier_invoice_no=f"B-{suffix}",
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        database.session.add_all([invoice_a, invoice_b])
        database.session.flush()
        reconciliation = PurchaseReconciliation(
            company="alpha",
            purchase_invoice_id=invoice_a.id,
            idempotency_key=f"retry-{suffix}",
            status="reconciled",
            matched_amount=Decimal("100"),
        )
        database.session.add(reconciliation)
        database.session.commit()
        ids = {
            "invoice_a": invoice_a.id,
            "invoice_b": invoice_b.id,
            "key": reconciliation.idempotency_key,
            "reconciliation": reconciliation.id,
            "matched_amount": reconciliation.matched_amount,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_same_invoice_replay_returns_the_registered_reconciliation(reconciliation_idempotency_scenario):
    """A retry of the original invoice keeps the idempotent result."""
    app, ids = reconciliation_idempotency_scenario

    with app.app_context():
        result = reconcile_purchase_invoice(ids["invoice_a"], ids["key"])

    assert result.reconciliation_id == ids["reconciliation"]
    assert result.matched_amount == ids["matched_amount"]


def test_replay_for_another_invoice_is_a_conflict(reconciliation_idempotency_scenario):
    """A key owned by invoice A cannot return evidence for invoice B."""
    app, ids = reconciliation_idempotency_scenario

    with app.app_context():
        with pytest.raises(PurchaseReconciliationError):
            reconcile_purchase_invoice(ids["invoice_b"], ids["key"])

        assert (
            database.session.execute(
                database.select(PurchaseReconciliation).filter_by(purchase_invoice_id=ids["invoice_b"])
            ).scalar_one_or_none()
            is None
        )


def test_replay_lookup_runs_after_locking_the_invoice(reconciliation_idempotency_scenario, monkeypatch):
    """The replay waits for the invoice lock before resolving the key (#1076)."""
    app, ids = reconciliation_idempotency_scenario
    from cacao_accounting.compras import purchase_reconciliation_service as service

    from cacao_accounting.database import database

    order: list[str] = []
    original_find = service._find_reconciliation_by_idempotency_key
    original_get = type(database.session).get

    def spy_find(key: str):
        order.append("find")
        return original_find(key)

    def spy_get(self, entity, ident, **kwargs):
        order.append("get")
        return original_get(self, entity, ident, **kwargs)

    monkeypatch.setattr(service, "_find_reconciliation_by_idempotency_key", spy_find)
    monkeypatch.setattr(type(database.session), "get", spy_get)

    with app.app_context():
        result = service.reconcile_purchase_invoice(ids["invoice_a"], ids["key"])

    assert result.reconciliation_id == ids["reconciliation"]
    assert order[:2] == ["get", "find"]


def test_cancelled_key_remains_visible_to_the_replay_lookup(reconciliation_idempotency_scenario):
    """Una clave cancelada se detecta como conflicto y no choca con la unicidad."""
    app, ids = reconciliation_idempotency_scenario

    with app.app_context():
        reconciliation = database.session.get(PurchaseReconciliation, ids["reconciliation"])
        reconciliation.status = "cancelled"
        database.session.commit()

        assert _find_reconciliation_by_idempotency_key(ids["key"]) is not None
