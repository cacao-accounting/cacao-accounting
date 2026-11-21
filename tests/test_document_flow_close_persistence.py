# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1466: el cierre de flujo persiste antes de responder 200.

Las rutas de cierre hacían flush del estado y terminaban sin commit; una
consulta posterior no encontraba el estado. Ahora la respuesta de éxito
solo se emite con el cambio confirmado.
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
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    SalesOrder,
    SalesOrderItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

CLOSE_LINE_URL = "/api/document-flow/close-line"
CLOSE_DOCUMENT_URL = "/api/document-flow/close-document"


@pytest.fixture
def close_persistence_scenario():
    """Create two approved sales orders with one line each for the seller."""
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
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        item = Item(
            code=f"ITEM-{suffix}",
            name="Producto",
            item_type="goods",
            is_stock_item=False,
            default_uom="Unidad",
        )
        database.session.add(item)
        database.session.flush()
        orders = []
        for index in (1, 2):
            order = SalesOrder(
                company="alpha",
                posting_date=date(2026, 5, 10),
                docstatus=1,
                document_no=f"SO-{index}-{suffix}",
                customer_name="Cliente Alfa",
            )
            database.session.add(order)
            database.session.flush()
            line = SalesOrderItem(
                sales_order_id=order.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("50"),
                qty_in_base_uom=Decimal("50"),
                uom="Unidad",
                rate=Decimal("5"),
                amount=Decimal("250"),
            )
            database.session.add(line)
            database.session.flush()
            orders.append({"order_id": order.id, "line_id": line.id})
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
        sales_role = Roles(name=f"close-persist-{suffix}", note="Cierre documental")
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
        ids = {"seller": f"seller-{suffix}", "orders": orders}

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


def _persisted_state(app, order_id: str, target_type: str) -> DocumentLineFlowState | None:
    """Read the flow state from a fresh session after the request teardown."""
    with app.app_context():
        return database.session.execute(
            database.select(DocumentLineFlowState).filter_by(source_id=order_id, target_type=target_type)
        ).scalar_one_or_none()


def test_close_line_persists_the_closed_balance(close_persistence_scenario):
    """The single-line closure survives the request session."""
    app, ids = close_persistence_scenario
    order = ids["orders"][0]
    client = _authenticated_client(app, ids["seller"])

    response = client.post(
        CLOSE_LINE_URL,
        json={
            "source_document_type": "sales_order",
            "source_document_id": order["order_id"],
            "source_row_id": order["line_id"],
            "target_document_type": "sales_invoice",
            "reason": "Cierre manual",
        },
    )

    assert response.status_code == 200
    assert Decimal(str(response.get_json()["state"]["closed_qty"])) == Decimal("50")
    state = _persisted_state(app, order["order_id"], "sales_invoice")
    assert state is not None
    assert Decimal(str(state.closed_qty)) == Decimal("50")
    assert Decimal(str(state.pending_qty)) == Decimal("0")


def test_close_document_persists_every_closed_line(close_persistence_scenario):
    """The whole-document closure creates a durable state row."""
    app, ids = close_persistence_scenario
    order = ids["orders"][1]
    client = _authenticated_client(app, ids["seller"])

    response = client.post(
        CLOSE_DOCUMENT_URL,
        json={
            "source_document_type": "sales_order",
            "source_document_id": order["order_id"],
            "target_document_type": "delivery_note",
            "reason": "Cierre manual del documento",
        },
    )

    assert response.status_code == 200
    assert Decimal(str(response.get_json()["states"][0]["closed_qty"])) == Decimal("50")
    state = _persisted_state(app, order["order_id"], "delivery_note")
    assert state is not None
    assert Decimal(str(state.closed_qty)) == Decimal("50")
    assert Decimal(str(state.pending_qty)) == Decimal("0")
