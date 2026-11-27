# SPDX-License-Identifier: Apache-2.0
"""#1872: cancelar StockEntry via aprobaci?n revierte relaci?n y refresca estado derivado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.internal_control_service import approval_request_transition
from cacao_accounting.database import (
    AccountingPeriod,
    ApprovalRequest,
    Book,
    DeliveryNote,
    DeliveryNoteItem,
    DocumentLineFlowState,
    DocumentRelation,
    FiscalYear,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerBookEntry,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.document_flow.service import get_source_items


def _seed(app):
    with app.app_context():
        suffix = "1872"
        fy = FiscalYear(
            entity="cacao",
            name="FY1872",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fy)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                fiscal_year_id=fy.id,
                entity="cacao",
                name="2026-05-1872",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                is_closed=False,
                enabled=True,
            )
        )
        database.session.merge(UOM(code="U1872", name="Unidad 1872", is_active=True))
        database.session.flush()
        database.session.add(Warehouse(code="WH1872", name="Bodega 1872", company="cacao"))
        database.session.add(Item(code="IT1872", name="Item 1872", item_type="goods", is_stock_item=True, default_uom="U1872"))
        database.session.flush()
        dn = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="approved",
            document_no=f"DN-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(dn)
        database.session.flush()
        dn_item = DeliveryNoteItem(
            delivery_note_id=dn.id, item_code="IT1872", qty=Decimal("1"), uom="U1872", qty_in_base_uom=Decimal("1")
        )
        database.session.add(dn_item)
        database.session.flush()

        se = StockEntry(
            company="cacao",
            purpose="material_issue",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="submitted",
            document_no=f"SE-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(se)
        database.session.flush()
        se_item = StockEntryItem(
            stock_entry_id=se.id, item_code="IT1872", qty=Decimal("1"), uom="U1872", qty_in_base_uom=Decimal("1")
        )
        database.session.add(se_item)
        database.session.flush()

        relation = DocumentRelation(
            source_type="delivery_note",
            source_id=dn.id,
            source_item_id=dn_item.id,
            target_type="stock_entry",
            target_id=se.id,
            target_item_id=se_item.id,
            qty=Decimal("1"),
            status="active",
            company="cacao",
            relation_type="delivery_note_to_stock_entry",
        )
        database.session.add(relation)
        database.session.add(
            DocumentLineFlowState(
                company="cacao",
                source_type="delivery_note",
                source_id=dn.id,
                source_item_id=dn_item.id,
                target_type="stock_entry",
                source_qty=Decimal("1"),
                processed_qty=Decimal("1"),
                cancelled_qty=Decimal("0"),
                closed_qty=Decimal("0"),
                pending_qty=Decimal("0"),
                line_status="complete",
            )
        )
        database.session.add(
            StockBin(
                company="cacao",
                item_code="IT1872",
                warehouse="WH1872",
                actual_qty=Decimal("0"),
                stock_value=Decimal("0"),
            )
        )
        sle = StockLedgerEntry(
            posting_date=date(2026, 5, 15),
            company="cacao",
            item_code="IT1872",
            warehouse="WH1872",
            qty_change=Decimal("-1"),
            stock_value_difference=Decimal("-10"),
            valuation_rate=Decimal("10"),
            qty_after_transaction=Decimal("0"),
            stock_value=Decimal("0"),
            voucher_type="stock_entry",
            voucher_id=se.id,
            is_cancelled=False,
        )
        database.session.add(sle)
        database.session.flush()
        book = database.session.execute(database.select(Book).filter_by(entity="cacao", code="DEFAULT_BOOK")).scalar_one()
        database.session.add(
            StockLedgerBookEntry(
                stock_ledger_entry_id=sle.id,
                ledger_id=book.id,
                posting_date=sle.posting_date,
                book_currency="NIO",
                book_amount=Decimal("-10"),
                exchange_rate=Decimal("1"),
            )
        )
        database.session.add(
            StockValuationLayer(
                item_code="IT1872",
                warehouse="WH1872",
                company="cacao",
                qty=Decimal("-1"),
                rate=Decimal("10"),
                stock_value_difference=Decimal("-10"),
                remaining_qty=Decimal("0"),
                remaining_stock_value=Decimal("0"),
                voucher_type="stock_entry",
                voucher_id=se.id,
                posting_date=date(2026, 5, 15),
            )
        )
        user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        req = ApprovalRequest(
            document_type="cancel_stock_entry",
            document_id=se.id,
            requested_by=str(user.id),
            company_id="cacao",
            current_level=1,
            required_level=1,
            status="pending",
            cancellation_reason="Prueba 1872",
        )
        database.session.add(req)
        database.session.flush()
        with approval_request_transition(req):
            req.status = "approved"
        database.session.commit()
        return dn.id, dn_item.id, se.id, req.id, str(user.id)


def test_approval_cancel_stock_entry_reverts_relation_and_refreshes_flow(app):
    dn_id, dn_item_id, se_id, req_id, user_id = _seed(app)
    with app.app_context():
        req = database.session.get(ApprovalRequest, req_id)
        se = database.session.get(StockEntry, se_id)
        user = SimpleNamespace(id=user_id, name="admin")
        ApprovalEngine._finalize_approval(req, se, user)
        database.session.commit()

        relation = database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="stock_entry", target_id=se_id)
        ).scalar_one()
        assert relation.status != "active"

        flow = database.session.execute(
            database.select(DocumentLineFlowState).filter_by(
                source_type="delivery_note", source_id=dn_id, source_item_id=dn_item_id, target_type="stock_entry"
            )
        ).scalar_one()
        assert Decimal(str(flow.pending_qty)) == Decimal("1")
        assert flow.line_status != "complete"

        payload = get_source_items("delivery_note", dn_id, "stock_entry")
        item = next(i for i in payload if str(i.get("source_item_id")) == dn_item_id)
        assert Decimal(str(item["pending_qty"])) == Decimal("1")
        assert item["line_status"] != "complete"
