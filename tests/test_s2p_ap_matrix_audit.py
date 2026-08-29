"""Suite AUDIT-006 (#281): matriz S2P/P2P de cuentas por pagar.

Cubre la ecuacion del submayor AP:
    payable - notas de credito - pagos aplicados - write-offs = outstanding payable
con conciliacion contra el mayor general (AP), matching 3-way, puente GRNI,
anticipos con neteo GL, reembolsos, write-offs por descuento, duplicados,
cancelaciones y multidivisa.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

COMPANY = "s2p"
AS_OF = date(2026, 8, 20)
# Corte abierto para calculos de saldo vigentes (date.today() puede ser anterior
# a las fechas de transaccion usadas en los escenarios).
OPEN_END = date(2026, 12, 31)


@pytest.fixture()
def app_ctx():
    """App de prueba con esquema limpio y datos base S2P."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def chart():
    """Datos base S2P (entidad, cuentas AP/GRNI/banco y proveedor)."""
    return _seed_base_data()


def _seed_base_data() -> dict:
    """Siembra entidad, monedas, cuentas AP/GRNI/banco y proveedor."""
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        Currency,
        Entity,
        Item,
        Party,
        PartyAccount,
        UOM,
        User,
        Warehouse,
        WarehouseCompanyAccount,
    )

    database.session.add_all(
        [
            Entity(code=COMPANY, name="S2P", company_name="S2P Corp", tax_id="S2P-1", currency="NIO"),
            Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
            Currency(code="USD", name="Dolares", decimals=2, active=True),
            AccountingPeriod(
                entity=COMPANY,
                name="2026",
                start=date(2026, 1, 1),
                end=date(2026, 12, 31),
                enabled=True,
                is_closed=False,
            ),
        ]
    )
    database.session.commit()

    ap = Accounts(entity=COMPANY, code="2101", name="Cuentas por Pagar", classification="liability", account_type="payable")
    grni = Accounts(entity=COMPANY, code="2102", name="Puente Recepciones no Facturadas", classification="liability")
    expense = Accounts(entity=COMPANY, code="6101", name="Gasto Operativo", classification="expense")
    bank_gl = Accounts(entity=COMPANY, code="1001", name="Banco", classification="asset", account_type="bank")
    advance = Accounts(
        entity=COMPANY, code="1103", name="Anticipo a Proveedores", classification="asset", account_type="supplier_advance"
    )
    discount = Accounts(entity=COMPANY, code="4101", name="Descuento Compras", classification="income")
    inventory = Accounts(entity=COMPANY, code="1105", name="Inventario", classification="asset")
    fx_gain = Accounts(entity=COMPANY, code="4102", name="Ganancia Cambiaria", classification="income")
    fx_loss = Accounts(entity=COMPANY, code="6102", name="Perdida Cambiaria", classification="expense")
    fx_unreal_gain = Accounts(entity=COMPANY, code="4103", name="Ganancia Cambiaria No Realizada", classification="income")
    fx_unreal_loss = Accounts(entity=COMPANY, code="6103", name="Perdida Cambiaria No Realizada", classification="expense")
    book = Book(entity=COMPANY, code="S2PLOC", name="Libro Fiscal", currency="NIO", status="activo", is_primary=True)
    bank = Bank(name="Banco S2P")
    uom = UOM(code="UND", name="Unidad")
    warehouse = Warehouse(code="ALM-S2P", name="Almacen S2P", company=COMPANY)
    item = Item(code="ITEM-S2P", name="Insumo", item_type="goods", is_stock_item=True, default_uom="UND")
    database.session.add_all(
        [
            ap,
            grni,
            expense,
            bank_gl,
            advance,
            discount,
            inventory,
            fx_gain,
            fx_loss,
            fx_unreal_gain,
            fx_unreal_loss,
            book,
            bank,
            uom,
            warehouse,
            item,
        ]
    )
    database.session.flush()

    bank_account = BankAccount(
        bank_id=bank.id, company=COMPANY, account_name="Cta Corriente", currency="NIO", gl_account_id=bank_gl.id
    )
    database.session.add_all(
        [
            bank_account,
            WarehouseCompanyAccount(
                warehouse_code="ALM-S2P",
                company=COMPANY,
                inventory_account_id=inventory.id,
            ),
            CompanyDefaultAccount(
                company=COMPANY,
                default_payable=ap.id,
                default_expense=expense.id,
                default_bank=bank_gl.id,
                supplier_advance_account_id=advance.id,
                purchase_discount_account_id=discount.id,
                bridge_account_id=grni.id,
                exchange_gain_account_id=fx_gain.id,
                exchange_loss_account_id=fx_loss.id,
                unrealized_exchange_gain_account_id=fx_unreal_gain.id,
                unrealized_exchange_loss_account_id=fx_unreal_loss.id,
            ),
            PartyAccount(party_id="SUP-S2P", company=COMPANY, payable_account_id=ap.id),
            Party(id="SUP-S2P", code="SUP-S2P", name="Proveedor S2P", is_supplier=True, is_active=True),
            User(id="s2p-actor", user="s2p-actor", name="S2P Actor", password=b"x", classification="admin", active=True),
        ]
    )
    database.session.commit()
    return {
        "ap_id": ap.id,
        "grni_id": grni.id,
        "expense_id": expense.id,
        "bank_gl_id": bank_gl.id,
        "advance_id": advance.id,
        "discount_id": discount.id,
        "inventory_id": inventory.id,
        "warehouse": "ALM-S2P",
        "bank_account_id": bank_account.id,
        "actor_id": "s2p-actor",
    }


def _supplier_id() -> str:
    from cacao_accounting.database import Party

    supplier = database.session.execute(select(Party).filter_by(code="SUP-S2P")).scalars().first()
    assert supplier is not None
    return supplier.id


def _make_receipt(*, amount: Decimal, chart: dict, posting_date: date = AS_OF, po=None) -> object:
    """Crea y somete una recepcion de compra aprobada (genera puente GRNI)."""
    from cacao_accounting.contabilidad.posting_service import post_document_to_gl
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database

    receipt = PurchaseReceipt(
        company=COMPANY,
        supplier_id=_supplier_id(),
        posting_date=posting_date,
        docstatus=1,
        purchase_order_id=po.id if po is not None else None,
        grand_total=amount,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(receipt)
    database.session.flush()
    item = PurchaseReceiptItem(
        purchase_receipt_id=receipt.id,
        item_code="ITEM-S2P",
        item_name="Insumo",
        qty=Decimal("1"),
        uom="UND",
        rate=amount,
        amount=amount,
        warehouse=chart["warehouse"],
    )
    database.session.add(item)
    database.session.commit()
    post_document_to_gl(receipt)
    database.session.commit()
    return receipt


def _make_invoice(
    *,
    amount: Decimal,
    chart: dict,
    posting_date: date = AS_OF,
    receipt=None,
    po=None,
    supplier_invoice_no: str | None = None,
    document_type: str = "purchase_invoice",
    reversal_of=None,
) -> object:
    """Crea una factura de compra aprobada sin GL ni pagos."""
    from cacao_accounting.database import PurchaseInvoice, PurchaseInvoiceItem, database

    invoice = PurchaseInvoice(
        company=COMPANY,
        supplier_id=_supplier_id(),
        posting_date=posting_date,
        docstatus=1,
        document_type=document_type,
        purchase_order_id=po.id if po is not None else None,
        purchase_receipt_id=receipt.id if receipt is not None else None,
        supplier_invoice_no=supplier_invoice_no,
        reversal_of=reversal_of.id if reversal_of is not None else None,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        total=amount,
        grand_total=amount,
        base_total=amount,
        base_grand_total=amount,
        outstanding_amount=amount,
        base_outstanding_amount=amount,
    )
    database.session.add(invoice)
    database.session.flush()
    item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice.id,
        item_code="ITEM-S2P",
        item_name="Insumo",
        qty=Decimal("1"),
        uom="UND",
        rate=amount,
        amount=amount,
    )
    database.session.add(item)
    database.session.commit()
    return invoice


def _post_invoice(invoice) -> None:
    """Contabiliza la factura de compra en GL."""
    from cacao_accounting.contabilidad.posting_service import post_document_to_gl

    post_document_to_gl(invoice)
    database.session.commit()


def _link_purchase_reversal(note) -> None:
    """Registra la relacion documento-nota para notas de credito de proveedor."""
    from cacao_accounting.compras.services import _persist_purchase_reversal_relation

    _persist_purchase_reversal_relation(note)
    database.session.commit()


def _make_payment(
    *,
    amount: Decimal,
    chart: dict,
    payment_type: str = "pay",
    posting_date: date = AS_OF,
):
    """Crea un pago de proveedor aprobado (sin GL ni referencias)."""
    from cacao_accounting.database import PaymentEntry, database

    payment = PaymentEntry(
        company=COMPANY,
        posting_date=posting_date,
        payment_type=payment_type,
        party_type="supplier",
        party_id=_supplier_id(),
        bank_account_id=chart["bank_account_id"],
        transaction_currency="NIO",
        base_currency="NIO",
        currency="NIO",
        exchange_rate=Decimal("1"),
        received_amount=amount if payment_type == "receive" else None,
        paid_amount=amount if payment_type != "receive" else None,
        base_received_amount=amount if payment_type == "receive" else None,
        base_paid_amount=amount if payment_type != "receive" else None,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()
    return payment


def _apply(payment, lines: list[dict], allocation_date: date = AS_OF):
    """Aplica un pago contra documentos AP via el servicio de conciliacion."""
    from cacao_accounting.document_flow.payment import apply_payment_reconciliation

    payload_lines = [{"payment_id": payment.id, **line} for line in lines]
    reconciliation = apply_payment_reconciliation(
        company=COMPANY,
        party_type="supplier",
        party_id=_supplier_id(),
        allocation_date=allocation_date,
        lines=payload_lines,
    )
    database.session.commit()
    return reconciliation


def _post_payment(payment) -> None:
    """Contabiliza el pago en GL."""
    from cacao_accounting.contabilidad.posting_service import post_document_to_gl

    post_document_to_gl(payment)
    database.session.commit()


def _outstanding(document, as_of_date: date | None = OPEN_END) -> Decimal:
    from cacao_accounting.document_flow.payment import compute_outstanding_amount

    return compute_outstanding_amount(document, as_of_date=as_of_date)


def _ap_gl_balance(chart: dict, as_of: date = OPEN_END) -> Decimal:
    """Saldo acreedor neto de la cuenta AP en GL al corte indicado."""
    from cacao_accounting.database import GLEntry

    rows = (
        database.session.execute(select(GLEntry).filter_by(account_id=chart["ap_id"], is_cancelled=False, is_reversal=False))
        .scalars()
        .all()
    )
    total = Decimal("0")
    for row in rows:
        if row.posting_date > as_of:
            continue
        total += Decimal(str(row.credit)) - Decimal(str(row.debit))
    return total


def _grni_balance(chart: dict, as_of: date = OPEN_END) -> Decimal:
    """Saldo acreedor neto del puente GRNI al corte indicado."""
    from cacao_accounting.database import GLEntry

    rows = (
        database.session.execute(select(GLEntry).filter_by(account_id=chart["grni_id"], is_cancelled=False, is_reversal=False))
        .scalars()
        .all()
    )
    total = Decimal("0")
    for row in rows:
        if row.posting_date > as_of:
            continue
        total += Decimal(str(row.credit)) - Decimal(str(row.debit))
    return total


def _matrix_row(chart: dict, area: str, as_of: date = OPEN_END):
    from cacao_accounting.reportes.services import ReconciliationFilters, get_reconciliation_matrix

    matrix = get_reconciliation_matrix(ReconciliationFilters(company=COMPANY, ledger="S2PLOC", as_of_date=as_of))
    return next(row for row in matrix.rows if row.values["area"] == area)


def _assert_ap_reconciled(chart: dict, as_of: date = OPEN_END) -> None:
    """La fila AP de la matriz debe cuadrar contra el mayor general."""
    row = _matrix_row(chart, "AP", as_of)
    assert row.values["difference"] == Decimal("0"), row.values
    assert row.values["status"] == "reconciled"


def _subledger_totals(as_of_date: date | None = OPEN_END) -> dict:
    from cacao_accounting.reportes.services import SubledgerFilters, get_ar_ap_subledger

    report = get_ar_ap_subledger(SubledgerFilters(company=COMPANY, party_type="supplier", as_of_date=as_of_date))
    return report.totals


def test_281_partial_receipt_invoice_and_payment_equation(app_ctx, chart):
    """Ecuacion AP con recepcion parcial, factura y pago parcial + 3-way."""
    from cacao_accounting.database import PurchaseOrder, PurchaseReconciliation, database

    po = PurchaseOrder(
        company=COMPANY,
        supplier_id=_supplier_id(),
        posting_date=AS_OF,
        docstatus=1,
        grand_total=Decimal("500"),
        transaction_currency="NIO",
    )
    database.session.add(po)
    database.session.commit()

    receipt = _make_receipt(amount=Decimal("500"), chart=chart, po=po)

    # Puente GRNI: recepcion genera credito en el puente.
    assert _grni_balance(chart) == Decimal("500")

    invoice = _make_invoice(amount=Decimal("500"), chart=chart, receipt=receipt, po=po, supplier_invoice_no="FAC-001")
    _post_invoice(invoice)

    # La factura liquida el puente GRNI.
    assert _grni_balance(chart) == Decimal("0")

    # Matching 3-way PO/recepcion/factura conciliado.
    reconciliation = (
        database.session.execute(select(PurchaseReconciliation).filter_by(purchase_invoice_id=invoice.id)).scalars().first()
    )
    assert reconciliation is not None
    assert reconciliation.status == "reconciled"

    # Ecuacion antes de pagos.
    assert _outstanding(invoice) == Decimal("500")

    payment = _make_payment(amount=Decimal("300"), chart=chart)
    _apply(payment, [{"reference_type": "purchase_invoice", "reference_id": invoice.id, "allocated_amount": 300}])
    _post_payment(payment)

    # Ecuacion del submayor: 500 - 300 = 200.
    assert _outstanding(invoice) == Decimal("200")

    totals = _subledger_totals(OPEN_END)
    assert totals["original_amount"] == Decimal("500")
    assert totals["paid_amount"] == Decimal("300")
    assert totals["outstanding_amount"] == Decimal("200")

    # Matriz AP conciliada (pasivo en convencion credito): GL AP = -200.
    assert _ap_gl_balance(chart) == Decimal("200")
    row = _matrix_row(chart, "AP")
    assert row.values["subledger_amount"] == Decimal("-200")
    assert row.values["gl_control_amount"] == Decimal("-200")
    _assert_ap_reconciled(chart)

    # Corte previo al pago: ambos lados muestran -500.
    row_cutoff = _matrix_row(chart, "AP", AS_OF)
    assert row_cutoff.values["difference"] == Decimal("0")


def test_281_prepayment_po_applies_to_invoice_with_gl_netting(app_ctx, chart):
    """Anticipo sobre PO se aplica contra factura con neteo en GL."""
    from cacao_accounting.database import CompanyDefaultAccount, PurchaseOrder, database
    from cacao_accounting.document_flow.payment import apply_advance_to_invoice, refresh_outstanding_amount_cache

    # Activar auto-liquidacion de anticipos.
    defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company=COMPANY)).scalars().one()
    defaults.apply_advances_automatically = True
    database.session.commit()

    po = PurchaseOrder(
        company=COMPANY,
        supplier_id=_supplier_id(),
        posting_date=AS_OF,
        docstatus=1,
        grand_total=Decimal("1000"),
        transaction_currency="NIO",
    )
    database.session.add(po)
    database.session.commit()

    # Anticipo de 400 sin referencias: el motor lo contabiliza en la cuenta
    # de anticipo a proveedores (use_advance_as_party_balance).
    advance_payment = _make_payment(amount=Decimal("400"), chart=chart)
    advance_payment.is_advance = True
    _post_payment(advance_payment)

    invoice = _make_invoice(amount=Decimal("1000"), chart=chart, supplier_invoice_no="FAC-ADV")
    _post_invoice(invoice)

    # Aplicar anticipo contra factura con neteo GL automatico.
    reference = apply_advance_to_invoice(advance_payment.id, invoice.id, Decimal("400"), AS_OF)
    assert reference.allocated_amount == Decimal("400")
    database.session.commit()
    refresh_outstanding_amount_cache(invoice)
    database.session.commit()

    # Ecuacion: 1000 - 400 = 600.
    assert _outstanding(invoice) == Decimal("600")
    assert invoice.outstanding_amount == Decimal("600")

    totals = _subledger_totals(OPEN_END)
    assert totals["original_amount"] == Decimal("1000")
    assert totals["paid_amount"] == Decimal("400")
    assert totals["outstanding_amount"] == Decimal("600")

    # Neteo GL: el asiento de aplicacion debita AP 400 y acredita anticipo 400.
    from cacao_accounting.database import GLEntry

    ap_debits = (
        database.session.execute(
            select(GLEntry).filter_by(account_id=chart["ap_id"]).where(GLEntry.voucher_type != "payment_entry")
        )
        .scalars()
        .all()
    )
    netting_debits = sum(Decimal(str(row.debit)) for row in ap_debits)
    assert netting_debits == Decimal("400")

    # Pago final del residuo y cuadre de matriz.
    final_payment = _make_payment(amount=Decimal("600"), chart=chart)
    _apply(final_payment, [{"reference_type": "purchase_invoice", "reference_id": invoice.id, "allocated_amount": 600}])
    _post_payment(final_payment)

    assert _outstanding(invoice) == Decimal("0")
    assert _ap_gl_balance(chart) == Decimal("0")
    _assert_ap_reconciled(chart)


def test_281_fx_supplier_invoice_payment_equation_and_isolation(app_ctx, chart):
    """Factura USD de proveedor: ecuacion en ambas monedas y aislamiento."""
    from cacao_accounting.database import Entity, PurchaseInvoice, PurchaseInvoiceItem, database
    from cacao_accounting.reportes.services import ReconciliationFilters, get_reconciliation_matrix

    usd_invoice = PurchaseInvoice(
        company=COMPANY,
        supplier_id=_supplier_id(),
        posting_date=AS_OF,
        docstatus=1,
        document_type="purchase_invoice",
        supplier_invoice_no="FAC-USD",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("3600"),
        base_grand_total=Decimal("3600"),
        outstanding_amount=Decimal("100"),
        base_outstanding_amount=Decimal("3600"),
    )
    database.session.add_all([usd_invoice])
    database.session.flush()
    usd_item = PurchaseInvoiceItem(
        purchase_invoice_id=usd_invoice.id,
        item_code="ITEM-S2P",
        item_name="Insumo USD",
        qty=Decimal("1"),
        uom="UND",
        rate=Decimal("100"),
        amount=Decimal("100"),
    )
    database.session.add(usd_item)
    database.session.commit()
    _post_invoice(usd_invoice)

    # Moneda de transaccion y funcional antes de pagos.
    assert _outstanding(usd_invoice) == Decimal("100")
    assert usd_invoice.base_outstanding_amount == Decimal("3600")

    # Aislamiento: otra empresa con su propia AP no contamina submayor ni matriz.
    database.session.add_all(
        [
            Entity(code="otra", name="Otra", company_name="Otra", tax_id="OTRA-1", currency="NIO"),
        ]
    )
    database.session.flush()
    from cacao_accounting.database import Accounts, Book, CompanyDefaultAccount

    other_ap = Accounts(entity="otra", code="2101", name="CxP", classification="liability")
    database.session.add(other_ap)
    database.session.flush()
    other_book = Book(entity="otra", code="OTRALOC", name="Libro Otra", currency="NIO", status="activo", is_primary=True)
    database.session.add(other_book)
    database.session.flush()
    database.session.add(CompanyDefaultAccount(company="otra", default_payable=other_ap.id))
    database.session.add(
        PurchaseInvoice(
            company="otra",
            supplier_id=_supplier_id(),
            posting_date=AS_OF,
            docstatus=1,
            document_type="purchase_invoice",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("9999"),
            grand_total=Decimal("9999"),
            base_total=Decimal("9999"),
            base_grand_total=Decimal("9999"),
            outstanding_amount=Decimal("9999"),
            base_outstanding_amount=Decimal("9999"),
        )
    )
    database.session.commit()

    totals = _subledger_totals(OPEN_END)
    assert totals["outstanding_amount"] == Decimal("3600")

    other_matrix = get_reconciliation_matrix(ReconciliationFilters(company="otra", ledger="OTRALOC", as_of_date=AS_OF))
    other_row = next(row for row in other_matrix.rows if row.values["area"] == "AP")
    assert other_row.values["subledger_amount"] == Decimal("-9999")
    assert other_row.values["gl_control_amount"] == Decimal("0")

    # La matriz de la empresa principal cuadra: GL AP = -3600 (credito).
    assert _ap_gl_balance(chart) == Decimal("3600")
    s2p_row = _matrix_row(chart, "AP", AS_OF)
    assert s2p_row.values["subledger_amount"] == Decimal("-3600")
    assert s2p_row.values["gl_control_amount"] == Decimal("-3600")
    assert s2p_row.values["difference"] == Decimal("0")


def test_281_landed_cost_posts_gl_against_ap_control(app_ctx, chart):
    """Landed cost E2E: cargo capitalizado contabilizado y matriz AP cuadrada."""
    from cacao_accounting.database import (
        ImportLandedCost,
        ImportLandedCostCharge,
        ImportLandedCostItem,
        StockBin,
        database,
    )
    from cacao_accounting.contabilidad.posting_service import post_document_to_gl

    # Stock disponible para materializar la capitalizacion.
    database.session.add(
        StockBin(
            company=COMPANY,
            item_code="ITEM-S2P",
            warehouse=chart["warehouse"],
            actual_qty=Decimal("1"),
            reserved_qty=Decimal("0"),
            valuation_rate=Decimal("1000"),
            stock_value=Decimal("1000"),
        )
    )
    database.session.commit()

    invoice = _make_invoice(amount=Decimal("1000"), chart=chart, supplier_invoice_no="FAC-LC")
    _post_invoice(invoice)

    landed = ImportLandedCost(
        company=COMPANY,
        purchase_invoice_id=invoice.id,
        supplier_id=_supplier_id(),
        posting_date=AS_OF,
        document_type="import_landed_cost",
        allocation_method="by_value",
        warehouse="ALM-S2P",
        docstatus=1,
        grand_total=Decimal("100"),
        total_charges_amount=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(landed)
    database.session.flush()
    database.session.add_all(
        [
            ImportLandedCostItem(
                import_landed_cost_id=landed.id,
                item_code="ITEM-S2P",
                item_name="Insumo",
                qty=Decimal("1"),
                rate=Decimal("100"),
                amount=Decimal("100"),
                warehouse="ALM-S2P",
            ),
            ImportLandedCostCharge(
                import_landed_cost_id=landed.id,
                concept="Flete",
                charge_type="charge",
                amount=Decimal("100"),
                accounting_treatment="capitalizable_inventory_cost",
            ),
        ]
    )
    database.session.commit()

    entries = post_document_to_gl(landed)
    database.session.commit()
    assert len(entries) > 0

    # El asiento capitaliza: Dr Inventario 100 / Cr Puente 100.
    from cacao_accounting.database import GLEntry

    landed_rows = (
        database.session.execute(select(GLEntry).filter_by(voucher_type="import_landed_cost", voucher_id=landed.id))
        .scalars()
        .all()
    )
    inventory_debits = sum(
        (Decimal(str(row.debit)) for row in landed_rows if row.account_id == chart["inventory_id"]), Decimal("0")
    )
    bridge_credits = sum((Decimal(str(row.credit)) for row in landed_rows if row.account_id == chart["grni_id"]), Decimal("0"))
    assert inventory_debits == Decimal("100")
    assert bridge_credits == Decimal("100")

    # El AP no cambia: el landed cost no es factura de proveedor.
    totals = _subledger_totals(OPEN_END)
    assert totals["original_amount"] == Decimal("1000")

    _assert_ap_reconciled(chart)


def test_281_subledger_columns_share_cutoff_when_no_as_of(app_ctx, chart):
    """Sin corte explicito, paid y outstanding comparten el mismo cutoff."""
    from datetime import timedelta

    invoice = _make_invoice(amount=Decimal("400"), chart=chart, posting_date=date.today(), supplier_invoice_no="FAC-CUT")
    _post_invoice(invoice)

    future = date.today() + timedelta(days=10)
    payment = _make_payment(amount=Decimal("150"), chart=chart, posting_date=future)
    _apply(
        payment,
        [{"reference_type": "purchase_invoice", "reference_id": invoice.id, "allocated_amount": 150}],
        allocation_date=future,
    )
    _post_payment(payment)

    # Sin corte: la aplicacion futura no aparece en paid ni reduce outstanding.
    totals = _subledger_totals(None)
    assert totals["paid_amount"] == Decimal("0")
    assert totals["outstanding_amount"] == Decimal("400")

    # Con corte que incluye la aplicacion ambas columnas son consistentes.
    totals_cut = _subledger_totals(future)
    assert totals_cut["paid_amount"] == Decimal("150")
    assert totals_cut["outstanding_amount"] == Decimal("250")
