# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1541: el detalle de artículo exige consulta y oculta cuentas ajenas.

La ruta ``GET /inventory/item/<code>`` debe requerir el permiso de consulta
del módulo de inventario y devolver solo las filas ``ItemAccount`` de las
compañías autorizadas. Un usuario sin permiso no accede al detalle y un
usuario con acceso acotado no ve la configuración contable de otra compañía.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    Currency,
    Entity,
    Item,
    ItemAccount,
    Modules,
    Party,
    Roles,
    RolesAccess,
    RolesUser,
    UOM,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def item_detail_scope_scenario():
    """Create a global item with private accounting rows in two companies."""
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
    local_company = f"l{suffix}"
    secret_company = f"s{suffix}"
    item_code = f"ITEM-{suffix}"
    reader_id = f"reader-{suffix}"
    no_permission_id = f"denied-{suffix}"
    no_grants_id = f"nogrants-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code=local_company,
                    name="Local",
                    company_name=f"Compañía Local {suffix}",
                    tax_id=f"TAX-L-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=secret_company,
                    name="Secret",
                    company_name=f"Compañía Secreta {suffix}",
                    tax_id=f"TAX-S-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.commit()

        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        database.session.add_all(
            [
                User(
                    id=reader_id,
                    user=reader_id,
                    name="Item Reader",
                    password=b"unused",
                    active=True,
                    company=local_company,
                ),
                User(
                    id=no_permission_id,
                    user=no_permission_id,
                    name="Item Reader Without Inventory Permission",
                    password=b"unused",
                    active=True,
                    company=local_company,
                ),
                User(
                    id=no_grants_id,
                    user=no_grants_id,
                    name="Item Reader Without Company Grants",
                    password=b"unused",
                    active=True,
                    company=local_company,
                ),
            ]
        )
        role = Roles(name=f"item-reader-{suffix}", note="Consulta de inventario")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=reader_id, role_id=role.id, active=True),
                RolesUser(user_id=no_grants_id, role_id=role.id, active=True),
            ]
        )
        database.session.flush()
        local_account = Accounts(entity=local_company, code=f"EXP-L-{suffix}", name="Gasto local", classification="expense")
        secret_account = Accounts(
            entity=secret_company, code=f"EXP-S-{suffix}", name="Gasto secreto", classification="expense"
        )
        local_supplier = Party(code=f"SUP-L-{suffix}", name=f"Proveedor Local {suffix}", is_supplier=True)
        secret_supplier = Party(code=f"SUP-S-{suffix}", name=f"Proveedor Secreto {suffix}", is_supplier=True)
        database.session.add_all(
            [
                UserCompanyAccess(user_id=reader_id, company_code=local_company),
                UserCompanyAccess(user_id=no_permission_id, company_code=local_company),
                local_account,
                secret_account,
                local_supplier,
                secret_supplier,
                Item(code=item_code, name="Artículo compartido", item_type="goods", is_stock_item=True, default_uom="EA"),
            ]
        )
        database.session.flush()
        item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one()
        item.default_supplier_id = secret_supplier.id
        database.session.add_all(
            [
                CompanyParty(company=local_company, party_id=local_supplier.id),
                CompanyParty(company=secret_company, party_id=secret_supplier.id),
                ItemAccount(item_code=item_code, company=local_company, expense_account_id=local_account.id),
                ItemAccount(item_code=item_code, company=secret_company, expense_account_id=secret_account.id),
            ]
        )
        database.session.commit()
        ids = {
            "item_code": item_code,
            "local_company": local_company,
            "secret_company": secret_company,
            "local_account": local_account.id,
            "secret_account": secret_account.id,
            "local_supplier": local_supplier.id,
            "local_supplier_name": local_supplier.name,
            "secret_supplier_name": secret_supplier.name,
            "reader_id": reader_id,
            "no_permission_id": no_permission_id,
            "no_grants_id": no_grants_id,
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


def test_item_detail_requires_inventory_permission(item_detail_scope_scenario):
    """A user without the inventory query permission never reaches the detail."""
    app, ids = item_detail_scope_scenario
    client = _authenticated_client(app, ids["no_permission_id"])

    response = client.get(f"/inventory/item/{ids['item_code']}")

    assert response.status_code == 403


def test_item_detail_only_exposes_authorized_company_accounts(item_detail_scope_scenario):
    """The reader sees its own ItemAccount row and never the foreign one."""
    app, ids = item_detail_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"/inventory/item/{ids['item_code']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["local_account"] in body
    assert ids["secret_account"] not in body
    assert ids["secret_company"] not in body


def test_item_detail_hides_accounts_when_user_has_no_company_grants(item_detail_scope_scenario):
    """A user with the module permission but no company grants sees no accounting rows."""
    app, ids = item_detail_scope_scenario
    client = _authenticated_client(app, ids["no_grants_id"])

    response = client.get(f"/inventory/item/{ids['item_code']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["local_account"] not in body
    assert ids["secret_account"] not in body
    assert ids["secret_company"] not in body


def test_item_detail_hides_default_supplier_from_foreign_company(item_detail_scope_scenario):
    """The default supplier only appears when it is active in an authorized company (#1181)."""
    app, ids = item_detail_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"/inventory/item/{ids['item_code']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["secret_supplier_name"] not in body


def test_item_detail_shows_default_supplier_of_authorized_company(item_detail_scope_scenario):
    """A supplier activated in the reader's company remains visible."""
    app, ids = item_detail_scope_scenario
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code=ids["item_code"])).scalar_one()
        item.default_supplier_id = ids["local_supplier"]
        database.session.commit()
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"/inventory/item/{ids['item_code']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["local_supplier_name"] in body
    assert ids["secret_supplier_name"] not in body
