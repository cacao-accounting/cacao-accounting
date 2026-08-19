# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regression tests for Stock Entry authorization and draft integrity."""

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Create an isolated database with administrative and regular users."""
    app = create_app(
        {
            **configuracion,
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="cafe",
                    name="Café Accounting",
                    company_name="Café Accounting SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="active",
                ),
                Modules(module="inventory", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                User(user="viewer", name="Viewer", password=b"x", classification="user", active=True),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    """Authenticate a test user without depending on password hashing."""
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_stock_entry_creation_requires_inventory_permission(app_ctx):
    """A logged-in user without create permission cannot open the endpoint."""
    from cacao_accounting.database import User

    viewer = User.query.filter_by(user="viewer").first()
    client = app_ctx.test_client()
    _login(client, viewer.id)

    response = client.get("/inventory/stock-entry/new")

    assert response.status_code == 403


def test_warehouse_detail_hides_inaccessible_company_accounts(app_ctx):
    """Warehouse details only expose account rows for readable companies."""
    from cacao_accounting.database import (
        Book,
        Modules,
        Roles,
        RolesAccess,
        RolesUser,
        User,
        UserBookAccess,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    viewer = User.query.filter_by(user="viewer").first()
    module = database.session.execute(database.select(Modules).filter_by(module="inventory")).scalar_one()
    role = Roles(name="inventory_reader", note="Inventory reader")
    book = Book(code="CACAO-BOOK", name="Cacao book", entity="cacao", is_primary=True)
    warehouse = Warehouse(code="SHARED-WH", name="Shared warehouse", company="cacao")
    database.session.add_all([role, book, warehouse])
    database.session.flush()
    database.session.add_all(
        [
            RolesUser(user_id=viewer.id, role_id=role.id, active=True),
            RolesAccess(rol_id=role.id, module_id=module.id, access=True, view=True),
            UserBookAccess(user_id=viewer.id, book_id=book.id, can_read=True),
            WarehouseCompanyAccount(warehouse_code=warehouse.code, company="cacao"),
            WarehouseCompanyAccount(warehouse_code=warehouse.code, company="cafe"),
        ]
    )
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, viewer.id)
    response = client.get(f"/inventory/warehouse/{warehouse.code}")

    assert response.status_code == 200
    assert b">cacao<" in response.data
    assert b">cafe<" not in response.data


def test_stock_entry_header_rejects_missing_or_invalid_date(app_ctx):
    """Draft creation rejects missing and malformed posting dates server-side."""
    from flask_login import login_user

    from cacao_accounting.database import User, database
    from cacao_accounting.inventario.services import _validate_stock_entry_posting_date

    admin = User.query.filter_by(user="admin").first()
    with app_ctx.test_request_context("/inventory/stock-entry/new", method="POST"):
        login_user(admin)
        with pytest.raises(ValueError, match="fecha de contabilización"):
            _validate_stock_entry_posting_date({"purpose": "material_receipt", "company": "cacao"})
        with pytest.raises(ValueError, match="fecha de contabilización"):
            _validate_stock_entry_posting_date(
                {"purpose": "material_receipt", "company": "cacao", "posting_date": "not-a-date"}
            )
    database.session.rollback()


def test_stock_entry_edit_keeps_company_and_purpose_immutable(app_ctx):
    """Editing a draft cannot move it across companies or accounting treatments."""
    from flask_login import login_user

    from cacao_accounting.database import StockEntry, User
    from cacao_accounting.inventario.services import _update_stock_entry_from_form

    admin = User.query.filter_by(user="admin").first()
    entry = StockEntry(company="cacao", purpose="material_receipt", posting_date=date(2026, 8, 19), docstatus=0)

    with app_ctx.test_request_context(
        "/inventory/stock-entry/entry/edit",
        method="POST",
        data={"purpose": "material_receipt", "company": "cafe", "posting_date": "2026-08-19"},
    ):
        login_user(admin)
        with pytest.raises(ValueError, match="compañía"):
            _update_stock_entry_from_form(entry)

    with app_ctx.test_request_context(
        "/inventory/stock-entry/entry/edit",
        method="POST",
        data={"purpose": "material_issue", "company": "cacao", "posting_date": "2026-08-19"},
    ):
        login_user(admin)
        with pytest.raises(ValueError, match="propósito"):
            _update_stock_entry_from_form(entry)


def test_stock_entry_draft_rejects_cross_company_warehouse(app_ctx):
    """A draft cannot persist a warehouse belonging to another company."""
    from cacao_accounting.database import StockEntry, User, Warehouse, database
    from cacao_accounting.inventario.services import _validate_stock_entry_warehouses

    database.session.add_all(
        [
            Warehouse(code="WH-CACAO", name="Cacao", company="cacao", is_active=True),
            Warehouse(code="WH-CAFE", name="Café", company="cafe", is_active=True),
        ]
    )
    database.session.flush()
    entry = StockEntry(company="cacao", purpose="material_transfer", from_warehouse="WH-CACAO")

    with pytest.raises(ValueError, match="WH-CAFE"):
        _validate_stock_entry_warehouses(entry, "WH-CAFE")
