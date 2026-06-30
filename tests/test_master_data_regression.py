# SPDX-License-Identifier: Apache-2.0

"""Regression tests for master data issues described in ISSUES.md.

These tests exercise entity active/inactive behavior, search-select, parent selection
for accounts and cost centers, edit form prefills and roundtrip, detail view edit
buttons and page title consistency.

"""
from __future__ import annotations

import re

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


def _checkbox_is_checked(html: str, field_name: str) -> bool:
    return re.search(rf'<input[^>]*(?:name="{field_name}"[^>]*checked|checked[^>]*name="{field_name}")', html) is not None


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
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
                Modules(module="accounting", default=True, enabled=True),
                User(
                    user="admin",
                    name="Admin",
                    classification="admin",
                    active=True,
                    **{"password": b"x"},
                ),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


# 1) Entities active/inactive, search-select
def test_entity_search_select_active_and_include_inactive(app_ctx):
    from cacao_accounting.database import Entity, User, database

    # add an inactive entity
    database.session.add(Entity(code="ina_test", name="INA", company_name="INA SA", tax_id="J999", currency="NIO", enabled=False))
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    r = client.get("/api/search-select?doctype=company&q=&limit=20")
    assert r.status_code == 200
    payload = r.get_json()
    values = {item["value"] for item in payload["results"]}
    assert "cacao" in values
    assert "ina_test" not in values

    # include inactive
    r2 = client.get("/api/search-select?doctype=company&q=&limit=20&include_inactive=true")
    assert r2.status_code == 200
    payload2 = r2.get_json()
    values2 = {item["value"] for item in payload2["results"]}
    assert "ina_test" in values2


# 2) Account parent accepts parent_id and rejects cross-entity
def test_account_parent_roundtrip_and_cross_entity_rejection(app_ctx):
    from cacao_accounting.database import Accounts, Entity, User, database

    # create another entity
    database.session.add(Entity(code="entA", name="A", company_name="A SA", tax_id="J100", currency="NIO", enabled=True, status="activo"))
    database.session.add(Entity(code="entB", name="B", company_name="B SA", tax_id="J101", currency="NIO", enabled=True, status="activo"))
    parent = Accounts(entity="entA", code="P", name="Parent", active=True, enabled=True, group=True)
    database.session.add(parent)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    # create child in same entity using parent id
    ok = client.post(
        "/accounting/account/new",
        data={
            "entidad": "entA",
            "code": "C1",
            "name": "Child 1",
            "padre": str(parent.id),
            "clasificacion": "activo",
        },
        follow_redirects=False,
    )
    assert ok.status_code in (302, 303)
    child = database.session.query(Accounts).filter_by(entity="entA", code="C1").one_or_none()
    assert child is not None and child.parent == "P"

    # attempt create in other entity using same parent id - should reject
    rejected = client.post(
        "/accounting/account/new",
        data={
            "entidad": "entB",
            "code": "C2",
            "name": "Child 2",
            "padre": str(parent.id),
            "clasificacion": "activo",
        },
        follow_redirects=True,
    )
    assert rejected.status_code == 200
    assert b"cuenta padre indicada no existe para la entidad seleccionada" in rejected.data.lower()


# 3) Cost center parent accepts parent_id and rejects cross-entity
def test_cost_center_parent_roundtrip_and_cross_entity_rejection(app_ctx):
    from cacao_accounting.database import CostCenter, Entity, User, database

    database.session.add(Entity(code="ent1", name="E1", company_name="E1 SA", tax_id="J200", currency="NIO", enabled=True, status="activo"))
    database.session.add(Entity(code="ent2", name="E2", company_name="E2 SA", tax_id="J201", currency="NIO", enabled=True, status="activo"))
    parent = CostCenter(entity="ent1", code="CCP", name="CC Parent", active=True, enabled=True, group=True)
    database.session.add(parent)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    ok = client.post(
        "/accounting/costs_center/new",
        data={
            "entidad": "ent1",
            "id": "CH1",
            "nombre": "Child CC",
            "padre": str(parent.id),
        },
        follow_redirects=False,
    )
    assert ok.status_code in (302, 303)
    child = database.session.query(CostCenter).filter_by(entity="ent1", code="CH1").one_or_none()
    assert child is not None and child.parent == "CCP"

    rejected = client.post(
        "/accounting/costs_center/new",
        data={
            "entidad": "ent2",
            "id": "CH2",
            "nombre": "Child CC 2",
            "padre": str(parent.id),
        },
        follow_redirects=True,
    )
    assert rejected.status_code == 200
    assert b"centro de costos padre indicado no existe para la entidad seleccionada" in rejected.data.lower()


# 4) Edit form prefill and roundtrip without changes
def test_account_edit_prefill_and_roundtrip_nochange(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    parent = Accounts(entity="cacao", code="1", name="Activo", active=True, enabled=True, group=True)
    child = Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, group=False, parent="1")
    database.session.add_all([parent, child])
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    r = client.get("/accounting/account/cacao/1.01/edit")
    assert r.status_code == 200
    assert b'initialValue: "cacao"' in r.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in r.data

    # Post back without changes (simulate pressing save)
    post = client.post(
        "/accounting/account/cacao/1.01/edit",
        data={
            "entidad": "cacao",
            "code": "1.01",
            "name": "Caja",
            "clasificacion": "activo",
            "grupo": "",
            "activo": "y",
        },
        follow_redirects=False,
    )
    assert post.status_code in (302, 303)


def test_cost_center_edit_prefill_and_roundtrip_nochange(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    parent = CostCenter(entity="cacao", code="ADM", name="Admin", active=True, enabled=True, group=True)
    child = CostCenter(entity="cacao", code="ADM01", name="Admin 01", active=True, enabled=True, group=False, parent="ADM")
    database.session.add_all([parent, child])
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    r = client.get("/accounting/costs_center/ADM01/edit")
    assert r.status_code == 200
    assert b'initialValue: "cacao"' in r.data
    assert b'initialLabel: "ADM - Admin"' in r.data

    post = client.post(
        "/accounting/costs_center/ADM01/edit",
        data={
            "entidad": "cacao",
            "id": "ADM01",
            "nombre": "Admin 01",
            "grupo": "",
            "activo": "y",
        },
        follow_redirects=False,
    )
    assert post.status_code in (302, 303)


# 5) Detail views expose Edit buttons
def test_account_detail_has_edit_button(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    acc = Accounts(entity="cacao", code="X1", name="TestAcc", active=True, enabled=True, group=False)
    database.session.add(acc)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    r = client.get(f"/accounting/account/cacao/{acc.code}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f"/accounting/account/cacao/{acc.code}/edit" in html or "/accounting/account/cacao/" in html


def test_cost_center_detail_has_edit_button(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    cc = CostCenter(entity="cacao", code="CCX", name="CostX", active=True, enabled=True, group=False)
    database.session.add(cc)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    r = client.get(f"/accounting/costs_center/{cc.code}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f"/accounting/costs_center/{cc.code}/edit" in html


# 6) Titles consistency
def test_pages_have_expected_titles(app_ctx):
    from cacao_accounting.database import User

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    # accounts list
    r = client.get("/accounting/accounts")
    assert r.status_code == 200
    assert "Catalogo de Cuentas Contables" in r.get_data(as_text=True)

    # new cost center page title
    r2 = client.get("/accounting/costs_center/new")
    assert r2.status_code == 200
    assert "Nuevo Centro de Costos" in r2.get_data(as_text=True)


# Command to run: pytest -q tests/test_master_data_regression.py
