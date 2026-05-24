# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José MORENO Reyes

import json
import pytest
from cacao_accounting import create_app
from cacao_accounting.database import database, Entity, Item, UOM, User, Roles, Modules, RolesUser, RolesAccess
from flask_login import login_user


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        # Setup basic data
        e = Entity(id="cacao", company_name="Cacao Company", tax_id="12345")
        database.session.add(e)
        u = UOM(id="und", code="UND", name="Unidad")
        database.session.add(u)
        database.session.flush()

        i = Item(id="test_item", code="ITEM01", name="Test Item", item_type="goods", default_uom="UND")
        database.session.add(i)

        # Create a user for authentication
        user = User(id="test_user", user="test", password=b"test", classification="admin", active=True)
        database.session.add(user)

        # Setup permissions for the test
        role = Roles(id="admin_role", name="admin", note="System Admin")
        database.session.add(role)

        mod_purchases = Modules(id="purchases_mod", module="purchases", default=True, enabled=True)
        mod_accounting = Modules(id="accounting_mod", module="accounting", default=True, enabled=True)
        mod_sales = Modules(id="sales_mod", module="sales", default=True, enabled=True)
        mod_inventory = Modules(id="inventory_mod", module="inventory", default=True, enabled=True)
        mod_cash = Modules(id="cash_mod", module="cash", default=True, enabled=True)
        mod_general = Modules(id="general_mod", module="general", default=True, enabled=True)
        database.session.add_all([mod_purchases, mod_accounting, mod_sales, mod_inventory, mod_cash, mod_general])
        database.session.flush()

        ru = RolesUser(user_id="test_user", role_id="admin_role", active=True)
        database.session.add(ru)

        # Grant import permissions
        for mod_id in ["purchases_mod", "accounting_mod", "sales_mod", "inventory_mod", "cash_mod", "general_mod"]:
            ra = RolesAccess(rol_id="admin_role", module_id=mod_id, access=True, import_=True, view=True)
            database.session.add(ra)

        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client, app):
    with app.test_request_context():
        user = database.session.get(User, "test_user")
        login_user(user)
        with client.session_transaction() as sess:
            sess["_user_id"] = "test_user"
            sess["_fresh"] = True
    return client


def test_get_line_import_schema(logged_in_client):
    response = logged_in_client.get("/api/line-import/schema?doctype=purchase_request")
    assert response.status_code == 200
    data = response.get_json()
    assert data["doctype"] == "purchase_request"
    assert any(col["key"] == "item_code" for col in data["columns"])


def test_get_operational_line_import_schemas(logged_in_client):
    doctypes = [
        "purchase_request",
        "purchase_quotation",
        "supplier_quotation",
        "purchase_order",
        "purchase_receipt",
        "purchase_invoice",
        "sales_request",
        "sales_quotation",
        "sales_order",
        "delivery_note",
        "sales_invoice",
        "stock_entry",
    ]

    for doctype in doctypes:
        response = logged_in_client.get(f"/api/line-import/schema?doctype={doctype}")
        assert response.status_code == 200, doctype
        assert response.get_json()["doctype"] == doctype


def test_validate_lines_rejects_missing_doctype(logged_in_client):
    payload = {"context": {"company_id": "cacao"}, "rows": [{"item_code": "ITEM01"}]}
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "Doctype no especificado"


def test_validate_lines_rejects_unsupported_doctype(logged_in_client):
    payload = {"doctype": "unknown", "context": {"company_id": "cacao"}, "rows": [{"item_code": "ITEM01"}]}
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "Doctype no soportado"


def test_validate_lines_rejects_missing_company_context(logged_in_client):
    payload = {"doctype": "purchase_request", "context": {}, "rows": [{"item_code": "ITEM01"}]}
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    data = response.get_json()
    assert data["valid"] is False
    assert data["errors"][0]["field"] == "company_id"


def test_validate_lines_rejects_unknown_company(logged_in_client):
    payload = {"doctype": "purchase_request", "context": {"company_id": "missing"}, "rows": [{"item_code": "ITEM01"}]}
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert "no existe" in response.get_json()["error"]


def test_validate_lines_success(logged_in_client):
    payload = {
        "doctype": "purchase_request",
        "context": {"company_id": "cacao"},
        "rows": [{"item_code": "ITEM01", "quantity": "10", "uom": "UND"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is True
    assert len(data["rows"]) == 1
    assert data["rows"][0]["item_name"] == "Test Item"


def test_validate_lines_invalid_item(logged_in_client):
    payload = {
        "doctype": "purchase_request",
        "context": {"company_id": "cacao"},
        "rows": [{"item_code": "NONEXISTENT", "quantity": "10", "uom": "UND"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("no existe" in err["message"] for err in data["errors"])


def test_validate_journal_entry_conflict(logged_in_client):
    payload = {
        "doctype": "journal_entry",
        "context": {"company_id": "cacao"},
        "rows": [{"account": "1010", "debit": "100", "credit": "50"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("misma línea" in err["message"] for err in data["errors"])


def test_validate_empty_import(logged_in_client):
    payload = {"doctype": "purchase_request", "context": {"company_id": "cacao"}, "rows": []}
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("al menos una línea" in err["message"] for err in data["errors"])


def test_validate_numeric_constraints(logged_in_client):
    # Test zero quantity
    payload = {
        "doctype": "purchase_request",
        "context": {"company_id": "cacao"},
        "rows": [{"item_code": "ITEM01", "quantity": "0", "uom": "UND"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("mayor que cero" in err["message"] for err in data["errors"])

    # Test negative rate
    payload = {
        "doctype": "purchase_order",
        "context": {"company_id": "cacao"},
        "rows": [{"item_code": "ITEM01", "quantity": "10", "uom": "UND", "rate": "-5"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("no puede ser negativo" in err["message"] for err in data["errors"])


def test_validate_lines_rejects_too_many_rows(logged_in_client):
    payload = {
        "doctype": "purchase_request",
        "context": {"company_id": "cacao"},
        "rows": [{"item_code": "ITEM01", "quantity": "1", "uom": "UND"}] * 501,
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("500" in err["message"] for err in data["errors"])


def test_validate_lines_rejects_invalid_decimal_and_date(logged_in_client):
    payload = {
        "doctype": "purchase_request",
        "context": {"company_id": "cacao"},
        "rows": [{"item_code": "ITEM01", "quantity": "abc", "uom": "UND", "required_date": "2026/05/24"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any("decimal inválido" in err["message"] for err in data["errors"])
    assert any("fecha inválido" in err["message"] for err in data["errors"])


@pytest.mark.parametrize(
    ("doctype", "row", "field", "message"),
    [
        ("purchase_request", {"item_code": "ITEM01", "quantity": "1", "uom": "BAD"}, "uom", "unidad de medida"),
        ("journal_entry", {"account": "1010", "debit": "100"}, "account", "cuenta contable"),
        (
            "purchase_request",
            {"item_code": "ITEM01", "quantity": "1", "uom": "UND", "cost_center": "BAD"},
            "cost_center",
            "centro de costo",
        ),
        (
            "purchase_request",
            {"item_code": "ITEM01", "quantity": "1", "uom": "UND", "project": "BAD"},
            "project",
            "proyecto",
        ),
        (
            "purchase_receipt",
            {"item_code": "ITEM01", "quantity": "1", "uom": "UND", "warehouse": "BAD"},
            "warehouse",
            "bodega",
        ),
    ],
)
def test_validate_lines_rejects_invalid_master_data(logged_in_client, doctype, row, field, message):
    payload = {"doctype": doctype, "context": {"company_id": "cacao"}, "rows": [row]}
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any(err["field"] == field and message in err["message"].lower() for err in data["errors"])
