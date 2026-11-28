# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1304: una referencia de pago sin DocumentRelation no altera el saldo.

DocumentRelation es el vínculo canónico del subledger; una fila huérfana
no representa una aplicación efectiva.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.arap_ledger_service import ARAPLedgerEntry
from cacao_accounting.contabilidad.posting_service import submit_document
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    CompanyDefaultAccount,
    DocumentRelation,
    GLEntry,
    Item,
    Party,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    SalesInvoiceItem,
    UOM,
    User,
    database,
)
from cacao_accounting.document_flow.payment import compute_outstanding_amount, compute_payment_unallocated_amount
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 15)


def _invoice() -> str:
    """Crea una factura de venta publicada por 100."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        document_type="sales_invoice",
        document_no="FAC-1304",
        posting_date=FECHA,
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    return str(invoice.id)


def _reference(invoice_id: str) -> PaymentReference:
    """Crea pago aprobado y su referencia, aún sin relación documental."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id=customer_id,
        posting_date=FECHA,
        received_amount=Decimal("40"),
        paid_amount=Decimal("40"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        document_no="PAY-1304",
    )
    database.session.add(payment)
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice_id,
        reference_document_no="FAC-1304",
        reference_date=FECHA,
        allocated_amount=Decimal("40"),
        payment_amount=Decimal("40"),
        party_type="customer",
        party_id=customer_id,
        company="cacao",
        currency="NIO",
    )
    database.session.add(reference)
    database.session.flush()
    return reference


def test_referencia_huerfana_no_reduce_el_saldo(entorno_contable_aislado):
    """Sin relación activa el saldo permanece en 100."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id = _invoice()
        reference = _reference(invoice_id)
        database.session.commit()
        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, reference.payment_id)

        assert compute_outstanding_amount(invoice, as_of_date=FECHA) == Decimal("100")
        assert compute_payment_unallocated_amount(payment) == Decimal("40")


def test_relacion_activa_es_la_unica_que_descuenta(entorno_contable_aislado):
    """Al crear la relación canónica el saldo baja a 60."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id = _invoice()
        reference = _reference(invoice_id)
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice_id,
                target_type="payment_entry",
                target_id=str(reference.payment_id),
                target_item_id=str(reference.id),
                company="cacao",
                qty=Decimal("40"),
                amount=Decimal("40"),
                relation_type="payment_allocation",
                status="active",
            )
        )
        database.session.commit()
        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, reference.payment_id)

        assert compute_outstanding_amount(invoice, as_of_date=FECHA) == Decimal("60")
        assert compute_payment_unallocated_amount(payment) == Decimal("0")


def test_relacion_con_otro_pago_destino_no_descuenta(entorno_contable_aislado):
    """El ítem referenciado no basta si el endpoint documental es otro pago."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id = _invoice()
        reference = _reference(invoice_id)
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice_id,
                target_type="payment_entry",
                target_id="OTRO-PAGO",
                target_item_id=str(reference.id),
                company="cacao",
                qty=Decimal("40"),
                amount=Decimal("40"),
                relation_type="payment_allocation",
                status="active",
            )
        )
        database.session.commit()
        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, reference.payment_id)

        assert compute_outstanding_amount(invoice, as_of_date=FECHA) == Decimal("100")
        assert compute_payment_unallocated_amount(payment) == Decimal("40")


def test_posting_con_referencia_huerfana_no_liquida_factura(entorno_contable_aislado):
    """El builder y el subledger ignoran una aplicación sin vínculo canónico."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer = database.session.execute(select(Party).filter_by(code="CLI001")).scalar_one()
        actor = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(select(UOM).filter_by(code="UND")).scalar_one()
        income = database.session.execute(select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        receivable = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1105")).scalar_one()
        bank_gl = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1102")).scalar_one()
        advance = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1201")).scalar_one_or_none()
        if advance is None:
            advance = Accounts(
                entity="cacao",
                code="1201",
                name="Anticipos de clientes",
                classification="asset",
                account_type="customer_advance",
                group=False,
                active=True,
                enabled=True,
            )
            database.session.add(advance)
            database.session.flush()
        defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.customer_advance_account_id = advance.id
        bank = Bank(name=f"Banco huérfano {FECHA}")
        database.session.add(bank)
        database.session.flush()
        bank_account = BankAccount(
            company="cacao",
            bank_id=bank.id,
            account_name="Cuenta huérfana",
            account_no="ORPHAN-1304",
            currency="NIO",
            gl_account_id=bank_gl.id,
            is_active=True,
        )
        database.session.add(bank_account)
        invoice = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            document_date=FECHA,
            document_no="FAC-1304-POST",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            base_total=Decimal("100"),
            grand_total=Decimal("100"),
            base_grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
            base_outstanding_amount=Decimal("100"),
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
                income_account_id=income.id,
            )
        )
        database.session.flush()
        with audit_actor(actor.id, actor.name), approved_execution(invoice, actor.id):
            submit_document(invoice)
        database.session.commit()

        payment = PaymentEntry(
            company="cacao",
            payment_type="receive",
            party_type="customer",
            party_id=customer.id,
            bank_account_id=bank_account.id,
            posting_date=FECHA,
            received_amount=Decimal("40"),
            paid_amount=Decimal("40"),
            currency="NIO",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
            document_no="PAY-1304-ORPHAN",
        )
        database.session.add(payment)
        database.session.flush()
        database.session.add(
            PaymentReference(
                payment_id=payment.id,
                reference_type="sales_invoice",
                reference_id=invoice.id,
                allocated_amount=Decimal("40"),
                payment_amount=Decimal("40"),
                company="cacao",
                party_type="customer",
                party_id=customer.id,
            )
        )
        database.session.commit()
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            submit_document(payment)
        database.session.commit()
        database.session.expire_all()

        invoice = database.session.get(SalesInvoice, invoice.id)
        payment = database.session.get(PaymentEntry, payment.id)
        assert invoice is not None and payment is not None
        assert payment.docstatus == 1
        assert invoice.outstanding_amount == Decimal("100")
        assert compute_outstanding_amount(invoice, as_of_date=FECHA) == Decimal("100")
        assert ARAPLedgerEntry.document_balance("sales_invoice", invoice.id) == Decimal("100")
        assert ARAPLedgerEntry.document_balance("payment_entry", payment.id) == Decimal("-40")
        payment_gl = (
            database.session.execute(select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
            .scalars()
            .all()
        )
        assert payment_gl
        assert receivable.id not in {entry.account_id for entry in payment_gl}
        assert advance.id in {entry.account_id for entry in payment_gl}
        assert bank_gl.id in {entry.account_id for entry in payment_gl}
        assert (
            database.session.execute(select(DocumentRelation.id).filter_by(target_id=payment.id)).scalar_one_or_none() is None
        )
