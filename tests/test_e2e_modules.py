# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations
import json
import re
from decimal import Decimal
from datetime import date
import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Entity,
    Book,
    ExchangeRate,
    User,
    Modules,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    SupplierQuotation,
    SupplierQuotationItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    SalesRequest,
    SalesRequestItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesOrder,
    SalesOrderItem,
    DeliveryNote,
    DeliveryNoteItem,
    SalesInvoice,
    SalesInvoiceItem,
    StockEntry,
    StockEntryItem,
    GLEntry,
    StockLedgerEntry,
    DocumentRelation,
    Party,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


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

        # Ensure 3 books: NIO (Primary), USD, EUR
        books = database.session.execute(database.select(Book).filter_by(entity="cacao")).scalars().all()
        book_codes = [b.code for b in books]

        if "USD_BOOK" not in book_codes:
            database.session.add(Book(code="USD_BOOK", name="Dólares", entity="cacao", currency="USD", status="activo"))
        if "EUR_BOOK" not in book_codes:
            database.session.add(Book(code="EUR_BOOK", name="Euros", entity="cacao", currency="EUR", status="activo"))

        # Ensure exchange rates for today
        today = date.today()
        rates = [
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.5"), date=today),
            ExchangeRate(origin="EUR", destination="NIO", rate=Decimal("40.0"), date=today),
        ]
        for r in rates:
            exists = (
                database.session.execute(
                    database.select(ExchangeRate).filter_by(origin=r.origin, destination=r.destination, date=r.date)
                )
                .scalars()
                .first()
            )
            if not exists:
                database.session.add(r)

        database.session.commit()
        yield app


def login(client, username, password):
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def get_error(data):
    if isinstance(data, bytes):
        data = data.decode()
    match = re.search(r'class="alert alert-danger.*?>(.*?)</div>', data, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def assert_no_danger(response, msg=""):
    error = get_error(response.data)
    assert error is None, f"{msg}: {error}"


def check_ledger_entries(voucher_id, expected_books_count=3):
    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=voucher_id)).scalars().all()

    # Group entries by ledger_id
    books_with_entries = set(e.ledger_id for e in entries)
    assert (
        len(books_with_entries) >= expected_books_count
    ), f"Expected entries in {expected_books_count} books, found {len(books_with_entries)}"

    # Check that for each book, debits == credits
    for ledger_id in books_with_entries:
        book_entries = [e for e in entries if e.ledger_id == ledger_id]
        debits = sum(e.debit for e in book_entries)
        credits = sum(e.credit for e in book_entries)
        assert abs(debits - credits) < Decimal("0.01"), f"Book {ledger_id} is not balanced: {debits} != {credits}"

    return entries


def check_document_relation(source_id, target_id):
    rel = (
        database.session.execute(database.select(DocumentRelation).filter_by(source_id=source_id, target_id=target_id))
        .scalars()
        .first()
    )
    assert rel is not None, f"Relation between {source_id} and {target_id} not found"


def test_setup_correct(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # Check books
    books = database.session.execute(database.select(Book).filter_by(entity="cacao")).scalars().all()
    assert len(books) >= 3

    # Check entities
    entities = database.session.execute(database.select(Entity)).scalars().all()
    assert len(entities) > 0


def test_purchase_happy_path(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Create Purchase Request
    pr_data = {
        "company": "cacao",
        "posting_date": date.today().isoformat(),
        "requested_by": "Test User",
        "department": "IT",
        "item_code_0": "ART-001",
        "item_name_0": "Chocolate 100g",
        "qty_0": "10",
        "uom_0": "UND",
        "rate_0": "50",
        "amount_0": "500",
    }
    response = client.post("/buying/purchase-request/new", data=pr_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Solicitud de compra creada correctamente" in response.data

    pr = database.session.execute(database.select(PurchaseRequest).order_by(PurchaseRequest.created.desc())).scalars().first()
    assert pr.docstatus == 0

    # Submit PR
    client.post(f"/buying/purchase-request/{pr.id}/submit", follow_redirects=True)
    database.session.refresh(pr)
    assert pr.docstatus == 1

    # 2. Create Purchase Quotation (RFQ) from PR
    # In real app, "Actualizar Elementos" or similar might be used.
    # The route /request-for-quotation/new handles from_request
    rfq_data = {
        "company": "cacao",
        "posting_date": date.today().isoformat(),
        "from_request": pr.id,
        "item_code_0": "ART-001",
        "item_name_0": "Chocolate 100g",
        "qty_0": "10",
        "uom_0": "UND",
        "rate_0": "50",
        "amount_0": "500",
        "source_type_0": "purchase_request",
        "source_id_0": pr.id,
        "source_item_id_0": "dummy",  # In real use, this would be the PR item ID
    }
    # Need to get actual PR item ID
    pr_item = (
        database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=pr.id)).scalars().first()
    )
    rfq_data["source_item_id_0"] = pr_item.id

    response = client.post("/buying/request-for-quotation/new", data=rfq_data, follow_redirects=True)
    assert response.status_code == 200
    rfq = (
        database.session.execute(database.select(PurchaseQuotation).order_by(PurchaseQuotation.created.desc()))
        .scalars()
        .first()
    )
    assert rfq.docstatus == 0
    check_document_relation(pr.id, rfq.id)

    client.post(f"/buying/request-for-quotation/{rfq.id}/submit", follow_redirects=True)
    database.session.refresh(rfq)
    assert rfq.docstatus == 1

    # 3. Create Supplier Quotation from RFQ
    supplier = database.session.execute(database.select(Party).filter_by(party_type="supplier")).scalars().first()
    sq_data = {
        "company": "cacao",
        "supplier_id": supplier.id,
        "posting_date": date.today().isoformat(),
        "from_rfq": rfq.id,
        "item_code_0": "ART-001",
        "qty_0": "10",
        "rate_0": "45",  # Supplier offered better price
        "amount_0": "450",
        "source_type_0": "purchase_quotation",
        "source_id_0": rfq.id,
        # Get rfq item id
        "source_item_id_0": database.session.execute(
            database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=rfq.id)
        )
        .scalars()
        .first()
        .id,
    }
    response = client.post("/buying/supplier-quotation/new", data=sq_data, follow_redirects=True)
    assert response.status_code == 200
    sq = (
        database.session.execute(database.select(SupplierQuotation).order_by(SupplierQuotation.created.desc()))
        .scalars()
        .first()
    )
    client.post(f"/buying/supplier-quotation/{sq.id}/submit", follow_redirects=True)
    database.session.refresh(sq)
    assert sq.docstatus == 1
    check_document_relation(rfq.id, sq.id)

    # 4. Create Purchase Order from SQ
    po_data = {
        "company": "cacao",
        "supplier_id": supplier.id,
        "posting_date": date.today().isoformat(),
        "item_code_0": "ART-001",
        "qty_0": "10",
        "rate_0": "45",
        "amount_0": "450",
        "source_type_0": "supplier_quotation",
        "source_id_0": sq.id,
        "source_item_id_0": database.session.execute(
            database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=sq.id)
        )
        .scalars()
        .first()
        .id,
    }
    response = client.post("/buying/purchase-order/new", data=po_data, follow_redirects=True)
    assert response.status_code == 200
    po = database.session.execute(database.select(PurchaseOrder).order_by(PurchaseOrder.created.desc())).scalars().first()
    client.post(f"/buying/purchase-order/{po.id}/submit", follow_redirects=True)
    database.session.refresh(po)
    assert po.docstatus == 1
    check_document_relation(sq.id, po.id)

    # 5. Create Purchase Receipt from PO
    # This should affect inventory and generate GL entries
    prc_data = {
        "company": "cacao",
        "supplier_id": supplier.id,
        "posting_date": date.today().isoformat(),
        "from_order": po.id,
        "item_code_0": "ART-001",
        "qty_0": "10",
        "rate_0": "45",
        "amount_0": "450",
        "warehouse_0": "PRINCIPAL",
        "source_type_0": "purchase_order",
        "source_id_0": po.id,
        "source_item_id_0": database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=po.id))
        .scalars()
        .first()
        .id,
    }
    response = client.post("/buying/purchase-receipt/new", data=prc_data, follow_redirects=True)
    assert response.status_code == 200
    prc = database.session.execute(database.select(PurchaseReceipt).order_by(PurchaseReceipt.created.desc())).scalars().first()
    client.post(f"/buying/purchase-receipt/{prc.id}/submit", follow_redirects=True)
    database.session.refresh(prc)
    assert prc.docstatus == 1
    check_document_relation(po.id, prc.id)

    # Validate GL Entries for Purchase Receipt
    check_ledger_entries(prc.id)

    # 6. Create Purchase Invoice from Purchase Receipt
    pi_data = {
        "company": "cacao",
        "supplier_id": supplier.id,
        "posting_date": date.today().isoformat(),
        "from_receipt": prc.id,
        "item_code_0": "ART-001",
        "qty_0": "10",
        "rate_0": "45",
        "amount_0": "450",
        "source_type_0": "purchase_receipt",
        "source_id_0": prc.id,
        "source_item_id_0": database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=prc.id)
        )
        .scalars()
        .first()
        .id,
    }
    response = client.post("/buying/purchase-invoice/new", data=pi_data, follow_redirects=True)
    assert response.status_code == 200
    pi = database.session.execute(database.select(PurchaseInvoice).order_by(PurchaseInvoice.created.desc())).scalars().first()
    client.post(f"/buying/purchase-invoice/{pi.id}/submit", follow_redirects=True)
    database.session.refresh(pi)
    assert pi.docstatus == 1
    check_document_relation(prc.id, pi.id)

    # Validate GL Entries for Purchase Invoice
    check_ledger_entries(pi.id)

    # Check reconciliation
    # Purchase Invoice should have reference to Purchase Receipt
    assert pi.purchase_receipt_id == prc.id


def test_sales_happy_path(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Create Sales Request
    customer = database.session.execute(database.select(Party).filter_by(party_type="customer")).scalars().first()
    sr_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "item_code_0": "ART-001",
        "item_name_0": "Chocolate 100g",
        "qty_0": "5",
        "uom_0": "UND",
        "rate_0": "80",
        "amount_0": "400",
    }
    response = client.post("/sales/sales-request/new", data=sr_data, follow_redirects=True)
    assert response.status_code == 200
    sr = database.session.execute(database.select(SalesRequest).order_by(SalesRequest.created.desc())).scalars().first()
    client.post(f"/sales/sales-request/{sr.id}/submit", follow_redirects=True)
    database.session.refresh(sr)
    assert sr.docstatus == 1

    # 2. Create Sales Quotation from SR
    sq_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "from_request": sr.id,
        "item_code_0": "ART-001",
        "qty_0": "5",
        "rate_0": "80",
        "amount_0": "400",
        "source_type_0": "sales_request",
        "source_id_0": sr.id,
        "source_item_id_0": database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=sr.id))
        .scalars()
        .first()
        .id,
    }
    response = client.post("/sales/quotation/new", data=sq_data, follow_redirects=True)
    assert response.status_code == 200
    sq = database.session.execute(database.select(SalesQuotation).order_by(SalesQuotation.created.desc())).scalars().first()
    client.post(f"/sales/sales-quotation/{sq.id}/submit", follow_redirects=True)
    database.session.refresh(sq)
    assert sq.docstatus == 1
    check_document_relation(sr.id, sq.id)

    # 3. Create Sales Order from SQ
    so_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "from_quotation": sq.id,
        "item_code_0": "ART-001",
        "qty_0": "5",
        "rate_0": "85",  # Price adjustment
        "amount_0": "425",
        "source_type_0": "sales_quotation",
        "source_id_0": sq.id,
        "source_item_id_0": database.session.execute(database.select(SalesQuotationItem).filter_by(sales_quotation_id=sq.id))
        .scalars()
        .first()
        .id,
    }
    response = client.post("/sales/sales-order/new", data=so_data, follow_redirects=True)
    assert response.status_code == 200
    so = database.session.execute(database.select(SalesOrder).order_by(SalesOrder.created.desc())).scalars().first()
    client.post(f"/sales/sales-order/{so.id}/submit", follow_redirects=True)
    database.session.refresh(so)
    assert so.docstatus == 1
    check_document_relation(sq.id, so.id)

    # 4. Create Delivery Note from SO
    # This should affect inventory and generate GL entries
    dn_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "from_order": so.id,
        "item_code_0": "ART-001",
        "qty_0": "5",
        "rate_0": "85",
        "amount_0": "425",
        "warehouse_0": "PRINCIPAL",
        "source_type_0": "sales_order",
        "source_id_0": so.id,
        "source_item_id_0": database.session.execute(database.select(SalesOrderItem).filter_by(sales_order_id=so.id))
        .scalars()
        .first()
        .id,
    }
    response = client.post("/sales/delivery-note/new", data=dn_data, follow_redirects=True)
    assert response.status_code == 200
    dn = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()

    # We need stock to deliver. Let's create a manual stock entry to receive some stock first.
    se = StockEntry(
        purpose="material_receipt", company="cacao", posting_date=date.today(), to_warehouse="PRINCIPAL", docstatus=0
    )
    database.session.add(se)
    database.session.flush()
    sei = StockEntryItem(
        stock_entry_id=se.id,
        item_code="ART-001",
        target_warehouse="PRINCIPAL",
        qty=100,
        uom="UND",
        qty_in_base_uom=100,
        basic_rate=50,
        amount=5000,
    )
    database.session.add(sei)
    database.session.commit()

    from cacao_accounting.contabilidad.posting import submit_document

    submit_document(se)
    database.session.commit()

    client.post(f"/sales/delivery-note/{dn.id}/submit", follow_redirects=True)
    database.session.refresh(dn)
    assert dn.docstatus == 1
    check_document_relation(so.id, dn.id)

    # Validate GL Entries for Delivery Note
    check_ledger_entries(dn.id)

    # 5. Create Sales Invoice from Delivery Note
    si_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "from_note": dn.id,
        "item_code_0": "ART-001",
        "qty_0": "5",
        "rate_0": "85",
        "amount_0": "425",
        "source_type_0": "delivery_note",
        "source_id_0": dn.id,
        "source_item_id_0": database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=dn.id))
        .scalars()
        .first()
        .id,
    }
    response = client.post("/sales/sales-invoice/new", data=si_data, follow_redirects=True)
    assert response.status_code == 200
    si = database.session.execute(database.select(SalesInvoice).order_by(SalesInvoice.created.desc())).scalars().first()
    client.post(f"/sales/sales-invoice/{si.id}/submit", follow_redirects=True)
    database.session.refresh(si)
    assert si.docstatus == 1
    check_document_relation(dn.id, si.id)

    # Validate GL Entries for Sales Invoice
    check_ledger_entries(si.id)

    # Check reconciliation
    assert si.delivery_note_id == dn.id


def test_inventory_cycle(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Material Receipt
    mr_data = {
        "company": "cacao",
        "purpose": "material_receipt",
        "posting_date": date.today().isoformat(),
        "to_warehouse": "PRINCIPAL",
        "item_code_0": "ART-001",
        "qty_0": "50",
        "uom_0": "UND",
        "rate_0": "60",
        "amount_0": "3000",
    }
    response = client.post("/inventory/stock-entry/new", data=mr_data, follow_redirects=True)
    assert response.status_code == 200
    mr = (
        database.session.execute(
            database.select(StockEntry).filter_by(purpose="material_receipt").order_by(StockEntry.created.desc())
        )
        .scalars()
        .first()
    )
    client.post(f"/inventory/stock-entry/{mr.id}/submit", follow_redirects=True)
    database.session.refresh(mr)
    assert mr.docstatus == 1
    check_ledger_entries(mr.id)

    # 2. Material Transfer
    mt_data = {
        "company": "cacao",
        "purpose": "material_transfer",
        "posting_date": date.today().isoformat(),
        "from_warehouse": "PRINCIPAL",
        "to_warehouse": "SUCURSAL",
        "item_code_0": "ART-001",
        "qty_0": "20",
        "uom_0": "UND",
        "rate_0": "60",
        "amount_0": "1200",
    }
    response = client.post("/inventory/stock-entry/new", data=mt_data, follow_redirects=True)
    assert response.status_code == 200
    mt = (
        database.session.execute(
            database.select(StockEntry).filter_by(purpose="material_transfer").order_by(StockEntry.created.desc())
        )
        .scalars()
        .first()
    )
    client.post(f"/inventory/stock-entry/{mt.id}/submit", follow_redirects=True)
    database.session.refresh(mt)
    assert mt.docstatus == 1
    # Material Transfer might not generate GL entries if only moving between warehouses in same company
    # But Stock Ledger should be created
    sle = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=mt.id)).scalars().all()
    assert len(sle) == 2  # One for out, one for in

    # 3. Material Issue (e.g., for internal use)
    mi_data = {
        "company": "cacao",
        "purpose": "material_issue",
        "posting_date": date.today().isoformat(),
        "from_warehouse": "SUCURSAL",
        "item_code_0": "ART-001",
        "qty_0": "5",
        "uom_0": "UND",
        "rate_0": "60",
        "amount_0": "300",
    }
    response = client.post("/inventory/stock-entry/new", data=mi_data, follow_redirects=True)
    assert response.status_code == 200
    mi = (
        database.session.execute(
            database.select(StockEntry).filter_by(purpose="material_issue").order_by(StockEntry.created.desc())
        )
        .scalars()
        .first()
    )
    client.post(f"/inventory/stock-entry/{mi.id}/submit", follow_redirects=True)
    database.session.refresh(mi)
    assert mi.docstatus == 1
    check_ledger_entries(mi.id)


def test_returns(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Sales Return (Credit Note)
    # First need a submitted invoice
    customer = database.session.execute(database.select(Party).filter_by(party_type="customer")).scalars().first()
    si = SalesInvoice(
        company="cacao", customer_id=customer.id, posting_date=date.today(), document_type="sales_invoice", docstatus=1
    )
    database.session.add(si)
    database.session.flush()
    sii = SalesInvoiceItem(sales_invoice_id=si.id, item_code="ART-001", qty=10, rate=100, amount=1000)
    database.session.add(sii)
    database.session.commit()

    # Post it manually to have GL entries to reverse
    from cacao_accounting.contabilidad.posting import post_document_to_gl, submit_document

    post_document_to_gl(si)
    database.session.commit()

    # Create Sales Return
    sr_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "document_type": "sales_credit_note",
        "from_invoice": si.id,
        "item_code_0": "ART-001",
        "qty_0": "10",
        "rate_0": "100",
        "amount_0": "1000",
        "source_type_0": "sales_invoice",
        "source_id_0": si.id,
        "source_item_id_0": sii.id,
    }
    response = client.post("/sales/sales-invoice/new", data=sr_data, follow_redirects=True)
    assert response.status_code == 200
    cn = (
        database.session.execute(
            database.select(SalesInvoice).filter_by(document_type="sales_credit_note").order_by(SalesInvoice.created.desc())
        )
        .scalars()
        .first()
    )
    client.post(f"/sales/sales-invoice/{cn.id}/submit", follow_redirects=True)
    database.session.refresh(cn)
    assert cn.docstatus == 1
    assert cn.is_return is True

    # Validate GL Entries for Credit Note (should be reverse of original)
    check_ledger_entries(cn.id)

    # 2. Purchase Return
    supplier = database.session.execute(database.select(Party).filter_by(party_type="supplier")).scalars().first()
    pi = PurchaseInvoice(
        company="cacao", supplier_id=supplier.id, posting_date=date.today(), document_type="purchase_invoice", docstatus=1
    )
    database.session.add(pi)
    database.session.flush()
    pii = PurchaseInvoiceItem(purchase_invoice_id=pi.id, item_code="ART-001", qty=10, rate=50, amount=500)
    database.session.add(pii)
    database.session.commit()
    post_document_to_gl(pi)
    database.session.commit()

    # Create Purchase Return (using document_type=purchase_return in common invoice form)
    pr_data = {
        "company": "cacao",
        "supplier_id": supplier.id,
        "posting_date": date.today().isoformat(),
        "document_type": "purchase_return",
        "from_invoice": pi.id,
        "item_code_0": "ART-001",
        "qty_0": "10",
        "rate_0": "50",
        "amount_0": "500",
        "source_type_0": "purchase_invoice",
        "source_id_0": pi.id,
        "source_item_id_0": pii.id,
    }
    response = client.post("/buying/purchase-invoice/new", data=pr_data, follow_redirects=True)
    assert response.status_code == 200
    pr = (
        database.session.execute(
            database.select(PurchaseInvoice)
            .filter_by(document_type="purchase_return")
            .order_by(PurchaseInvoice.created.desc())
        )
        .scalars()
        .first()
    )
    client.post(f"/buying/purchase-invoice/{pr.id}/submit", follow_redirects=True)
    database.session.refresh(pr)
    assert pr.docstatus == 1
    assert pr.is_return is True
    check_ledger_entries(pr.id)


def test_partial_and_over_deliveries(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Partial Delivery
    customer = database.session.execute(database.select(Party).filter_by(party_type="customer")).scalars().first()
    so = SalesOrder(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=1)
    database.session.add(so)
    database.session.flush()
    soi = SalesOrderItem(sales_order_id=so.id, item_code="ART-001", qty=20, rate=100, amount=2000)
    database.session.add(soi)
    database.session.commit()

    # First Delivery Note (Partial: 10 of 20)
    dn1_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "from_order": so.id,
        "item_code_0": "ART-001",
        "qty_0": "10",
        "qty_in_base_uom_0": "10",
        "rate_0": "100",
        "amount_0": "1000",
        "warehouse_0": "PRINCIPAL",
        "source_type_0": "sales_order",
        "source_id_0": so.id,
        "source_item_id_0": soi.id,
    }
    client.post("/sales/delivery-note/new", data=dn1_data, follow_redirects=True)
    dn1 = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()

    # Ensure stock
    se = StockEntry(
        purpose="material_receipt", company="cacao", posting_date=date.today(), to_warehouse="PRINCIPAL", docstatus=1
    )
    database.session.add(se)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=se.id,
            item_code="ART-001",
            target_warehouse="PRINCIPAL",
            qty=100,
            uom="UND",
            qty_in_base_uom=100,
            basic_rate=50,
            amount=5000,
        )
    )
    database.session.commit()
    from cacao_accounting.contabilidad.posting import post_document_to_gl

    post_document_to_gl(se)
    database.session.commit()

    client.post(f"/sales/delivery-note/{dn1.id}/submit", follow_redirects=True)
    database.session.refresh(dn1)
    assert dn1.docstatus == 1

    # Second Delivery Note (Remaining: 10 of 20)
    dn2_data = dn1_data.copy()
    dn2_data["qty_0"] = "10"
    dn2_data["qty_in_base_uom_0"] = "10"
    client.post("/sales/delivery-note/new", data=dn2_data, follow_redirects=True)
    dn2 = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()
    response = client.post(f"/sales/delivery-note/{dn2.id}/submit", follow_redirects=True)
    assert_no_danger(response, "PARTIAL DN2 ERROR")
    database.session.refresh(dn2)
    assert dn2.docstatus == 1

    # 2. Over Delivery
    # Depending on business logic, this might be allowed or not.
    # Usually it's allowed but might need confirmation.
    dn3_data = dn1_data.copy()
    dn3_data["qty_0"] = "5"  # Extra 5
    dn3_data["qty_in_base_uom_0"] = "5"
    client.post("/sales/delivery-note/new", data=dn3_data, follow_redirects=True)
    dn3 = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()
    response = client.post(f"/sales/delivery-note/{dn3.id}/submit", follow_redirects=True)
    assert_no_danger(response, "OVER DN3 ERROR")
    database.session.refresh(dn3)
    assert dn3.docstatus == 1  # If it submitted, then over-delivery is technically allowed by engine
