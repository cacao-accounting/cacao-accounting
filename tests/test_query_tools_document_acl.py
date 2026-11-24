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
    Item,
    Modules,
    PaymentEntry,
    PurchaseInvoice,
    SalesInvoice,
    SalesInvoiceItem,
    UOM,
    database,
)
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.handlers.documents import (
    get_document_details_handler,
    get_document_flow,
    get_document_lines_handler,
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
        database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.flush()
        database.session.add(
            Item(
                code="ART-2252",
                name="Artículo consultado",
                item_type="goods",
                is_stock_item=False,
                default_uom="UND",
            )
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
            SalesInvoiceItem(
                sales_invoice_id=sale.id,
                item_code="ART-2252",
                item_name="Artículo consultado",
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom="UND",
                rate=Decimal("50"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
            )
        )
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=sale.id,
                target_type="payment_entry",
                target_id=payment.id,
                company="alpha",
                qty=Decimal("1"),
                amount=Decimal("0"),
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


def test_document_lines_require_the_owning_module(document_acl_scenario):
    """El ámbito documents no sustituye el permiso del módulo para get_lines."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read"})

    with app.app_context():
        _denied(
            lambda: get_document_lines_handler.handler(
                context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
            )
        )


def test_sales_scope_reads_lines_and_status(document_acl_scenario):
    """Las tres herramientas responden con el módulo dueño autorizado."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read", "receivables.reports.read"})

    with app.app_context():
        lineas = get_document_lines_handler.handler(
            context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
        )
        estado = get_document_status_handler.handler(
            context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
        )
        detalle = get_document_details_handler.handler(
            context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
        )

        assert lineas["found"] is True
        assert len(lineas["items"]) == 1
        linea = lineas["items"][0]
        assert linea["item_code"] == "ART-2252"
        assert linea["item_name"] == "Artículo consultado"
        assert linea["qty"] == "2.000000000"
        assert linea["uom"] == "UND"
        assert linea["rate"] == "50.0000"
        assert linea["amount"] == "100.0000"
        assert lineas["page"]["total_items"] == 1
        assert estado["found"] is True
        assert detalle["found"] is True


def test_sales_scope_reads_sales_but_not_purchase(document_acl_scenario):
    """The sales module opens sales invoices and rejects purchases."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read", "receivables.reports.read"})

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
    context = _context({"documents.reports.read", "receivables.reports.read"})

    with app.app_context():
        flow = get_document_flow.handler(
            context=context,
            company_id="alpha",
            document_type="sales_invoice",
            document_id=ids["sale"],
        )
        assert flow["items"] == []

        cash_context = _context({"documents.reports.read", "receivables.reports.read", "banking.reports.read"})
        visible = get_document_flow.handler(
            context=cash_context,
            company_id="alpha",
            document_type="sales_invoice",
            document_id=ids["sale"],
        )
        assert len(visible["items"]) == 1
        assert visible["items"][0]["amount"] == "0.0000"

        relation = database.session.execute(database.select(DocumentRelation).filter_by(source_id=ids["sale"])).scalar_one()
        relation.amount = None
        database.session.commit()
        missing_amount = get_document_flow.handler(
            context=cash_context,
            company_id="alpha",
            document_type="sales_invoice",
            document_id=ids["sale"],
        )
        assert missing_amount["items"][0]["amount"] is None


def test_search_relations_filters_by_readable_modules(document_acl_scenario):
    """A relation touching an unreadable module is excluded from the search."""
    app, ids = document_acl_scenario

    with app.app_context():
        sales_only = search_document_relations.handler(
            context=_context({"documents.reports.read", "receivables.reports.read"}),
            company_id="alpha",
        )
        assert sales_only["items"] == []

        with_cash = search_document_relations.handler(
            context=_context({"documents.reports.read", "receivables.reports.read", "banking.reports.read"}),
            company_id="alpha",
        )
        assert len(with_cash["items"]) == 1
        assert with_cash["items"][0]["target_id"] == ids["payment"]


def test_document_tools_enforce_company_scope(document_acl_scenario):
    """A scope for another company cannot read the document."""
    app, ids = document_acl_scenario
    context = _context({"documents.reports.read", "receivables.reports.read"}, companies=["beta"])

    with app.app_context():
        _denied(
            lambda: get_document_details_handler.handler(
                context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
            )
        )


def test_disabled_module_is_excluded_for_service_principals(document_acl_scenario):
    """Keeping the scope is not enough when the module is disabled."""
    app, _ids = document_acl_scenario
    context = _context({"documents.reports.read", "receivables.reports.read", "banking.reports.read"})

    with app.app_context():
        sales = database.session.execute(database.select(Modules).filter_by(module="sales")).scalar_one()
        sales.enabled = False
        database.session.commit()
        items = search_document_relations.handler(context=context, company_id="alpha")["items"]

    assert items == []


def test_real_service_scopes_open_sales_documents(document_acl_scenario):
    """The published scope vocabulary maps receivables to sales documents."""
    from cacao_accounting.query_tools.publication import permissions_for_scopes

    app, ids = document_acl_scenario
    context = _context(permissions_for_scopes({"documents.read", "receivables.read"}))

    with app.app_context():
        sale = get_document_details_handler.handler(
            context=context, company_id="alpha", document_type="sales_invoice", document_id=ids["sale"]
        )

    assert sale["found"] is True
