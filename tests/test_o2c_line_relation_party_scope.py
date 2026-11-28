# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1388: las relaciones O2C no mezclan clientes entre documentos.

La validación vive en `create_document_relation`, por lo que cubre tanto la
creación manual por línea de Ventas como el endpoint genérico de destino.
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
    Party,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    UOM,
    database,
)
from cacao_accounting.document_flow.service import (
    DocumentFlowError,
    assert_relation_same_party,
    create_document_relation,
)


@pytest.fixture
def sales_relation_party_scenario():
    """Create a quotation for Customer A and orders for A and B."""
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
                Modules(module="sales", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        database.session.add(UOM(code="EA", name="Each", is_active=True))
        database.session.flush()
        database.session.add(
            Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        )
        customer_a = Party(code=f"CUST-A-{suffix}", name="Cliente A", is_customer=True, is_active=True)
        customer_b = Party(code=f"CUST-B-{suffix}", name="Cliente B", is_customer=True, is_active=True)
        database.session.add_all([customer_a, customer_b])
        database.session.flush()

        quotation = SalesQuotation(
            company="alpha",
            document_no="SQ1",
            customer_id=customer_a.id,
            customer_name="Cliente A",
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        order_a = SalesOrder(
            company="alpha",
            document_no="SO-A",
            customer_id=customer_a.id,
            customer_name="Cliente A",
            posting_date=date(2026, 5, 11),
            docstatus=0,
        )
        order_b = SalesOrder(
            company="alpha",
            document_no="SO-B",
            customer_id=customer_b.id,
            customer_name="Cliente B",
            posting_date=date(2026, 5, 11),
            docstatus=0,
        )
        database.session.add_all([quotation, order_a, order_b])
        database.session.flush()
        quotation_item = SalesQuotationItem(
            sales_quotation_id=quotation.id,
            item_code=f"ITEM-{suffix}",
            item_name="Artículo",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("50"),
        )
        order_a_item = SalesOrderItem(
            sales_order_id=order_a.id,
            item_code=f"ITEM-{suffix}",
            item_name="Artículo",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
        order_b_item = SalesOrderItem(
            sales_order_id=order_b.id,
            item_code=f"ITEM-{suffix}",
            item_name="Artículo",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
        database.session.add_all([quotation_item, order_a_item, order_b_item])
        database.session.commit()
        ids = {
            "quotation": quotation.id,
            "quotation_item": quotation_item.id,
            "order_a": order_a.id,
            "order_a_item": order_a_item.id,
            "order_b": order_b.id,
            "order_b_item": order_b_item.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _create_relation(ids, order_key: str, item_key: str) -> DocumentRelation:
    """Create the quotation-to-order relation for the requested order."""
    return create_document_relation(
        source_type="sales_quotation",
        source_id=ids["quotation"],
        source_item_id=ids["quotation_item"],
        target_type="sales_order",
        target_id=ids[order_key],
        target_item_id=ids[item_key],
        qty=Decimal("1"),
        uom="EA",
        rate=Decimal("10"),
        amount=Decimal("10"),
    )


def test_relation_between_different_customers_is_rejected(sales_relation_party_scenario):
    """A quotation for Customer A cannot feed an order for Customer B."""
    app, ids = sales_relation_party_scenario

    with app.app_context():
        with pytest.raises(DocumentFlowError) as error:
            _create_relation(ids, "order_b", "order_b_item")
        database.session.rollback()
        assert error.value.status_code == 409
        assert database.session.execute(database.select(DocumentRelation)).scalars().all() == []


def test_relation_between_same_customer_is_persisted(sales_relation_party_scenario):
    """The same customer keeps the normal O2C relation flow."""
    app, ids = sales_relation_party_scenario

    with app.app_context():
        relation = _create_relation(ids, "order_a", "order_a_item")
        database.session.commit()
        assert relation.source_id == ids["quotation"]
        assert relation.target_id == ids["order_a"]


def test_direct_relation_writes_validate_the_same_party(sales_relation_party_scenario):
    """Las rutas directas reutilizan la guarda de tercero de las relaciones O2C."""
    app, ids = sales_relation_party_scenario

    with app.app_context():
        assert_relation_same_party("sales_quotation", ids["quotation"], "sales_order", ids["order_a"])
        with pytest.raises(DocumentFlowError) as error:
            assert_relation_same_party("sales_quotation", ids["quotation"], "sales_order", ids["order_b"])
        assert error.value.status_code == 409
