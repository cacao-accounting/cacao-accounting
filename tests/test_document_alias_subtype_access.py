# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#998: los alias de notas validan compañía y subtipo real.

`sales_credit_note`, `sales_debit_note`, `sales_return` y sus pares de compra
comparten modelo con la factura. La API debe exigir el permiso del alias y
rechazar un documento que no sea del subtipo solicitado.
"""

from __future__ import annotations

from importlib import import_module
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    File,
    FileAttachment,
    Modules,
    PurchaseInvoice,
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)

STATUS_URL = "/api/document-flow/recalculate-status/{document_type}/{document_id}"
api_module = import_module("cacao_accounting.api")


@pytest.fixture
def document_alias_scenario(tmp_path: Path, monkeypatch):
    """Create sales and purchase aliases, foreign records and linked files."""
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
    attachment_path = tmp_path / "credit-note.pdf"
    attachment_path.write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr("cacao_accounting.messaging.email.can_send_transaction_emails", lambda: True)

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
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
        database.session.add_all(
            [
                User(
                    id=f"seller-{suffix}",
                    user=f"seller-{suffix}",
                    name="Vendedor",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"buyer-{suffix}",
                    user=f"buyer-{suffix}",
                    name="Comprador",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"outsider-{suffix}",
                    user=f"outsider-{suffix}",
                    name="Sin ventas",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        documents = {
            "invoice": SalesInvoice(
                company="alpha",
                posting_date=date(2026, 5, 10),
                docstatus=1,
                document_no=f"INV-{suffix}",
                document_type="sales_invoice",
                customer_name="Cliente Alfa",
            ),
            "credit_note": SalesInvoice(
                company="alpha",
                posting_date=date(2026, 5, 11),
                docstatus=1,
                document_no=f"CN-{suffix}",
                document_type="sales_credit_note",
                customer_name="Cliente Alfa",
            ),
            "foreign_note": SalesInvoice(
                company="beta",
                posting_date=date(2026, 5, 12),
                docstatus=1,
                document_no=f"CN-B-{suffix}",
                document_type="sales_credit_note",
                customer_name="Cliente Beta",
            ),
            "purchase_note": PurchaseInvoice(
                company="alpha",
                posting_date=date(2026, 5, 13),
                docstatus=1,
                document_no=f"PCN-{suffix}",
                document_type="purchase_credit_note",
                supplier_name="Proveedor Alfa",
            ),
            "foreign_purchase_note": PurchaseInvoice(
                company="beta",
                posting_date=date(2026, 5, 14),
                docstatus=1,
                document_no=f"PCN-B-{suffix}",
                document_type="purchase_credit_note",
                supplier_name="Proveedor Beta",
            ),
            "purchase_invoice": PurchaseInvoice(
                company="alpha",
                posting_date=date(2026, 5, 15),
                docstatus=1,
                document_no=f"PINV-{suffix}",
                document_type="purchase_invoice",
                supplier_name="Proveedor Alfa",
            ),
        }
        database.session.add_all(documents.values())
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        purchases_module = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        sales_role = Roles(name=f"alias-sales-{suffix}", note="Consulta de ventas")
        database.session.add(sales_role)
        purchase_role = Roles(name=f"alias-purchases-{suffix}", note="Consulta de compras")
        database.session.add(purchase_role)
        database.session.flush()
        files = {
            key: File(
                file_name=attachment_path.name,
                file_path=str(attachment_path),
                file_size=attachment_path.stat().st_size,
                mime_type="application/pdf",
            )
            for key in (
                "attachment",
                "sales_foreign_attachment",
                "sales_mismatch_attachment",
                "purchase_attachment",
                "purchase_foreign_attachment",
                "purchase_mismatch_attachment",
            )
        }
        database.session.add_all(files.values())
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=purchase_role.id, module_id=purchases_module, access=True, view=True),
                RolesUser(user_id=f"seller-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"buyer-{suffix}", role_id=purchase_role.id, active=True),
                RolesUser(user_id=f"outsider-{suffix}", role_id=sales_role.id, active=False),
                UserCompanyAccess(user_id=f"buyer-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"seller-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"outsider-{suffix}", company_code="alpha"),
                FileAttachment(
                    file_id=files["attachment"].id,
                    reference_type="sales_credit_note",
                    reference_id=documents["credit_note"].id,
                ),
                FileAttachment(
                    file_id=files["sales_foreign_attachment"].id,
                    reference_type="sales_credit_note",
                    reference_id=documents["foreign_note"].id,
                ),
                FileAttachment(
                    file_id=files["sales_mismatch_attachment"].id,
                    reference_type="sales_credit_note",
                    reference_id=documents["invoice"].id,
                ),
                FileAttachment(
                    file_id=files["purchase_attachment"].id,
                    reference_type="purchase_credit_note",
                    reference_id=documents["purchase_note"].id,
                ),
                FileAttachment(
                    file_id=files["purchase_foreign_attachment"].id,
                    reference_type="purchase_credit_note",
                    reference_id=documents["foreign_purchase_note"].id,
                ),
                FileAttachment(
                    file_id=files["purchase_mismatch_attachment"].id,
                    reference_type="purchase_credit_note",
                    reference_id=documents["purchase_invoice"].id,
                ),
            ]
        )
        database.session.commit()
        ids = {
            "seller": f"seller-{suffix}",
            "buyer": f"buyer-{suffix}",
            "outsider": f"outsider-{suffix}",
            **{key: document.id for key, document in documents.items()},
            **{key: attachment.id for key, attachment in files.items()},
            "attachment_path": str(attachment_path),
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


def test_credit_note_alias_rejects_a_plain_invoice(document_alias_scenario):
    """The alias cannot serve a document of another subtype."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["invoice"]))

    assert response.status_code == 404


def test_plain_invoice_alias_rejects_a_credit_note(document_alias_scenario):
    """The reverse mismatch is rejected as well."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_invoice", document_id=ids["credit_note"]))

    assert response.status_code == 404


def test_credit_note_alias_accepts_the_matching_subtype(document_alias_scenario):
    """A real credit note keeps the documented read path."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["credit_note"]))

    assert response.status_code == 200


def test_credit_note_alias_enforces_company_scope(document_alias_scenario):
    """The alias keeps the company-scoped sales permission."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["foreign_note"]))

    assert response.status_code == 403


def test_credit_note_alias_requires_the_sales_module(document_alias_scenario):
    """A user without a current sales assignment is rejected."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["outsider"])

    response = client.post(STATUS_URL.format(document_type="sales_credit_note", document_id=ids["credit_note"]))

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("user_key", "document_key", "status_code"),
    [("seller", "credit_note", 200), ("seller", "foreign_note", 403), ("seller", "invoice", 404)],
)
def test_email_info_enforces_sales_alias_scope_and_subtype(document_alias_scenario, user_key, document_key, status_code):
    """Email metadata is exposed only for the authorized matching note subtype."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids[user_key])

    response = client.get(f"/api/documents/sales_credit_note/{ids[document_key]}/email-info")

    assert response.status_code == status_code
    if status_code == 200:
        assert response.json["document_no"].startswith("CN-")


@pytest.mark.parametrize(
    ("user_key", "document_key", "status_code"),
    [
        ("buyer", "purchase_note", 200),
        ("buyer", "foreign_purchase_note", 403),
        ("buyer", "purchase_invoice", 404),
    ],
)
def test_purchase_credit_note_email_info_enforces_company_scope(document_alias_scenario, user_key, document_key, status_code):
    """Purchase aliases apply their own module and company authorization."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids[user_key])

    response = client.get(f"/api/documents/purchase_credit_note/{ids[document_key]}/email-info")

    assert response.status_code == status_code


@pytest.mark.parametrize(("document_key", "status_code"), [("credit_note", 200), ("foreign_note", 403), ("invoice", 404)])
def test_credit_note_attachment_listing_checks_access_before_listing(document_alias_scenario, document_key, status_code):
    """Attachment listing follows alias company and subtype checks."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])

    response = client.get(f"/api/attachments/sales_credit_note/{ids[document_key]}")

    assert response.status_code == status_code
    if status_code == 200:
        assert response.json[0]["file_id"] == ids["attachment"]


@pytest.mark.parametrize(
    ("file_key", "status_code"),
    [("attachment", 200), ("sales_foreign_attachment", 403), ("sales_mismatch_attachment", 404)],
)
def test_credit_note_attachment_download_checks_link_access(document_alias_scenario, file_key, status_code, monkeypatch):
    """Attachment download requires access to its linked alias document."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["seller"])
    file_reads = []
    original_get_attachment_file = api_module.get_attachment_file

    def track_file_read(file_id):
        file_reads.append(file_id)
        return original_get_attachment_file(file_id)

    monkeypatch.setattr(api_module, "get_attachment_file", track_file_read)

    response = client.get(f"/attachments/download/{ids[file_key]}")

    assert response.status_code == status_code
    if status_code == 200:
        assert response.data == Path(ids["attachment_path"]).read_bytes()
        assert file_reads == [ids[file_key]]
    else:
        assert not file_reads


@pytest.mark.parametrize(
    ("document_key", "status_code"),
    [("purchase_note", 200), ("foreign_purchase_note", 403), ("purchase_invoice", 404)],
)
def test_purchase_credit_note_attachment_listing_checks_access(document_alias_scenario, document_key, status_code):
    """Purchase attachment listing enforces company and subtype for aliases."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["buyer"])

    response = client.get(f"/api/attachments/purchase_credit_note/{ids[document_key]}")

    assert response.status_code == status_code
    if status_code == 200:
        assert response.json[0]["file_id"] == ids["purchase_attachment"]


@pytest.mark.parametrize(
    ("file_key", "status_code"),
    [("purchase_attachment", 200), ("purchase_foreign_attachment", 403), ("purchase_mismatch_attachment", 404)],
)
def test_purchase_credit_note_attachment_download_requires_purchase_access(
    document_alias_scenario, file_key, status_code, monkeypatch
):
    """Purchase alias file is delivered to its authorized module only."""
    app, ids = document_alias_scenario
    client = _authenticated_client(app, ids["buyer"])
    file_reads = []
    original_get_attachment_file = api_module.get_attachment_file

    def track_file_read(file_id):
        file_reads.append(file_id)
        return original_get_attachment_file(file_id)

    monkeypatch.setattr(api_module, "get_attachment_file", track_file_read)

    response = client.get(f"/attachments/download/{ids[file_key]}")

    assert response.status_code == status_code
    if status_code == 200:
        assert response.data == Path(ids["attachment_path"]).read_bytes()
        assert file_reads == [ids[file_key]]
    else:
        assert not file_reads
