# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""N6: el selector de lotes no enumera evidencia de otras compañías.

`Batch` no guarda compañía; su alcance se deriva del libro de stock y de las
capas de valoración. Un lote solo es visible si tiene evidencia en alguna
compañía autorizada del usuario.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
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
    StockValuationLayer,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)


@pytest.fixture
def batch_scope_scenario():
    """Create batches with evidence in alpha and beta for an alpha reader."""
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
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"
    reader = f"inventory-reader-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=True, enabled=True),
                Entity(
                    code=company_alpha,
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                User(
                    id=reader,
                    user=reader,
                    name="Lector de inventario",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
            ]
        )
        database.session.flush()
        database.session.add(UOM(code="EA", name="Each", is_active=True))
        database.session.flush()
        item = Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        database.session.add(item)
        database.session.flush()
        warehouse_alpha = Warehouse(code=f"WA{suffix}", name="Alfa", company=company_alpha)
        warehouse_beta = Warehouse(code=f"WB{suffix}", name="Beta", company=company_beta)
        database.session.add_all([warehouse_alpha, warehouse_beta])
        database.session.flush()
        batch_alpha = Batch(item_code=item.code, batch_no=f"B-A-{suffix}", is_active=True)
        batch_beta = Batch(item_code=item.code, batch_no=f"B-B-{suffix}", is_active=True)
        batch_ledger = Batch(item_code=item.code, batch_no=f"B-L-{suffix}", is_active=True)
        database.session.add_all([batch_alpha, batch_beta, batch_ledger])
        database.session.flush()
        database.session.add_all(
            [
                StockValuationLayer(
                    item_code=item.code,
                    warehouse=warehouse_alpha.code,
                    company=company_alpha,
                    qty=Decimal("1"),
                    rate=Decimal("10"),
                    voucher_type="stock_entry",
                    voucher_id=f"SE-A-{suffix}",
                    posting_date=date(2026, 5, 10),
                    batch_id=batch_alpha.id,
                ),
                StockValuationLayer(
                    item_code=item.code,
                    warehouse=warehouse_beta.code,
                    company=company_beta,
                    qty=Decimal("1"),
                    rate=Decimal("10"),
                    voucher_type="stock_entry",
                    voucher_id=f"SE-B-{suffix}",
                    posting_date=date(2026, 5, 10),
                    batch_id=batch_beta.id,
                ),
                StockLedgerEntry(
                    item_code=item.code,
                    warehouse=warehouse_alpha.code,
                    company=company_alpha,
                    qty_change=Decimal("1"),
                    voucher_type="stock_entry",
                    voucher_id=f"SE-L-{suffix}",
                    posting_date=date(2026, 5, 11),
                    batch_id=batch_ledger.id,
                ),
            ]
        )
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        role = Roles(name=f"batch-reader-{suffix}", note="Consulta de inventario")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=reader, role_id=role.id, active=True),
                UserCompanyAccess(user_id=reader, company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "reader": reader,
            "alpha": batch_alpha.id,
            "ledger": batch_ledger.id,
            "beta": batch_beta.id,
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


def test_batch_search_only_lists_evidence_from_authorized_companies(batch_scope_scenario):
    """Valuation and ledger evidence from alpha are visible; beta is not."""
    app, ids = batch_scope_scenario
    client = _authenticated_client(app, ids["reader"])

    response = client.get("/api/search-select?doctype=batch")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert values == {ids["alpha"], ids["ledger"]}
    assert ids["beta"] not in values
