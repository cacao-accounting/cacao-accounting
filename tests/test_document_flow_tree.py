# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del servicio de árbol de flujo documental recursivo."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app():
    """Aplicación aislada con base SQLite en memoria."""
    application = create_app({**configuracion, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with application.app_context():
        from cacao_accounting.database import database

        database.create_all()
        yield application


# ---------------------------------------------------------------------------
# Helpers de seed
# ---------------------------------------------------------------------------


def _seed_entity(db):
    from cacao_accounting.database import Entity

    entity = Entity(code="TEST", name="Test SA", company_name="Test SA", tax_id="J0099", currency="NIO")
    db.session.add(entity)
    db.session.flush()
    return entity


def _seed_purchase_chain(db):
    """Crea: PurchaseRequest → PurchaseOrder → PurchaseReceipt → PurchaseInvoice."""
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        PurchaseRequest,
        PurchaseRequestItem,
        UOM,
    )
    from cacao_accounting.document_flow import create_document_relation

    uom = UOM(code="UND", name="Unidad")
    item = Item(code="CHOC-001", name="Chocolate", item_type="goods", is_stock_item=True, default_uom="UND")
    db.session.add_all([uom, item])

    req = PurchaseRequest(id="REQ-001", company="TEST", posting_date=date(2026, 5, 1), docstatus=1)
    req_item = PurchaseRequestItem(
        purchase_request_id="REQ-001", item_code="CHOC-001", item_name="Chocolate", qty=Decimal("10"), uom="UND"
    )
    db.session.add_all([req, req_item])

    po = PurchaseOrder(id="PO-001", company="TEST", posting_date=date(2026, 5, 2), docstatus=1)
    po_item = PurchaseOrderItem(
        purchase_order_id="PO-001",
        item_code="CHOC-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("50"),
    )
    db.session.add_all([po, po_item])

    pr = PurchaseReceipt(id="PR-001", company="TEST", posting_date=date(2026, 5, 3), docstatus=1)
    pr_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-001",
        item_code="CHOC-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("50"),
    )
    db.session.add_all([pr, pr_item])

    inv = PurchaseInvoice(id="PINV-001", company="TEST", posting_date=date(2026, 5, 4), docstatus=1)
    inv_item = PurchaseInvoiceItem(
        purchase_invoice_id="PINV-001",
        item_code="CHOC-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("50"),
    )
    db.session.add_all([inv, inv_item])
    db.session.flush()

    # REQ → PO
    create_document_relation(
        source_type="purchase_request",
        source_id="REQ-001",
        source_item_id=req_item.id,
        target_type="purchase_order",
        target_id="PO-001",
        target_item_id=po_item.id,
        qty=Decimal("10"),
        uom="UND",
    )
    # PO → PR
    create_document_relation(
        source_type="purchase_order",
        source_id="PO-001",
        source_item_id=po_item.id,
        target_type="purchase_receipt",
        target_id="PR-001",
        target_item_id=pr_item.id,
        qty=Decimal("10"),
        uom="UND",
    )
    # PR → PINV
    create_document_relation(
        source_type="purchase_receipt",
        source_id="PR-001",
        source_item_id=pr_item.id,
        target_type="purchase_invoice",
        target_id="PINV-001",
        target_item_id=inv_item.id,
        qty=Decimal("10"),
        uom="UND",
    )

    return {"req": req, "po": po, "pr": pr, "inv": inv}


def _seed_sales_chain(db):
    """Crea: SalesOrder → SalesInvoice con dos PaymentEntry."""
    from cacao_accounting.database import (
        Item,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        SalesInvoiceItem,
        SalesOrder,
        SalesOrderItem,
        UOM,
    )
    from cacao_accounting.document_flow import create_document_relation

    uom = UOM(code="UND2", name="Unidad2")
    item = Item(code="PROD-001", name="Producto", item_type="goods", is_stock_item=True, default_uom="UND2")
    db.session.add_all([uom, item])

    so = SalesOrder(id="SO-001", company="TEST", posting_date=date(2026, 5, 1), docstatus=1)
    so_item = SalesOrderItem(
        sales_order_id="SO-001",
        item_code="PROD-001",
        item_name="Producto",
        qty=Decimal("5"),
        uom="UND2",
        rate=Decimal("100"),
        amount=Decimal("500"),
    )
    db.session.add_all([so, so_item])

    sinv = SalesInvoice(id="SINV-001", company="TEST", posting_date=date(2026, 5, 2), docstatus=1, grand_total=Decimal("500"))
    sinv_item = SalesInvoiceItem(
        sales_invoice_id="SINV-001",
        item_code="PROD-001",
        item_name="Producto",
        qty=Decimal("5"),
        uom="UND2",
        rate=Decimal("100"),
        amount=Decimal("500"),
    )
    db.session.add_all([sinv, sinv_item])

    pay1 = PaymentEntry(id="PAY-001", company="TEST", posting_date=date(2026, 5, 10), docstatus=1, payment_type="receive")
    pay2 = PaymentEntry(id="PAY-002", company="TEST", posting_date=date(2026, 5, 15), docstatus=1, payment_type="receive")
    db.session.add_all([pay1, pay2])
    db.session.flush()

    # SO → SINV
    create_document_relation(
        source_type="sales_order",
        source_id="SO-001",
        source_item_id=so_item.id,
        target_type="sales_invoice",
        target_id="SINV-001",
        target_item_id=sinv_item.id,
        qty=Decimal("5"),
        uom="UND2",
    )

    # PaymentReference vincula SINV ← PAY1 y PAY2
    ref1 = PaymentReference(
        payment_id="PAY-001",
        reference_type="sales_invoice",
        reference_id="SINV-001",
        allocated_amount=Decimal("300"),
        company="TEST",
    )
    ref2 = PaymentReference(
        payment_id="PAY-002",
        reference_type="sales_invoice",
        reference_id="SINV-001",
        allocated_amount=Decimal("200"),
        company="TEST",
    )
    db.session.add_all([ref1, ref2])
    db.session.flush()

    return {"so": so, "sinv": sinv, "pay1": pay1, "pay2": pay2}


def _seed_journal_for_invoice(db):
    """Crea un comprobante contable con línea referenciada a una factura."""
    from cacao_accounting.contabilidad.journal_service import sync_journal_document_relations
    from cacao_accounting.database import ComprobanteContable, ComprobanteContableDetalle

    journal = ComprobanteContable(
        id="JRN-001",
        entity="TEST",
        date=date(2026, 5, 6),
        document_no="JRN-0001",
        status="submitted",
        voucher_type="journal_entry",
        transaction_currency="NIO",
    )
    line = ComprobanteContableDetalle(
        id="JRN-LINE-001",
        entity="TEST",
        account="1101",
        date=date(2026, 5, 6),
        transaction="journal_entry",
        transaction_id="JRN-001",
        order=1,
        value=Decimal("500"),
        currency_id="NIO",
        value_default=Decimal("500"),
        internal_reference="sales_invoice",
        internal_reference_id="SINV-001",
        reference="SINV-001",
        voucher_type="journal_entry",
    )
    db.session.add_all([journal, line])
    db.session.flush()
    sync_journal_document_relations(journal)
    db.session.flush()
    return journal


# ---------------------------------------------------------------------------
# Tests del nodo individual
# ---------------------------------------------------------------------------


def test_get_document_node_returns_fields(app):
    """get_document_node devuelve metadatos mínimos para un documento."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_document_node

    _seed_entity(database)
    _seed_purchase_chain(database)

    node = get_document_node("purchase_invoice", "PINV-001")

    assert node["document_type"] == "purchase_invoice"
    assert node["document_id"] == "PINV-001"
    assert node["label"] is not None
    assert node["docstatus"] == 1
    assert "status" in node


def test_get_document_node_unknown_document(app):
    """get_document_node con documento inexistente devuelve None en status."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_document_node

    _seed_entity(database)

    node = get_document_node("purchase_invoice", "NO-EXISTE")

    assert node["document_type"] == "purchase_invoice"
    assert node["status"] is None


# ---------------------------------------------------------------------------
# Tests de upstream
# ---------------------------------------------------------------------------


def test_upstream_desde_purchase_invoice(app):
    """El upstream de PINV-001 debe incluir PR, PO y REQ recursivamente."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_upstream_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    upstream = get_upstream_tree("purchase_invoice", "PINV-001")

    assert len(upstream) == 1  # PR-001 directo
    pr_node = upstream[0]
    assert pr_node["document_type"] == "purchase_receipt"
    assert pr_node["document_id"] == "PR-001"

    # El hijo del PR es el PO
    children = pr_node["children"]
    assert len(children) == 1
    po_node = children[0]
    assert po_node["document_type"] == "purchase_order"

    # El hijo del PO es el REQ
    assert len(po_node["children"]) == 1
    req_node = po_node["children"][0]
    assert req_node["document_type"] == "purchase_request"
    assert len(req_node["children"]) == 0  # REQ no tiene origen


def test_upstream_documento_sin_relaciones(app):
    """Un documento sin relaciones upstream devuelve lista vacía."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_upstream_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    upstream = get_upstream_tree("purchase_request", "REQ-001")
    assert upstream == []


# ---------------------------------------------------------------------------
# Tests de downstream
# ---------------------------------------------------------------------------


def test_downstream_desde_purchase_request(app):
    """El downstream de REQ-001 debe incluir PO → PR → PINV recursivamente."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_downstream_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    downstream = get_downstream_tree("purchase_request", "REQ-001")

    assert len(downstream) == 1
    po_node = downstream[0]
    assert po_node["document_type"] == "purchase_order"

    pr_node = po_node["children"][0]
    assert pr_node["document_type"] == "purchase_receipt"

    inv_node = pr_node["children"][0]
    assert inv_node["document_type"] == "purchase_invoice"
    assert len(inv_node["children"]) == 0


def test_downstream_desde_sales_invoice_incluye_pagos(app):
    """El downstream de SINV-001 incluye los pagos vía PaymentReference."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_downstream_tree

    _seed_entity(database)
    _seed_sales_chain(database)

    downstream = get_downstream_tree("sales_invoice", "SINV-001")

    pay_ids = {n["document_id"] for n in downstream if n.get("document_type") == "payment_entry"}
    assert "PAY-001" in pay_ids
    assert "PAY-002" in pay_ids

    # Los pagos deben tener applied_amount
    for node in downstream:
        if node.get("document_type") == "payment_entry":
            assert node["applied_amount"] >= 0


def test_downstream_desde_payment_entry_incluye_referencias(app):
    """El downstream de un pago incluye facturas/notas aplicadas vía PaymentReference."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_downstream_tree

    _seed_entity(database)
    _seed_sales_chain(database)

    downstream = get_downstream_tree("payment_entry", "PAY-001")

    refs = [n for n in downstream if n.get("document_type") == "sales_invoice"]
    assert len(refs) == 1
    assert refs[0]["document_id"] == "SINV-001"
    assert refs[0]["applied_amount"] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Tests del árbol completo
# ---------------------------------------------------------------------------


def test_build_document_flow_tree_completo(app):
    """build_document_flow_tree devuelve current, upstream, downstream y meta."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    tree = build_document_flow_tree("purchase_invoice", "PINV-001")

    assert tree["current"]["document_id"] == "PINV-001"
    assert len(tree["upstream"]) > 0
    assert tree["downstream"] == []
    assert "meta" in tree
    assert tree["meta"]["node_count"] > 0


def test_build_tree_direction_upstream(app):
    """Con direction=upstream no se calculan nodos downstream."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    tree = build_document_flow_tree("purchase_receipt", "PR-001", direction="upstream")

    assert len(tree["upstream"]) > 0
    assert tree["downstream"] == []


def test_build_tree_direction_downstream(app):
    """Con direction=downstream no se calculan nodos upstream."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    tree = build_document_flow_tree("purchase_receipt", "PR-001", direction="downstream")

    assert tree["upstream"] == []
    assert len(tree["downstream"]) > 0


def test_build_tree_factura_con_multiples_pagos(app):
    """Una factura con N pagos los expone todos en downstream."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_sales_chain(database)

    tree = build_document_flow_tree("sales_invoice", "SINV-001", direction="downstream")

    pay_ids = {n["document_id"] for n in tree["downstream"] if n.get("document_type") == "payment_entry"}
    assert len(pay_ids) == 2


def test_journal_entry_registrado_y_relacionado(app):
    """journal_entry responde como tipo documental y se relaciona desde líneas."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_sales_chain(database)
    _seed_journal_for_invoice(database)

    invoice_tree = build_document_flow_tree("sales_invoice", "SINV-001", direction="downstream")
    journal_nodes = [n for n in invoice_tree["downstream"] if n.get("document_type") == "journal_entry"]
    assert len(journal_nodes) == 1
    assert journal_nodes[0]["document_id"] == "JRN-001"

    journal_tree = build_document_flow_tree("journal_entry", "JRN-001", direction="upstream")
    assert journal_tree["current"]["posting_date"] == "2026-05-06"
    assert journal_tree["current"]["currency"] == "NIO"
    assert journal_tree["current"]["total"] == pytest.approx(500.0)
    assert journal_tree["upstream"][0]["document_type"] == "sales_invoice"
    assert journal_tree["upstream"][0]["document_id"] == "SINV-001"


def test_apply_advance_to_invoice_crea_referencia_y_relacion(app):
    """La aplicación de anticipo crea PaymentReference y DocumentRelation."""
    from cacao_accounting.database import DocumentRelation, PaymentEntry, SalesInvoice, database
    from cacao_accounting.document_flow.service import apply_advance_to_invoice
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    invoice = SalesInvoice(
        id="SINV-ADV-001",
        company="TEST",
        posting_date=date(2026, 5, 7),
        docstatus=1,
        grand_total=Decimal("500"),
        outstanding_amount=Decimal("500"),
    )
    advance = PaymentEntry(
        id="ADV-001",
        company="TEST",
        posting_date=date(2026, 5, 7),
        docstatus=1,
        payment_type="receive",
        party_id=None,
        received_amount=Decimal("500"),
        currency="NIO",
    )
    database.session.add_all([invoice, advance])
    database.session.flush()

    reference = apply_advance_to_invoice("ADV-001", "SINV-ADV-001", Decimal("125"), date(2026, 5, 8))
    relation = database.session.execute(
        database.select(DocumentRelation).filter_by(
            source_type="sales_invoice",
            source_id="SINV-ADV-001",
            target_type="payment_entry",
            target_id="ADV-001",
            target_item_id=reference.id,
            status="active",
        )
    ).scalar_one_or_none()

    assert reference.company == "TEST"
    assert reference.reference_document_no == "SINV-ADV-001"
    assert reference.outstanding_amount_after == Decimal("375.0000")
    assert relation is not None

    tree = build_document_flow_tree("sales_invoice", "SINV-ADV-001", direction="downstream")
    payment_ids = {n["document_id"] for n in tree["downstream"] if n.get("document_type") == "payment_entry"}
    assert "ADV-001" in payment_ids


# ---------------------------------------------------------------------------
# Tests de prevención de ciclos y límites
# ---------------------------------------------------------------------------


def test_max_depth_limita_recursion(app):
    """Con max_depth=1 el árbol no supera un nivel de profundidad."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import get_upstream_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    upstream = get_upstream_tree("purchase_invoice", "PINV-001", max_depth=1)

    assert len(upstream) == 1  # PR-001
    # Con profundidad 1, los hijos de PR deben marcar max_depth_reached
    assert any(c.get("max_depth_reached") for c in upstream[0]["children"])


def test_max_nodes_limita_nodos(app):
    """Con max_nodes=1 el árbol se detiene tras el primer nodo."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    tree = build_document_flow_tree("purchase_request", "REQ-001", direction="downstream", max_nodes=1)

    assert tree["meta"]["node_count"] <= 1


def test_sin_ciclos_en_cadena_normal(app):
    """La cadena lineal purchase no genera ciclos."""
    from cacao_accounting.database import database
    from cacao_accounting.document_flow.tree import build_document_flow_tree

    _seed_entity(database)
    _seed_purchase_chain(database)

    tree = build_document_flow_tree("purchase_invoice", "PINV-001")

    assert tree["meta"]["cycle_detected"] is False


# ---------------------------------------------------------------------------
# Tests del endpoint API
# ---------------------------------------------------------------------------


def test_api_document_flow_tree_requiere_parametros(app):
    """El endpoint devuelve 400 sin parámetros."""
    from cacao_accounting.database import User, database

    with app.app_context():
        user = User(id="U1", user="treetest", name="Test", password=b"x", classification="admin", active=True)
        database.session.add(user)
        database.session.flush()
        database.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = "U1"
        sess["_fresh"] = True

    resp = client.get("/api/document-flow/tree")
    assert resp.status_code == 400


def test_api_document_flow_tree_devuelve_arbol(app):
    """El endpoint devuelve el árbol completo en JSON."""
    from cacao_accounting.database import database

    _seed_entity(database)
    _seed_purchase_chain(database)

    with app.test_request_context():
        pass

    from cacao_accounting.database import User

    user = User(id="U2", user="treetest2", name="Test2", password=b"x", classification="admin", active=True)
    database.session.add(user)
    database.session.flush()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = "U2"
        sess["_fresh"] = True

    resp = client.get("/api/document-flow/tree?document_type=purchase_invoice&document_id=PINV-001")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "current" in data
    assert "upstream" in data
    assert "downstream" in data
    assert "meta" in data


def test_vista_comprobante_contable_renderiza_flujo_documental(app):
    """La vista de journal incluye la sección reusable de flujo documental."""
    from cacao_accounting.database import Modules, User, database

    _seed_entity(database)
    _seed_sales_chain(database)
    _seed_journal_for_invoice(database)

    module = Modules(id="MOD-ACCOUNTING", module="accounting", default=True, enabled=True)
    user = User(id="U3", user="journalviewer", name="Journal Viewer", password=b"x", classification="admin", active=True)
    database.session.add_all([module, user])
    database.session.flush()
    database.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = "U3"
        sess["_fresh"] = True

    resp = client.get("/accounting/journal/JRN-001")
    assert resp.status_code == 200
    assert "Flujo documental".encode("utf-8") in resp.data
    assert b"/api/document-flow/tree" in resp.data


def test_s2p07_settle_advance_generates_netting_journal(app):
    """S2P-07: al aplicar anticipo con flag activo se netea la cuenta de anticipo.

    Compras: Dr Cuenta por Pagar / Cr Cuenta de Anticipo a Proveedores.
    """
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        Book,
        CompanyDefaultAccount,
        FiscalYear,
        GLEntry,
        PaymentEntry,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        database,
    )
    from cacao_accounting.document_flow.service import apply_advance_to_invoice

    entity = _seed_entity(database)
    entity.currency = "NIO"
    payable = Accounts(entity="TEST", code="21.01", name="Cuentas por Pagar", account_type="payable", active=True, enabled=True)
    advance = Accounts(
        entity="TEST", code="21.02", name="Anticipos a Proveedores", account_type="supplier_advance", active=True, enabled=True
    )
    book = Book(entity="TEST", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO")
    fy = FiscalYear(
        entity="TEST", name="FY2026", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31)
    )
    database.session.add_all([payable, advance, book, fy])
    database.session.flush()
    period = AccountingPeriod(
        entity="TEST",
        fiscal_year_id=fy.id,
        name="2026-05",
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        enabled=True,
        is_closed=False,
    )
    database.session.add(period)
    defaults = CompanyDefaultAccount(
        company="TEST",
        default_payable=payable.id,
        supplier_advance_account_id=advance.id,
        apply_advances_automatically=True,
    )
    database.session.add(defaults)
    database.session.flush()

    invoice = PurchaseInvoice(
        id="PINV-ADV-001",
        company="TEST",
        posting_date=date(2026, 5, 7),
        docstatus=1,
        grand_total=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
    )
    inv_item = PurchaseInvoiceItem(
        purchase_invoice_id="PINV-ADV-001", item_code="ITEM-1", item_name="Item", qty=Decimal("1"), rate=Decimal("1000"), amount=Decimal("1000")
    )
    advance_pay = PaymentEntry(
        id="ADV-P-001",
        company="TEST",
        posting_date=date(2026, 5, 7),
        docstatus=1,
        payment_type="pay",
        paid_amount=Decimal("500"),
        currency="NIO",
    )
    database.session.add_all([invoice, inv_item, advance_pay])
    database.session.flush()

    apply_advance_to_invoice("ADV-P-001", "PINV-ADV-001", Decimal("500"), date(2026, 5, 8))

    entries = (
        database.session.execute(select(GLEntry).filter_by(company="TEST", voucher_type="journal_entry"))
        .scalars()
        .all()
    )
    assert len(entries) == 2
    debits = [e for e in entries if e.debit > 0]
    credits = [e for e in entries if e.credit > 0]
    assert len(debits) == 1 and len(credits) == 1
    assert debits[0].account_id == payable.id
    assert credits[0].account_id == advance.id
    assert debits[0].debit == Decimal("500")
    assert credits[0].credit == Decimal("500")

