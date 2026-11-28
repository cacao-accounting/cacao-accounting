# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1019: el cierre de saldo valida la línea contra el documento autorizado.

La guardia de la ruta autoriza la compañía de la cabecera fuente. El cierre
debe rechazar una línea de otro documento, aunque su compañía tenga datos
accesibles para el usuario, y no mutar el estado de una línea ajena.
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
    DocumentLineFlowState,
    DocumentRelation,
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    SalesOrder,
    SalesOrderItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_flow.service import DocumentFlowError, close_document_balances, close_line_balance

CLOSE_URL = "/api/document-flow/close-line"


@pytest.fixture
def close_line_scenario():
    """Create one order per company and a seller scoped to alpha."""
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
                UOM(code="Unidad", name="Unidad"),
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
        alpha_order = SalesOrder(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"SO-A-{suffix}",
            customer_name="Cliente Alfa",
        )
        beta_order = SalesOrder(
            company="beta",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"SO-B-{suffix}",
            customer_name="Cliente Beta",
        )
        database.session.add_all([alpha_order, beta_order])
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code=f"ITEM-A-{suffix}",
                    name="Producto Alfa",
                    item_type="goods",
                    is_stock_item=False,
                    default_uom="Unidad",
                ),
                Item(
                    code=f"ITEM-B-{suffix}",
                    name="Producto Beta",
                    item_type="goods",
                    is_stock_item=False,
                    default_uom="Unidad",
                ),
            ]
        )
        alpha_line = SalesOrderItem(
            sales_order_id=alpha_order.id,
            item_code=f"ITEM-A-{suffix}",
            item_name="Producto Alfa",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="Unidad",
            rate=Decimal("5"),
            amount=Decimal("50"),
        )
        beta_line = SalesOrderItem(
            sales_order_id=beta_order.id,
            item_code=f"ITEM-B-{suffix}",
            item_name="Producto Beta",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="Unidad",
            rate=Decimal("7"),
            amount=Decimal("70"),
        )
        database.session.add_all([alpha_line, beta_line])
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
        sales_role = Roles(name=f"close-line-{suffix}", note="Consulta de ventas")
        database.session.add(sales_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True, edit=True),
                RolesUser(user_id=f"seller-{suffix}", role_id=sales_role.id, active=True),
                UserCompanyAccess(user_id=f"seller-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "seller": f"seller-{suffix}",
            "alpha_order": alpha_order.id,
            "alpha_line": alpha_line.id,
            "beta_order": beta_order.id,
            "beta_line": beta_line.id,
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


def test_close_line_rejects_a_line_from_another_document(close_line_scenario):
    """A header in alpha cannot be used to close a beta line."""
    app, ids = close_line_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(
        CLOSE_URL,
        json={
            "source_document_type": "sales_order",
            "source_document_id": ids["alpha_order"],
            "source_row_id": ids["beta_line"],
            "target_document_type": "sales_invoice",
            "reason": "Cierre cruzado",
        },
    )

    assert response.status_code == 400
    with app.app_context():
        state = database.session.execute(
            database.select(DocumentLineFlowState).filter_by(
                source_id=ids["alpha_order"],
                target_type="sales_invoice",
            )
        ).scalar_one_or_none()
        assert state is None


def test_close_line_rejects_consistent_foreign_document_and_line(close_line_scenario):
    """A correctly paired foreign source and line still fail the user's company ACL."""
    app, ids = close_line_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(
        CLOSE_URL,
        json={
            "source_document_type": "sales_order",
            "source_document_id": ids["beta_order"],
            "source_row_id": ids["beta_line"],
            "target_document_type": "sales_invoice",
            "reason": "Cierre de compañía no autorizada",
        },
    )

    assert response.status_code == 403
    with app.app_context():
        state = database.session.execute(
            database.select(DocumentLineFlowState).filter_by(
                source_id=ids["beta_order"],
                target_type="sales_invoice",
            )
        ).scalar_one_or_none()
        assert state is None


def test_service_rejects_a_line_from_another_document(close_line_scenario):
    """The service keeps the same invariant without the HTTP guard."""
    app, ids = close_line_scenario

    with app.app_context():
        with pytest.raises(DocumentFlowError):
            close_line_balance(
                source_type="sales_order",
                source_id=ids["alpha_order"],
                source_item_id=ids["beta_line"],
                target_type="sales_invoice",
                reason="Cierre cruzado",
            )


def test_close_line_accepts_its_own_line(close_line_scenario):
    """The documented closure path still works for the authorized line."""
    app, ids = close_line_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(
        CLOSE_URL,
        json={
            "source_document_type": "sales_order",
            "source_document_id": ids["alpha_order"],
            "source_row_id": ids["alpha_line"],
            "target_document_type": "sales_invoice",
            "reason": "Cierre autorizado",
        },
    )

    assert response.status_code == 200
    assert Decimal(str(response.get_json()["state"]["closed_qty"])) == Decimal("10")


def test_close_document_ignores_draft_target_reservations(close_line_scenario):
    """Document-wide and per-line closure use the same pending-quantity rule."""
    app, ids = close_line_scenario
    with app.app_context():
        order = database.session.get(SalesOrder, ids["alpha_order"])
        assert order is not None
        draft_invoice = SalesInvoice(company="alpha", posting_date=date(2026, 5, 11), docstatus=0)
        database.session.add(draft_invoice)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_order",
                source_id=order.id,
                source_item_id=ids["alpha_line"],
                target_type="sales_invoice",
                target_id=draft_invoice.id,
                target_item_id="",
                company="alpha",
                qty=Decimal("10"),
                qty_in_base_uom=Decimal("10"),
                uom="Unidad",
                relation_type="billing",
                status="active",
            )
        )
        database.session.flush()

        closed = close_document_balances(
            source_type="sales_order",
            source_id=order.id,
            target_type="sales_invoice",
            reason="Saldo no facturable cerrado",
        )

        assert len(closed) == 1
        assert closed[0]["source_item_id"] == ids["alpha_line"]
        assert Decimal(str(closed[0]["closed_qty"])) == Decimal("10")
