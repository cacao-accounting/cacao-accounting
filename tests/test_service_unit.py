# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests unitarios para funciones publicas de document_flow/service.py sin cobertura previa.

Funciones cubiertas:
- pending_qty
- get_document_flow_items
- get_pending_lines
- close_document_balances
- list_source_documents
- refresh_source_caches_for_target
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    Party,
    DocumentRelation,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.document_flow.service import (
    DocumentFlowError,
    close_document_balances,
    close_line_balance,
    create_document_relation,
    get_document_flow_items,
    get_pending_lines,
    list_source_documents,
    pending_qty,
    refresh_source_caches_for_target,
)
from cacao_accounting.document_flow.repository import get_document_item


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()
        database.session.commit()
        yield app


def _get_supplier():
    return database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()


def _create_purchase_order(supplier, qty=Decimal("10"), rate=Decimal("100")):
    po = PurchaseOrder(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        docstatus=1,
    )
    database.session.add(po)
    database.session.flush()

    item = PurchaseOrderItem(
        purchase_order_id=po.id,
        item_code="TEST-ITEM-001",
        qty=qty,
        rate=rate,
        amount=qty * rate,
    )
    database.session.add(item)
    database.session.commit()
    return po, item


def _create_receipt(supplier, po_id):
    pr = PurchaseReceipt(
        company="cacao",
        supplier_id=supplier.id,
        purchase_order_id=po_id,
        posting_date=date.today(),
        docstatus=1,
    )
    database.session.add(pr)
    database.session.flush()
    return pr


class TestPendingQty:
    def test_full_pending_no_relations(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))

        result = pending_qty("purchase_order", po.id, item.id, "purchase_receipt")
        assert result == Decimal("10")

    def test_partial_consumption(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))
        pr = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("4"),
        )

        result = pending_qty("purchase_order", po.id, item.id, "purchase_receipt")
        assert result == Decimal("6")

    def test_full_consumption_returns_zero(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))
        pr = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("10"),
        )

        result = pending_qty("purchase_order", po.id, item.id, "purchase_receipt")
        assert result == Decimal("0")

    def test_zero_floor_when_over_consumed(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))
        pr = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("10"),
        )

        state = database.session.execute(
            database.select(
                __import__("cacao_accounting.database", fromlist=["DocumentLineFlowState"]).DocumentLineFlowState
            ).filter_by(
                source_type="purchase_order",
                source_id=po.id,
                source_item_id=item.id,
                target_type="purchase_receipt",
            )
        ).scalar_one_or_none()
        if state:
            state.cancelled_qty = Decimal("2")
            database.session.commit()

        result = pending_qty("purchase_order", po.id, item.id, "purchase_receipt")
        assert result >= Decimal("0")

    def test_missing_source_item_raises(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)

        with pytest.raises(DocumentFlowError) as exc_info:
            pending_qty("purchase_order", po.id, "NONEXISTENT_ITEM", "purchase_receipt")
        assert exc_info.value.status_code == 404


class TestGetDocumentFlowItems:
    def test_valid_single_source(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier)

        items = get_document_flow_items(
            target_type="purchase_receipt",
            source_values=[f"purchase_order:{po.id}"],
        )
        assert len(items) == 1
        assert items[0]["source_item_id"] == item.id

    def test_valid_multiple_sources(self, app_ctx):
        supplier = _get_supplier()
        po1, item1 = _create_purchase_order(supplier, qty=Decimal("5"))
        po2, item2 = _create_purchase_order(supplier, qty=Decimal("8"))

        items = get_document_flow_items(
            target_type="purchase_receipt",
            source_values=[
                f"purchase_order:{po1.id}",
                f"purchase_order:{po2.id}",
            ],
        )
        assert len(items) == 2
        ids = {i["source_item_id"] for i in items}
        assert item1.id in ids
        assert item2.id in ids

    def test_malformed_input_no_colon_raises(self, app_ctx):
        with pytest.raises(DocumentFlowError) as exc_info:
            get_document_flow_items(
                target_type="purchase_receipt",
                source_values=["purchase_order"],
            )
        assert exc_info.value.status_code == 400

    def test_empty_source_values(self, app_ctx):
        items = get_document_flow_items(
            target_type="purchase_receipt",
            source_values=[],
        )
        assert items == []

    def test_returns_only_pending_items(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("5"))
        pr = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("5"),
        )

        items = get_document_flow_items(
            target_type="purchase_receipt",
            source_values=[f"purchase_order:{po.id}"],
        )
        assert items == []


class TestGetPendingLines:
    def test_returns_enriched_lines(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier)

        lines = get_pending_lines(
            source_document_type="purchase_order",
            source_document_ids=[po.id],
            target_document_type="purchase_receipt",
            company="cacao",
        )
        assert len(lines) == 1
        assert lines[0]["source_document_no"] is not None
        assert lines[0]["source_item_id"] == item.id

    def test_company_mismatch_raises(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)

        with pytest.raises(DocumentFlowError) as exc_info:
            get_pending_lines(
                source_document_type="purchase_order",
                source_document_ids=[po.id],
                target_document_type="purchase_receipt",
                company="other_company",
            )
        assert exc_info.value.status_code == 409

    def test_multiple_source_documents(self, app_ctx):
        supplier = _get_supplier()
        po1, item1 = _create_purchase_order(supplier, qty=Decimal("3"))
        po2, item2 = _create_purchase_order(supplier, qty=Decimal("7"))

        lines = get_pending_lines(
            source_document_type="purchase_order",
            source_document_ids=[po1.id, po2.id],
            target_document_type="purchase_receipt",
            company="cacao",
        )
        assert len(lines) == 2
        item_ids = {l["source_item_id"] for l in lines}
        assert item1.id in item_ids
        assert item2.id in item_ids

    def test_no_company_filter(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)

        lines = get_pending_lines(
            source_document_type="purchase_order",
            source_document_ids=[po.id],
            target_document_type="purchase_receipt",
        )
        assert len(lines) == 1


class TestCloseDocumentBalances:
    def test_closes_all_pending_items(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))

        closed = close_document_balances(
            source_type="purchase_order",
            source_id=po.id,
            target_type="purchase_receipt",
            reason="Saldo cancelado por proveedor",
        )
        assert len(closed) == 1
        assert closed[0]["closed_qty"] == 10.0

    def test_skips_already_closed_items(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))

        pr = _create_receipt(supplier, po.id)
        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("10"),
        )

        closed = close_document_balances(
            source_type="purchase_order",
            source_id=po.id,
            target_type="purchase_receipt",
            reason="Ya consume todo",
        )
        assert closed == []

    def test_closes_partial_remaining(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))
        pr = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("4"),
        )

        closed = close_document_balances(
            source_type="purchase_order",
            source_id=po.id,
            target_type="purchase_receipt",
            reason="Cerrando saldo restante",
        )
        assert len(closed) == 1
        assert closed[0]["closed_qty"] == 6.0


class TestCloseLineBalance:
    def test_close_full_pending(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))

        result = close_line_balance(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            qty=Decimal("10"),
            reason="Proveedor no entregara el resto",
        )
        assert result["closed_qty"] == 10.0
        assert result["pending_qty"] == 0.0

    def test_close_partial(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))

        result = close_line_balance(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            qty=Decimal("3"),
            reason="Cancelacion parcial",
        )
        assert result["closed_qty"] == 3.0
        assert result["pending_qty"] == 7.0

    def test_close_all_pending_when_qty_none(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))

        result = close_line_balance(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            qty=None,
            reason="Cerrar todo",
        )
        assert result["closed_qty"] == 10.0

    def test_empty_reason_raises(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier)

        with pytest.raises(DocumentFlowError) as exc_info:
            close_line_balance(
                source_type="purchase_order",
                source_id=po.id,
                source_item_id=item.id,
                target_type="purchase_receipt",
                qty=Decimal("5"),
                reason="   ",
            )
        assert exc_info.value.status_code == 409

    def test_zero_qty_raises(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier)

        with pytest.raises(DocumentFlowError) as exc_info:
            close_line_balance(
                source_type="purchase_order",
                source_id=po.id,
                source_item_id=item.id,
                target_type="purchase_receipt",
                qty=Decimal("0"),
                reason="Motivo",
            )
        assert exc_info.value.status_code == 409

    def test_exceeds_pending_raises(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("5"))

        with pytest.raises(DocumentFlowError) as exc_info:
            close_line_balance(
                source_type="purchase_order",
                source_id=po.id,
                source_item_id=item.id,
                target_type="purchase_receipt",
                qty=Decimal("10"),
                reason="Exceso",
            )
        assert exc_info.value.status_code == 409


class TestListSourceDocuments:
    def test_returns_approved_documents_with_pending(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)

        docs = list_source_documents(
            target_type="purchase_receipt",
            company="cacao",
        )
        assert len(docs) >= 1
        assert any(d["source_id"] == po.id for d in docs)

    def test_filters_by_company(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)

        docs = list_source_documents(
            target_type="purchase_receipt",
            company="other_company",
        )
        assert all(d["source_id"] != po.id for d in docs)

    def test_filters_by_party(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)

        docs = list_source_documents(
            target_type="purchase_receipt",
            company="cacao",
            party_type="supplier",
            party_id="NONEXISTENT_PARTY",
        )
        assert all(d["source_id"] != po.id for d in docs)

    def test_empty_when_no_approved_documents(self, app_ctx):
        supplier = _get_supplier()
        po = PurchaseOrder(
            company="cacao",
            supplier_id=supplier.id,
            posting_date=date.today(),
            docstatus=0,
        )
        database.session.add(po)
        database.session.flush()

        item = PurchaseOrderItem(
            purchase_order_id=po.id,
            item_code="TEST-ITEM-001",
            qty=Decimal("10"),
            rate=Decimal("100"),
            amount=Decimal("1000"),
        )
        database.session.add(item)
        database.session.commit()

        docs = list_source_documents(
            target_type="purchase_receipt",
            company="cacao",
        )
        assert all(d["source_id"] != po.id for d in docs)


class TestRefreshSourceCachesForTarget:
    def test_updates_received_qty_for_purchase_receipt(self, app_ctx):
        from cacao_accounting.document_flow.registry import normalize_doctype

        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("10"))
        pr = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr.id,
            target_item_id=None,
            qty=Decimal("6"),
        )

        refresh_source_caches_for_target("purchase_receipt", pr.id)

        refreshed_item = get_document_item("purchase_order", item.id)
        assert Decimal(str(refreshed_item.received_qty)) == Decimal("6")

    def test_no_error_when_no_relations(self, app_ctx):
        supplier = _get_supplier()
        po, _ = _create_purchase_order(supplier)
        pr = _create_receipt(supplier, po.id)

        refresh_source_caches_for_target("purchase_receipt", pr.id)

    def test_updates_after_relation_creation(self, app_ctx):
        supplier = _get_supplier()
        po, item = _create_purchase_order(supplier, qty=Decimal("20"))
        pr1 = _create_receipt(supplier, po.id)
        pr2 = _create_receipt(supplier, po.id)

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr1.id,
            target_item_id=None,
            qty=Decimal("5"),
        )

        create_document_relation(
            source_type="purchase_order",
            source_id=po.id,
            source_item_id=item.id,
            target_type="purchase_receipt",
            target_id=pr2.id,
            target_item_id=None,
            qty=Decimal("8"),
        )

        refresh_source_caches_for_target("purchase_receipt", pr1.id)

        refreshed_item = get_document_item("purchase_order", item.id)
        assert Decimal(str(refreshed_item.received_qty)) == Decimal("13")
