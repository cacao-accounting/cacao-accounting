# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#998 QA2 B11: los nodos del árbol respetan el subtipo documental.

Un alias de nota enlazado a una factura común no debe exponer metadatos del
subtipo equivocado en el panel de trazabilidad.
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
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_flow.tree import build_document_flow_tree, get_document_node


@pytest.fixture
def tree_subtype_scenario():
    """Create a credit note linked to a plain invoice under two relation types."""
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
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        credit_note = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"CN-{suffix}",
            document_type="sales_credit_note",
            customer_name="Cliente Alfa",
        )
        invoice = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"INV-{suffix}",
            document_type="sales_invoice",
            customer_name="Cliente Alfa",
        )
        database.session.add_all([credit_note, invoice])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_credit_note",
                source_id=credit_note.id,
                target_type="sales_return",
                target_id=invoice.id,
                company="alpha",
                qty=Decimal("1"),
                relation_type="reference",
                status="active",
            )
        )
        database.session.add(
            User(
                id=f"seller-{suffix}",
                user=f"seller-{suffix}",
                name="Vendedor",
                password=b"unused",
                active=True,
                company="alpha",
            )
        )
        database.session.flush()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        sales_role = Roles(name=f"tree-subtype-{suffix}", note="Consulta de ventas")
        database.session.add(sales_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesUser(user_id=f"seller-{suffix}", role_id=sales_role.id, active=True),
                UserCompanyAccess(user_id=f"seller-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "seller": f"seller-{suffix}",
            "credit_note": credit_note.id,
            "invoice": invoice.id,
            "invoice_no": invoice.document_no,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(app, user_id: str):
    """Log the requested user into the current request context."""
    from flask_login import login_user

    login_user(database.session.get(User, user_id), remember=False, force=True)


def test_tree_hides_a_related_document_with_a_mismatched_subtype(tree_subtype_scenario):
    """A relation declared as sales_return does not expose the plain invoice."""
    app, ids = tree_subtype_scenario

    with app.test_request_context("/"):
        _login(app, ids["seller"])
        tree = build_document_flow_tree("sales_credit_note", ids["credit_note"], direction="downstream")

    assert tree["downstream"] == []


def test_document_node_does_not_render_metadata_of_another_subtype(tree_subtype_scenario):
    """The node falls back to the requested id when the subtype does not match."""
    app, ids = tree_subtype_scenario

    with app.test_request_context("/"):
        _login(app, ids["seller"])
        node = get_document_node("sales_return", ids["invoice"])

    assert node["document_no"] == ids["invoice"]
    assert node["document_no"] != ids["invoice_no"]
    assert node["status"] is None
    assert node["party_name"] in (None, "")
