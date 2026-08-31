# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José MORENO Reyes

import json
from io import BytesIO
from decimal import Decimal
import pytest
from types import SimpleNamespace
from openpyxl import Workbook
from cacao_accounting import create_app
from cacao_accounting.api import line_import
from cacao_accounting.database import Accounts, database, Entity, Item, UOM, User, Roles, Modules, RolesUser, RolesAccess
from cacao_accounting.document_flow import payment as payment_flow
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
        e = Entity(id="cacao", code="cacao", company_name="Cacao Company", tax_id="12345")
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


def test_get_payment_reconciliation_import_schema(logged_in_client):
    """La conciliación usa el mismo contrato de carga XLSX del backend."""
    response = logged_in_client.get("/api/line-import/schema?doctype=payment_reconciliation")
    assert response.status_code == 200
    keys = {column["key"] for column in response.get_json()["columns"]}
    assert {"payment_id", "reference_type", "reference_id", "allocated_amount"}.issubset(keys)


def test_validate_payment_reconciliation_rejects_unknown_documents(logged_in_client):
    """La validación previa evita importar pagos o referencias inexistentes."""
    payload = {
        "doctype": "payment_reconciliation",
        "context": {"company_id": "cacao"},
        "rows": [
            {
                "payment_id": "missing-payment",
                "reference_type": "sales_invoice",
                "reference_id": "missing-invoice",
                "allocated_amount": "10",
            }
        ],
    }
    response = logged_in_client.post("/api/line-import/validate", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert {error["field"] for error in data["errors"]} >= {"payment_id", "reference_id"}


def test_validate_payment_reconciliation_accepts_matching_payment_and_document(logged_in_client, monkeypatch):
    """A valid payment allocation passes identity and outstanding-balance checks."""
    payment = SimpleNamespace(company="cacao", docstatus=1, party_type="customer", party_id="customer-1", currency="USD")
    reference = SimpleNamespace(company="cacao", docstatus=1, customer_id="customer-1", transaction_currency="USD")

    def fake_get(model, identifier):
        if model is line_import.PaymentEntry:
            return payment
        if model is line_import.SalesInvoice:
            return reference
        raise AssertionError(f"Unexpected model: {model}")

    monkeypatch.setattr(line_import.database.session, "get", fake_get)
    monkeypatch.setattr(payment_flow, "compute_outstanding_amount", lambda document: Decimal("100"))
    monkeypatch.setattr(payment_flow, "compute_payment_unallocated_amount", lambda document: Decimal("100"))

    errors = []
    line_import._validate_payment_reconciliation_row(
        {"payment_id": "payment-1", "reference_type": "sales_invoice", "reference_id": "invoice-1", "allocated_amount": "25"},
        1,
        "cacao",
        errors,
    )

    assert errors == []


def test_validate_payment_reconciliation_reports_party_currency_and_balance_errors(logged_in_client, monkeypatch):
    """Mismatched party, missing FX rate, and excessive amounts are reported together."""
    payment = SimpleNamespace(company="cacao", docstatus=1, party_type="customer", party_id="customer-1", currency="USD")
    reference = SimpleNamespace(company="cacao", docstatus=1, customer_id="customer-2", transaction_currency="EUR")

    def fake_get(model, identifier):
        return payment if model is line_import.PaymentEntry else reference

    monkeypatch.setattr(line_import.database.session, "get", fake_get)
    monkeypatch.setattr(payment_flow, "compute_outstanding_amount", lambda document: Decimal("10"))
    monkeypatch.setattr(payment_flow, "compute_payment_unallocated_amount", lambda document: Decimal("5"))

    errors = []
    line_import._validate_payment_reconciliation_row(
        {"payment_id": "payment-1", "reference_type": "sales_invoice", "reference_id": "invoice-1", "allocated_amount": "20"},
        4,
        "cacao",
        errors,
    )

    assert {error["field"] for error in errors} == {"reference_id", "payment_exchange_rate", "allocated_amount"}
    assert sum(error["field"] == "allocated_amount" for error in errors) == 2


def test_validate_payment_reconciliation_rejects_non_positive_allocation(logged_in_client, monkeypatch):
    """A zero allocation is invalid even when payment and reference lookup fails."""
    monkeypatch.setattr(line_import.database.session, "get", lambda model, identifier: None)

    errors = []
    line_import._validate_payment_reconciliation_row(
        {"payment_id": "missing", "reference_type": "unsupported", "reference_id": "missing", "allocated_amount": "0"},
        2,
        "cacao",
        errors,
    )

    assert [error["field"] for error in errors] == ["payment_id", "reference_type", "allocated_amount"]


@pytest.mark.parametrize(
    ("reference_type", "party_type", "expected"),
    [
        ("invoice", "customer", "sales_invoice"),
        ("invoice", "supplier", "purchase_invoice"),
        ("debit_note", "customer", "sales_debit_note"),
        ("credit_note", "supplier", "purchase_credit_note"),
        ("journal_entry", "customer", "journal_entry"),
    ],
)
def test_resolve_open_item_reference_type(reference_type, party_type, expected):
    """Generic references resolve to the correct AP/AR document type."""
    assert line_import._resolve_open_item_reference_type(reference_type, party_type) == expected


def test_validate_open_item_reference_accepts_materialized_match(logged_in_client, monkeypatch):
    """A materialized open item is copied to the canonical imported row."""
    match = SimpleNamespace(id="open-1", document_no="INV-001", document_id="invoice-1")
    query = SimpleNamespace(filter=lambda *args: query, all=lambda: [match])
    monkeypatch.setattr(line_import.database.session, "query", lambda model: query)

    validated_row = {"party": "customer-1", "party_type": "customer"}
    errors = []
    line_import._validate_open_item_reference(
        {"reference_type": "invoice", "reference_document": "INV-001", "reference_line": "2"},
        validated_row,
        3,
        "cacao",
        errors,
    )

    assert errors == []
    assert validated_row == {
        "party": "customer-1",
        "party_type": "customer",
        "reference_type": "sales_invoice",
        "reference_open_item_id": "open-1",
        "reference_document": "INV-001",
    }


def test_validate_open_item_reference_uses_ledger_fallback(logged_in_client, monkeypatch):
    """A unique ledger item is accepted when its materialized cache is absent."""
    from cacao_accounting.contabilidad import arap_allocation

    match = SimpleNamespace(document_type="purchase_invoice", document_no="PINV-001", document_id="invoice-1", outstanding=25)
    query = SimpleNamespace(filter=lambda *args: query, all=lambda: [])
    monkeypatch.setattr(line_import.database.session, "query", lambda model: query)
    monkeypatch.setattr(arap_allocation, "list_open_items", lambda **kwargs: [match])

    validated_row = {"party": "supplier-1", "party_type": "supplier"}
    errors = []
    line_import._validate_open_item_reference(
        {"reference_type": "invoice", "reference_document": "invoice-1", "reference_line": "economic-line-1"},
        validated_row,
        5,
        "cacao",
        errors,
    )

    assert errors == []
    assert validated_row["reference_type"] == "purchase_invoice"
    assert validated_row["reference_document"] == "PINV-001"
    assert "reference_open_item_id" not in validated_row


@pytest.mark.parametrize(
    ("matches", "ledger_matches", "expected_field"),
    [
        ([], [], "reference_document"),
        (
            [],
            [SimpleNamespace(document_type="sales_invoice", document_no="INV-1", document_id="1", outstanding=10)] * 2,
            "reference_line",
        ),
        ([SimpleNamespace(id="1", document_no="INV-1", document_id="1")] * 2, [], "reference_line"),
    ],
)
def test_validate_open_item_reference_reports_unresolved_or_ambiguous(
    logged_in_client, monkeypatch, matches, ledger_matches, expected_field
):
    """Missing and ambiguous references return the appropriate import error field."""
    from cacao_accounting.contabilidad import arap_allocation

    query = SimpleNamespace(filter=lambda *args: query, all=lambda: matches)
    monkeypatch.setattr(line_import.database.session, "query", lambda model: query)
    monkeypatch.setattr(arap_allocation, "list_open_items", lambda **kwargs: ledger_matches)

    errors = []
    line_import._validate_open_item_reference(
        {"reference_type": "sales_invoice", "reference_document": "INV-1"},
        {"party_type": "customer", "party": "customer-1"},
        7,
        "cacao",
        errors,
    )

    assert len(errors) == 1
    assert errors[0]["field"] == expected_field


def test_validate_open_item_reference_rejects_incomplete_reference(logged_in_client):
    """Reference type and document must be supplied together."""
    errors = []
    line_import._validate_open_item_reference(
        {"reference_type": "invoice"},
        {},
        8,
        "cacao",
        errors,
    )

    assert errors[0]["field"] == "reference_type"
    assert "juntos" in errors[0]["message"]


@pytest.mark.parametrize(
    ("doctype", "column_key", "expected_aliases"),
    [
        ("purchase_request", "item_code", {"producto", "product", "item code"}),
        ("purchase_request", "quantity", {"cantidad", "qty", "quantity"}),
        ("journal_entry", "account", {"cuenta contable", "account", "account code"}),
        ("journal_entry", "debit", {"debe", "debit"}),
        ("journal_entry", "credit", {"haber", "credit"}),
    ],
)
def test_get_line_import_schema_exposes_spanish_and_english_aliases(logged_in_client, doctype, column_key, expected_aliases):
    response = logged_in_client.get(f"/api/line-import/schema?doctype={doctype}")

    assert response.status_code == 200
    data = response.get_json()
    column = next(col for col in data["columns"] if col["key"] == column_key)
    aliases = set(column.get("aliases", []))

    assert expected_aliases.issubset(aliases)


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


@pytest.mark.parametrize("payload", [{"context": [], "rows": []}, {"context": {}, "rows": {}}])
def test_validate_lines_rejects_invalid_payload_shapes(logged_in_client, payload):
    """Malformed JSON shapes return structured client errors instead of HTTP 500."""
    response = logged_in_client.post("/api/line-import/validate", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Doctype no especificado"


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


def test_validate_lines_accepts_company_code_when_entity_id_differs(logged_in_client):
    entity = Entity(id="entity_internal_id", code="company-code", company_name="Company Code", tax_id="67890")
    database.session.add(entity)
    database.session.commit()

    payload = {
        "doctype": "purchase_request",
        "context": {"company_id": "company-code"},
        "rows": [{"item_code": "ITEM01", "quantity": "10", "uom": "UND"}],
    }
    response = logged_in_client.post("/api/line-import/validate", data=json.dumps(payload), content_type="application/json")

    assert response.status_code == 200
    assert response.get_json()["valid"] is True


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


def test_parse_xlsx_journal_uses_server_schema_and_rejects_formulas(logged_in_client):
    """El parser XLSX canónico acepta encabezados localizados y bloquea fórmulas."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Lineas"
    worksheet.append(["Cuenta", "Débito", "Crédito"])
    worksheet.append(["1010", 100, "=SUM(1,2)"])
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)

    response = logged_in_client.post(
        "/api/line-import/parse-xlsx",
        data={"doctype": "journal_entry", "file": (stream, "journal.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any(error["field"] == "credit" and "fórmulas" in error["message"] for error in data["errors"])


def test_validate_journal_import_includes_existing_lines(logged_in_client):
    """La validación combina filas importadas con las líneas ya capturadas."""
    database.session.add_all(
        [
            Accounts(entity="cacao", code="1010", name="Debe", active=True, enabled=True, group=False),
            Accounts(entity="cacao", code="2020", name="Haber", active=True, enabled=True, group=False),
        ]
    )
    database.session.commit()
    payload = {
        "doctype": "journal_entry",
        "context": {
            "company_id": "cacao",
            "existing_lines": [{"account": "1010", "debit": "100", "credit": "0"}],
        },
        "rows": [{"account": "2020", "debit": "0", "credit": "60"}],
    }
    response = logged_in_client.post("/api/line-import/validate", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is False
    assert any(error["field"] == "voucher" and "balanceado" in error["message"] for error in data["errors"])


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
