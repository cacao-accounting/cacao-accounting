# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Payment forms enforce company scope for every referenced source document."""

import json
from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    Accounts,
    Currency,
    DocumentRelation,
    Entity,
    Modules,
    PaymentEntry,
    PaymentReference,
    Party,
    PurchaseOrder,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def payment_source_company_scenario():
    """Create a treasury user scoped to Alpha and source orders in both companies."""
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
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                *[
                    Modules(module=module, default=module == "accounting", enabled=True)
                    for module in ("accounting", "cash", "purchases", "sales", "inventory", "imports")
                ],
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J-ALPHA",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J-BETA",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="cash_scope_user",
                    user="cash_scope_user",
                    name="Tesorería Alpha",
                    password=proteger_passwd("cash-scope-password"),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id="cash_scope_user", company_code="alpha"),
                PurchaseOrder(
                    company="alpha",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-ALPHA",
                    supplier_name="Proveedor Alpha",
                    grand_total=100,
                ),
                PurchaseOrder(
                    company="beta",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-BETA-SECRET",
                    supplier_name="Proveedor Confidencial Beta",
                    grand_total=200,
                ),
                PurchaseOrder(
                    company=None,
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-LEGACY-UNSCOPED",
                    supplier_name="Proveedor sin compañía verificable",
                    grand_total=300,
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("cash_scope_user", "auxiliar_of_treasury")
        database.session.commit()
        ids = {
            company: database.session.query(PurchaseOrder.id).filter_by(company=company).scalar()
            for company in ("alpha", "beta")
        }
        ids["unscoped"] = database.session.query(PurchaseOrder.id).filter_by(document_no="PO-LEGACY-UNSCOPED").scalar()

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app):
    """Return a test client authenticated as the Alpha-only treasury user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "cash_scope_user"
        session["_fresh"] = True
    return client


def test_payment_form_hides_source_order_from_another_company(payment_source_company_scenario):
    """A source order in a company outside the user's cash scope returns 403."""
    app, ids = payment_source_company_scenario

    response = _authenticated_client(app).get(f"/cash_management/payment/new?from_purchase_order={ids['beta']}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "PO-BETA-SECRET" not in body
    assert "Proveedor Confidencial Beta" not in body


def test_payment_form_rejects_mixed_authorized_and_foreign_sources(payment_source_company_scenario):
    """All selected sources must be authorized before any one is rendered."""
    app, ids = payment_source_company_scenario

    response = _authenticated_client(app).get(
        f"/cash_management/payment/new?from_purchase_order={ids['alpha']}&from_purchase_order={ids['beta']}"
    )

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "PO-ALPHA" not in body
    assert "PO-BETA-SECRET" not in body


def test_payment_form_rejects_source_without_verifiable_company(payment_source_company_scenario):
    """Legacy source documents without a company cannot bypass company access checks."""
    app, ids = payment_source_company_scenario

    response = _authenticated_client(app).get(f"/cash_management/payment/new?from_purchase_order={ids['unscoped']}")

    assert response.status_code == 403
    assert "PO-LEGACY-UNSCOPED" not in response.get_data(as_text=True)


def test_payment_form_preserves_source_order_in_authorized_company(payment_source_company_scenario):
    """Authorized source orders continue to prefill the payment form."""
    app, ids = payment_source_company_scenario

    response = _authenticated_client(app).get(f"/cash_management/payment/new?from_purchase_order={ids['alpha']}")

    assert response.status_code == 200
    assert "PO-ALPHA" in response.get_data(as_text=True)


def test_payment_post_uses_form_sources_instead_of_query_sources(payment_source_company_scenario):
    """A POST ignores a stale foreign query value when the form selects an authorized source."""
    app, ids = payment_source_company_scenario
    response = _authenticated_client(app).post(
        f"/cash_management/payment/new?from_purchase_order={ids['beta']}",
        data={"from_purchase_order": ids["alpha"]},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "PO-ALPHA" in body
    assert "PO-BETA-SECRET" not in body


def test_payment_post_rejects_unscoped_source_without_persisting(app, entorno_contable, authenticated_client):
    """A forged POST cannot apply an unscoped order or leave partial payment evidence."""
    with app.app_context():
        bank_gl_account_id = database.session.query(Accounts.id).filter_by(entity="cacao", code="1102").scalar()
        supplier = database.session.query(Party).filter_by(code="PRV001").one()
        supplier_id = supplier.id
        supplier_name = supplier.name
        bank = Bank(name="Banco del pago de prueba")
        database.session.add(bank)
        database.session.flush()
        bank_account = BankAccount(
            company="cacao",
            bank_id=bank.id,
            account_name="Cuenta del pago de prueba",
            currency="NIO",
            gl_account_id=bank_gl_account_id,
        )
        order = PurchaseOrder(
            company=None,
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no="PO-UNSCOPED-POST",
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=1,
            grand_total=25,
        )
        database.session.add_all([bank_account, order])
        database.session.commit()
        bank_account_id = bank_account.id
        order_id = order.id
        payment_count_before = database.session.query(PaymentEntry).count()
        reference_count_before = database.session.query(PaymentReference).count()
        relation_count_before = database.session.query(DocumentRelation).filter_by(target_type="payment_entry").count()

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank_account_id,
        "posting_date": "2026-05-15",
        "paid_amount": "25",
        "party_type": "supplier",
        "party_id": supplier_id,
        "advance_mode": True,
        "lines": [
            {
                "reference_type": "purchase_order",
                "flow_source_type": "purchase_order",
                "reference_id": order_id,
                "allocated_amount": "25",
            }
        ],
    }
    response = authenticated_client("admin").post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payload)}
    )

    assert response.status_code == 409
    with app.app_context():
        assert database.session.query(PaymentEntry).count() == payment_count_before
        assert database.session.query(PaymentReference).count() == reference_count_before
        assert database.session.query(DocumentRelation).filter_by(target_type="payment_entry").count() == relation_count_before
