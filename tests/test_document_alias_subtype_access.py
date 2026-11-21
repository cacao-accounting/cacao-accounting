# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#998: los alias de notas validan compañía y subtipo real.

`sales_credit_note`, `sales_debit_note`, `sales_return` y sus pares de compra
comparten modelo con la factura. La API debe exigir el permiso del alias y
rechazar un documento que no sea del subtipo solicitado.
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
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)

STATUS_URL = "/api/document-flow/recalculate-status/{document_type}/{document_id}"


@pytest.fixture
def document_alias_scenario():
    """Create a plain invoice, a credit note and a foreign credit note."""
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
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id=f"seller-{suffix}",
                    user=f"seller-{suffix}",
                    name="Vendedor",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"outsider-{suffix}",
                    user=f"outsider-{suffix}",
                    name="Sin ventas",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        invoice = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"INV-{suffix}",
            document_type="sales_invoice",
            customer_name="Cliente Alfa",
        )
        credit_note = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 11),
            docstatus=1,
            document_no=f"CN-{suffix}",
            document_type="sales_credit_note",
            customer_name="Cliente Alfa",
        )
        foreign_note = SalesInvoice(
            company="beta",
            posting_date=date(2026, 5, 12),
            docstatus=1,
            document_no=f"CN-B-{suffix}",
            document_type="sales_credit_note",
            customer_name="Cliente Beta",
        )
        database.session.add_all([invoice, credit_note, foreign_note])
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        sales_role = Roles(name=f"alias-sales-{suffix}", note="Consulta de ventas")
        database.session.add(sales_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesUser(user_id=f"seller-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"outsider-{suffix}", role_id=sales_role.id, active=False),
                UserCompanyAccess(user_id=f"seller-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"outsider-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "seller": f"seller-{suffix}",
            "outsider": f"outsider-{suffix}",
            "invoice": invoice.id,
            "credit_note": credit_note.id,
            "foreign_note": foreign_note.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_credit_note_alias_rejects_a_plain_invoice(document_alias_scenario):
    """The alias cannot serve a document of another subtype."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["invoice"]))

    assert response.status_code == 404


def test_plain_invoice_alias_rejects_a_credit_note(document_alias_scenario):
    """The reverse mismatch is rejected as well."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_invoice", document_id=ids["credit_note"]))

    assert response.status_code == 404


def test_credit_note_alias_accepts_the_matching_subtype(document_alias_scenario):
    """A real credit note keeps the documented read path."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["credit_note"]))

    assert response.status_code == 200


def test_credit_note_alias_enforces_company_scope(document_alias_scenario):
    """The alias keeps the company-scoped sales permission."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["foreign_note"]))

    assert response.status_code == 403


def test_credit_note_alias_requires_the_sales_module(document_alias_scenario):
    """A user without a current sales assignment is rejected."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["outsider"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["credit_note"]))

    assert response.status_code == 403
