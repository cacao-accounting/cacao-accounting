# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del motor de relaciones documentales."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicacion aislada con base SQLite en memoria."""

    app = create_app({**configuracion, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        from cacao_accounting.database import database

        database.create_all()
        yield app


def _seed_purchase_order(app_ctx):
    from cacao_accounting.database import Entity, Item, PurchaseOrder, PurchaseOrderItem, UOM, database

    entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO")
    uom = UOM(code="UND", name="Unidad")
    item = Item(code="ART-001", name="Chocolate", item_type="goods", is_stock_item=True, default_uom="UND")
    order = PurchaseOrder(id="PO-001", company="cacao", posting_date=date(2026, 5, 3), docstatus=1)
    order_item = PurchaseOrderItem(
        purchase_order_id="PO-001",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("50"),
    )
    database.session.add_all([entity, uom, item, order, order_item])
    database.session.flush()
    return order_item


def test_document_flow_tracks_partial_pending_qty(app_ctx):
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import create_document_relation
    from cacao_accounting.document_flow.service import get_source_items

    order_item = _seed_purchase_order(app_ctx)
    receipt = PurchaseReceipt(id="PR-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=0)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-001",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("4"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("20"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()

    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-001",
        target_item_id=receipt_item.id,
        qty=Decimal("4"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("20"),
    )

    items = get_source_items("purchase_order", "PO-001", "purchase_receipt")

    assert items[0]["source_qty"] == 10
    assert items[0]["consumed_qty"] == 4
    assert items[0]["pending_qty"] == 6
    assert order_item.received_qty == Decimal("4")


def test_document_flow_blocks_overconsumption(app_ctx):
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import DocumentFlowError, create_document_relation

    order_item = _seed_purchase_order(app_ctx)
    receipt = PurchaseReceipt(id="PR-002", company="cacao", posting_date=date(2026, 5, 4), docstatus=0)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-002",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("11"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("55"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()

    with pytest.raises(DocumentFlowError) as exc_info:
        create_document_relation(
            source_type="purchase_order",
            source_id="PO-001",
            source_item_id=order_item.id,
            target_type="purchase_receipt",
            target_id="PR-002",
            target_item_id=receipt_item.id,
            qty=Decimal("11"),
            uom="UND",
            rate=Decimal("5"),
            amount=Decimal("55"),
        )

    assert exc_info.value.status_code == 409


def test_document_flow_releases_pending_qty_when_target_is_reverted(app_ctx):
    from cacao_accounting.database import DocumentRelation, PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import create_document_relation, revert_relations_for_target
    from cacao_accounting.document_flow.service import get_source_items

    order_item = _seed_purchase_order(app_ctx)
    receipt = PurchaseReceipt(id="PR-003", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-003",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("4"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("20"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()
    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-003",
        target_item_id=receipt_item.id,
        qty=Decimal("4"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("20"),
    )

    receipt.docstatus = 2
    reverted = revert_relations_for_target("purchase_receipt", "PR-003")
    items = get_source_items("purchase_order", "PO-001", "purchase_receipt")
    relation = database.session.execute(database.select(DocumentRelation)).scalar_one()

    assert reverted == 1
    assert relation.status == "reverted"
    assert items[0]["pending_qty"] == 10
    assert order_item.received_qty == Decimal("0")


def test_document_flow_closes_manual_line_balance(app_ctx):
    from cacao_accounting.document_flow import DocumentFlowError, close_line_balance, create_document_relation
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow.service import get_source_items

    order_item = _seed_purchase_order(app_ctx)
    state = close_line_balance(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        qty=Decimal("3"),
        reason="Proveedor no enviara saldo",
    )
    receipt = PurchaseReceipt(id="PR-004", company="cacao", posting_date=date(2026, 5, 4), docstatus=0)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-004",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("8"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("40"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()

    with pytest.raises(DocumentFlowError):
        create_document_relation(
            source_type="purchase_order",
            source_id="PO-001",
            source_item_id=order_item.id,
            target_type="purchase_receipt",
            target_id="PR-004",
            target_item_id=receipt_item.id,
            qty=Decimal("8"),
            uom="UND",
            rate=Decimal("5"),
            amount=Decimal("40"),
        )

    items = get_source_items("purchase_order", "PO-001", "purchase_receipt")

    assert state["closed_qty"] == 3
    assert state["pending_qty"] == 7
    assert items[0]["closed_qty"] == 3
    assert items[0]["pending_qty"] == 7


def test_document_status_uses_single_operational_badge(app_ctx):
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import close_line_balance, create_document_relation
    from cacao_accounting.document_flow.status import calculate_document_status

    order_item = _seed_purchase_order(app_ctx)

    open_status = calculate_document_status("purchase_order", "PO-001")
    assert open_status.label == "Pendiente Recibir"
    assert open_status.badge_class == "text-bg-primary"

    receipt = PurchaseReceipt(id="PR-005", company="cacao", posting_date=date(2026, 5, 4), docstatus=0)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-005",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("4"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("20"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()
    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-005",
        target_item_id=receipt_item.id,
        qty=Decimal("4"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("20"),
    )

    partial_status = calculate_document_status("purchase_order", "PO-001")
    assert partial_status.label == "Recibido Parcialmente"

    close_line_balance(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        qty=Decimal("6"),
        reason="Cierre operacional",
    )

    billing_status = calculate_document_status("purchase_order", "PO-001")
    assert billing_status.label == "Pendiente Facturar"

    close_line_balance(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_invoice",
        qty=Decimal("10"),
        reason="Cierre de facturacion",
    )

    completed_status = calculate_document_status("purchase_order", "PO-001")
    assert completed_status.label == "Completado"
    assert completed_status.badge_class == "text-bg-success"


def test_document_status_maps_journal_entry_state_without_docstatus(app_ctx):
    from types import SimpleNamespace

    from cacao_accounting.document_flow.status import calculate_document_status

    submitted_status = calculate_document_status("journal_entry", SimpleNamespace(docstatus=None, status="submitted"))
    assert submitted_status.label == "Contabilizado"
    assert submitted_status.badge_class == "text-bg-primary"

    rejected_status = calculate_document_status("journal_entry", SimpleNamespace(docstatus=None, status="rejected"))
    assert rejected_status.label == "Borrador"
    assert rejected_status.badge_class == "text-bg-secondary"


def test_document_flow_summary_returns_grouped_relations(app_ctx):
    """document_flow_summary agrupa upstream/downstream por tipo documental."""

    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import create_document_relation
    from cacao_accounting.document_flow.tracing import document_flow_summary

    order_item = _seed_purchase_order(app_ctx)
    receipt = PurchaseReceipt(id="PR-SUM-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-SUM-001",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()

    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-SUM-001",
        target_item_id=receipt_item.id,
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )

    summary = document_flow_summary("purchase_order", "PO-001")

    assert summary["document_type"] == "purchase_order"
    assert summary["document_id"] == "PO-001"
    assert len(summary["downstream"]) == 1
    group = summary["downstream"][0]
    assert group["doctype"] == "purchase_receipt"
    assert group["active_count"] == 1
    assert group["historical_count"] == 0
    assert len(group["documents"]) == 1
    assert group["documents"][0]["document"]["document_id"] == "PR-SUM-001"


def test_document_flow_summary_counts_historical_after_revert(app_ctx):
    """document_flow_summary distingue relaciones activas e historicas."""

    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import create_document_relation, revert_relations_for_target
    from cacao_accounting.document_flow.tracing import document_flow_summary

    order_item = _seed_purchase_order(app_ctx)
    receipt = PurchaseReceipt(id="PR-SUM-002", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-SUM-002",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("3"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("15"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()

    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-SUM-002",
        target_item_id=receipt_item.id,
        qty=Decimal("3"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("15"),
    )

    receipt.docstatus = 2
    revert_relations_for_target("purchase_receipt", "PR-SUM-002")

    summary = document_flow_summary("purchase_order", "PO-001")

    assert len(summary["downstream"]) == 1
    group = summary["downstream"][0]
    assert group["active_count"] == 0
    assert group["historical_count"] == 1


def test_document_flow_summary_upstream_from_receipt(app_ctx):
    """document_flow_summary incluye documentos upstream para un recibo."""

    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database
    from cacao_accounting.document_flow import create_document_relation
    from cacao_accounting.document_flow.tracing import document_flow_summary

    order_item = _seed_purchase_order(app_ctx)
    receipt = PurchaseReceipt(id="PR-SUM-003", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-SUM-003",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )
    database.session.add_all([receipt, receipt_item])
    database.session.flush()

    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-SUM-003",
        target_item_id=receipt_item.id,
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )

    summary = document_flow_summary("purchase_receipt", "PR-SUM-003")

    assert len(summary["upstream"]) == 1
    group = summary["upstream"][0]
    assert group["doctype"] == "purchase_order"
    assert group["label"] == "Orden de Compra"
    assert group["active_count"] == 1


def test_document_flow_summary_includes_create_actions(app_ctx):
    """document_flow_summary expone acciones de creacion del tipo documental."""

    from cacao_accounting.document_flow.tracing import document_flow_summary

    _seed_purchase_order(app_ctx)
    summary = document_flow_summary("purchase_order", "PO-001")

    action_targets = [a["target_type"] for a in summary["create_actions"]]
    assert "purchase_receipt" in action_targets
    assert "purchase_invoice" in action_targets
    assert "payment_entry" in action_targets


def test_document_flow_summary_includes_rfq_to_order_action(app_ctx):
    """La RFQ expone accion para crear orden de compra."""

    from cacao_accounting.database import PurchaseQuotation, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    quotation = PurchaseQuotation(id="RFQ-ACT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    database.session.add(quotation)
    database.session.flush()

    summary = document_flow_summary("purchase_quotation", quotation.id)

    action_targets = [a["target_type"] for a in summary["create_actions"]]
    assert "supplier_quotation" in action_targets
    assert "purchase_order" in action_targets


def test_document_flow_summary_includes_request_to_supplier_quotation_action(app_ctx):
    """La solicitud de compra expone accion para crear cotizacion de proveedor."""

    from cacao_accounting.database import PurchaseRequest, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    request_doc = PurchaseRequest(id="PREQ-ACT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    database.session.add(request_doc)
    database.session.flush()

    summary = document_flow_summary("purchase_request", request_doc.id)

    action_targets = [a["target_type"] for a in summary["create_actions"]]
    assert "purchase_quotation" in action_targets
    assert "supplier_quotation" in action_targets
    assert "purchase_order" in action_targets


def test_document_flow_summary_includes_sales_request_to_order_action(app_ctx):
    """El pedido de venta expone accion para crear orden de venta."""

    from cacao_accounting.database import SalesRequest, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    request_doc = SalesRequest(id="SR-ACT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    database.session.add(request_doc)
    database.session.flush()

    summary = document_flow_summary("sales_request", request_doc.id)

    action_targets = [a["target_type"] for a in summary["create_actions"]]
    assert "sales_quotation" in action_targets
    assert "sales_order" in action_targets


def test_document_flow_summary_includes_sales_order_payment_action(app_ctx):
    """La orden de venta expone accion para crear pago (anticipo/cobro)."""

    from cacao_accounting.database import SalesOrder, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    order = SalesOrder(id="SO-ACT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    database.session.add(order)
    database.session.flush()

    summary = document_flow_summary("sales_order", order.id)

    action_targets = [a["target_type"] for a in summary["create_actions"]]
    assert "delivery_note" in action_targets
    assert "sales_invoice" in action_targets
    assert "payment_entry" in action_targets


def test_document_flow_summary_hides_create_actions_for_non_submitted_documents(app_ctx):
    """`create_actions` solo se expone para documentos aprobados (`docstatus=1`)."""

    from cacao_accounting.database import PurchaseOrder, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    draft_order = PurchaseOrder(id="PO-DRAFT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=0)
    cancelled_order = PurchaseOrder(id="PO-CAN-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=2)
    submitted_order = PurchaseOrder(id="PO-SUB-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    database.session.add_all([draft_order, cancelled_order, submitted_order])
    database.session.flush()

    draft_summary = document_flow_summary("purchase_order", draft_order.id)
    cancelled_summary = document_flow_summary("purchase_order", cancelled_order.id)
    submitted_summary = document_flow_summary("purchase_order", submitted_order.id)

    assert draft_summary["create_actions"] == []
    assert cancelled_summary["create_actions"] == []
    assert len(submitted_summary["create_actions"]) >= 1


def test_document_flow_summary_builds_create_urls_with_query_params(app_ctx):
    """Las acciones de notas/devoluciones exponen URL con query params esperados."""

    from cacao_accounting.database import DeliveryNote, PurchaseInvoice, PurchaseReceipt, SalesInvoice, StockEntry, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    purchase_invoice = PurchaseInvoice(
        id="PINV-ACT-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="purchase_invoice",
        docstatus=1,
    )
    purchase_receipt = PurchaseReceipt(id="PREC-ACT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    sales_invoice = SalesInvoice(
        id="SINV-ACT-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="sales_invoice",
        docstatus=1,
    )
    delivery_note = DeliveryNote(id="DN-ACT-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    stock_entry = StockEntry(
        id="STE-ACT-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        docstatus=1,
    )
    database.session.add_all([purchase_invoice, purchase_receipt, sales_invoice, delivery_note, stock_entry])
    database.session.flush()

    with app_ctx.test_request_context():
        purchase_invoice_summary = document_flow_summary("purchase_invoice", purchase_invoice.id)
        purchase_receipt_summary = document_flow_summary("purchase_receipt", purchase_receipt.id)
        sales_invoice_summary = document_flow_summary("sales_invoice", sales_invoice.id)
        delivery_note_summary = document_flow_summary("delivery_note", delivery_note.id)
        stock_entry_summary = document_flow_summary("stock_entry", stock_entry.id)

    def _find_action(summary: dict, label: str) -> dict:
        for action in summary["create_actions"]:
            if action["label"] == label:
                return action
        raise AssertionError(f"Action '{label}' not found")

    purchase_credit = _find_action(purchase_invoice_summary, "Crear Nota de Crédito")
    assert purchase_credit["query_params"]["document_type"] == "purchase_credit_note"
    assert "from_invoice=PINV-ACT-001" in (purchase_credit["create_url"] or "")
    assert "document_type=purchase_credit_note" in (purchase_credit["create_url"] or "")

    purchase_debit = _find_action(purchase_invoice_summary, "Crear Nota de Débito")
    assert purchase_debit["query_params"]["document_type"] == "purchase_debit_note"
    assert "from_invoice=PINV-ACT-001" in (purchase_debit["create_url"] or "")
    assert "document_type=purchase_debit_note" in (purchase_debit["create_url"] or "")

    purchase_return = _find_action(purchase_receipt_summary, "Crear Devolución")
    assert purchase_return["query_params"]["document_type"] == "purchase_return"
    assert "from_receipt=PREC-ACT-001" in (purchase_return["create_url"] or "")
    assert "document_type=purchase_return" in (purchase_return["create_url"] or "")

    purchase_receipt_credit = _find_action(purchase_receipt_summary, "Crear Nota de Crédito")
    assert purchase_receipt_credit["query_params"]["document_type"] == "purchase_credit_note"
    assert "from_receipt=PREC-ACT-001" in (purchase_receipt_credit["create_url"] or "")
    assert "document_type=purchase_credit_note" in (purchase_receipt_credit["create_url"] or "")

    purchase_receipt_debit = _find_action(purchase_receipt_summary, "Crear Nota de Débito")
    assert purchase_receipt_debit["query_params"]["document_type"] == "purchase_debit_note"
    assert "from_receipt=PREC-ACT-001" in (purchase_receipt_debit["create_url"] or "")
    assert "document_type=purchase_debit_note" in (purchase_receipt_debit["create_url"] or "")

    purchase_receipt_stock = _find_action(purchase_receipt_summary, "Crear Entrada de Almacén")
    assert purchase_receipt_stock["query_params"]["source_type"] == "purchase_receipt"
    assert "source_id=PREC-ACT-001" in (purchase_receipt_stock["create_url"] or "")
    assert "source_type=purchase_receipt" in (purchase_receipt_stock["create_url"] or "")

    sales_credit = _find_action(sales_invoice_summary, "Crear Nota de Crédito")
    assert sales_credit["query_params"]["document_type"] == "sales_credit_note"
    assert "from_invoice=SINV-ACT-001" in (sales_credit["create_url"] or "")
    assert "document_type=sales_credit_note" in (sales_credit["create_url"] or "")

    sales_debit = _find_action(sales_invoice_summary, "Crear Nota de Débito")
    assert sales_debit["query_params"]["document_type"] == "sales_debit_note"
    assert "from_invoice=SINV-ACT-001" in (sales_debit["create_url"] or "")
    assert "document_type=sales_debit_note" in (sales_debit["create_url"] or "")

    delivery_credit = _find_action(delivery_note_summary, "Crear Nota de Crédito")
    assert delivery_credit["query_params"]["document_type"] == "sales_credit_note"
    assert "from_note=DN-ACT-001" in (delivery_credit["create_url"] or "")
    assert "document_type=sales_credit_note" in (delivery_credit["create_url"] or "")

    delivery_debit = _find_action(delivery_note_summary, "Crear Nota de Débito")
    assert delivery_debit["query_params"]["document_type"] == "sales_debit_note"
    assert "from_note=DN-ACT-001" in (delivery_debit["create_url"] or "")
    assert "document_type=sales_debit_note" in (delivery_debit["create_url"] or "")

    delivery_stock = _find_action(delivery_note_summary, "Crear Movimiento de Inventario")
    assert delivery_stock["query_params"]["source_type"] == "delivery_note"
    assert "source_id=DN-ACT-001" in (delivery_stock["create_url"] or "")
    assert "source_type=delivery_note" in (delivery_stock["create_url"] or "")

    stock_reuse = _find_action(stock_entry_summary, "Crear Reuso Interno")
    assert stock_reuse["target_type"] == "stock_entry"
    assert stock_reuse["query_params"]["source_type"] == "stock_entry"
    assert "source_id=STE-ACT-001" in (stock_reuse["create_url"] or "")
    assert "source_type=stock_entry" in (stock_reuse["create_url"] or "")


def test_document_flow_summary_includes_note_payment_actions(app_ctx):
    """Las notas de crédito/débito exponen acción de pago/reembolso en trazabilidad."""

    from cacao_accounting.database import PurchaseInvoice, SalesInvoice, database
    from cacao_accounting.document_flow.tracing import document_flow_summary

    purchase_credit = PurchaseInvoice(
        id="PINV-CN-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="purchase_credit_note",
        docstatus=1,
    )
    purchase_debit = PurchaseInvoice(
        id="PINV-DN-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="purchase_debit_note",
        docstatus=1,
    )
    sales_credit = SalesInvoice(
        id="SINV-CN-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="sales_credit_note",
        docstatus=1,
    )
    sales_debit = SalesInvoice(
        id="SINV-DN-001",
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="sales_debit_note",
        docstatus=1,
    )
    database.session.add_all([purchase_credit, purchase_debit, sales_credit, sales_debit])
    database.session.flush()

    with app_ctx.test_request_context():
        purchase_credit_summary = document_flow_summary("purchase_credit_note", purchase_credit.id)
        purchase_debit_summary = document_flow_summary("purchase_debit_note", purchase_debit.id)
        sales_credit_summary = document_flow_summary("sales_credit_note", sales_credit.id)
        sales_debit_summary = document_flow_summary("sales_debit_note", sales_debit.id)

    purchase_credit_action = purchase_credit_summary["create_actions"][0]
    assert purchase_credit_action["target_type"] == "payment_entry"
    assert "from_purchase_credit_note=PINV-CN-001" in (purchase_credit_action["create_url"] or "")

    purchase_debit_action = purchase_debit_summary["create_actions"][0]
    assert purchase_debit_action["target_type"] == "payment_entry"
    assert "from_purchase_debit_note=PINV-DN-001" in (purchase_debit_action["create_url"] or "")

    sales_credit_action = sales_credit_summary["create_actions"][0]
    assert sales_credit_action["target_type"] == "payment_entry"
    assert "from_sales_credit_note=SINV-CN-001" in (sales_credit_action["create_url"] or "")

    sales_debit_action = sales_debit_summary["create_actions"][0]
    assert sales_debit_action["target_type"] == "payment_entry"
    assert "from_sales_debit_note=SINV-DN-001" in (sales_debit_action["create_url"] or "")


def test_document_flow_summary_excludes_disabled_actions(app_ctx):
    """Las acciones deshabilitadas en el registro no se exponen en el resumen."""

    from cacao_accounting.database import PurchaseOrder, database
    from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, DocumentAction
    from cacao_accounting.document_flow.tracing import document_flow_summary

    order = PurchaseOrder(id="PO-ENABLED-001", company="cacao", posting_date=date(2026, 5, 4), docstatus=1)
    database.session.add(order)
    database.session.flush()

    original_type = DOCUMENT_TYPES["purchase_order"]
    disabled_action = DocumentAction(
        label="Acción Deshabilitada",
        target_type="purchase_invoice",
        endpoint="compras.compras_factura_compra_nuevo",
        source_param="from_order",
        enabled=False,
    )
    DOCUMENT_TYPES["purchase_order"] = original_type.__class__(
        **{**original_type.__dict__, "create_actions": original_type.create_actions + (disabled_action,)}
    )
    try:
        summary = document_flow_summary("purchase_order", order.id)
    finally:
        DOCUMENT_TYPES["purchase_order"] = original_type

    labels = [action["label"] for action in summary["create_actions"]]
    assert "Acción Deshabilitada" not in labels


def test_allowed_flows_include_order_advances_and_receipt_notes():
    """La matriz soporta anticipos desde ordenes y notas desde recepcion."""

    from cacao_accounting.document_flow.registry import is_allowed_flow

    assert is_allowed_flow("purchase_order", "payment_entry")
    assert is_allowed_flow("sales_order", "payment_entry")
    assert is_allowed_flow("purchase_request", "supplier_quotation")
    assert is_allowed_flow("purchase_receipt", "purchase_credit_note")
    assert is_allowed_flow("purchase_receipt", "purchase_debit_note")
    assert is_allowed_flow("purchase_receipt", "stock_entry")
    assert is_allowed_flow("purchase_credit_note", "payment_entry")
    assert is_allowed_flow("purchase_debit_note", "payment_entry")
    assert is_allowed_flow("sales_credit_note", "payment_entry")
    assert is_allowed_flow("sales_debit_note", "payment_entry")


def test_purchase_return_document_type_registered():
    """Verifica que purchase_return existe como DocumentType en el registro."""
    from cacao_accounting.document_flow.registry import DOCUMENT_TYPES

    assert "purchase_return" in DOCUMENT_TYPES
    spec = DOCUMENT_TYPES["purchase_return"]
    assert spec.label == "Devolución de Compra"
    assert spec.module == "purchases"
    assert spec.list_endpoint == "compras.compras_factura_compra_devolucion_lista"


def test_purchase_return_flow_is_allowed():
    """Verifica que purchase_receipt -> purchase_return esta permitido."""
    from cacao_accounting.document_flow.registry import is_allowed_flow

    assert is_allowed_flow("purchase_receipt", "purchase_return")
