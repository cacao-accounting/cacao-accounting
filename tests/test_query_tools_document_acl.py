# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2252/#2253: las herramientas documentales aplican el ACL por módulo.

El ámbito `documents.reports.read` autoriza la familia, pero no sustituye el
permiso del módulo dueño ni el acceso a la compañía del documento.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Modules,
    PaymentEntry,
    PurchaseInvoice,
    SalesInvoice,
    database,
)
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.handlers.documents import (
    get_document_details_handler,
    get_document_flow,
    get_document_status_handler,
)
from cacao_accounting.query_tools.handlers.operational import search_document_relations


@pytest.fixture
def document_acl_scenario():
    """Create documents of three modules and one cross-module relation."""
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
                *[Modules(module=name, default=False, enabled=True) for name in ("sales", "purchases", "cash", "inventory")],
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
        sale = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"INV-{suffix}",
            document_type="sales_invoice",
            customer_name="Cliente",
            grand_total=100,
        )
        purchase = PurchaseInvoice(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"COM-{suffix}",
            document_type="purchase_invoice",
            supplier_name="Proveedor",
            grand_total=80,
        )
        payment = PaymentEntry(
            company="alpha",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"PAY-{suffix}",
            payment_type="receive",
            party_type="customer",
            party_name="Cliente",
            paid_amount=100,
        )
        database.session.add_all([sale, purchase, payment])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=sale.id,
                target_type="payment_entry",
                target_id=payment.id,
                company="alpha",
                qty=Decimal("1"),
                relation_type="payment",
                status="active",
            )
        )
        database.session.commit()
        ids = {
            "sale": sale.id,
            "purchase": purchase.id,
            "payment": payment.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _context(permissions: set[str], companies: list[str] | None = None) -> QueryContext:
    """Build a service-principal context with the requested scopes."""
    return QueryContext(
        user_id="service",
        company_ids=companies or ["alpha"],
        permissions=permissions,
        is_service_principal=True,
    )


def _denied(callable_) -> None:
    """Assert the call fails with a permission error."""
    with pytest.raises(QueryToolError) as excinfo:
        callable_()
    assert excinfo.value.code in {
        ErrorCode.PERMISSION_DENIED,
        ErrorCode.MODULE_DISABLED,
        ErrorCode.COMPANY_ACCESS_DENIED,
    }


def test_document_tools_require_the_owning_module(document_acl_scenario):
    """The company scope alone cannot read an invoice projection."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read"})

    with app.app_context():
        _denied(
            lambda: get_document_details_handler.handler(
                context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
            )
        )
        _denied(
            lambda: get_document_status_handler.handler(
                context=context, company_id="alpha", document_type="purchase_invoice", document_id=ids["purchase"]
            )
        )


def test_sales_scope_reads_sales_but_not_purchase(document_acl_scenario):
    """The sales module opens sales invoices and rejects purchases."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read", "sales.reports.read"})

    with app.app_context():
        sale = get_document_details_handler.handler(
            context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
        )
        assert sale["found"] is True
        _denied(
            lambda: get_document_details_handler.handler(
                context=context, company_id="alpha", document_type="purchase_invoice", document_id=ids["purchase"]
            )
        )


def test_flow_hides_relations_to_modules_without_permission(document_acl_scenario):
    """A sales reader does not see the linked cash payment in the flow."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read", "sales.reports.read"})

    with app.app_context():
        flow = get_document_flow.handler(
            context=context,
            company_id="alpha",
            document_type="sales_invoice",
            document_id=ids["sale"],
        )
        assert flow["items"] == []

        cash_context = _context({"documents.reports.read", "sales.reports.read", "cash.reports.read"})
        visible = get_document_flow.handler(
            context=cash_context,
            company_id="alpha",
            document_type="sales_invoice",
            document_id=ids["sale"],
        )
        assert len(visible["items"]) == 1


def test_search_relations_filters_by_readable_modules(document_acl_scenario):
    """A relation touching an unreadable module is excluded from the search."""
    app, ids = document_acl_scenario

    with app.app_context():
        sales_only = search_document_relations.handler(
            context=_context({"documents.reports.read", "sales.reports.read"}),
            company_id="alpha",
        )
        assert sales_only["items"] == []

        with_cash = search_document_relations.handler(
            context=_context({"documents.reports.read", "sales.reports.read", "cash.reports.read"}),
            company_id="alpha",
        )
        assert len(with_cash["items"]) == 1
        assert with_cash["items"][0]["target_id"] == ids["payment"]


def test_document_tools_enforce_company_scope(document_acl_scenario):
    """A scope for another company cannot read the document."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read", "sales.reports.read"}, companies=["beta"])

    with app.app_context():
        _denied(
            lambda: get_document_details_handler.handler(
                context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
            )
        )
