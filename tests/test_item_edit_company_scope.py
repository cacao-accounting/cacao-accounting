# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1418/#1542: editar un artículo no borra cuentas de otras compañías.

El reemplazo completo de ``ItemAccount`` debe limitarse a las compañías que
el usuario puede editar. Un POST que omite la fila de otra compañía no puede
eliminarla, y un POST que intenta incluirla debe rechazarse sin mutar el
artículo.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    Item,
    ItemAccount,
    ItemUOMConversion,
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
def item_edit_scope_scenario():
    """Create a shared item with accounting rows in two companies and an editor for one."""
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
    editor_id = f"editor-{suffix}"

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
                UOM(code="BOX", name="Box", is_active=True),
            ]
        )
        database.session.commit()

        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        database.session.add(
            User(
                id=editor_id,
                user=editor_id,
                name="Item Editor",
                password=b"unused",
                active=True,
                company=local_company,
            )
        )
        role = Roles(name=f"item-editor-{suffix}", note="Edición de inventario")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True, edit=True),
                RolesUser(user_id=editor_id, role_id=role.id, active=True),
            ]
        )
        database.session.flush()
        local_account = Accounts(
            entity=local_company,
            code=f"EXP-L-{suffix}",
            name="Gasto local",
            classification="expense",
            account_type="expense",
        )
        local_alternate = Accounts(
            entity=local_company,
            code=f"ALT-L-{suffix}",
            name="Gasto local alterno",
            classification="expense",
            account_type="expense",
        )
        secret_account = Accounts(
            entity=secret_company,
            code=f"EXP-S-{suffix}",
            name="Gasto secreto",
            classification="expense",
            account_type="expense",
        )
        database.session.add_all(
            [
                UserCompanyAccess(user_id=editor_id, company_code=local_company),
                local_account,
                local_alternate,
                secret_account,
                Item(code=item_code, name="Artículo compartido", item_type="goods", is_stock_item=True, default_uom="EA"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
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
            "local_alternate": local_alternate.id,
            "secret_account": secret_account.id,
            "editor_id": editor_id,
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


def _valid_item_form(**extra: object) -> dict[str, object]:
    """Build a valid item edit payload, optionally adding account rows."""
    data: dict[str, object] = {
        "name": "Artículo actualizado",
        "item_type": "goods",
        "is_stock_item": "y",
        "is_purchase_item": "y",
        "is_sale_item": "y",
        "default_uom": "EA",
    }
    data.update(extra)
    return data


def _persisted_rows(app, item_code: str) -> dict[str, ItemAccount]:
    """Return persisted ItemAccount rows keyed by company."""
    with app.app_context():
        rows = database.session.execute(database.select(ItemAccount).filter_by(item_code=item_code)).scalars().all()
        return {str(row.company): row for row in rows}


def test_item_edit_preserves_foreign_rows_when_payload_omits_them(item_edit_scope_scenario):
    """Omitting another company's accounting row must not delete it (#1418)."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])

    response = client.post(f"/inventory/item/{ids['item_code']}/edit", data=_valid_item_form())

    assert response.status_code == 302
    rows = _persisted_rows(app, ids["item_code"])
    assert ids["secret_company"] in rows
    assert rows[ids["secret_company"]].expense_account_id == ids["secret_account"]
    assert ids["local_company"] not in rows
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code=ids["item_code"])).scalar_one()
        assert item.name == "Artículo actualizado"


def test_item_edit_updates_only_the_authorized_company_row(item_edit_scope_scenario):
    """The authorized company row is replaced while the foreign row stays untouched."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])

    response = client.post(
        f"/inventory/item/{ids['item_code']}/edit",
        data=_valid_item_form(
            account_company=ids["local_company"],
            expense_account_id=ids["local_alternate"],
        ),
    )

    assert response.status_code == 302
    rows = _persisted_rows(app, ids["item_code"])
    assert rows[ids["local_company"]].expense_account_id == ids["local_alternate"]
    assert rows[ids["secret_company"]].expense_account_id == ids["secret_account"]


def test_item_edit_rejects_payload_with_foreign_company_row(item_edit_scope_scenario):
    """A payload that includes a foreign company is rejected without mutation (#1542)."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])

    response = client.post(
        f"/inventory/item/{ids['item_code']}/edit",
        data=_valid_item_form(
            name="Intento ajeno",
            account_company=ids["secret_company"],
            expense_account_id=ids["secret_account"],
        ),
    )

    assert response.status_code == 403
    rows = _persisted_rows(app, ids["item_code"])
    assert rows[ids["local_company"]].expense_account_id == ids["local_account"]
    assert rows[ids["secret_company"]].expense_account_id == ids["secret_account"]
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code=ids["item_code"])).scalar_one()
        assert item.name == "Artículo compartido"


def test_item_edit_form_does_not_render_foreign_company_rows(item_edit_scope_scenario):
    """The edit form only embeds accounting rows of companies the user may edit (#1181)."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])

    response = client.get(f"/inventory/item/{ids['item_code']}/edit")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["local_account"] in body
    assert ids["secret_account"] not in body
    assert ids["secret_company"] not in body


def _set_stock_adjustment_account(app, item_code: str, company: str, account_id: str | None) -> None:
    """Assign the persisted stock adjustment account for one company row."""
    with app.app_context():
        row = database.session.execute(
            database.select(ItemAccount).filter_by(item_code=item_code, company=company)
        ).scalar_one()
        row.stock_adjustment_account_id = account_id
        database.session.commit()


def test_item_edit_form_renders_stock_adjustment_account_selector(item_edit_scope_scenario):
    """El formulario de edición debe enviar la cuenta de ajuste (#1825)."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])
    _set_stock_adjustment_account(app, ids["item_code"], ids["local_company"], ids["local_alternate"])

    response = client.get(f"/inventory/item/{ids['item_code']}/edit")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="stock_adjustment_account_id"' in body
    assert ids["local_alternate"] in body


def test_item_edit_without_stock_adjustment_field_preserves_existing_value(item_edit_scope_scenario):
    """Un POST sin la columna no puede borrar la cuenta de ajuste configurada (#1825)."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])
    _set_stock_adjustment_account(app, ids["item_code"], ids["local_company"], ids["local_alternate"])

    response = client.post(
        f"/inventory/item/{ids['item_code']}/edit",
        data=_valid_item_form(
            account_company=ids["local_company"],
            expense_account_id=ids["local_account"],
        ),
    )

    assert response.status_code == 302
    rows = _persisted_rows(app, ids["item_code"])
    assert rows[ids["local_company"]].stock_adjustment_account_id == ids["local_alternate"]


def test_item_edit_updates_and_clears_stock_adjustment_account(item_edit_scope_scenario):
    """La columna enviada se respeta: cambia la cuenta y un valor vacío la limpia."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])
    _set_stock_adjustment_account(app, ids["item_code"], ids["local_company"], ids["local_account"])

    updated = client.post(
        f"/inventory/item/{ids['item_code']}/edit",
        data=_valid_item_form(
            account_company=ids["local_company"],
            expense_account_id=ids["local_account"],
            stock_adjustment_account_id=ids["local_alternate"],
        ),
    )
    assert updated.status_code == 302
    assert _persisted_rows(app, ids["item_code"])[ids["local_company"]].stock_adjustment_account_id == ids["local_alternate"]

    cleared = client.post(
        f"/inventory/item/{ids['item_code']}/edit",
        data=_valid_item_form(
            account_company=ids["local_company"],
            expense_account_id=ids["local_account"],
            stock_adjustment_account_id="",
        ),
    )
    assert cleared.status_code == 302
    assert _persisted_rows(app, ids["item_code"])[ids["local_company"]].stock_adjustment_account_id is None


@pytest.mark.parametrize("factor", ["NaN", "Infinity", "0.0000000001"])
def test_item_edit_renders_invalid_uom_factor_as_validation_error(item_edit_scope_scenario, factor):
    """A non-finite or unrepresentable UOM factor stays in handled validation."""
    app, ids = item_edit_scope_scenario
    client = _authenticated_client(app, ids["editor_id"])

    response = client.post(
        f"/inventory/item/{ids['item_code']}/edit",
        data=_valid_item_form(uom_code="BOX", uom_conversion_factor=factor),
    )

    assert response.status_code == 200
    assert "Artículo compartido" in response.get_data(as_text=True)
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code=ids["item_code"])).scalar_one()
        conversions = (
            database.session.execute(database.select(ItemUOMConversion).filter_by(item_code=ids["item_code"])).scalars().all()
        )
        assert item.name == "Artículo compartido"
        assert conversions == []
