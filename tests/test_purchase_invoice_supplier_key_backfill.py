# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""N13: las facturas históricas reciben su clave de duplicidad.

El listener de `PurchaseInvoice` solo actúa en altas y actualizaciones. Las
filas heredadas con `supplier_invoice_key` nula quedaban fuera del índice
único; el backfill las incorpora cuando el número es inequívoco y deja los
duplicados históricos en nulo para revisión manual.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Party,
    PurchaseInvoice,
    database,
)
from cacao_accounting.database.helpers import _ensure_purchase_invoice_supplier_key


@pytest.fixture
def supplier_invoice_backfill_scenario():
    """Seed legacy invoices whose supplier key was not populated."""
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
        definitions = {
            "unique": ("UNICA-1", 1),
            "duplicate_a": ("DUP-1", 1),
            "duplicate_b": ("DUP-1", 1),
            "cancelled": ("CANCELADA-1", 2),
            "blank": (None, 1),
        }
        ids = {}
        for name, (number, docstatus) in definitions.items():
            inserted = database.session.execute(
                database.insert(PurchaseInvoice).values(
                    company="alpha",
                    document_type="purchase_invoice",
                    document_no=f"PI-{name}-{suffix}",
                    supplier_id=supplier.id,
                    supplier_name=supplier.name,
                    supplier_invoice_no=number,
                    posting_date=date(2026, 5, 10),
                    docstatus=docstatus,
                )
            )
            ids[name] = inserted.inserted_primary_key[0]
        database.session.commit()

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_backfill_sets_only_unambiguous_supplier_keys(supplier_invoice_backfill_scenario):
    """Unique numbers get a key; duplicates, cancelled and blank stay null."""
    app, ids = supplier_invoice_backfill_scenario

    with app.app_context():
        _ensure_purchase_invoice_supplier_key()
        _ensure_purchase_invoice_supplier_key()

        keys = {
            invoice_id: database.session.get(PurchaseInvoice, invoice_id).supplier_invoice_key for invoice_id in ids.values()
        }

    assert keys[ids["unique"]] == "UNICA-1"
    assert keys[ids["duplicate_a"]] is None
    assert keys[ids["duplicate_b"]] is None
    assert keys[ids["cancelled"]] is None
    assert keys[ids["blank"]] is None
