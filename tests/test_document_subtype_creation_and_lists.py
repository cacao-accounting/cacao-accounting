# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2254/#2255: el subtipo lógico se conserva al crear, listar y colaborar.

Los alias de nota comparten modelo con la factura; la creación debe guardar
`document_type` y las superficies de lista/colaboración deben rechazar el
subtipo que no coincide.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting import create_app
from cacao_accounting.api import _filter_authorized_documents
from cacao_accounting.collaboration_service import CollaborationError, _document_for_collaboration
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_flow import service as flow_service
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES


@pytest.fixture
def document_subtype_scenario(monkeypatch):
    """Create a company, an admin and two invoices with different subtypes."""
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
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        # #1828: en Cloud la clasificación admin no concede compañías por sí sola.
        database.session.add(UserCompanyAccess(user_id=f"admin-{suffix}", company_code="alpha"))
        invoice = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"INV-{suffix}",
            document_type="sales_invoice",
            customer_name="Cliente",
            grand_total=100,
        )
        credit_note = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"CN-{suffix}",
            document_type="sales_credit_note",
            customer_name="Cliente",
            grand_total=100,
        )
        database.session.add_all([invoice, credit_note])
        database.session.commit()
        ids = {
            "admin": f"admin-{suffix}",
            "invoice": invoice.id,
            "credit_note": credit_note.id,
        }

    monkeypatch.setattr(flow_service, "assign_document_identifier", lambda **kwargs: None)
    monkeypatch.setattr(flow_service, "log_create", lambda document: None)

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize("target_type", ["sales_credit_note", "sales_return"])
def test_target_header_persists_the_requested_subtype(document_subtype_scenario, target_type):
    """The created invoice keeps the logical alias instead of the model default."""
    app, _ids = document_subtype_scenario

    with app.app_context():
        target = flow_service._create_target_header(
            DOCUMENT_TYPES[target_type],
            target_type,
            "alpha",
            date(2026, 5, 10),
            {"customer_name": "Cliente"},
        )
        database.session.commit()
        persisted = database.session.get(SalesInvoice, target.id)
        assert persisted is not None
        assert persisted.document_type == target_type


def test_related_list_filters_by_logical_subtype(document_subtype_scenario):
    """A plain invoice is excluded when the list asks for a return."""
    app, ids = document_subtype_scenario

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["admin"]), remember=False, force=True)
        invoice = database.session.get(SalesInvoice, ids["invoice"])
        credit_note = database.session.get(SalesInvoice, ids["credit_note"])
        assert _filter_authorized_documents([invoice], "sales_return") == []
        assert _filter_authorized_documents([invoice], "sales_invoice") == [invoice]
        assert _filter_authorized_documents([credit_note], "sales_credit_note") == [credit_note]


def test_collaboration_rejects_a_mismatched_subtype(document_subtype_scenario):
    """A task cannot resolve a plain invoice as a return."""
    app, ids = document_subtype_scenario

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["admin"]), remember=False, force=True)
        with pytest.raises(CollaborationError):
            _document_for_collaboration("sales_return", ids["invoice"], ids["admin"])
        document = _document_for_collaboration("sales_credit_note", ids["credit_note"], ids["admin"])
        assert document.document_type == "sales_credit_note"
