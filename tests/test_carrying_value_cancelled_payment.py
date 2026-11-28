# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1310: el valor en libros excluye pagos cancelados y sus reversas.

Una referencia append-only de un pago cancelado no debe sumar su reversión
activa al valor contable de la factura.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.accounting_engine.document_builders import _document_carrying_value_in_ledger
from cacao_accounting.database import (
    Accounts,
    Book,
    GLEntry,
    Party,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    database,
)

FECHA = date(2026, 5, 15)


def _seed_invoice() -> tuple[str, str, str, str]:
    """Crea factura AR de 100 con su GL y devuelve ids del escenario."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    receivable_id = str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="1105")).scalar_one())
    book = database.session.execute(select(Book).where(Book.entity == "cacao", Book.is_primary.is_(True))).scalar_one()
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        document_type="sales_invoice",
        document_no="FAC-1310",
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
    database.session.add(
        GLEntry(
            company="cacao",
            ledger_id=book.id,
            account_id=receivable_id,
            debit=Decimal("100"),
            credit=Decimal("0"),
            is_cancelled=False,
            is_reversal=False,
            party_type="customer",
            party_id=customer_id,
            posting_date=FECHA,
            voucher_type="sales_invoice",
            voucher_id=str(invoice.id),
            document_no="FAC-1310",
        )
    )
    database.session.flush()
    return str(invoice.id), customer_id, receivable_id, str(book.id)


def _payment(
    invoice_id: str,
    customer_id: str,
    receivable_id: str,
    book_id: str,
    *,
    cancelled: bool,
) -> str:
    """Crea un pago de 50 aplicado a la factura, activo o cancelado."""
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id=customer_id,
        posting_date=FECHA,
        received_amount=Decimal("50"),
        paid_amount=Decimal("50"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=2 if cancelled else 1,
        document_no="PAY-1310-C" if cancelled else "PAY-1310-A",
    )
    database.session.add(payment)
    database.session.flush()
    database.session.add(
        PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice_id,
            allocated_amount=Decimal("50"),
            payment_amount=Decimal("50"),
            company="cacao",
            party_type="customer",
            party_id=customer_id,
        )
    )
    database.session.add(
        GLEntry(
            company="cacao",
            ledger_id=book_id,
            account_id=receivable_id,
            debit=Decimal("0"),
            credit=Decimal("50"),
            is_cancelled=cancelled,
            is_reversal=False,
            party_type="customer",
            party_id=customer_id,
            posting_date=FECHA,
            voucher_type="payment_entry",
            voucher_id=str(payment.id),
            document_no=payment.document_no,
        )
    )
    if cancelled:
        database.session.add(
            GLEntry(
                company="cacao",
                ledger_id=book_id,
                account_id=receivable_id,
                debit=Decimal("50"),
                credit=Decimal("0"),
                is_cancelled=False,
                is_reversal=True,
                party_type="customer",
                party_id=customer_id,
                posting_date=FECHA,
                voucher_type="payment_entry",
                voucher_id=str(payment.id),
                document_no=payment.document_no,
            )
        )
    database.session.commit()
    return str(payment.id)


def _carrying(invoice_id: str, receivable_id: str, book_id: str) -> Decimal | None:
    """Ejecuta el helper de valor en libros para la factura."""
    return _document_carrying_value_in_ledger(
        company="cacao",
        document_type="sales_invoice",
        document_id=invoice_id,
        exclude_payment_id="",
        party_account_id=receivable_id,
        ledger_id=book_id,
        receivable=True,
        as_of_date=FECHA,
    )


def test_pago_activo_reduce_el_valor_en_libros(entorno_contable_aislado):
    """Un pago vigente de 50 deja el valor contable en 50."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, customer_id, receivable_id, book_id = _seed_invoice()
        _payment(invoice_id, customer_id, receivable_id, book_id, cancelled=False)
        database.session.commit()

        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("50.0000")


def test_pago_cancelado_no_suma_su_reversa(entorno_contable_aislado):
    """Cancelar el pago restaura 100 y no duplica la reversión activa."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, customer_id, receivable_id, book_id = _seed_invoice()
        _payment(invoice_id, customer_id, receivable_id, book_id, cancelled=True)
        database.session.commit()

        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("100.0000")
