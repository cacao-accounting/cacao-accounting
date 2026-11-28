# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1161: la revaluación incluye el GL de las notas relacionadas.

Una factura reducida por una nota de crédito debe comparar el mismo conjunto
de transacciones en su saldo abierto y en su valor contable anterior.
"""

# pylint: disable=duplicate-code,too-many-arguments,too-many-positional-arguments

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.accounting_engine.document_builders import _document_carrying_value_in_ledger
from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyDefaultAccount,
    DocumentRelation,
    ExchangeRate,
    GLEntry,
    Party,
    SalesInvoice,
    database,
)

FECHA = date(2026, 5, 15)
CIERRE = date(2026, 5, 31)


def _customer_id() -> str:
    """Devuelve el cliente del escenario contable."""
    return str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())


def _receivable_id() -> str:
    """Cuenta de cartera del escenario."""
    return str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="1105")).scalar_one())


def _invoice(party_id: str, document_type: str, number: str, total: Decimal, is_return: bool = False) -> SalesInvoice:
    """Crea una factura o nota de venta publicada en USD."""
    invoice = SalesInvoice(
        company="cacao",
        customer_id=party_id,
        document_type=document_type,
        document_no=number,
        posting_date=FECHA,
        docstatus=1,
        is_return=is_return,
        total=total,
        grand_total=total,
        base_total=total * Decimal("36"),
        base_grand_total=total * Decimal("36"),
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _gl(book: Book, party_id: str, account_id: str, document: SalesInvoice, debit: Decimal, credit: Decimal) -> None:
    """Registra una línea GL del documento en el libro indicado."""
    database.session.add(
        GLEntry(
            company="cacao",
            ledger_id=book.id,
            account_id=account_id,
            debit=debit,
            credit=credit,
            debit_in_account_currency=debit / Decimal("36") if debit > 0 else Decimal("0"),
            credit_in_account_currency=credit / Decimal("36") if credit > 0 else Decimal("0"),
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36"),
            party_type="customer",
            party_id=party_id,
            posting_date=FECHA,
            voucher_type=str(document.document_type),
            voucher_id=str(document.id),
            document_no=document.document_no,
        )
    )


def _scenario() -> tuple[str, str, list[str]]:
    """Crea factura de 100, nota de crédito de 25 y su evidencia GL."""
    party_id = _customer_id()
    receivable_id = _receivable_id()
    books = database.session.execute(select(Book).where(Book.entity == "cacao", Book.status == "activo")).scalars().all()
    invoice = _invoice(party_id, "sales_invoice", "FAC-1161", Decimal("100"))
    note = _invoice(party_id, "sales_credit_note", "NC-1161", Decimal("25"), is_return=True)
    for book in books:
        _gl(book, party_id, receivable_id, invoice, Decimal("3600"), Decimal("0"))
        _gl(book, party_id, receivable_id, note, Decimal("0"), Decimal("900"))
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=str(invoice.id),
            target_type="sales_credit_note",
            target_id=str(note.id),
            company="cacao",
            amount=Decimal("25"),
            qty=Decimal("25"),
            relation_type="invoice_reversal",
            status="active",
        )
    )
    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=CIERRE))
    defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
    defaults.unrealized_exchange_gain_account_id = str(
        database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="4101")).scalar_one()
    )
    defaults.unrealized_exchange_loss_account_id = str(
        database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="5101")).scalar_one()
    )
    database.session.commit()
    return str(invoice.id), receivable_id, [str(book.id) for book in books]


def test_valor_contable_incluye_el_gl_de_la_nota(entorno_contable_aislado):
    """La factura de 3,600 menos la nota de 900 expone 2,700 en libros."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, receivable_id, ledger_ids = _scenario()
        for ledger_id in ledger_ids:
            carrying = _document_carrying_value_in_ledger(
                company="cacao",
                document_type="sales_invoice",
                document_id=invoice_id,
                exclude_payment_id="",
                party_account_id=receivable_id,
                ledger_id=ledger_id,
                receivable=True,
                as_of_date=CIERRE,
            )
            assert carrying == Decimal("2700.0000")


def test_revaluacion_sin_cambio_de_tasa_no_ajusta_la_factura_con_nota(entorno_contable_aislado):
    """Con la tasa de cierre igual a la histórica no hay diferencia ficticia."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _scenario()

        run = ExchangeRevaluationService().run(company="cacao", period_id="P2026-05")

        assert run.affected_documents_count == 0
        items = database.session.execute(select(GLEntry).where(GLEntry.voucher_type == "exchange_revaluation")).scalars().all()
        assert items == []
