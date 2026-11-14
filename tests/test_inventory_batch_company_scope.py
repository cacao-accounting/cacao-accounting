# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Inventory batch routes expose only authorized companies' stock evidence."""

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    Currency,
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    StockLedgerEntry,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)


@pytest.fixture
def batch_company_scope_scenario():
    """Create a batch used in two companies and a user authorized in only one."""
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
    suffix = uuid4().hex[:8]
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"
    user_id = f"user-{suffix}"
    denied_user_id = f"denied-{suffix}"
    role_name = f"inventory-reader-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=company_alpha,
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name="Beta SA",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(id=user_id, user=user_id, name="Alpha Inventory Reader", password=b"unused", active=True),
                User(
                    id=denied_user_id,
                    user=denied_user_id,
                    name="Inventory User Without View Permission",
                    password=b"unused",
                    active=True,
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        role = Roles(name=role_name, note="Inventory view limited to Alpha")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code=company_alpha),
                UserCompanyAccess(user_id=denied_user_id, company_code=company_alpha),
                Item(
                    code=f"ITEM-{suffix}",
                    name="Shared lot item",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="EA",
                ),
            ]
        )
        database.session.flush()
        item_code = f"ITEM-{suffix}"
        shared_batch = Batch(item_code=item_code, batch_no=f"SHARED-{suffix}")
        beta_batch = Batch(item_code=item_code, batch_no=f"BETA-ONLY-{suffix}")
        warehouse_alpha = Warehouse(code=f"A-{suffix}", name="Alpha warehouse", company=company_alpha)
        warehouse_beta = Warehouse(code=f"B-{suffix}", name="Beta warehouse", company=company_beta)
        database.session.add_all([shared_batch, beta_batch, warehouse_alpha, warehouse_beta])
        database.session.flush()
        database.session.add_all(
            [
                StockLedgerEntry(
                    posting_date=date(2026, 11, 1),
                    item_code=item_code,
                    warehouse=warehouse_alpha.code,
                    company=company_alpha,
                    qty_change=5,
                    qty_after_transaction=5,
                    valuation_rate=10,
                    stock_value_difference=50,
                    stock_value=50,
                    voucher_type="stock_entry",
                    voucher_id=f"VOUCHER-ALPHA-{suffix}",
                    batch_id=shared_batch.id,
                ),
                StockLedgerEntry(
                    posting_date=date(2026, 11, 1),
                    item_code=item_code,
                    warehouse=warehouse_beta.code,
                    company=company_beta,
                    qty_change=70,
                    qty_after_transaction=70,
                    valuation_rate=10,
                    stock_value_difference=700,
                    stock_value=700,
                    voucher_type="stock_entry",
                    voucher_id=f"VOUCHER-BETA-SECRET-{suffix}",
                    batch_id=shared_batch.id,
                ),
                StockLedgerEntry(
                    posting_date=date(2026, 11, 1),
                    item_code=item_code,
                    warehouse=warehouse_beta.code,
                    company=company_beta,
                    qty_change=9,
                    qty_after_transaction=9,
                    valuation_rate=10,
                    stock_value_difference=90,
                    stock_value=90,
                    voucher_type="stock_entry",
                    voucher_id=f"VOUCHER-BETA-ONLY-{suffix}",
                    batch_id=beta_batch.id,
                ),
            ]
        )
        database.session.commit()
        ids = {
            "shared_batch": shared_batch.id,
            "beta_batch": beta_batch.id,
            "shared_batch_no": shared_batch.batch_no,
            "beta_batch_no": beta_batch.batch_no,
            "user_id": user_id,
            "denied_user_id": denied_user_id,
            "alpha_warehouse": warehouse_alpha.code,
            "beta_warehouse": warehouse_beta.code,
            "suffix": suffix,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate a test client with the given seeded user ID."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_batch_routes_require_view_permission(batch_company_scope_scenario):
    """Authenticated users without Inventory view permission cannot read batch routes."""
    app, ids = batch_company_scope_scenario
    client = _authenticated_client(app, ids["denied_user_id"])

    assert client.get("/inventory/batch/list").status_code == 403
    assert client.get(f"/inventory/batch/{ids['shared_batch']}").status_code == 403


def test_batch_routes_limit_lists_balances_and_movements_to_authorized_companies(batch_company_scope_scenario):
    """A shared lot shows only authorized activity and a foreign-only lot stays hidden."""
    app, ids = batch_company_scope_scenario
    client = _authenticated_client(app, ids["user_id"])

    listing = client.get("/inventory/batch/list")
    assert listing.status_code == 200
    assert ids["shared_batch_no"] in listing.get_data(as_text=True)
    assert ids["beta_batch_no"] not in listing.get_data(as_text=True)

    detail = client.get(f"/inventory/batch/{ids['shared_batch']}")
    detail_html = detail.get_data(as_text=True)
    assert detail.status_code == 200
    assert ids["alpha_warehouse"] in detail_html
    assert "5.000000000" in detail_html
    assert ids["beta_warehouse"] not in detail_html
    assert f"VOUCHER-BETA-SECRET-{ids['suffix']}" not in detail_html

    assert client.get(f"/inventory/batch/{ids['beta_batch']}").status_code == 404
