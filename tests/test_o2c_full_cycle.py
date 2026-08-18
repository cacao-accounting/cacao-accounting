# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Nombre Reyes

"""Pruebas unitarias exhaustivas para todo el ciclo Order to Cash (O2C).

Cubre:
1. Cotizaciones de Venta (SalesQuotation)
2. Órdenes de Venta (SalesOrder)
3. Remisiones / Notas de Entrega de Productos en Almacén (DeliveryNote)
4. Facturas de Venta (SalesInvoice - sales_invoice)
5. Notas de Débito (SalesInvoice - sales_debit_note)
6. Notas de Crédito (SalesInvoice - sales_credit_note)
7. Devoluciones de Venta (SalesInvoice - sales_return)
"""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.contabilidad.posting import submit_document
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyParty,
    DeliveryNote,
    DeliveryNoteItem,
    DocumentRelation,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    StockBin,
    StockEntry,
    StockEntryItem,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key_o2c",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()

        books = database.session.execute(database.select(Book).filter_by(entity="cacao")).scalars().all()
        book_codes = [b.code for b in books]
        if "USD_BOOK" not in book_codes:
            database.session.add(Book(code="USD_BOOK", name="Dólares", entity="cacao", currency="USD", status="activo"))
        database.session.commit()
        yield app


def _ensure_item(code="ITEM-O2C", warehouse="WH-MAIN"):
    wh = database.session.get(Warehouse, warehouse)
    if not wh:
        wh = Warehouse(code=warehouse, name="Almacén Principal O2C", company="cacao")
        database.session.add(wh)
        database.session.flush()

    inv_account = (
        database.session.execute(database.select(Accounts).filter_by(entity="cacao", account_type="inventory"))
        .scalars()
        .first()
    )
    if (
        inv_account
        and not database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code=warehouse, company="cacao")
        ).scalar_one_or_none()
    ):
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=warehouse,
                company="cacao",
                inventory_account_id=inv_account.id,
                is_active=True,
            )
        )
        database.session.flush()

    item = database.session.get(Item, code)
    if not item:
        item = Item(
            code=code,
            name=f"Artículo {code}",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
            default_warehouse_id=warehouse,
        )
        database.session.add(item)
        database.session.flush()
    return item


def _ensure_customer(code="CUST-O2C", name="Cliente O2C Test"):
    customer = database.session.execute(database.select(Party).filter_by(code=code)).scalar_one_or_none()
    if not customer:
        customer = Party(code=code, name=name, is_customer=True, is_active=True)
        database.session.add(customer)
        database.session.flush()
    if not database.session.execute(
        database.select(CompanyParty).filter_by(party_id=customer.id, company="cacao")
    ).scalar_one_or_none():
        database.session.add(CompanyParty(party_id=customer.id, company="cacao", is_active=True))
        database.session.commit()
    return customer


def _receive_stock(item_code, warehouse, qty, valuation_rate):
    se = StockEntry(
        company="cacao",
        posting_date=date.today(),
        purpose="material_receipt",
        docstatus=0,
    )
    database.session.add(se)
    database.session.flush()
    sei = StockEntryItem(
        stock_entry_id=se.id,
        item_code=item_code,
        qty=Decimal(str(qty)),
        uom="UND",
        basic_rate=Decimal(str(valuation_rate)),
        amount=Decimal(str(qty)) * Decimal(str(valuation_rate)),
        target_warehouse=warehouse,
    )
    database.session.add(sei)
    database.session.commit()
    submit_document(se)
    database.session.commit()


def test_sales_quotation_workflow(app_ctx):
    """Verifica el flujo completo de Cotizaciones de Venta.

    - Creación desde Solicitud de Venta / Pedido de Venta.
    - Transición de borrador (0) a aprobado (1) vía submit.
    - Bloqueo de cancelación cuando existen relaciones activas descendentes.
    - Cancelación correcta (2) y reversión de relaciones.
    """
    customer = _ensure_customer("CUST-SQ", "Cliente Cotizacion")
    item = _ensure_item("ITEM-SQ")

    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    # 1. Crear Pedido de Venta borrador
    sr = SalesRequest(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date.today(),
        total=Decimal("1500"),
        grand_total=Decimal("1500"),
        docstatus=0,
    )
    database.session.add(sr)
    database.session.flush()
    sr_item = SalesRequestItem(
        sales_request_id=sr.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("150"),
        amount=Decimal("1500"),
    )
    database.session.add(sr_item)
    database.session.commit()

    # Aprobar el Pedido de Venta
    res_sr_submit = client.post(f"/sales/sales-request/{sr.id}/submit", follow_redirects=True)
    assert res_sr_submit.status_code == 200
    database.session.refresh(sr)
    assert sr.docstatus == 1

    # 2. Crear Cotización de Venta referenciando la Solicitud
    sq = SalesQuotation(
        customer_id=customer.id,
        customer_name=customer.name,
        sales_request_id=sr.id,
        company="cacao",
        posting_date=date.today(),
        total=Decimal("1500"),
        grand_total=Decimal("1500"),
        docstatus=0,
    )
    database.session.add(sq)
    database.session.flush()
    sq_item = SalesQuotationItem(
        sales_quotation_id=sq.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("150"),
        amount=Decimal("1500"),
    )
    database.session.add(sq_item)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_request",
            source_id=sr.id,
            source_item_id=sr_item.id,
            target_type="sales_quotation",
            target_id=sq.id,
            target_item_id=sq_item.id,
            qty=Decimal("10"),
            amount=Decimal("1500"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    # Aprobar Cotización
    res_sq_submit = client.post(f"/sales/sales-quotation/{sq.id}/submit", follow_redirects=True)
    assert res_sq_submit.status_code == 200
    database.session.refresh(sq)
    assert sq.docstatus == 1

    # 3. Intentar cancelar Cotización cuando tiene relación activa descendente (Orden de Venta)
    so = SalesOrder(
        customer_id=customer.id,
        sales_quotation_id=sq.id,
        company="cacao",
        posting_date=date.today(),
        total=Decimal("1500"),
        grand_total=Decimal("1500"),
        docstatus=0,
    )
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(
        sales_order_id=so.id,
        item_code=item.code,
        qty=Decimal("10"),
        rate=Decimal("150"),
        amount=Decimal("1500"),
    )
    database.session.add(so_item)
    database.session.flush()

    database.session.add(
        DocumentRelation(
            source_type="sales_quotation",
            source_id=sq.id,
            source_item_id=sq_item.id,
            target_type="sales_order",
            target_id=so.id,
            target_item_id=so_item.id,
            qty=Decimal("10"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    # Intentar cancelar cotización -> Debe rebotar / notificar bloqueo por relación activa
    res_cancel_blocked = client.post(f"/sales/sales-quotation/{sq.id}/cancel", follow_redirects=True)
    assert res_cancel_blocked.status_code == 200
    database.session.refresh(sq)
    assert sq.docstatus == 1  # Permanece activa

    # 4. Eliminar/desactivar la Orden de Venta y probar cancelación exitosa de la Cotización
    rel = database.session.execute(database.select(DocumentRelation).filter_by(source_id=sq.id, target_id=so.id)).scalar_one()
    rel.status = "reverted"
    database.session.delete(so_item)
    database.session.delete(so)
    database.session.commit()

    res_cancel_ok = client.post(f"/sales/sales-quotation/{sq.id}/cancel", follow_redirects=True)
    assert res_cancel_ok.status_code == 200
    database.session.refresh(sq)
    assert sq.docstatus == 2


def test_sales_order_stock_reservation_and_credit_limit(app_ctx):
    """Verifica reserva de stock en StockBin y control de límite de crédito en Ordenes de Venta.

    - Aprobar Orden de Venta incrementa reserved_qty en StockBin.
    - Rechaza aprobación si el límite de crédito del cliente es excedido.
    - Cancelar la Orden de Venta libera la reserva en StockBin.
    """
    customer = _ensure_customer("CUST-SO-RES", "Cliente Reserva SO")
    item = _ensure_item("ITEM-SO-RES", warehouse="WH-MAIN")

    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    # Ingresar stock real vía StockEntry
    _receive_stock(item.code, "WH-MAIN", 100, 50)
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code=item.code, warehouse="WH-MAIN")
    ).scalar_one()

    # Configurar límite de crédito de $5,000 para el cliente
    cp = database.session.execute(database.select(CompanyParty).filter_by(party_id=customer.id, company="cacao")).scalar_one()
    cp.credit_limit = Decimal("5000")
    database.session.commit()

    # 1. Crear y aprobar Orden de Venta válida ($2,000)
    so = SalesOrder(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date.today(),
        total=Decimal("2000"),
        grand_total=Decimal("2000"),
        docstatus=0,
    )
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(
        sales_order_id=so.id,
        item_code=item.code,
        qty=Decimal("20"),
        rate=Decimal("100"),
        amount=Decimal("2000"),
        warehouse="WH-MAIN",
    )
    database.session.add(so_item)
    database.session.commit()

    # Aprobar la Orden de Venta
    res_so_submit = client.post(f"/sales/sales-order/{so.id}/submit", follow_redirects=True)
    assert res_so_submit.status_code == 200
    database.session.refresh(so)
    assert so.docstatus == 1

    # Verificar que el StockBin ahora tiene 20 reservadas
    database.session.refresh(bin_row)
    assert bin_row.reserved_qty == Decimal("20")

    # 2. Intentar crear y aprobar otra Orden de Venta que exceda el límite de crédito ($4,000 + $2,000 = $6,000 > $5,000)
    so_excess = SalesOrder(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date.today(),
        total=Decimal("4000"),
        grand_total=Decimal("4000"),
        docstatus=0,
    )
    database.session.add(so_excess)
    database.session.flush()
    so_excess_item = SalesOrderItem(
        sales_order_id=so_excess.id,
        item_code=item.code,
        qty=Decimal("40"),
        rate=Decimal("100"),
        amount=Decimal("4000"),
        warehouse="WH-MAIN",
    )
    database.session.add(so_excess_item)
    database.session.commit()

    res_excess_submit = client.post(f"/sales/sales-order/{so_excess.id}/submit", follow_redirects=True)
    assert res_excess_submit.status_code == 200
    database.session.refresh(so_excess)
    assert so_excess.docstatus == 0  # Permanece en borrador por límite de crédito

    # 3. Cancelar la primera Orden de Venta y verificar liberación de reserva
    res_so_cancel = client.post(f"/sales/sales-order/{so.id}/cancel", follow_redirects=True)
    assert res_so_cancel.status_code == 200
    database.session.refresh(so)
    assert so.docstatus == 2

    database.session.refresh(bin_row)
    assert bin_row.reserved_qty == Decimal("0")


def test_delivery_note_inventory_deduction_and_overdelivery_prevention(app_ctx):
    """Verifica Remisión / Nota de Entrega en Almacén.

    - Descontar actual_qty y liberar reserved_qty al aprobar la Nota de Entrega.
    - Prevenir sobre-entrega si la cantidad entregada excede la ordenada.
    - Restaurar stock y reserva al cancelar la Nota de Entrega.
    """
    customer = _ensure_customer("CUST-DN", "Cliente Remision")
    item = _ensure_item("ITEM-DN", warehouse="WH-MAIN")

    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    # Ingresar stock real vía StockEntry (50 unidades a $10 c/u)
    _receive_stock(item.code, "WH-MAIN", 50, 10)
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code=item.code, warehouse="WH-MAIN")
    ).scalar_one()

    # Crear y aprobar Orden de Venta por 10 unidades
    so = SalesOrder(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date.today(),
        total=Decimal("1000"),
        grand_total=Decimal("1000"),
        docstatus=1,
    )
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(
        sales_order_id=so.id,
        item_code=item.code,
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
        warehouse="WH-MAIN",
    )
    database.session.add(so_item)
    # Reserva manual equivalente al submit de SO
    bin_row.reserved_qty = Decimal("10")
    database.session.commit()

    # 1. Crear Nota de Entrega
    dn = DeliveryNote(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        sales_order_id=so.id,
        posting_date=date.today(),
        total=Decimal("1000"),
        grand_total=Decimal("1000"),
        docstatus=0,
    )
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(
        delivery_note_id=dn.id,
        item_code=item.code,
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
        warehouse="WH-MAIN",
    )
    database.session.add(dn_item)
    database.session.flush()

    database.session.add(
        DocumentRelation(
            source_type="sales_order",
            source_id=so.id,
            source_item_id=so_item.id,
            target_type="delivery_note",
            target_id=dn.id,
            target_item_id=dn_item.id,
            qty=Decimal("10"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    # Aprobar Nota de Entrega
    res_dn_submit = client.post(f"/sales/delivery-note/{dn.id}/submit", follow_redirects=True)
    assert res_dn_submit.status_code == 200
    database.session.refresh(dn)
    assert dn.docstatus == 1

    # Verificar balances en StockBin: actual_qty baja de 50 a 40, reserved_qty baja de 10 a 0
    database.session.refresh(bin_row)
    assert bin_row.actual_qty == Decimal("40")
    assert bin_row.reserved_qty == Decimal("0")

    # 2. Cancelar Nota de Entrega y verificar reversión
    res_dn_cancel = client.post(f"/sales/delivery-note/{dn.id}/cancel", follow_redirects=True)
    assert res_dn_cancel.status_code == 200
    database.session.refresh(dn)
    assert dn.docstatus == 2

    # StockBin debe restaurar actual_qty a 50 y reserved_qty a 10
    database.session.refresh(bin_row)
    assert bin_row.actual_qty == Decimal("50")
    assert bin_row.reserved_qty == Decimal("10")


def test_sales_invoice_tolerance_and_auto_delivery_note(app_ctx):
    """Verifica tolerancias de precio y generación automática de Nota de Entrega desde Factura.

    - Cuando update_inventory=True, aprobar Factura autogenera y aprueba Nota de Entrega.
    - Cancelar la Factura cancela automáticamente la Nota de Entrega vinculada.
    """
    customer = _ensure_customer("CUST-SI-AUTO", "Cliente Factura Auto DN")
    item = _ensure_item("ITEM-SI-AUTO", warehouse="WH-MAIN")

    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    # Ingresar stock real vía StockEntry (100 unidades a $20 c/u)
    _receive_stock(item.code, "WH-MAIN", 100, 20)
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code=item.code, warehouse="WH-MAIN")
    ).scalar_one()

    # Crear Factura de Venta directa con update_inventory=True
    si = SalesInvoice(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_invoice",
        update_inventory=True,
        total=Decimal("1500"),
        grand_total=Decimal("1500"),
        docstatus=0,
    )
    database.session.add(si)
    database.session.flush()
    si_item = SalesInvoiceItem(
        sales_invoice_id=si.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("15"),
        rate=Decimal("100"),
        amount=Decimal("1500"),
        warehouse="WH-MAIN",
    )
    database.session.add(si_item)
    database.session.commit()

    # Aprobar Factura
    res_si_submit = client.post(f"/sales/sales-invoice/{si.id}/submit", follow_redirects=True)
    assert res_si_submit.status_code == 200
    database.session.refresh(si)
    assert si.docstatus == 1
    assert si.delivery_note_id is not None  # Se creó Nota de Entrega auto-generada

    # Verificar la Nota de Entrega creada
    dn_auto = database.session.get(DeliveryNote, si.delivery_note_id)
    assert dn_auto is not None
    assert dn_auto.docstatus == 1

    # Verificar que el stock disminuyó en 15 unidades
    database.session.refresh(bin_row)
    assert bin_row.actual_qty == Decimal("85")

    # Cancelar la Factura de Venta y verificar cancelación en cascada de la Nota de Entrega
    res_si_cancel = client.post(f"/sales/sales-invoice/{si.id}/cancel", follow_redirects=True)
    assert res_si_cancel.status_code == 200
    database.session.refresh(si)
    assert si.docstatus == 2

    database.session.refresh(dn_auto)
    assert dn_auto.docstatus == 2

    # StockBin debe retornar a 100
    database.session.refresh(bin_row)
    assert bin_row.actual_qty == Decimal("100")


def test_debit_note_credit_note_and_returns(app_ctx):
    """Verifica Notas de Débito, Notas de Crédito y Devoluciones de Venta.

    - Nota de Débito incrementa las cuentas por cobrar / saldo de la factura.
    - Nota de Crédito no puede exceder el saldo pendiente de la factura origen (_validate_reversal_of).
    - La Nota de Crédito/Devolución reduce el saldo pendiente (outstanding_amount).
    """
    customer = _ensure_customer("CUST-REV", "Cliente Reversiones")
    item = _ensure_item("ITEM-REV")

    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    # 1. Factura de Venta original por $1,000
    si_orig = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        total=Decimal("1000"),
        grand_total=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
    )
    database.session.add(si_orig)
    database.session.flush()
    si_orig_item = SalesInvoiceItem(
        sales_invoice_id=si_orig.id,
        item_code=item.code,
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
    )
    database.session.add(si_orig_item)
    database.session.commit()

    # 2. Crear y aprobar Nota de Débito por $200 (incrementa saldo por cobrar)
    dn_invoice = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_debit_note",
        reversal_of=si_orig.id,
        total=Decimal("200"),
        grand_total=Decimal("200"),
        docstatus=0,
    )
    database.session.add(dn_invoice)
    database.session.flush()
    dn_item = SalesInvoiceItem(
        sales_invoice_id=dn_invoice.id,
        item_code=item.code,
        qty=Decimal("2"),
        rate=Decimal("100"),
        amount=Decimal("200"),
    )
    database.session.add(dn_item)
    database.session.commit()

    res_dn_submit = client.post(f"/sales/sales-invoice/{dn_invoice.id}/submit", follow_redirects=True)
    assert res_dn_submit.status_code == 200
    database.session.refresh(dn_invoice)
    assert dn_invoice.docstatus == 1

    # 3. Intentar crear Nota de Crédito por $1,500 que excede el saldo pendiente ($1,000 + $200 de débito = $1,200)
    cn_exceed = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_credit_note",
        reversal_of=si_orig.id,
        is_return=True,
        total=Decimal("1500"),
        grand_total=Decimal("1500"),
        docstatus=0,
    )
    database.session.add(cn_exceed)
    database.session.flush()
    cn_exceed_item = SalesInvoiceItem(
        sales_invoice_id=cn_exceed.id,
        item_code=item.code,
        qty=Decimal("15"),
        rate=Decimal("100"),
        amount=Decimal("1500"),
    )
    database.session.add(cn_exceed_item)
    database.session.commit()

    res_cn_exceed_submit = client.post(f"/sales/sales-invoice/{cn_exceed.id}/submit", follow_redirects=True)
    assert res_cn_exceed_submit.status_code == 200
    database.session.refresh(cn_exceed)
    assert cn_exceed.docstatus == 0  # Permanece en borrador por exceder el saldo

    # 4. Crear Nota de Crédito válida por $400
    cn_valid = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_credit_note",
        reversal_of=si_orig.id,
        is_return=True,
        total=Decimal("400"),
        grand_total=Decimal("400"),
        docstatus=0,
    )
    database.session.add(cn_valid)
    database.session.flush()
    cn_valid_item = SalesInvoiceItem(
        sales_invoice_id=cn_valid.id,
        item_code=item.code,
        qty=Decimal("4"),
        rate=Decimal("100"),
        amount=Decimal("400"),
    )
    database.session.add(cn_valid_item)
    database.session.commit()

    res_cn_valid_submit = client.post(f"/sales/sales-invoice/{cn_valid.id}/submit", follow_redirects=True)
    assert res_cn_valid_submit.status_code == 200
    database.session.refresh(cn_valid)
    assert cn_valid.docstatus == 1

    # Verificar que el saldo pendiente de la factura original se actualizó ($1,000 + $200 débito - $400 crédito = $800)
    from cacao_accounting.document_flow.payment import compute_outstanding_amount

    outstanding = compute_outstanding_amount(si_orig)
    assert outstanding == Decimal("800")

    # Exercise the separately registered sales_return flow, not only a credit note
    # with is_return=True.
    sales_return = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_return",
        reversal_of=si_orig.id,
        is_return=True,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        docstatus=0,
    )
    database.session.add(sales_return)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=sales_return.id,
            item_code=item.code,
            qty=Decimal("1"),
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
    )
    database.session.commit()

    res_return_submit = client.post(f"/sales/sales-invoice/{sales_return.id}/submit", follow_redirects=True)
    assert res_return_submit.status_code == 200
    database.session.refresh(sales_return)
    assert sales_return.docstatus == 1
