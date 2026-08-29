"""Ledger documental de cuentas por cobrar y pagar.

El módulo mantiene el saldo de cada documento en su moneda documental y una
valoración independiente por libro.  Los movimientos se crean únicamente al
contabilizar o anular una operación; los cachés de los documentos siguen siendo
una optimización para consultas del día actual.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select

from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    Book,
    Entity,
    ExchangeRate,
    GLEntry,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    SalesInvoice,
    database,
)


def _decimal(value: Any) -> Decimal:
    """Normaliza valores ORM y evita cálculos con ``None``."""
    return Decimal(str(value or "0"))


def _document_type(document: Any) -> str:
    """Obtiene el tipo estable usado por el registro documental."""
    return str(getattr(document, "document_type", None) or getattr(document, "__tablename__", ""))


def _ledger_type(document: Any) -> str:
    """Resuelve AR para ventas y AP para compras."""
    if isinstance(document, PaymentEntry):
        return (
            "AR"
            if getattr(document, "payment_type", None) == "receive" or getattr(document, "party_type", None) == "customer"
            else "AP"
        )
    return "AR" if isinstance(document, SalesInvoice) or _document_type(document).startswith("sales_") else "AP"


def _party_id(document: Any) -> str | None:
    """Obtiene el tercero dueño del saldo documental."""
    return (
        getattr(document, "customer_id", None) or getattr(document, "supplier_id", None) or getattr(document, "party_id", None)
    )


def _document_amount(document: Any) -> Decimal:
    """Obtiene el importe nominal de apertura de un documento."""
    return _decimal(
        getattr(document, "grand_total", None)
        or getattr(document, "paid_amount", None)
        or getattr(document, "received_amount", None)
    )


def _currency(document: Any) -> str | None:
    """Obtiene la moneda documental explícita."""
    return getattr(document, "transaction_currency", None) or getattr(document, "currency", None)


def _party_gl_entries(entries: Iterable[GLEntry], party_id: str | None) -> list[GLEntry]:
    """Filtra las líneas GL que representan el saldo del tercero."""
    if not party_id:
        return []
    return [entry for entry in entries if str(getattr(entry, "party_id", None) or "") == str(party_id)]


def _book_value_from_gl(entry: GLEntry, ledger_type: str) -> Decimal:
    """Convierte una línea GL al signo normal del subledger."""
    net = _decimal(entry.debit) - _decimal(entry.credit)
    return net if ledger_type == "AR" else -net


def _book_entries_for(ledger_id: str | None, entries: Iterable[GLEntry]) -> list[GLEntry]:
    """Selecciona las líneas GL de un libro."""
    return [entry for entry in entries if str(getattr(entry, "ledger_id", None) or "") == str(ledger_id or "")]


def _add_book_entry(
    movement: ARAPLedgerEntry,
    *,
    book: Book,
    amount: Decimal,
    gl_entry: GLEntry | None,
    is_reversal: bool = False,
    reversal_of: ARAPLedgerBookEntry | None = None,
) -> None:
    """Agrega una valoración por libro con débito/crédito normalizado."""
    if not amount:
        return
    document_amount = _decimal(movement.document_amount)
    exchange_rate = abs(amount / document_amount) if document_amount else Decimal("1")
    if movement.ledger_type == "AR":
        debit = amount if amount > 0 else Decimal("0")
        credit = -amount if amount < 0 else Decimal("0")
    else:
        debit = -amount if amount < 0 else Decimal("0")
        credit = amount if amount > 0 else Decimal("0")
    row = ARAPLedgerBookEntry(
        ledger_entry_id=movement.id,
        ledger_id=book.id,
        posting_date=movement.posting_date,
        document_currency=movement.currency,
        book_currency=book.currency,
        document_amount=document_amount,
        book_amount=amount,
        exchange_rate=exchange_rate or Decimal("1"),
        debit=debit,
        credit=credit,
        gl_entry_id=getattr(gl_entry, "id", None),
        is_reversal=is_reversal,
        reversal_of=getattr(reversal_of, "id", None),
    )
    database.session.add(row)


def _new_movement(
    document: Any,
    *,
    amount: Decimal,
    event_type: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    is_reversal: bool = False,
    reversal_of: str | None = None,
) -> ARAPLedgerEntry:
    """Construye un movimiento documental."""
    movement = ARAPLedgerEntry(
        company=str(document.company),
        ledger_type=_ledger_type(document),
        party_type=str(
            getattr(document, "party_type", None) or ("customer" if _ledger_type(document) == "AR" else "supplier")
        ),
        party_id=str(_party_id(document) or ""),
        document_type=_document_type(document),
        document_id=str(document.id),
        document_no=getattr(document, "document_no", None),
        posting_date=getattr(document, "posting_date", None) or date.today(),
        document_date=getattr(document, "posting_date", None),
        event_type=event_type,
        currency=str(_currency(document) or ""),
        document_amount=amount,
        reference_type=reference_type,
        reference_id=reference_id,
        voucher_type=_document_type(document),
        voucher_id=str(document.id),
        is_reversal=is_reversal,
        reversal_of=reversal_of,
    )
    database.session.add(movement)
    database.session.flush()
    return movement


def _active_books(company: str) -> list[Book]:
    """Obtiene todos los libros activos de una compañía."""
    return list(database.session.execute(select(Book).where(Book.entity == company, Book.status == "activo")).scalars().all())


def _book_exchange_rate(company: str, source: str, target: str, posting_date: date, fallback: Decimal) -> Decimal:
    """Obtiene una tasa snapshot entre la moneda documental y la del libro."""
    if source == target:
        return Decimal("1")
    row = database.session.execute(
        select(ExchangeRate)
        .where(ExchangeRate.origin == source, ExchangeRate.destination == target, ExchangeRate.date <= posting_date)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row and _decimal(row.rate) > 0:
        return _decimal(row.rate)
    inverse = database.session.execute(
        select(ExchangeRate)
        .where(ExchangeRate.origin == target, ExchangeRate.destination == source, ExchangeRate.date <= posting_date)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if inverse and _decimal(inverse.rate) > 0:
        return Decimal("1") / _decimal(inverse.rate)
    company_currency = database.session.execute(select(Entity.currency).where(Entity.code == company)).scalar_one_or_none()
    if target == company_currency and fallback > 0:
        return fallback
    if source == company_currency and fallback > 0:
        return Decimal("1") / fallback
    return Decimal("1")


def post_document_ar_ap(document: Any, entries: Iterable[GLEntry]) -> list[ARAPLedgerEntry]:
    """Registra la apertura documental y la valoración GL de una factura."""
    if not isinstance(document, (SalesInvoice, PurchaseInvoice)):
        return []
    if _party_id(document) is None or not _currency(document):
        return []
    # Devoluciones/credit notes reduce the documentary balance and therefore
    # enter the subledger with the opposite sign of a normal invoice.
    sign = Decimal("-1") if getattr(document, "is_return", False) else Decimal("1")
    movement = _new_movement(document, amount=sign * _document_amount(document), event_type="opening")
    party_entries = _party_gl_entries(entries, _party_id(document))
    books = _active_books(str(document.company))
    for book in books:
        candidates = _book_entries_for(str(book.id), party_entries)
        if not candidates:
            continue
        _add_book_entry(
            movement,
            book=book,
            amount=sum((_book_value_from_gl(row, movement.ledger_type) for row in candidates), Decimal("0")),
            gl_entry=candidates[0],
        )
    return [movement]


def post_payment_ar_ap(document: PaymentEntry, entries: Iterable[GLEntry]) -> list[ARAPLedgerEntry]:
    """Registra el saldo propio del pago y sus aplicaciones documentales."""
    references = list(
        database.session.execute(select(PaymentReference).where(PaymentReference.payment_id == document.id)).scalars().all()
    )
    if not references and not _party_id(document):
        return []
    total = _decimal(document.paid_amount or document.received_amount)
    movements: list[ARAPLedgerEntry] = []
    party_entries = _party_gl_entries(entries, _party_id(document))
    payment_currency = str(_currency(document) or "")
    payment_date = getattr(document, "posting_date", None) or date.today()
    if total:
        payment_opening = _new_movement(document, amount=-total, event_type="opening")
        movements.append(payment_opening)
        for book in _active_books(str(document.company)):
            rate = _book_exchange_rate(
                str(document.company),
                payment_currency,
                str(book.currency or payment_currency),
                payment_date,
                _decimal(document.exchange_rate),
            )
            candidates = _book_entries_for(str(book.id), party_entries)
            # Unallocated payments post directly against the party account;
            # retain that GL trace. When references exist, the party line is
            # linked to the allocation movement below instead.
            opening_gl = candidates[0] if not references and candidates else None
            _add_book_entry(
                payment_opening,
                book=book,
                amount=-(total * rate).quantize(Decimal("0.0001")),
                gl_entry=opening_gl,
            )
    for reference in references:
        if not reference.allocated_amount or not reference.reference_id:
            continue
        target = database.session.get(
            SalesInvoice if str(reference.reference_type).startswith("sales_") else PurchaseInvoice, reference.reference_id
        )
        if target is None:
            continue
        amount = _decimal(reference.allocated_amount)
        target_movement = _new_movement(
            target,
            amount=-amount,
            event_type="allocation",
            reference_type="payment_entry",
            reference_id=str(document.id),
        )
        movements.append(target_movement)
        for book in _active_books(str(document.company)):
            target_currency = str(_currency(target) or reference.currency or payment_currency)
            target_rate = _book_exchange_rate(
                str(document.company),
                target_currency,
                str(book.currency or target_currency),
                payment_date,
                _decimal(target.exchange_rate),
            )
            book_amount = -(amount * target_rate).quantize(Decimal("0.0001"))
            candidates = _book_entries_for(str(book.id), party_entries)
            _add_book_entry(target_movement, book=book, amount=book_amount, gl_entry=candidates[0] if candidates else None)
        applied = _new_movement(
            document,
            amount=_decimal(reference.payment_amount or reference.allocated_amount),
            event_type="allocation",
            reference_type=str(reference.reference_type),
            reference_id=str(reference.reference_id),
        )
        movements.append(applied)
        for book in _active_books(str(document.company)):
            rate = _book_exchange_rate(
                str(document.company),
                payment_currency,
                str(book.currency or payment_currency),
                payment_date,
                _decimal(document.exchange_rate),
            )
            _add_book_entry(
                applied,
                book=book,
                amount=_decimal(reference.payment_amount or reference.allocated_amount) * rate,
                gl_entry=None,
            )
    return movements


def cancel_document_ar_ap(document: Any, *, cancellation_date: date | None = None) -> list[ARAPLedgerEntry]:
    """Agrega contrapartidas documentales para una anulación del mismo período."""
    source_types = {_document_type(document)}
    source_ids = {str(document.id)}
    if isinstance(document, PaymentEntry):
        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.is_reversal.is_(False),
                    (
                        (
                            (ARAPLedgerEntry.document_type == "payment_entry")
                            & (ARAPLedgerEntry.document_id == str(document.id))
                        )
                        | (
                            (ARAPLedgerEntry.reference_type == "payment_entry")
                            & (ARAPLedgerEntry.reference_id == str(document.id))
                        )
                    ),
                )
            )
            .scalars()
            .all()
        )
    else:
        originals = (
            database.session.execute(
                select(ARAPLedgerEntry).where(
                    ARAPLedgerEntry.document_type.in_(source_types),
                    ARAPLedgerEntry.document_id.in_(source_ids),
                    ARAPLedgerEntry.is_reversal.is_(False),
                )
            )
            .scalars()
            .all()
        )
    reversals: list[ARAPLedgerEntry] = []
    for original in originals:
        reversal = ARAPLedgerEntry(
            company=original.company,
            ledger_type=original.ledger_type,
            party_type=original.party_type,
            party_id=original.party_id,
            document_type=original.document_type,
            document_id=original.document_id,
            document_no=original.document_no,
            posting_date=cancellation_date or getattr(document, "posting_date", None) or date.today(),
            document_date=original.document_date,
            event_type="cancellation",
            currency=original.currency,
            document_amount=-_decimal(original.document_amount),
            reference_type=original.reference_type,
            reference_id=original.reference_id,
            voucher_type=_document_type(document),
            voucher_id=str(document.id),
            is_reversal=True,
            reversal_of=original.id,
        )
        database.session.add(reversal)
        database.session.flush()
        for book_row in original.book_entries:
            book = database.session.get(Book, book_row.ledger_id)
            if book:
                _add_book_entry(
                    reversal,
                    book=book,
                    amount=-_decimal(book_row.book_amount),
                    gl_entry=None,
                    is_reversal=True,
                    reversal_of=book_row,
                )
        reversals.append(reversal)
    return reversals
