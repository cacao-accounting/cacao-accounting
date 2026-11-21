# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1433: el precheck de factura duplicada usa la misma clave que la base.

La restricción única es global por proveedor y número normalizado, sin compañía.
El servicio debe detectar el duplicado antes del flush y normalizar el número.
"""

from __future__ import annotations

from datetime import date
from importlib import import_module
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras.services import _validate_duplicate_supplier_invoice
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Modules,
    Party,
    PurchaseInvoice,
    database,
)


@pytest.fixture
def duplicate_invoice_scenario():
    """Create an invoice with a trailing-space supplier number in company A."""
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
                Modules(module="purchases", default=True, enabled=True),
                Entity(
                    code="co1",
                    name="CO1",
                    company_name=f"Compañía 1 {suffix}",
                    tax_id=f"TAX-1-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="co2",
                    name="CO2",
                    company_name=f"Compañía 2 {suffix}",
                    tax_id=f"TAX-2-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        supplier = Party(code=f"SUP-{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        database.session.add(
            CompanyParty(
                company="co2",
                party_id=supplier.id,
                is_active=True,
                allow_purchase_invoice_without_order=True,
                allow_purchase_invoice_without_receipt=True,
            )
        )
        existing = PurchaseInvoice(
            company="co1",
            document_type="purchase_invoice",
            document_no="PI-1",
            supplier_id=supplier.id,
            supplier_name="Proveedor",
            supplier_invoice_no="INV-1 ",
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        database.session.add(existing)
        database.session.commit()
        ids = {
            "supplier": supplier.id,
            "existing": existing.id,
            "existing_key": existing.supplier_invoice_key,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_listener_normalizes_the_supplier_invoice_key(duplicate_invoice_scenario):
    """The stored unique key drops surrounding whitespace."""
    app, ids = duplicate_invoice_scenario

    with app.app_context():
        assert ids["existing_key"] == "INV-1"


def test_precheck_detects_duplicate_with_different_spacing(duplicate_invoice_scenario):
    """The precheck compares the normalized key, not the raw number."""
    app, ids = duplicate_invoice_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            _validate_duplicate_supplier_invoice(ids["supplier"], "INV-1")


def test_precheck_is_global_across_companies(duplicate_invoice_scenario):
    """The duplicate is detected before inserting in another company."""
    app, ids = duplicate_invoice_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            _validate_duplicate_supplier_invoice(ids["supplier"], "INV-1")
        _validate_duplicate_supplier_invoice(ids["supplier"], "INV-2")
        _validate_duplicate_supplier_invoice(ids["supplier"], "INV-1", exclude_id=ids["existing"])


def test_creation_rejects_third_invoice_before_materializing_legacy_null_key_group(duplicate_invoice_scenario, monkeypatch):
    """A third invoice is rejected before construction when legacy keys are null."""
    app, ids = duplicate_invoice_scenario
    services = import_module("cacao_accounting.compras.services")
    constructions = []
    monkeypatch.setattr(services, "exige_acceso_compania", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_build_purchase_invoice", lambda context: constructions.append(context))

    with (
        app.app_context(),
        app.test_request_context(
            "/purchase-invoice/new",
            method="POST",
            data={
                "company": "co2",
                "supplier_id": ids["supplier"],
                "supplier_invoice_no": "LEGACY-1",
                "posting_date": "2026-05-12",
                "transaction_currency": "NIO",
            },
        ),
    ):
        for company, document_no in (("co1", "LEG-1"), ("co2", "LEG-2")):
            database.session.execute(
                database.insert(PurchaseInvoice).values(
                    company=company,
                    document_type="purchase_invoice",
                    document_no=document_no,
                    supplier_id=ids["supplier"],
                    supplier_name="Proveedor",
                    supplier_invoice_no="\tLEGACY-1 \t",
                    supplier_invoice_key=None,
                    posting_date=date(2026, 5, 11),
                    docstatus=1,
                )
            )
        database.session.commit()

        created = services._create_purchase_invoice_from_request()
        invoice_ids = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()

    assert created is None
    assert constructions == []
    assert len(invoice_ids) == 3
