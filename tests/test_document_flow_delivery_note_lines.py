# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1410: Ventas e Inventario pueden cargar líneas de una nota de entrega.

La lectura directa de una nota de entrega acepta cualquiera de los dos módulos;
el endpoint de líneas pendientes debe aplicar la misma política para que Ventas
pueda facturar la entrega.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DeliveryNote,
    DeliveryNoteItem,
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    UOM,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def delivery_note_lines_scenario():
    """Create an approved delivery note with one line and scoped readers."""
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
                Modules(module="inventory", default=False, enabled=True),
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
        database.session.add(UOM(code="EA", name="Each", is_active=True))
        database.session.flush()
        database.session.add(
            Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        )
        database.session.flush()
        note = DeliveryNote(
            company="alpha",
            document_no="DN1",
            customer_name="Cliente Alfa",
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        database.session.add(note)
        database.session.flush()
        database.session.add(
            DeliveryNoteItem(
                delivery_note_id=note.id,
                item_code=f"ITEM-{suffix}",
                item_name="Artículo",
                qty=1,
                uom="EA",
                qty_in_base_uom=1,
            )
        )
        database.session.add_all(
            [
                User(
                    id=f"sales-{suffix}",
                    user=f"sales-{suffix}",
                    name="Ventas",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"inventory-{suffix}",
                    user=f"inventory-{suffix}",
                    name="Inventario",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"denied-{suffix}",
                    user=f"denied-{suffix}",
                    name="Sin módulos",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        inventory_module = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        sales_role = Roles(name=f"lines-sales-{suffix}", note="Consulta de ventas")
        inventory_role = Roles(name=f"lines-inventory-{suffix}", note="Consulta de inventario")
        database.session.add_all([sales_role, inventory_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=inventory_role.id, module_id=inventory_module, access=True, view=True),
                RolesUser(user_id=f"sales-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"inventory-{suffix}", role_id=inventory_role.id, active=True),
                UserCompanyAccess(user_id=f"sales-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"inventory-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"denied-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "note": note.id,
            "sales": f"sales-{suffix}",
            "inventory": f"inventory-{suffix}",
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


def _pending_lines(app, user_id: str, note_id: str):
    """Request the delivery-note pending lines as the given user."""
    client = _authenticated_client(app, user_id)
    return client.get(
        "/api/document-flow/pending-lines",
        query_string={
            "source_type": "delivery_note",
            "target_type": "sales_invoice",
            "source_document_ids[]": note_id,
            "company": "alpha",
        },
    )


def test_sales_reader_can_load_delivery_note_lines(delivery_note_lines_scenario):
    """A sales reader obtains the delivery-note lines for invoicing."""
    app, ids = delivery_note_lines_scenario

    response = _pending_lines(app, ids["sales"], ids["note"])

    assert response.status_code == 200
    assert response.get_json()["target_type"] == "sales_invoice"


def test_inventory_reader_can_load_delivery_note_lines(delivery_note_lines_scenario):
    """Inventory keeps the same read policy for delivery notes."""
    app, ids = delivery_note_lines_scenario

    response = _pending_lines(app, ids["inventory"], ids["note"])

    assert response.status_code == 200


def test_delivery_note_lines_require_one_of_the_two_modules(delivery_note_lines_scenario):
    """A user without Sales or Inventory cannot read the lines."""
    app, ids = delivery_note_lines_scenario

    response = _pending_lines(app, ids["denied"], ids["note"])

    assert response.status_code == 403
