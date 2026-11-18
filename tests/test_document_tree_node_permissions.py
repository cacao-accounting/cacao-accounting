# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1407: cada nodo del árbol documental exige permiso de su módulo.

El árbol se autorizaba solo por la raíz. Un usuario de Caja podía ver los
metadatos de una factura de Ventas relacionada aunque el detalle directo de
esa factura le respondiera 403.
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
    DocumentRelation,
    Entity,
    Modules,
    PaymentEntry,
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def document_tree_scope_scenario():
    """Create an invoice linked to a payment and two scoped readers."""
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
                Modules(module="cash", default=False, enabled=True),
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
        invoice = SalesInvoice(
            company="alpha",
            document_type="sales_invoice",
            document_no="INV1",
            customer_name="Sensitive Customer",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            total=Decimal("12345.67"),
            grand_total=Decimal("12345.67"),
        )
        payment = PaymentEntry(
            company="alpha",
            payment_type="receive",
            document_no="PAY1",
            party_name="Pago Autorizado",
            posting_date=date(2026, 5, 11),
            docstatus=1,
        )
        database.session.add_all([invoice, payment])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice.id,
                target_type="payment_entry",
                target_id=payment.id,
                company="alpha",
                qty=1,
                relation_type="payment",
            )
        )
        database.session.add_all(
            [
                User(
                    id=f"cash-only-{suffix}",
                    user=f"cash-only-{suffix}",
                    name="Caja",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"sales-cash-{suffix}",
                    user=f"sales-cash-{suffix}",
                    name="Ventas y Caja",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        cash_module = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        sales_role = Roles(name=f"tree-sales-{suffix}", note="Consulta de ventas")
        cash_role = Roles(name=f"tree-cash-{suffix}", note="Consulta de caja")
        database.session.add_all([sales_role, cash_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=cash_role.id, module_id=cash_module, access=True, view=True),
                RolesUser(user_id=f"cash-only-{suffix}", role_id=cash_role.id, active=True),
                RolesUser(user_id=f"sales-cash-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"sales-cash-{suffix}", role_id=cash_role.id, active=True),
                UserCompanyAccess(user_id=f"cash-only-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"sales-cash-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "invoice": invoice.id,
            "payment": payment.id,
            "cash_only": f"cash-only-{suffix}",
            "sales_cash": f"sales-cash-{suffix}",
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


def _tree_path(ids) -> str:
    """Build the upstream tree URL for the payment."""
    return f"/api/document-flow/tree?document_type=payment_entry&document_id={ids['payment']}&direction=upstream"


def test_tree_hides_invoice_nodes_without_module_permission(document_tree_scope_scenario):
    """A cash-only reader does not receive invoice metadata from the tree."""
    app, ids = document_tree_scope_scenario
    client = _authenticated_client(app, ids["cash_only"])

    response = client.get(_tree_path(ids))

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["invoice"] not in body
    assert "Sensitive Customer" not in body
    assert "12345.67" not in body


def test_tree_shows_invoice_nodes_with_both_modules(document_tree_scope_scenario):
    """A reader with Sales and Cash keeps the related invoice node."""
    app, ids = document_tree_scope_scenario
    client = _authenticated_client(app, ids["sales_cash"])

    response = client.get(_tree_path(ids))

    assert response.status_code == 200
    payload = response.get_json()
    invoice_nodes = [node for node in payload["upstream"] if node.get("document_type") == "sales_invoice"]
    assert invoice_nodes
    assert invoice_nodes[0]["document_id"] == ids["invoice"]
    assert invoice_nodes[0]["party_name"] == "Sensitive Customer"
