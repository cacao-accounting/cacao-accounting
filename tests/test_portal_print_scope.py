# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1562: el portal imprime solo documentos de su propia compañía.

Un cliente o proveedor de portal puede compartir el tercero global con otra
compañía; la autorización de impresión debe exigir además que el documento
pertenezca a `user.company` y que el tercero coincida.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Party,
    PurchaseInvoice,
    SalesInvoice,
    User,
    database,
)
from cacao_accounting.printing.exceptions import PrintPermissionError
from cacao_accounting.printing.seed import seed_print_templates
from cacao_accounting.printing.service import PrintService


@pytest.fixture
def portal_print_scenario():
    """Create shared parties and one invoice per company for each portal user."""
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
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        customer = Party(
            code=f"CLI-{suffix}",
            name="Cliente Compartido",
            is_customer=True,
            is_active=True,
        )
        supplier = Party(
            code=f"SUP-{suffix}",
            name="Proveedor Compartido",
            is_supplier=True,
            is_active=True,
        )
        database.session.add_all([customer, supplier])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="alpha", party_id=customer.id, is_active=True),
                CompanyParty(company="alpha", party_id=supplier.id, is_active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id=f"portal-customer-{suffix}",
                    user=f"portal-customer-{suffix}",
                    name="Cliente Portal",
                    password=b"unused",
                    active=True,
                    company="alpha",
                    classification="customer",
                    party_id=customer.id,
                ),
                User(
                    id=f"portal-supplier-{suffix}",
                    user=f"portal-supplier-{suffix}",
                    name="Proveedor Portal",
                    password=b"unused",
                    active=True,
                    company="alpha",
                    classification="supplier",
                    party_id=supplier.id,
                ),
            ]
        )
        sales_alpha = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"FAC-A-{suffix}",
            document_type="sales_invoice",
            customer_id=customer.id,
            customer_name="Cliente Compartido",
            grand_total=100,
        )
        sales_beta = SalesInvoice(
            company="beta",
            posting_date=date(2026, 5, 11),
            docstatus=1,
            document_no=f"FAC-B-{suffix}",
            document_type="sales_invoice",
            customer_id=customer.id,
            customer_name="Cliente Compartido",
            grand_total=200,
        )
        purchase_alpha = PurchaseInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"COM-A-{suffix}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name="Proveedor Compartido",
            grand_total=50,
        )
        purchase_beta = PurchaseInvoice(
            company="beta",
            posting_date=date(2026, 5, 11),
            docstatus=1,
            document_no=f"COM-B-{suffix}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name="Proveedor Compartido",
            grand_total=75,
        )
        database.session.add_all([sales_alpha, sales_beta, purchase_alpha, purchase_beta])
        database.session.commit()
        seed_print_templates()
        ids = {
            "customer_user": f"portal-customer-{suffix}",
            "supplier_user": f"portal-supplier-{suffix}",
            "sales_alpha": sales_alpha.id,
            "sales_beta": sales_beta.id,
            "purchase_alpha": purchase_alpha.id,
            "purchase_beta": purchase_beta.id,
            "sales_beta_no": sales_beta.document_no,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested portal user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_portal_customer_cannot_authorize_a_foreign_company_invoice(portal_print_scenario):
    """The shared party does not grant printing for another company."""
    app, ids = portal_print_scenario

    with app.app_context():
        user = database.session.get(User, ids["customer_user"])
        with pytest.raises(PrintPermissionError):
            PrintService()._authorize_document("sales_invoice", ids["sales_beta"], user, "beta")


def test_portal_customer_can_authorize_its_own_company_invoice(portal_print_scenario):
    """The customer keeps printing the documents of its own company."""
    app, ids = portal_print_scenario

    with app.app_context():
        user = database.session.get(User, ids["customer_user"])
        PrintService()._authorize_document("sales_invoice", ids["sales_alpha"], user, "alpha")


def test_portal_supplier_cannot_authorize_a_foreign_company_invoice(portal_print_scenario):
    """The supplier branch applies the same company restriction."""
    app, ids = portal_print_scenario

    with app.app_context():
        user = database.session.get(User, ids["supplier_user"])
        with pytest.raises(PrintPermissionError):
            PrintService()._authorize_document("purchase_invoice", ids["purchase_beta"], user, "beta")


def test_portal_supplier_can_authorize_its_own_company_invoice(portal_print_scenario):
    """The supplier keeps printing the documents of its own company."""
    app, ids = portal_print_scenario

    with app.app_context():
        user = database.session.get(User, ids["supplier_user"])
        PrintService()._authorize_document("purchase_invoice", ids["purchase_alpha"], user, "alpha")


def test_portal_preview_rejects_the_foreign_company_without_leaking_data(portal_print_scenario):
    """The preview route returns a generic 404 for the other company."""
    app, ids = portal_print_scenario
    client = _authenticated_client(app, ids["customer_user"])

    response = client.get(f"/print/sales_invoice/{ids['sales_beta']}/preview?company=beta")

    assert response.status_code == 404
    assert ids["sales_beta_no"].encode() not in response.data


def test_portal_preview_renders_its_own_company_invoice(portal_print_scenario):
    """The own-company preview keeps working for the portal customer."""
    app, ids = portal_print_scenario
    client = _authenticated_client(app, ids["customer_user"])

    response = client.get(f"/print/sales_invoice/{ids['sales_alpha']}/preview")

    assert response.status_code == 200
    assert b"<html" in response.data.lower()


def _desactivar_tercero(app, party_id: str) -> None:
    """Desactiva el tercero conservando sus documentos."""
    with app.app_context():
        party = database.session.get(Party, party_id)
        party.is_active = False
        database.session.commit()


def _desactivar_vinculo(app, company_code: str, party_id: str) -> None:
    """Desactiva el vínculo del tercero con la compañía."""
    with app.app_context():
        link = database.session.execute(
            database.select(CompanyParty).filter_by(company=company_code, party_id=party_id)
        ).scalar_one()
        link.is_active = False
        database.session.commit()


def test_portal_preview_rechaza_tercero_inactivo(portal_print_scenario):
    """Un cliente inactivo no puede previsualizar su propia factura."""
    app, ids = portal_print_scenario
    client = _authenticated_client(app, ids["customer_user"])
    with app.app_context():
        party_id = database.session.get(User, ids["customer_user"]).party_id
    _desactivar_tercero(app, party_id)

    response = client.get(f"/print/sales_invoice/{ids['sales_alpha']}/preview?company=alpha")

    assert response.status_code == 404


def test_portal_preview_rechaza_vinculo_inactivo(portal_print_scenario):
    """Un vínculo CompanyParty inactivo revoca también la previsualización."""
    app, ids = portal_print_scenario
    client = _authenticated_client(app, ids["customer_user"])
    with app.app_context():
        party_id = database.session.get(User, ids["customer_user"]).party_id
    _desactivar_vinculo(app, "alpha", party_id)

    response = client.get(f"/print/sales_invoice/{ids['sales_alpha']}/preview?company=alpha")

    assert response.status_code == 404


def test_portal_pdf_rechaza_tercero_inactivo(portal_print_scenario):
    """La exportación PDF aplica la misma revocación que la vista previa."""
    app, ids = portal_print_scenario
    client = _authenticated_client(app, ids["customer_user"])
    with app.app_context():
        party_id = database.session.get(User, ids["customer_user"]).party_id
    _desactivar_tercero(app, party_id)

    response = client.get(f"/print/sales_invoice/{ids['sales_alpha']}/pdf?company=alpha")

    assert response.status_code == 404


def test_portal_proveedor_preview_rechaza_vinculo_inactivo(portal_print_scenario):
    """El proveedor con vínculo inactivo no imprime su factura de compra."""
    app, ids = portal_print_scenario
    client = _authenticated_client(app, ids["supplier_user"])
    with app.app_context():
        party_id = database.session.get(User, ids["supplier_user"]).party_id
    _desactivar_vinculo(app, "alpha", party_id)

    response = client.get(f"/print/purchase_invoice/{ids['purchase_alpha']}/preview?company=alpha")

    assert response.status_code == 404
