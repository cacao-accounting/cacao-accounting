# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1511: el precargado de pagos exige acceso a la compañía del documento.

`GET /cash_management/payment/new?from_purchase_invoice=<id>` no debe renderizar
datos de una factura de otra compañía antes de validar el alcance de Caja.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    PurchaseInvoice,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def payment_preload_scenario():
    """Create a foreign purchase invoice and scoped cash readers."""
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
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name=f"Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        invoice = PurchaseInvoice(
            company="beta",
            document_type="purchase_invoice",
            document_no="SECRET-INV-007",
            supplier_name="Proveedor Secreto",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            total=Decimal("1234.56"),
            grand_total=Decimal("1234.56"),
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id=f"alpha-{suffix}",
                    user=f"alpha-{suffix}",
                    name="Caja Alfa",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"beta-{suffix}",
                    user=f"beta-{suffix}",
                    name="Caja Beta",
                    password=b"unused",
                    active=True,
                    company="beta",
                ),
                User(
                    id=f"denied-{suffix}",
                    user=f"denied-{suffix}",
                    name="Sin Caja",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        role = Roles(name=f"cash-reader-{suffix}", note="Consulta de caja")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=f"alpha-{suffix}", role_id=role.id, active=True),
                RolesUser(user_id=f"beta-{suffix}", role_id=role.id, active=True),
                UserCompanyAccess(user_id=f"alpha-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"beta-{suffix}", company_code="beta"),
                UserCompanyAccess(user_id=f"denied-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "invoice": invoice.id,
            "alpha": f"alpha-{suffix}",
            "beta": f"beta-{suffix}",
            "denied": f"denied-{suffix}",
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


def test_payment_preload_rejects_foreign_invoice(payment_preload_scenario):
    """A cash reader from Alpha cannot render Beta's invoice."""
    app, ids = payment_preload_scenario
    client = _authenticated_client(app, ids["alpha"])

    response = client.get(f"/cash_management/payment/new?from_purchase_invoice={ids['invoice']}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "SECRET-INV-007" not in body
    assert "1234.56" not in body


def test_payment_preload_rejects_user_without_cash_permission(payment_preload_scenario):
    """A user without cash permission receives 403 even for its own company."""
    app, ids = payment_preload_scenario
    client = _authenticated_client(app, ids["denied"])

    response = client.get(f"/cash_management/payment/new?from_purchase_invoice={ids['invoice']}")

    assert response.status_code == 403
    assert "SECRET-INV-007" not in response.get_data(as_text=True)


def test_payment_preload_accepts_authorized_company(payment_preload_scenario):
    """The reader of Beta receives the invoice data in the form."""
    app, ids = payment_preload_scenario
    client = _authenticated_client(app, ids["beta"])

    response = client.get(f"/cash_management/payment/new?from_purchase_invoice={ids['invoice']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "SECRET-INV-007" in body
    assert "1234.56" in body
