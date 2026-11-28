# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1140: al contabilizar un pago se revalida el saldo del documento destino.

Dos borradores pueden reservar el mismo saldo. Al postear el segundo, la
factura no debe quedar negativa: la aplicación se limita a su saldo vigente
y el excedente permanece como anticipo del mismo tercero.
"""

# pylint: disable=duplicate-code

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.arap_gl_reconciliation import reconcile_arap_to_gl
from cacao_accounting.contabilidad.arap_ledger_service import post_payment_ar_ap
from cacao_accounting.contabilidad.posting_service import post_payment_entry, submit_document
from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    Accounts,
    Bank,
    BankAccount,
    Book,
    CompanyDefaultAccount,
    GLEntry,
    Party,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    SalesInvoice,
    User,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 15)


def _advance_accounts() -> tuple[str, str]:
    """Crea las cuentas de anticipo de cliente y proveedor del escenario."""
    accounts = {}
    for code, name, account_type in (
        ("1201", "Anticipos de clientes", "customer_advance"),
        ("2201", "Anticipos a proveedores", "supplier_advance"),
    ):
        existing = database.session.execute(select(Accounts.id).filter_by(entity="cacao", code=code)).scalar_one_or_none()
        if existing is None:
            account = Accounts(
                entity="cacao",
                code=code,
                name=name,
                classification="asset" if account_type == "customer_advance" else "liability",
                account_type=account_type,
                group=False,
                active=True,
                enabled=True,
            )
            database.session.add(account)
            database.session.flush()
            existing = account.id
        accounts[account_type] = str(existing)
    defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    defaults.customer_advance_account_id = accounts["customer_advance"]
    defaults.supplier_advance_account_id = accounts["supplier_advance"]
    return accounts["customer_advance"], accounts["supplier_advance"]


def _bank_account() -> str:
    """Crea una cuenta bancaria con su cuenta GL."""
    bank = Bank(name="Banco Revalidación", is_active=True)
    database.session.add(bank)
    database.session.flush()
    gl_account_id = database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="1102")).scalar_one()
    account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta Revalidación",
        account_no="REV-1140",
        currency="NIO",
        gl_account_id=gl_account_id,
    )
    database.session.add(account)
    database.session.flush()
    return str(account.id)


def _invoice(model, party_field: str, party_id: str, number: str, total: Decimal):
    """Crea una factura publicada con apertura canónica en AR/AP."""
    invoice = model(
        company="cacao",
        **{party_field: party_id},
        document_no=number,
        document_type="sales_invoice" if model is SalesInvoice else "purchase_invoice",
        posting_date=FECHA,
        docstatus=1,
        status="open",
        total=total,
        grand_total=total,
        base_total=total,
        base_grand_total=total,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR" if model is SalesInvoice else "AP",
            party_type="customer" if model is SalesInvoice else "supplier",
            party_id=party_id,
            document_type=invoice.document_type,
            document_id=str(invoice.id),
            document_no=number,
            posting_date=FECHA,
            event_type="opening",
            currency="NIO",
            document_amount=total,
        )
    )
    database.session.flush()
    return invoice


def _payment(bank_account_id: str, invoice, amount: Decimal, number: str) -> str:
    """Crea un pago en borrador que aplica el monto indicado a la factura."""
    is_sales = isinstance(invoice, SalesInvoice)
    party_type = "customer" if is_sales else "supplier"
    party_id = str(invoice.customer_id if is_sales else invoice.supplier_id)
    document = PaymentEntry(
        company="cacao",
        payment_type="receive" if is_sales else "pay",
        party_type=party_type,
        party_id=party_id,
        bank_account_id=bank_account_id,
        posting_date=date(2026, 5, 20),
        paid_amount=amount,
        received_amount=amount,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=0,
        document_no=number,
    )
    database.session.add(document)
    database.session.flush()
    database.session.add(
        PaymentReference(
            payment_id=document.id,
            reference_type=str(invoice.document_type),
            reference_id=str(invoice.id),
            reference_document_no=invoice.document_no,
            reference_date=FECHA,
            allocated_amount=amount,
            payment_amount=amount,
            total_amount=amount,
            outstanding_amount=amount,
            party_type=party_type,
            party_id=party_id,
        )
    )
    database.session.flush()
    return str(document.id)


def _post(payment_id: str) -> None:
    """Contabiliza GL y AR/AP del pago con el actor de auditoría del escenario."""
    payment = database.session.get(PaymentEntry, payment_id)
    payment.docstatus = 1
    admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
    with audit_actor(admin_id, "Admin"), approved_execution(payment, admin_id):
        entries = post_payment_entry(payment)
        post_payment_ar_ap(payment, entries)
    database.session.commit()


def _amounts_by_book(payment_id: str, account_id: str, column) -> list[Decimal]:
    """Suma débitos o créditos GL del pago contra una cuenta, por libro."""
    rows = database.session.execute(
        select(GLEntry.ledger_id, func.coalesce(func.sum(column), Decimal("0")))
        .where(GLEntry.voucher_id == payment_id, GLEntry.account_id == account_id)
        .group_by(GLEntry.ledger_id)
    ).all()
    return [Decimal(str(value)) for _, value in rows]


def test_segundo_pago_restringe_la_aplicacion_y_deja_anticipo(entorno_contable_aislado):
    """Dos borradores de 100: el segundo no deja la factura en negativo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _, supplier_advance = _advance_accounts()
        bank_account_id = _bank_account()
        supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
        invoice = _invoice(PurchaseInvoice, "supplier_id", supplier_id, "PI-1140", Decimal("100"))
        first = _payment(bank_account_id, invoice, Decimal("100"), "PAY-1140-1")
        second = _payment(bank_account_id, invoice, Decimal("100"), "PAY-1140-2")

        _post(first)
        _post(second)

        assert ARAPLedgerEntry.document_balance("purchase_invoice", str(invoice.id)) == Decimal("0")
        assert ARAPLedgerEntry.document_balance("payment_entry", first) == Decimal("0")
        assert ARAPLedgerEntry.document_balance("payment_entry", second) == Decimal("-100.0000")
        advance_debits = _amounts_by_book(second, supplier_advance, GLEntry.debit)
        assert advance_debits and all(value == Decimal("100.0000") for value in advance_debits)
        reference = database.session.execute(select(PaymentReference).filter_by(payment_id=second)).scalar_one()
        assert reference.allocated_amount == Decimal("0.0000")


def test_cobro_duplicado_de_cliente_deja_anticipo(entorno_contable_aislado):
    """El mismo criterio aplica a cobros de cliente (dirección AR)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer_advance, _ = _advance_accounts()
        bank_account_id = _bank_account()
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
        invoice = _invoice(SalesInvoice, "customer_id", customer_id, "SI-1140", Decimal("100"))
        first = _payment(bank_account_id, invoice, Decimal("100"), "REC-1140-1")
        second = _payment(bank_account_id, invoice, Decimal("100"), "REC-1140-2")

        _post(first)
        _post(second)

        assert ARAPLedgerEntry.document_balance("sales_invoice", str(invoice.id)) == Decimal("0")
        assert ARAPLedgerEntry.document_balance("payment_entry", second) == Decimal("-100.0000")
        advance_credits = _amounts_by_book(second, customer_advance, GLEntry.credit)
        assert advance_credits and all(value == Decimal("100.0000") for value in advance_credits)


def test_pago_con_excedente_desde_el_borrador_separa_anticipo(entorno_contable_aislado):
    """Un único pago de 150 contra 100 aplica 100 y deja 50 como anticipo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _, supplier_advance = _advance_accounts()
        bank_account_id = _bank_account()
        supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
        invoice = _invoice(PurchaseInvoice, "supplier_id", supplier_id, "PI-1140-EXC", Decimal("100"))
        payment = _payment(bank_account_id, invoice, Decimal("150"), "PAY-1140-EXC")

        _post(payment)

        assert ARAPLedgerEntry.document_balance("purchase_invoice", str(invoice.id)) == Decimal("0")
        assert ARAPLedgerEntry.document_balance("payment_entry", payment) == Decimal("-50.0000")
        advance_debits = _amounts_by_book(payment, supplier_advance, GLEntry.debit)
        assert advance_debits and all(value == Decimal("50.0000") for value in advance_debits)


def _seed_invoice_gl_and_books(invoice: PurchaseInvoice, supplier_id: str) -> list[str]:
    """Siembra GL y evidencia por libro de la factura para conciliar con AR/AP."""
    payable_id = str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="2101")).scalar_one())
    expense_id = str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="5101")).scalar_one())
    opening = database.session.execute(
        select(ARAPLedgerEntry).where(
            ARAPLedgerEntry.document_type == "purchase_invoice",
            ARAPLedgerEntry.document_id == str(invoice.id),
            ARAPLedgerEntry.event_type == "opening",
        )
    ).scalar_one()
    books = database.session.execute(select(Book).where(Book.entity == "cacao", Book.status == "activo")).scalars().all()
    for book in books:
        database.session.add(
            ARAPLedgerBookEntry(
                ledger_entry_id=opening.id,
                ledger_id=book.id,
                posting_date=FECHA,
                document_currency="NIO",
                book_currency=book.currency or "NIO",
                document_amount=Decimal("100"),
                book_amount=Decimal("100"),
                exchange_rate=Decimal("1"),
                debit=Decimal("100"),
                credit=Decimal("0"),
                account_id=payable_id,
                account_code="2101",
            )
        )
        database.session.add_all(
            [
                GLEntry(
                    company="cacao",
                    ledger_id=book.id,
                    account_id=payable_id,
                    account_code="2101",
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    debit_in_account_currency=Decimal("0"),
                    credit_in_account_currency=Decimal("100"),
                    account_currency="NIO",
                    company_currency="NIO",
                    exchange_rate=Decimal("1"),
                    party_type="supplier",
                    party_id=supplier_id,
                    posting_date=FECHA,
                    voucher_type="purchase_invoice",
                    voucher_id=str(invoice.id),
                    document_no=invoice.document_no,
                ),
                GLEntry(
                    company="cacao",
                    ledger_id=book.id,
                    account_id=expense_id,
                    account_code="5101",
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    debit_in_account_currency=Decimal("100"),
                    credit_in_account_currency=Decimal("0"),
                    account_currency="NIO",
                    company_currency="NIO",
                    exchange_rate=Decimal("1"),
                    posting_date=FECHA,
                    voucher_type="purchase_invoice",
                    voucher_id=str(invoice.id),
                    document_no=invoice.document_no,
                ),
            ]
        )
    database.session.flush()
    return [str(book.id) for book in books]


def test_conciliacion_arap_gl_tras_restringir_el_segundo_pago(entorno_contable_aislado):
    """El posting real mantiene conciliados AR/AP y GL tras el exceso."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _advance_accounts()
        bank_account_id = _bank_account()
        supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
        invoice = _invoice(PurchaseInvoice, "supplier_id", supplier_id, "PI-1140-GL", Decimal("100"))
        ledger_ids = _seed_invoice_gl_and_books(invoice, supplier_id)
        first = _payment(bank_account_id, invoice, Decimal("100"), "PAY-1140-GL-1")
        second = _payment(bank_account_id, invoice, Decimal("100"), "PAY-1140-GL-2")
        database.session.commit()
        admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())

        for payment_id in (first, second):
            payment = database.session.get(PaymentEntry, payment_id)
            with audit_actor(admin_id, "Admin"), approved_execution(payment, admin_id):
                submit_document(payment)
            database.session.commit()

        assert ARAPLedgerEntry.document_balance("purchase_invoice", str(invoice.id)) == Decimal("0")
        assert ARAPLedgerEntry.document_balance("payment_entry", second) == Decimal("-100.0000")
        reconcile_arap_to_gl(
            company="cacao",
            as_of_date=date(2026, 5, 20),
            party_type="supplier",
            party_id=supplier_id,
            ledger_ids=ledger_ids,
        )
