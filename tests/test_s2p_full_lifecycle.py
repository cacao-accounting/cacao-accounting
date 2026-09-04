# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Nombre Reyes

"""
Pruebas integrales exhaustivas de flujo completo Source to Pay (S2P) en Cacao Accounting.

Cubre toda la lógica de negocio y ciclo de vida de compras:
1. Solicitud de Compra (PurchaseRequest)
2. Solicitud de Cotización (PurchaseQuotation / RFQ)
3. Cotización de Proveedor (SupplierQuotation)
4. Comparativo de Ofertas y Rondas de Negociación (Comparativos y Adjudicación)
5. Orden de Compra (PurchaseOrder)
6. Recepción de Productos en Almacén (PurchaseReceipt) - Recepciones parciales y totales, inventarios y contabilidad
7. Factura de Proveedor (PurchaseInvoice) - Matching 2-way y 3-way, impuestos, saldos pendientes
8. Nota de Crédito de Proveedor (purchase_credit_note) - Reducción de saldo pendiente
9. Nota de Débito de Proveedor (purchase_debit_note) - Incremento de saldo pendiente
10. Devolución de Compra (purchase_return) - Devolución física de mercancía en almacén
11. Pago / Entrada de Pago y Cancelación (PaymentEntry) - Asignación y reversión en cascada
12. Aplicación de Anticipo contra factura (is_advance=True / advance_mode)
"""

from datetime import date
from decimal import Decimal
import pytest
from flask import current_app

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Entity,
    Book,
    Party,
    CompanyParty,
    Item,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    Accounts,
    AccountingPeriod,
    CompanyDefaultAccount,
    Bank,
    BankAccount,
    PartyAccount,
    PurchaseReconciliation,
    PurchaseReconciliationItem,
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
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
    PaymentEntry,
    PaymentReference,
    StockLedgerEntry,
    StockBin,
    User,
    Roles,
    RolesUser,
    DocumentRelation,
    database,
)
from cacao_accounting.compras.purchase_sourcing_service import (
    open_negotiation_round,
)
from cacao_accounting.compras.purchase_request_comparison_service import (
    create_purchase_request_comparison,
    save_purchase_request_comparison_draft,
    finalize_purchase_request_comparison,
    create_purchase_orders_from_comparison,
)
from cacao_accounting.compras import (
    _validate_purchase_reversal_of,
    _persist_purchase_reversal_relation,
)
from cacao_accounting.contabilidad.posting import (
    submit_document,
)
from cacao_accounting.document_flow.payment import (
    compute_outstanding_amount,
    refresh_outstanding_amount_cache,
)
from cacao_accounting.document_flow import (
    revert_relations_for_target,
    refresh_source_caches_for_target,
)


@pytest.fixture()
def app_ctx():
    """Contexto de aplicación aislado en memoria para pruebas del flujo S2P."""
    app = create_app({**configuracion, "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        _setup_base_data()
        yield app
        database.session.remove()
        database.drop_all()


def _setup_base_data():
    today = date.today()
    """Configura los maestros básicos de entidad, almacén, unidades, cuentas por defecto y proveedores."""
    entity = Entity(code="cacao", name="Cacao Corp", company_name="Cacao Corp", tax_id="J0310000000001", currency="NIO")
    uom = UOM(code="UND", name="Unidad")
    item = Item(code="ITEM-S2P-01", name="Laptop Pro", item_type="goods", is_stock_item=True, default_uom="UND")
    warehouse = Warehouse(code="ALM-MAIN", name="Almacén Principal", company="cacao", is_active=True)

    inv_acc = Accounts(id="ACC-INV", code="11.01.001", name="Inventario", entity="cacao", account_type="asset")
    bridge_acc = Accounts(id="ACC-BRIDGE", code="21.01.001", name="Cuenta Puente", entity="cacao", account_type="liability")
    exp_acc = Accounts(id="ACC-EXP", code="51.01.001", name="Gasto", entity="cacao", account_type="expense")
    pay_acc = Accounts(id="ACC-PAY", code="21.01.002", name="Cuentas por Pagar", entity="cacao", account_type="payable")
    bank_acc = Accounts(id="ACC-BANK", code="11.01.002", name="Banco", entity="cacao", account_type="bank")
    book = Book(code="S2P", name="S2P", entity="cacao", currency="NIO", is_primary=True, status="activo")

    wca = WarehouseCompanyAccount(
        warehouse_code="ALM-MAIN",
        company="cacao",
        inventory_account_id=inv_acc.id,
        is_active=True,
    )

    defaults = CompanyDefaultAccount(
        company="cacao",
        bridge_account_id=bridge_acc.id,
        default_expense=exp_acc.id,
        default_payable=pay_acc.id,
        default_bank=bank_acc.id,
    )
    bank = Bank(id="BANK-S2P", name="Banco S2P")
    bank_account = BankAccount(
        id="BANK-ACC-S2P",
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta corriente S2P",
        account_no="S2P-001",
        currency="NIO",
        gl_account_id=bank_acc.id,
    )

    supplier1 = Party(id="SUP-S2P-01", code="SUP-S2P-01", name="Proveedor Alpha", is_supplier=True, is_active=True)
    supplier2 = Party(id="SUP-S2P-02", code="SUP-S2P-02", name="Proveedor Beta", is_supplier=True, is_active=True)

    c_party1 = CompanyParty(
        company="cacao",
        party_id="SUP-S2P-01",
        is_active=True,
        allow_purchase_invoice_without_receipt=True,
        allow_purchase_invoice_without_order=True,
    )
    c_party2 = CompanyParty(
        company="cacao",
        party_id="SUP-S2P-02",
        is_active=True,
        allow_purchase_invoice_without_receipt=True,
        allow_purchase_invoice_without_order=True,
    )

    manager = User(
        id="user-manager", user="manager", name="Purchase Manager", password=b"testpass", classification="admin", active=True
    )
    role = Roles(name="Purchase Manager", note="Gerente de Compras")
    role_user = RolesUser(user_id=manager.id, role_id=role.id, active=True)

    database.session.add_all(
        [
            entity,
            AccountingPeriod(
                entity="cacao",
                name=str(today.year),
                start=date(today.year, 1, 1),
                end=date(today.year, 12, 31),
                enabled=True,
                is_closed=False,
            ),
            uom,
            item,
            warehouse,
            inv_acc,
            bridge_acc,
            exp_acc,
            pay_acc,
            bank_acc,
            bank,
            book,
            bank_account,
            wca,
            defaults,
            supplier1,
            supplier2,
            c_party1,
            c_party2,
            manager,
            role,
            role_user,
            PartyAccount(party_id="SUP-S2P-01", company="cacao", payable_account_id=pay_acc.id),
            PartyAccount(party_id="SUP-S2P-02", company="cacao", payable_account_id=pay_acc.id),
        ]
    )
    database.session.commit()


def test_purchase_receipt_rejects_cross_company_warehouse(app_ctx):
    """Una recepción no puede usar una bodega perteneciente a otra compañía."""
    from cacao_accounting.compras.services import _validate_receipt_warehouse
    from cacao_accounting.document_flow import DocumentFlowError

    with app_ctx.app_context():
        database.session.add(Entity(code="other", name="Otra", company_name="Otra", tax_id="J-OTHER", currency="NIO"))
        database.session.add(Warehouse(code="ALM-OTHER", name="Almacén ajeno", company="other", is_active=True))
        database.session.commit()

        with pytest.raises(DocumentFlowError, match="no pertenece a la compañía"):
            _validate_receipt_warehouse("ALM-OTHER", "ITEM-S2P-01", "cacao")


def test_import_landed_cost_preserves_invoice_currency_and_base_amounts(app_ctx):
    """Los landed costs conservan la tasa de la factura y calculan sus bases."""
    from cacao_accounting.compras.services import (
        _landed_cost_currency_context,
        _save_import_landed_cost_charges,
        _save_import_landed_cost_items,
    )

    source_invoice = PurchaseInvoice(
        supplier_id="SUP-S2P-01",
        company="cacao",
        posting_date=date.today(),
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
    )
    database.session.add(source_invoice)
    database.session.flush()

    currency, base_currency, exchange_rate = _landed_cost_currency_context(
        source_invoice,
        "cacao",
        date.today(),
    )
    assert (currency, base_currency, exchange_rate) == ("USD", "NIO", Decimal("36"))

    document = ImportLandedCost(
        company="cacao",
        posting_date=date.today(),
        purchase_invoice_id=source_invoice.id,
        transaction_currency=currency,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
    )
    database.session.add(document)
    database.session.flush()

    with current_app.test_request_context(
        "/buying/import-landed-cost/new",
        method="POST",
        data={
            "item_item_code_0": "ITEM-S2P-01",
            "item_item_name_0": "Laptop Pro",
            "item_qty_0": "2",
            "item_rate_0": "10",
            "item_uom_0": "UND",
            "charge_concept_0": "Flete",
            "charge_amount_0": "5",
            "charge_type_0": "charge",
        },
    ):
        assert _save_import_landed_cost_items(document) == Decimal("20")
        assert _save_import_landed_cost_charges(document) == Decimal("5")

    item = database.session.execute(
        database.select(ImportLandedCostItem).filter_by(import_landed_cost_id=document.id)
    ).scalar_one()
    charge = database.session.execute(
        database.select(ImportLandedCostCharge).filter_by(import_landed_cost_id=document.id)
    ).scalar_one()
    assert item.base_rate == Decimal("360.0000")
    assert item.base_amount == Decimal("720.0000")
    assert charge.base_amount == Decimal("180.0000")


def test_s2p_sourcing_and_negotiation_rounds(app_ctx):
    """
    Prueba paso a paso el flujo inicial de Sourcing:
    Solicitud de Compra -> Solicitud de Cotización -> Cotizaciones de Proveedores ->
    Rondas de Negociación -> Comparativo de Ofertas y Adjudicación -> Orden de Compra
    """
    # 1. Solicitud de Compra (PurchaseRequest)
    pr = PurchaseRequest(
        id="PR-FULL-01",
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
    )
    pr_item = PurchaseRequestItem(
        id="PRI-FULL-01",
        purchase_request_id=pr.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("1000.00"),
        amount=Decimal("10000.00"),
    )
    database.session.add_all([pr, pr_item])
    database.session.commit()

    # 2. Solicitud de Cotización (PurchaseQuotation / RFQ)
    rfq = PurchaseQuotation(
        id="RFQ-FULL-01",
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
    )
    rfq_item = PurchaseQuotationItem(
        id="RFQI-FULL-01",
        purchase_quotation_id=rfq.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("0.00"),
        amount=Decimal("0.00"),
    )
    database.session.add_all([rfq, rfq_item])

    # Vincular Solicitud de Compra con RFQ mediante DocumentRelation
    rel_pr_rfq = DocumentRelation(
        source_type="purchase_request",
        source_id=pr.id,
        target_type="purchase_quotation",
        target_id=rfq.id,
        qty=Decimal("10"),
        relation_type="sourcing",
        status="active",
    )
    database.session.add(rel_pr_rfq)
    database.session.commit()

    # 3. Cotizaciones de Proveedores (SupplierQuotation) - Ronda 1
    sq_alpha = SupplierQuotation(
        id="SQ-ALPHA-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        supplier_name="Proveedor Alpha",
        purchase_quotation_id=rfq.id,
        posting_date=date.today(),
        docstatus=1,
    )
    sqi_alpha = SupplierQuotationItem(
        id="SQI-ALPHA-01",
        supplier_quotation_id=sq_alpha.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("950.00"),
        amount=Decimal("9500.00"),
    )

    sq_beta = SupplierQuotation(
        id="SQ-BETA-01",
        company="cacao",
        supplier_id="SUP-S2P-02",
        supplier_name="Proveedor Beta",
        purchase_quotation_id=rfq.id,
        posting_date=date.today(),
        docstatus=1,
    )
    sqi_beta = SupplierQuotationItem(
        id="SQI-BETA-01",
        supplier_quotation_id=sq_beta.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("920.00"),
        amount=Decimal("9200.00"),
    )
    database.session.add_all([sq_alpha, sqi_alpha, sq_beta, sqi_beta])
    database.session.commit()

    # Enlazar las cotizaciones al RFQ mediante DocumentRelation
    rel_rfq_sq_a = DocumentRelation(
        source_type="purchase_quotation",
        source_id=rfq.id,
        target_type="supplier_quotation",
        target_id=sq_alpha.id,
        qty=Decimal("10"),
        relation_type="sourcing",
        status="active",
    )
    rel_rfq_sq_b = DocumentRelation(
        source_type="purchase_quotation",
        source_id=rfq.id,
        target_type="supplier_quotation",
        target_id=sq_beta.id,
        qty=Decimal("10"),
        relation_type="sourcing",
        status="active",
    )
    database.session.add_all([rel_rfq_sq_a, rel_rfq_sq_b])
    database.session.commit()

    # 4. Ronda de Negociación 2 (Abrir segunda ronda)
    round2 = open_negotiation_round(rfq.id, "user-manager")
    database.session.commit()
    assert round2.round_number == 1

    # Oferta mejorada de Alpha en la nueva ronda
    sq_alpha2 = SupplierQuotation(
        id="SQ-ALPHA-02",
        company="cacao",
        supplier_id="SUP-S2P-01",
        supplier_name="Proveedor Alpha",
        purchase_quotation_id=rfq.id,
        negotiation_round_id=round2.id,
        posting_date=date.today(),
        docstatus=1,
    )
    sqi_alpha2 = SupplierQuotationItem(
        id="SQI-ALPHA-02",
        supplier_quotation_id=sq_alpha2.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("880.00"),
        amount=Decimal("8800.00"),
    )
    database.session.add_all([sq_alpha2, sqi_alpha2])
    database.session.commit()

    rel_rfq_sq_a2 = DocumentRelation(
        source_type="purchase_quotation",
        source_id=rfq.id,
        target_type="supplier_quotation",
        target_id=sq_alpha2.id,
        qty=Decimal("10"),
        relation_type="sourcing",
        status="active",
    )
    database.session.add(rel_rfq_sq_a2)
    database.session.commit()

    # 5. Comparativo de Ofertas y Adjudicación desde Solicitud de Compra
    comparison = create_purchase_request_comparison(
        pr,
        [sq_beta.id, sq_alpha2.id],
        "user-manager",
    )
    database.session.commit()

    # Guardar borrador con la oferta recomendada (Proveedor Alpha2 a 880.00)
    selections = {"PRI-FULL-01": sq_alpha2.id}
    reasons = {}
    save_purchase_request_comparison_draft(comparison, selections, reasons, "user-manager")
    database.session.commit()

    # Finalizar el comparativo
    finalize_purchase_request_comparison(comparison, "user-manager", is_authorizer=True)
    database.session.commit()

    orders = create_purchase_orders_from_comparison(comparison)
    database.session.commit()

    assert len(orders) == 1
    generated_po = orders[0]
    assert generated_po.supplier_id == "SUP-S2P-01"
    assert generated_po.grand_total == Decimal("8800.00")


def test_s2p_operational_execution_and_3way_matching(app_ctx):
    """
    Prueba de ejecución operativa de Compras:
    Orden de Compra -> Recepción de Almacén (Recepción parcial/total y Kardex) ->
    Factura de Proveedor (Matching 3-way y Puente de Recepción)
    """
    # 1. Orden de Compra (PurchaseOrder) para 10 unidades de Laptop Pro a 880.00
    po = PurchaseOrder(
        id="PO-EXEC-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        supplier_name="Proveedor Alpha",
        posting_date=date.today(),
        docstatus=1,
        grand_total=Decimal("8800.00"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    po_item = PurchaseOrderItem(
        id="POI-EXEC-01",
        purchase_order_id=po.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("880.00"),
        amount=Decimal("8800.00"),
    )
    database.session.add_all([po, po_item])
    database.session.commit()

    # 2. Recepción de Almacén (PurchaseReceipt) - Recepción de 10 unidades
    receipt = PurchaseReceipt(
        id="PREC-EXEC-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        purchase_order_id=po.id,
        grand_total=Decimal("8800.00"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    receipt_item = PurchaseReceiptItem(
        id="PRECI-EXEC-01",
        purchase_receipt_id=receipt.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("880.00"),
        amount=Decimal("8800.00"),
        warehouse="ALM-MAIN",
    )
    database.session.add_all([receipt, receipt_item])
    database.session.commit()

    # Someter la Recepción
    submit_document(receipt)
    database.session.commit()

    assert receipt.docstatus == 1
    # Verificación en Kardex / StockBin
    bin_entry = database.session.query(StockBin).filter_by(warehouse="ALM-MAIN", item_code="ITEM-S2P-01").one()
    assert bin_entry.actual_qty == Decimal("10")

    # Verificación de movimientos en el libro de stock
    sle = database.session.query(StockLedgerEntry).filter_by(voucher_id=receipt.id).one()
    assert sle.qty_change == Decimal("10")

    # 3. Factura de Proveedor (PurchaseInvoice) - Matching 3-way
    invoice = PurchaseInvoice(
        id="PINV-EXEC-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        document_type="purchase_invoice",
        purchase_order_id=po.id,
        purchase_receipt_id=receipt.id,
        grand_total=Decimal("8800.00"),
        outstanding_amount=Decimal("8800.00"),
        base_outstanding_amount=Decimal("8800.00"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    invoice_item = PurchaseInvoiceItem(
        id="PINVI-EXEC-01",
        purchase_invoice_id=invoice.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("880.00"),
        amount=Decimal("8800.00"),
    )
    database.session.add_all([invoice, invoice_item])
    database.session.commit()

    submit_document(invoice)
    database.session.commit()

    assert invoice.docstatus == 1
    assert invoice.outstanding_amount == Decimal("8800.00")
    reconciliation = database.session.query(PurchaseReconciliation).filter_by(purchase_invoice_id=invoice.id).one()
    assert reconciliation.status == "reconciled"
    assert reconciliation.matched_amount == Decimal("8800.00")
    reconciliation_items = (
        database.session.query(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation.id).all()
    )
    assert len(reconciliation_items) == 1
    assert reconciliation_items[0].purchase_receipt_item_id == receipt_item.id
    assert reconciliation_items[0].purchase_invoice_item_id == invoice_item.id


def test_s2p_credit_and_debit_notes_and_returns(app_ctx):
    """
    Prueba la lógica de ajuste y devoluciones de compras:
    - Nota de Crédito de Proveedor (disminuye saldo de la factura origen)
    - Nota de Débito de Proveedor (incrementa saldo de la factura origen)
    - Devolución de Compra (devolución física de mercancías al proveedor)
    """
    # 1. Factura Origen
    source_inv = PurchaseInvoice(
        id="PINV-ORIG-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("5000.00"),
        outstanding_amount=Decimal("5000.00"),
        base_outstanding_amount=Decimal("5000.00"),
        transaction_currency="NIO",
    )
    database.session.add(source_inv)
    database.session.commit()

    # 2. Nota de Crédito por 1000.00
    credit_note = PurchaseInvoice(
        id="PINV-CN-S2P-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        document_type="purchase_credit_note",
        grand_total=Decimal("1000.00"),
        outstanding_amount=Decimal("1000.00"),
        reversal_of="PINV-ORIG-01",
        is_return=True,
        transaction_currency="NIO",
    )
    database.session.add(credit_note)
    database.session.commit()

    _validate_purchase_reversal_of(
        reversal_of=credit_note.reversal_of,
        supplier_id=credit_note.supplier_id,
        company=credit_note.company,
        note_amount=credit_note.grand_total,
        document_type=credit_note.document_type,
        posting_date=credit_note.posting_date,
    )

    credit_note.docstatus = 1
    _persist_purchase_reversal_relation(credit_note)
    database.session.commit()

    assert compute_outstanding_amount(source_inv) == Decimal("4000.00")
    assert source_inv.outstanding_amount == Decimal("4000.00")

    # 3. Nota de Débito por 500.00
    debit_note = PurchaseInvoice(
        id="PINV-DN-S2P-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        document_type="purchase_debit_note",
        grand_total=Decimal("500.00"),
        outstanding_amount=Decimal("500.00"),
        reversal_of="PINV-ORIG-01",
        transaction_currency="NIO",
    )
    database.session.add(debit_note)
    database.session.commit()

    _validate_purchase_reversal_of(
        reversal_of=debit_note.reversal_of,
        supplier_id=debit_note.supplier_id,
        company=debit_note.company,
        note_amount=debit_note.grand_total,
        document_type=debit_note.document_type,
        posting_date=debit_note.posting_date,
    )

    debit_note.docstatus = 1
    _persist_purchase_reversal_relation(debit_note)
    database.session.commit()

    # El saldo acumulado en la factura origen refleja el descuento de la NC y el aumento de la ND (4000 + 500 = 4500)
    assert compute_outstanding_amount(source_inv) == Decimal("4500.00")

    # 4. Devolución de Recepción de Compra (purchase_return)
    # Primero se hace una recepción original de 5 unidades y se somete
    receipt = PurchaseReceipt(
        id="PREC-RET-ORIG-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        transaction_currency="NIO",
        base_currency="NIO",
        grand_total=Decimal("2500.00"),
    )
    receipt_item = PurchaseReceiptItem(
        id="PRECI-RET-ORIG-01",
        purchase_receipt_id=receipt.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("500.00"),
        amount=Decimal("2500.00"),
        warehouse="ALM-MAIN",
    )
    database.session.add_all([receipt, receipt_item])
    database.session.commit()

    submit_document(receipt)
    database.session.commit()

    bin_entry = database.session.query(StockBin).filter_by(warehouse="ALM-MAIN", item_code="ITEM-S2P-01").one()
    assert bin_entry.actual_qty == Decimal("5.00")

    # Devolución de 2 unidades
    ret_receipt = PurchaseReceipt(
        id="PREC-RET-DEV-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        is_return=True,
        transaction_currency="NIO",
        base_currency="NIO",
        grand_total=Decimal("1000.00"),
    )
    ret_item = PurchaseReceiptItem(
        id="PRECI-RET-DEV-01",
        purchase_receipt_id=ret_receipt.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("2"),
        uom="UND",
        rate=Decimal("500.00"),
        amount=Decimal("1000.00"),
        warehouse="ALM-MAIN",
    )
    database.session.add_all([ret_receipt, ret_item])
    database.session.commit()

    submit_document(ret_receipt)
    database.session.commit()

    assert ret_receipt.docstatus == 1
    # StockBin debe reflejar 5 - 2 = 3 unidades
    assert bin_entry.actual_qty == Decimal("3.00")
    # El GL de inventario debe decrecer con la devolución (reverso del cargo original)
    from cacao_accounting.database import GLEntry

    wca_gl_account = database.session.execute(
        database.select(WarehouseCompanyAccount.inventory_account_id).filter_by(
            warehouse_code="ALM-MAIN", company="cacao"
        )
    ).scalar_one()
    inventory_gl = database.session.execute(
        database.select(database.func.coalesce(database.func.sum(GLEntry.debit - GLEntry.credit), 0)).filter_by(
            voucher_type="purchase_receipt",
            voucher_id=ret_receipt.id,
            account_id=wca_gl_account,
        )
    ).scalar_one()
    assert inventory_gl == Decimal("-1000.00")


def test_s2p_payment_application_and_advance_against_invoice(app_ctx):
    """
    Prueba los pagos, aplicaciones de anticipo y cancelación de pagos:
    - Anticipo registrado sobre Orden de Compra (is_advance=True / advance_mode)
    - Facturación final del proveedor
    - Aplicación del anticipo contra la factura final
    - Verificación del saldo residual y cancelación de pagos
    """
    # 1. Orden de Compra por 10,000.00
    po = PurchaseOrder(
        id="PO-ADV-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        supplier_name="Proveedor Alpha",
        posting_date=date.today(),
        docstatus=1,
        grand_total=Decimal("10000.00"),
        transaction_currency="NIO",
    )
    database.session.add(po)
    database.session.commit()

    # 2. Registro de Anticipo (PaymentEntry) de 3,000.00 vinculado a la PO
    payment_advance = PaymentEntry(
        id="PAY-ADV-01",
        company="cacao",
        payment_type="pay",
        party_type="supplier",
        party_id="SUP-S2P-01",
        posting_date=date.today(),
        paid_amount=Decimal("3000.00"),
        currency="NIO",
        is_advance=True,
        docstatus=1,
    )
    ref_advance = PaymentReference(
        id="PAYREF-ADV-01",
        payment_id=payment_advance.id,
        reference_type="purchase_order",
        reference_id=po.id,
        allocated_amount=Decimal("3000.00"),
    )
    database.session.add_all([payment_advance, ref_advance])
    database.session.commit()

    # Enlazar la relación de pago anticipado
    rel_po_pay = DocumentRelation(
        source_type="purchase_order",
        source_id=po.id,
        target_type="payment_entry",
        target_id=payment_advance.id,
        target_item_id=ref_advance.id,
        qty=Decimal("3000.00"),
        relation_type="advance_payment",
        status="active",
        company="cacao",
    )
    database.session.add(rel_po_pay)
    database.session.commit()

    # 3. Factura de Proveedor por 10,000.00
    invoice = PurchaseInvoice(
        id="PINV-ADV-FINAL-01",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        purchase_order_id=po.id,
        grand_total=Decimal("10000.00"),
        outstanding_amount=Decimal("10000.00"),
        base_outstanding_amount=Decimal("10000.00"),
        transaction_currency="NIO",
    )
    database.session.add(invoice)
    database.session.commit()

    # 4. Crear PaymentReference de la Factura y DocumentRelation para el anticipo
    ref_inv_advance = PaymentReference(
        id="PAYREF-INV-ADV-01",
        payment_id=payment_advance.id,
        reference_type="purchase_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("3000.00"),
        allocation_date=date.today(),
    )
    database.session.add(ref_inv_advance)
    database.session.commit()

    rel_inv_pay = DocumentRelation(
        source_type="purchase_invoice",
        source_id=invoice.id,
        target_type="payment_entry",
        target_id=payment_advance.id,
        target_item_id=ref_inv_advance.id,
        qty=Decimal("3000.00"),
        relation_type="payment_application",
        status="active",
        company="cacao",
    )
    database.session.add(rel_inv_pay)
    database.session.commit()

    refresh_outstanding_amount_cache(invoice)
    database.session.commit()

    # Saldo pendiente debe ser 10000 - 3000 = 7000.00
    assert compute_outstanding_amount(invoice) == Decimal("7000.00")
    assert invoice.outstanding_amount == Decimal("7000.00")

    # 5. Pago por el Saldo Restante de 7,000.00
    payment_final = PaymentEntry(
        id="PAY-FINAL-01",
        company="cacao",
        payment_type="pay",
        party_type="supplier",
        party_id="SUP-S2P-01",
        posting_date=date.today(),
        paid_amount=Decimal("7000.00"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
        bank_account_id="BANK-ACC-S2P",
    )
    ref_final = PaymentReference(
        id="PAYREF-FINAL-01",
        payment_id=payment_final.id,
        reference_type="purchase_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("7000.00"),
        allocation_date=date.today(),
    )
    database.session.add_all([payment_final, ref_final])
    database.session.commit()

    submit_document(payment_final)
    database.session.commit()

    rel_inv_pay_final = DocumentRelation(
        source_type="purchase_invoice",
        source_id=invoice.id,
        target_type="payment_entry",
        target_id=payment_final.id,
        target_item_id=ref_final.id,
        qty=Decimal("7000.00"),
        relation_type="payment",
        status="active",
        company="cacao",
    )
    database.session.add(rel_inv_pay_final)
    database.session.commit()

    refresh_outstanding_amount_cache(invoice)
    database.session.commit()

    # Factura totalmente pagada
    assert compute_outstanding_amount(invoice) == Decimal("0.00")
    assert invoice.outstanding_amount == Decimal("0.00")

    # 6. Pago por Cancelación: Se cancela el pago final PAY-FINAL-01
    from cacao_accounting.contabilidad.posting import cancel_document

    cancel_document(payment_final, reason="Correccion de pago", actor_user_id="user-manager")
    revert_relations_for_target("payment_entry", payment_final.id)
    refresh_source_caches_for_target("payment_entry", payment_final.id)
    refresh_outstanding_amount_cache(invoice)
    database.session.commit()

    # Saldo pendiente se restaura a 7000.00 (manteniendo activo solo el anticipo de 3000.00)
    assert compute_outstanding_amount(invoice) == Decimal("7000.00")
    assert invoice.outstanding_amount == Decimal("7000.00")
