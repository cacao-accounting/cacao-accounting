# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""P6: dos relaciones no pueden sobreconsumir la misma línea origen.

`create_document_relation` calculaba el pendiente y luego insertaba la
relación. Sin serializar por línea, dos transacciones leían el mismo pendiente
y creaban relaciones hacia destinos distintos que, juntas, excedían la
cantidad aprobada.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event, local
from uuid import uuid4

from sqlalchemy import func, inspect as sa_inspect

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentFlowLock,
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
from cacao_accounting.database.helpers import _ensure_document_flow_lock_table
from cacao_accounting.document_flow import service
from cacao_accounting.document_flow.service import DocumentFlowError, create_document_relation


def _build_app(database_uri: str):
    """Create an application isolated on the given database URI."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )


def _seed_quotation(app):
    """Seed a quotation for five units and two orders of three units."""
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
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        )
        database.session.flush()
        customer = Party(code=f"CUST-{suffix}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(customer)
        database.session.flush()
        quotation = SalesQuotation(
            company="alpha",
            document_no=f"SQ-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        order_a = SalesOrder(
            company="alpha",
            document_no=f"SO-A-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            posting_date=date(2026, 5, 11),
            docstatus=1,
        )
        order_b = SalesOrder(
            company="alpha",
            document_no=f"SO-B-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            posting_date=date(2026, 5, 11),
            docstatus=1,
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
        order_items = [
            SalesOrderItem(
                sales_order_id=order.id,
                item_code=f"ITEM-{suffix}",
                item_name="Artículo",
                qty=Decimal("3"),
                qty_in_base_uom=Decimal("3"),
                uom="EA",
                rate=Decimal("10"),
                amount=Decimal("30"),
            )
            for order in (order_a, order_b)
        ]
        database.session.add_all([quotation_item, *order_items])
        database.session.commit()
        ids = {
            "source_id": quotation.id,
            "source_item_id": quotation_item.id,
            "targets": [(order_a.id, order_items[0].id), (order_b.id, order_items[1].id)],
        }
        database.session.remove()
    return ids


def test_concurrent_relations_cannot_overconsume_source_line(tmp_path, monkeypatch):
    """A second relation waits for the first and rejects the unavailable qty."""
    app = _build_app(f"sqlite:///{tmp_path / 'document-relation.sqlite'}")
    ids = _seed_quotation(app)

    state = local()
    paused = Event()
    release = Event()
    contender_done = Event()
    original_save = service.save_relation

    def controlled_save(relation):
        if getattr(state, "pause_before_save", False):
            state.pause_before_save = False
            paused.set()
            assert release.wait(timeout=10), "La prueba no liberó la relación contendiente."
        return original_save(relation)

    monkeypatch.setattr(service, "save_relation", controlled_save)

    def create_relation(target, hold=False):
        state.pause_before_save = hold
        with app.app_context():
            try:
                create_document_relation(
                    source_type="sales_quotation",
                    source_id=ids["source_id"],
                    source_item_id=ids["source_item_id"],
                    target_type="sales_order",
                    target_id=target[0],
                    target_item_id=target[1],
                    qty=Decimal("3"),
                )
                database.session.commit()
                return "created"
            except DocumentFlowError:
                database.session.rollback()
                return "rejected"
            finally:
                if not hold:
                    contender_done.set()
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        holder = executor.submit(create_relation, ids["targets"][0], True)
        assert paused.wait(timeout=10), "La relación inicial no llegó a persistirse."
        contender = executor.submit(create_relation, ids["targets"][1])
        # Sin bloqueo, la relación contendiente termina mientras la primera
        # sigue pausada antes de insertar; con bloqueo, espera el turno.
        contender_done.wait(timeout=1)
        release.set()
        results = [holder.result(timeout=20), contender.result(timeout=20)]

    assert sorted(results) == ["created", "rejected"]

    with app.app_context():
        consumed = database.session.execute(
            database.select(func.coalesce(func.sum(DocumentRelation.qty_in_base_uom), 0)).filter_by(
                source_type="sales_quotation",
                source_id=ids["source_id"],
                source_item_id=ids["source_item_id"],
                status="active",
            )
        ).scalar_one()
        assert Decimal(str(consumed)) == Decimal("3")
        database.session.remove()


def test_existing_database_receives_document_flow_lock_table(tmp_path):
    """A legacy database without the lock table gets it at startup/ensure time."""
    app = _build_app(f"sqlite:///{tmp_path / 'legacy-document-flow.sqlite'}")

    with app.app_context():
        DocumentFlowLock.__table__.drop(bind=database.engine)
        assert not sa_inspect(database.engine).has_table(DocumentFlowLock.__tablename__)

        _ensure_document_flow_lock_table()

        assert sa_inspect(database.engine).has_table(DocumentFlowLock.__tablename__)
        database.session.remove()
        database.engine.dispose()
