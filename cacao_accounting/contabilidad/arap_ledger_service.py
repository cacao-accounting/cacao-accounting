"""Ledger documental de cuentas por cobrar y pagar.

El módulo mantiene el saldo de cada documento en su moneda documental y una
valoración independiente por libro.  Los movimientos se crean únicamente al
contabilizar o anular una operación; los cachés de los documentos siguen siendo
una optimización para consultas del día actual.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, cast

from sqlalchemy import select

from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    ARAPOpenItem,
    Accounts,
    Book,
    ComprobanteContable,
    ComprobanteContableDetalle,
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


def _is_return_document(document: Any) -> bool:
    """Identifica devoluciones/notas de credito con el mismo criterio del GL.

    El motor contable revierte una nota de credito cuando ``is_return`` es
    verdadero o cuando el ``document_type`` es ``sales_credit_note`` /
    ``purchase_credit_note``. El subledger debe usar el mismo criterio para no
    divergir de las lineas de la cuenta de control.
    """
    if bool(getattr(document, "is_return", False)) or bool(getattr(document, "is_reversal", False)):
        return True
    return _document_type(document).lower() in {"sales_credit_note", "purchase_credit_note"}


def _ledger_type(document: Any) -> str:
    """Resuelve AR para ventas y AP para compras."""
    if isinstance(document, PaymentEntry):
        return "AR" if getattr(document, "party_type", None) == "customer" else "AP"
    return "AR" if isinstance(document, SalesInvoice) or _document_type(document).startswith("sales_") else "AP"


def _payment_party_sign(document: PaymentEntry) -> Decimal:
    """Signo del movimiento del pago sobre el saldo documental del tercero.

    Un cobro de cliente y un pago a proveedor LIQUIDAN el saldo del tercero (lo
    reducen): signo -1. Un reembolso (pago a cliente / cobro de proveedor, por
    ejemplo contra una nota de credito) AUMENTA el saldo documental: signo +1.
    Asi el subledger sigue el mismo sentido que las lineas GL de la cuenta de
    control del tercero.
    """
    receive = getattr(document, "payment_type", "") == "receive"
    if _ledger_type(document) == "AR":
        return Decimal("-1") if receive else Decimal("1")
    return Decimal("1") if receive else Decimal("-1")


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
    ledger_type: str | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
    currency: str | None = None,
    document_type: str | None = None,
    document_id: str | None = None,
    economic_line_id: str | None = None,
    posting_date: date | None = None,
    voucher_type: str | None = None,
    voucher_id: str | None = None,
) -> ARAPLedgerEntry:
    """Construye un movimiento documental."""
    movement = ARAPLedgerEntry(
        company=str(getattr(document, "company", None) or getattr(document, "entity", "")),
        ledger_type=ledger_type or _ledger_type(document),
        party_type=str(
            party_type
            or getattr(document, "party_type", None)
            or ("customer" if (ledger_type or _ledger_type(document)) == "AR" else "supplier")
        ),
        party_id=str(party_id or _party_id(document) or ""),
        document_type=document_type or _document_type(document),
        document_id=str(document_id or document.id),
        document_no=getattr(document, "document_no", None),
        posting_date=posting_date
        or getattr(document, "posting_date", None)
        or getattr(document, "date", None)
        or date.today(),
        document_date=getattr(document, "posting_date", None) or getattr(document, "date", None),
        event_type=event_type,
        currency=str(currency or _currency(document) or ""),
        document_amount=amount,
        economic_line_id=economic_line_id,
        reference_type=reference_type,
        reference_id=reference_id,
        voucher_type=voucher_type or _document_type(document),
        voucher_id=str(voucher_id or document.id),
        is_reversal=is_reversal,
        reversal_of=reversal_of,
    )
    database.session.add(movement)
    database.session.flush()
    return movement


def _active_books(company: str) -> list[Book]:
    """Obtiene todos los libros activos de una compañía."""
    return list(database.session.execute(select(Book).where(Book.entity == company, Book.status == "activo")).scalars().all())


def _upsert_open_item_cache(
    *,
    movement: ARAPLedgerEntry,
    amount: Decimal,
    direction: str,
    account_id: str,
    economic_line_id: str,
    unallocated_amount: Decimal | None = None,
) -> ARAPOpenItem:
    """Mantiene el saldo rápido de un movimiento documental.

    La fila no sustituye a ``ARAPLedgerEntry``: únicamente materializa el
    saldo positivo actual para búsquedas y selectores. Las anulaciones y
    aplicaciones siguen registrándose como movimientos append-only.
    """
    row = database.session.execute(
        select(ARAPOpenItem).where(
            ARAPOpenItem.document_type == movement.document_type,
            ARAPOpenItem.document_id == movement.document_id,
            ARAPOpenItem.economic_line_id == economic_line_id,
        )
    ).scalar_one_or_none()
    value = abs(_decimal(unallocated_amount if unallocated_amount is not None else amount))
    if row is None:
        row = ARAPOpenItem(
            company=movement.company,
            ledger_type=movement.ledger_type,
            party_type=movement.party_type,
            party_id=movement.party_id,
            account_id=account_id,
            document_type=movement.document_type,
            document_id=movement.document_id,
            document_no=movement.document_no,
            economic_line_id=economic_line_id,
            posting_date=movement.posting_date,
            document_date=movement.document_date,
            currency=movement.currency,
            original_amount=abs(_decimal(amount)),
            unallocated_amount=value,
            direction=direction,
            status="open" if value else "closed",
            source_voucher_type=movement.voucher_type,
            source_voucher_id=movement.voucher_id,
        )
        database.session.add(row)
    else:
        row.unallocated_amount = value
        row.status = "open" if value else "closed"
        row.version = int(row.version or 1) + 1
    database.session.flush()
    return row


def _decrease_open_item_cache(open_item_id: str | None, amount: Decimal) -> None:
    """Consume una parte de un open item cacheado, sin alterar su historia."""
    if not open_item_id:
        return
    row = database.session.get(ARAPOpenItem, open_item_id, with_for_update=True)
    if row is None:
        return
    remaining = max(_decimal(row.unallocated_amount) - abs(_decimal(amount)), Decimal("0"))
    row.unallocated_amount = remaining
    row.status = "open" if remaining else "closed"
    row.version = int(row.version or 1) + 1
    database.session.add(row)


def _close_open_item_cache_for_movement(movement: ARAPLedgerEntry) -> None:
    """Cierra el snapshot rápido cuando una reversa ya neutraliza su origen."""
    economic_line_id = movement.economic_line_id or movement.document_id
    row = database.session.execute(
        select(ARAPOpenItem).where(
            ARAPOpenItem.document_type == movement.document_type,
            ARAPOpenItem.document_id == movement.document_id,
            ARAPOpenItem.economic_line_id == economic_line_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return
    row.unallocated_amount = Decimal("0")
    row.status = "closed"
    row.version = int(row.version or 1) + 1
    database.session.add(row)


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
    """Registra la apertura documental y la valoración GL de una factura.

    La apertura es idempotente: si el movimiento de apertura del documento ya
    existe no se duplica, lo que permite invocar la función desde
    ``post_document_to_gl`` y desde ``submit_document`` sin riesgo de
    registrar dos veces el mismo documento.
    """
    if not isinstance(document, (SalesInvoice, PurchaseInvoice)):
        return []
    if _party_id(document) is None or not _currency(document):
        return []
    existing = database.session.execute(
        select(ARAPLedgerEntry)
        .where(
            ARAPLedgerEntry.document_type == _document_type(document),
            ARAPLedgerEntry.document_id == str(document.id),
            ARAPLedgerEntry.event_type == "opening",
            ARAPLedgerEntry.is_reversal.is_(False),
        )
        .order_by(ARAPLedgerEntry.id)
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return [existing]
    # Devoluciones/credit notes reduce the documentary balance and therefore
    # enter the subledger with the opposite sign of a normal invoice.
    sign = Decimal("-1") if _is_return_document(document) else Decimal("1")
    movement = _new_movement(document, amount=sign * _document_amount(document), event_type="opening")
    party_entries = _party_gl_entries(entries, _party_id(document))
    account_id = str(getattr(party_entries[0], "account_id", None) or "") if party_entries else ""
    if account_id:
        _upsert_open_item_cache(
            movement=movement,
            amount=abs(sign * _document_amount(document)),
            direction="debit" if sign * _document_amount(document) > 0 else "credit",
            account_id=account_id,
            economic_line_id=str(document.id),
        )
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


def _populate_existing_payment_opening_books(
    existing_opening: ARAPLedgerEntry,
    document: PaymentEntry,
    entries: Iterable[GLEntry],
    total: Decimal,
    payment_sign: Decimal,
) -> None:
    """Popula las valoraciones por libro si la apertura ya existe pero no tenia valoraciones."""
    if not existing_opening.book_entries and total:
        party_entries = _party_gl_entries(entries, _party_id(document))
        payment_currency = str(_currency(document) or "")
        payment_date = getattr(document, "posting_date", None) or date.today()
        for book in _active_books(str(document.company)):
            rate = _book_exchange_rate(
                str(document.company),
                payment_currency,
                str(book.currency or payment_currency),
                payment_date,
                _decimal(document.exchange_rate),
            )
            candidates = _book_entries_for(str(book.id), party_entries)
            opening_gl = candidates[0] if candidates else None
            _add_book_entry(
                existing_opening,
                book=book,
                amount=(payment_sign * total * rate).quantize(Decimal("0.0001")),
                gl_entry=opening_gl,
            )


def _process_payment_reference(
    document: PaymentEntry,
    reference: PaymentReference,
    party_entries: list[GLEntry],
    payment_currency: str,
    payment_date: date,
    payment_sign: Decimal,
) -> list[ARAPLedgerEntry]:
    """Procesa una referencia individual de un pago."""
    if not reference.allocated_amount or not reference.reference_id:
        return []
    target = database.session.get(
        SalesInvoice if str(reference.reference_type).startswith("sales_") else PurchaseInvoice, reference.reference_id
    )
    if target is None:
        return []
    already_applied = database.session.execute(
        select(ARAPLedgerEntry)
        .where(
            ARAPLedgerEntry.document_type == _document_type(target),
            ARAPLedgerEntry.document_id == str(target.id),
            ARAPLedgerEntry.event_type == "allocation",
            ARAPLedgerEntry.reference_type == "payment_entry",
            ARAPLedgerEntry.reference_id == str(document.id),
            ARAPLedgerEntry.is_reversal.is_(False),
        )
        .order_by(ARAPLedgerEntry.id)
        .limit(1)
    ).scalar_one_or_none()
    if already_applied is not None:
        return []
    amount = _decimal(reference.allocated_amount)
    target_cache = database.session.execute(
        select(ARAPOpenItem)
        .where(
            ARAPOpenItem.document_type == _document_type(target),
            ARAPOpenItem.document_id == str(target.id),
            ARAPOpenItem.unallocated_amount > 0,
        )
        .order_by(ARAPOpenItem.id)
        .limit(1)
    ).scalar_one_or_none()
    target_economic_line_id = str(target_cache.economic_line_id if target_cache is not None else target.id)
    if target_cache is not None:
        target_direction = target_cache.direction
    elif _is_return_document(target):
        target_direction = "credit"
    else:
        target_direction = "debit"
    target_delta = -amount if target_direction == "debit" else amount
    target_movement = _new_movement(
        target,
        amount=target_delta,
        event_type="allocation",
        reference_type="payment_entry",
        reference_id=str(document.id),
        economic_line_id=target_economic_line_id,
        posting_date=payment_date,
        voucher_type="payment_entry",
        voucher_id=str(document.id),
    )
    movements = [target_movement]
    if target_cache is not None:
        _decrease_open_item_cache(target_cache.id, amount)
    for book in _active_books(str(document.company)):
        target_currency = str(_currency(target) or reference.currency or payment_currency)
        target_rate = _book_exchange_rate(
            str(document.company),
            target_currency,
            str(book.currency or target_currency),
            payment_date,
            _decimal(target.exchange_rate),
        )
        book_amount = (target_delta * target_rate).quantize(Decimal("0.0001"))
        candidates = _book_entries_for(str(book.id), party_entries)
        _add_book_entry(target_movement, book=book, amount=book_amount, gl_entry=candidates[0] if candidates else None)
    applied = _new_movement(
        document,
        amount=-payment_sign * _decimal(reference.payment_amount or reference.allocated_amount),
        event_type="allocation",
        reference_type=str(reference.reference_type),
        reference_id=str(reference.reference_id),
        economic_line_id=str(document.id),
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
            amount=(-payment_sign * _decimal(reference.payment_amount or reference.allocated_amount) * rate).quantize(
                Decimal("0.0001")
            ),
            gl_entry=None,
        )
    return movements


@dataclass(frozen=True)
class _PaymentPostingContext:
    """Estado consolidado para registrar la apertura documental de un pago.

    Centraliza los datos que el orquestador y los helpers comparten para evitar
    pasar siete argumentos por posicion y mantener ``post_payment_ar_ap`` como
    un orquestador delgado.
    """

    document: PaymentEntry
    party_entries: list[GLEntry]
    references: list[PaymentReference]
    total: Decimal
    payment_sign: Decimal
    payment_currency: str
    payment_date: date
    payment_account_id: str

    @property
    def consumed_cash(self) -> Decimal:
        """Importe total aplicado por las referencias del pago."""
        return sum(
            (_decimal(reference.payment_amount or reference.allocated_amount) for reference in self.references),
            Decimal("0"),
        )


def _load_payment_references(document: PaymentEntry) -> list[PaymentReference]:
    """Carga las referencias documentales asociadas a un pago."""
    return list(
        database.session.execute(select(PaymentReference).where(PaymentReference.payment_id == document.id)).scalars().all()
    )


def _find_existing_payment_opening(document: PaymentEntry) -> ARAPLedgerEntry | None:
    """Devuelve la apertura del pago si ya existe y no esta revertida."""
    return database.session.execute(
        select(ARAPLedgerEntry)
        .where(
            ARAPLedgerEntry.document_type == "payment_entry",
            ARAPLedgerEntry.document_id == str(document.id),
            ARAPLedgerEntry.event_type == "opening",
            ARAPLedgerEntry.is_reversal.is_(False),
        )
        .order_by(ARAPLedgerEntry.id)
        .limit(1)
    ).scalar_one_or_none()


def _has_postable_payment_context(document: PaymentEntry, references: list[PaymentReference]) -> bool:
    """Indica si un pago tiene referencias o un tercero que justifique el posting."""
    return bool(references) or _party_id(document) is not None


def _build_payment_posting_context(
    document: PaymentEntry, references: list[PaymentReference], entries: Iterable[GLEntry]
) -> _PaymentPostingContext:
    """Consolida los datos documentales del pago para el posting."""
    party_entries = _party_gl_entries(entries, _party_id(document))
    payment_account_id = str(getattr(party_entries[0], "account_id", None) or "") if party_entries else ""
    return _PaymentPostingContext(
        document=document,
        party_entries=party_entries,
        references=references,
        total=_decimal(document.paid_amount or document.received_amount),
        payment_sign=_payment_party_sign(document),
        payment_currency=str(_currency(document) or ""),
        payment_date=getattr(document, "posting_date", None) or date.today(),
        payment_account_id=payment_account_id,
    )


def _create_payment_opening_movement(context: _PaymentPostingContext) -> ARAPLedgerEntry:
    """Crea el movimiento de apertura del pago con el signo correspondiente."""
    movement = _new_movement(
        context.document,
        amount=context.payment_sign * context.total,
        event_type="opening",
        economic_line_id=str(context.document.id),
    )
    database.session.flush()
    return movement


def _record_payment_open_item_cache(movement: ARAPLedgerEntry, context: _PaymentPostingContext) -> None:
    """Actualiza el cache ARAPOpenItem del pago con la porcion no consumida."""
    if not context.payment_account_id:
        return
    unallocated = max(context.total - context.consumed_cash, Decimal("0"))
    _upsert_open_item_cache(
        movement=movement,
        amount=context.total,
        direction="debit" if movement.document_amount > 0 else "credit",
        account_id=context.payment_account_id,
        economic_line_id=str(context.document.id),
        unallocated_amount=unallocated,
    )


def _value_payment_movement_in_books(
    movement: ARAPLedgerEntry,
    context: _PaymentPostingContext,
    *,
    associate_opening_gl: bool,
) -> None:
    """Itera los libros activos, resuelve la tasa snapshot y registra el book entry.

    Cuando ``associate_opening_gl`` es verdadero y el primer candidato GL
    pertenece al libro actual, ese GL se asocia al book entry de apertura;
    cuando es falso (hay references) el GL queda ``None``.
    """
    document = context.document
    signed_amount = context.payment_sign * context.total
    for book in _active_books(str(document.company)):
        rate = _book_exchange_rate(
            str(document.company),
            context.payment_currency,
            str(book.currency or context.payment_currency),
            context.payment_date,
            _decimal(document.exchange_rate),
        )
        gl_entry: GLEntry | None = None
        if associate_opening_gl:
            candidates = _book_entries_for(str(book.id), context.party_entries)
            gl_entry = candidates[0] if candidates else None
        _add_book_entry(
            movement,
            book=book,
            amount=(signed_amount * rate).quantize(Decimal("0.0001")),
            gl_entry=gl_entry,
        )


def post_payment_ar_ap(document: PaymentEntry, entries: Iterable[GLEntry]) -> list[ARAPLedgerEntry]:
    """Registra el saldo propio del pago y sus aplicaciones documentales."""
    references = _load_payment_references(document)
    if not _has_postable_payment_context(document, references):
        return []
    existing_opening = _find_existing_payment_opening(document)
    if existing_opening is not None:
        _populate_existing_payment_opening_books(
            existing_opening,
            document,
            entries,
            _decimal(document.paid_amount or document.received_amount),
            _payment_party_sign(document),
        )
        return [existing_opening]
    context = _build_payment_posting_context(document, references, entries)
    movements: list[ARAPLedgerEntry] = []
    if context.total:
        opening = _create_payment_opening_movement(context)
        movements.append(opening)
        _record_payment_open_item_cache(opening, context)
        _value_payment_movement_in_books(opening, context, associate_opening_gl=not references)
    movements += [
        movement
        for reference in references
        for movement in _process_payment_reference(
            document,
            reference,
            context.party_entries,
            context.payment_currency,
            context.payment_date,
            context.payment_sign,
        )
    ]
    return movements


def _resolve_application_target_item(
    company: str,
    document: Any,
    document_type: str,
    document_currency: str,
    party_type: str,
    party_id: str,
    target_ledger_type: str,
    amount: Decimal,
    allocation_date: date,
) -> tuple[ARAPLedgerEntry, ARAPOpenItem | None, list[ARAPLedgerEntry]]:
    """Resuelve la apertura y el item cacheado del documento destino."""
    target_opening = database.session.execute(
        select(ARAPLedgerEntry)
        .where(
            ARAPLedgerEntry.company == company,
            ARAPLedgerEntry.document_type == document_type,
            ARAPLedgerEntry.document_id == str(document.id),
            ARAPLedgerEntry.event_type == "opening",
            ARAPLedgerEntry.is_reversal.is_(False),
        )
        .order_by(ARAPLedgerEntry.posting_date, ARAPLedgerEntry.id)
        .limit(1)
    ).scalar_one_or_none()
    target_cache = database.session.execute(
        select(ARAPOpenItem)
        .where(
            ARAPOpenItem.company == company,
            ARAPOpenItem.document_type == document_type,
            ARAPOpenItem.document_id == str(document.id),
            ARAPOpenItem.unallocated_amount > 0,
        )
        .order_by(ARAPOpenItem.id)
        .limit(1)
    ).scalar_one_or_none()
    new_movements: list[ARAPLedgerEntry] = []
    if target_opening is None:
        opening_amount = _document_amount(document) or amount
        signed_target = -opening_amount if _is_return_document(document) else opening_amount
        target_opening = _new_movement(
            document,
            amount=signed_target,
            event_type="opening",
            ledger_type=target_ledger_type,
            party_type=party_type,
            party_id=party_id,
            currency=document_currency,
            document_type=document_type,
            document_id=str(document.id),
            economic_line_id=str(getattr(document, "id", "")),
            posting_date=getattr(document, "posting_date", None) or allocation_date,
            voucher_type=document_type,
            voucher_id=str(document.id),
        )
        new_movements.append(target_opening)
    if target_cache is None:
        target_cache = _cache_for_movement(target_opening)
        if target_cache is None:
            account_id = _party_account_from_gl(company, document_type, str(document.id), party_id)
            if account_id:
                target_cache = _upsert_open_item_cache(
                    movement=target_opening,
                    amount=abs(_decimal(target_opening.document_amount)),
                    direction="debit" if _decimal(target_opening.document_amount) > 0 else "credit",
                    account_id=account_id,
                    economic_line_id=str(target_opening.economic_line_id or document.id),
                )
    if target_cache is not None and amount > _decimal(target_cache.unallocated_amount):
        raise ValueError("La aplicación excede el saldo pendiente del documento.")
    return target_opening, target_cache, new_movements


def _resolve_application_payment_item(
    company: str,
    payment: PaymentEntry,
    payment_type: str,
    payment_id: str,
    payment_currency: str,
    party_type: str,
    party_id: str,
    target_ledger_type: str,
    consumed: Decimal,
    allocation_date: date,
) -> tuple[ARAPLedgerEntry, ARAPOpenItem | None, list[ARAPLedgerEntry]]:
    """Resuelve la apertura y el item cacheado del pago."""
    payment_opening = database.session.execute(
        select(ARAPLedgerEntry)
        .where(
            ARAPLedgerEntry.company == company,
            ARAPLedgerEntry.document_type == payment_type,
            ARAPLedgerEntry.document_id == payment_id,
            ARAPLedgerEntry.event_type == "opening",
            ARAPLedgerEntry.is_reversal.is_(False),
        )
        .order_by(ARAPLedgerEntry.posting_date, ARAPLedgerEntry.id)
        .limit(1)
    ).scalar_one_or_none()
    payment_cache = database.session.execute(
        select(ARAPOpenItem)
        .where(
            ARAPOpenItem.company == company,
            ARAPOpenItem.document_type == payment_type,
            ARAPOpenItem.document_id == payment_id,
            ARAPOpenItem.unallocated_amount > 0,
        )
        .order_by(ARAPOpenItem.id)
        .limit(1)
    ).scalar_one_or_none()
    payment_total = _decimal(payment.paid_amount or payment.received_amount)
    payment_sign = _payment_party_sign(payment)
    if consumed > payment_total:
        raise ValueError("La aplicación excede el saldo nominal del pago.")
    new_movements: list[ARAPLedgerEntry] = []
    if payment_opening is None:
        payment_opening = _new_movement(
            payment,
            amount=payment_sign * payment_total,
            event_type="opening",
            ledger_type=target_ledger_type,
            party_type=party_type,
            party_id=party_id,
            currency=payment_currency,
            document_type=payment_type,
            document_id=payment_id,
            economic_line_id=payment_id,
            posting_date=getattr(payment, "posting_date", None) or allocation_date,
            voucher_type=payment_type,
            voucher_id=payment_id,
        )
        new_movements.append(payment_opening)
    if payment_cache is None:
        payment_cache = _cache_for_movement(payment_opening)
        if payment_cache is None:
            account_id = _party_account_from_gl(company, payment_type, payment_id, party_id)
            if account_id:
                payment_cache = _upsert_open_item_cache(
                    movement=payment_opening,
                    amount=payment_total,
                    direction="debit" if payment_opening.document_amount > 0 else "credit",
                    account_id=account_id,
                    economic_line_id=payment_id,
                    unallocated_amount=payment_total,
                )
    if payment_cache is not None and consumed > _decimal(payment_cache.unallocated_amount):
        raise ValueError("La aplicación excede el saldo disponible del pago.")
    return payment_opening, payment_cache, new_movements


def _build_application_movements(
    company: str,
    payment: PaymentEntry,
    document: Any,
    document_type: str,
    payment_type: str,
    payment_id: str,
    document_currency: str,
    payment_currency: str,
    party_type: str,
    party_id: str,
    target_ledger_type: str,
    amount: Decimal,
    consumed: Decimal,
    allocation_date: date,
    reference_type: str | None,
    target_opening: ARAPLedgerEntry,
    target_cache: ARAPOpenItem | None,
    payment_cache: ARAPOpenItem | None,
) -> list[ARAPLedgerEntry]:
    """Crea los movimientos de asignacion y actualiza las valoraciones por libro."""
    payment_sign = _payment_party_sign(payment)
    if target_cache is not None:
        target_direction = target_cache.direction
    elif _decimal(target_opening.document_amount) > 0:
        target_direction = "debit"
    else:
        target_direction = "credit"
    target_delta = -amount if target_direction == "debit" else amount
    already_applied = database.session.execute(
        select(ARAPLedgerEntry)
        .where(
            ARAPLedgerEntry.document_type == document_type,
            ARAPLedgerEntry.document_id == str(document.id),
            ARAPLedgerEntry.event_type == "allocation",
            ARAPLedgerEntry.reference_type == "payment_entry",
            ARAPLedgerEntry.reference_id == payment_id,
            ARAPLedgerEntry.is_reversal.is_(False),
        )
        .order_by(ARAPLedgerEntry.id)
        .limit(1)
    ).scalar_one_or_none()
    if already_applied is not None:
        return []
    target_movement = _new_movement(
        payment,
        amount=target_delta,
        event_type="allocation",
        reference_type="payment_entry",
        reference_id=payment_id,
        ledger_type=target_cache.ledger_type if target_cache is not None else target_ledger_type,
        party_type=party_type,
        party_id=party_id,
        currency=document_currency,
        document_type=document_type,
        document_id=str(document.id),
        economic_line_id=(target_cache.economic_line_id if target_cache is not None else target_opening.economic_line_id),
        posting_date=allocation_date,
        voucher_type=payment_type,
        voucher_id=payment_id,
    )
    payment_movement = _new_movement(
        payment,
        amount=-payment_sign * consumed,
        event_type="allocation",
        reference_type=reference_type or document_type,
        reference_id=str(document.id),
        ledger_type=target_cache.ledger_type if target_cache is not None else target_ledger_type,
        party_type=party_type,
        party_id=party_id,
        currency=payment_currency,
        document_type=payment_type,
        document_id=payment_id,
        economic_line_id=payment_id,
        posting_date=allocation_date,
        voucher_type=payment_type,
        voucher_id=payment_id,
    )
    movements = [target_movement, payment_movement]
    for book in _active_books(company):
        target_rate = _book_exchange_rate(
            company,
            document_currency,
            str(book.currency or document_currency),
            allocation_date,
            _decimal(getattr(document, "exchange_rate", None)),
        )
        payment_rate = _book_exchange_rate(
            company,
            payment_currency,
            str(book.currency or payment_currency),
            allocation_date,
            _decimal(getattr(payment, "exchange_rate", None)),
        )
        _add_book_entry(target_movement, book=book, amount=target_delta * target_rate, gl_entry=None)
        _add_book_entry(payment_movement, book=book, amount=(-payment_sign * consumed * payment_rate), gl_entry=None)
    if target_cache is not None:
        _decrease_open_item_cache(target_cache.id, amount)
    if payment_cache is not None:
        _decrease_open_item_cache(payment_cache.id, consumed)
    return movements


def post_payment_application_ar_ap(
    payment: PaymentEntry,
    document: Any,
    *,
    document_amount: Decimal,
    payment_amount: Decimal,
    allocation_date: date,
    reference_type: str | None = None,
) -> list[ARAPLedgerEntry]:
    """Registra una aplicación posterior de pago en el ledger documental."""
    amount = _decimal(document_amount)
    consumed = _decimal(payment_amount)
    if amount <= 0 or consumed <= 0:
        raise ValueError("La aplicación AP/AR requiere importes positivos.")
    company = str(getattr(payment, "company", None) or getattr(document, "company", None) or "")
    party_type = str(getattr(payment, "party_type", None) or "").lower()
    party_id = str(getattr(payment, "party_id", None) or "")
    if not company or party_type not in {"customer", "supplier"} or not party_id:
        raise ValueError("La aplicación AP/AR requiere compañía y tercero explícitos.")

    payment_type = "payment_entry"
    payment_id = str(payment.id)
    payment_currency = str(_currency(payment) or "")
    document_type = _document_type(document)
    document_currency = str(_currency(document) or payment_currency)
    if not payment_currency or not document_currency:
        raise ValueError("La aplicación AP/AR requiere monedas explícitas.")

    target_ledger_type = "AR" if party_type == "customer" else "AP"
    target_party_id = str(_party_id(document) or party_id)
    if target_party_id != party_id:
        raise ValueError("El documento y el pago deben pertenecer al mismo tercero.")

    movements: list[ARAPLedgerEntry] = []
    target_opening, target_cache, target_new_movements = _resolve_application_target_item(
        company, document, document_type, document_currency, party_type, party_id, target_ledger_type, amount, allocation_date
    )
    movements.extend(target_new_movements)
    payment_opening, payment_cache, payment_new_movements = _resolve_application_payment_item(
        company,
        payment,
        payment_type,
        payment_id,
        payment_currency,
        party_type,
        party_id,
        target_ledger_type,
        consumed,
        allocation_date,
    )
    movements.extend(payment_new_movements)
    alloc_movements = _build_application_movements(
        company,
        payment,
        document,
        document_type,
        payment_type,
        payment_id,
        document_currency,
        payment_currency,
        party_type,
        party_id,
        target_ledger_type,
        amount,
        consumed,
        allocation_date,
        reference_type,
        target_opening,
        target_cache,
        payment_cache,
    )
    movements.extend(alloc_movements)
    return movements


def _cache_for_movement(movement: ARAPLedgerEntry) -> ARAPOpenItem | None:
    """Busca el snapshot de una línea económica ya abierta."""
    return database.session.execute(
        select(ARAPOpenItem)
        .where(
            ARAPOpenItem.document_type == movement.document_type,
            ARAPOpenItem.document_id == movement.document_id,
            ARAPOpenItem.economic_line_id == (movement.economic_line_id or movement.document_id),
        )
        .limit(1)
    ).scalar_one_or_none()


def _party_account_from_gl(company: str, document_type: str, document_id: str, party_id: str) -> str | None:
    """Obtiene la cuenta auxiliar desde una línea GL histórica."""
    return database.session.execute(
        select(GLEntry.account_id)
        .where(
            GLEntry.company == company,
            GLEntry.voucher_type == document_type,
            GLEntry.voucher_id == document_id,
            GLEntry.party_id == party_id,
        )
        .order_by(GLEntry.id)
        .limit(1)
    ).scalar_one_or_none()


def _journal_party_lines(document: ComprobanteContable) -> list[ComprobanteContableDetalle]:
    """Obtiene las líneas de tercero de un comprobante manual."""
    return list(
        database.session.execute(
            select(ComprobanteContableDetalle)
            .where(
                ComprobanteContableDetalle.transaction == "journal_entry",
                ComprobanteContableDetalle.transaction_id == document.id,
                ComprobanteContableDetalle.third_code.is_not(None),
            )
            .order_by(ComprobanteContableDetalle.order, ComprobanteContableDetalle.id)
        )
        .scalars()
        .all()
    )


def _journal_account(line: ComprobanteContableDetalle, company: str, entries: list[GLEntry]) -> Any:
    """Resuelve la cuenta de una línea manual por id, código o GL."""
    line_account = str(getattr(line, "account", None) or "")
    account = database.session.get(Accounts, line_account)
    if account is None and line_account:
        account = database.session.execute(
            select(Accounts).where(Accounts.entity == company, Accounts.code == line_account)
        ).scalar_one_or_none()
    if account is not None:
        return account
    economic_id = str(getattr(line, "economic_line_id", None) or line.id)
    gl = next((entry for entry in entries if str(getattr(entry, "economic_line_id", "")) == economic_id), None)
    return database.session.get(Accounts, getattr(gl, "account_id", None)) if gl else None


def _journal_line_signed_amount(line: ComprobanteContableDetalle, ledger_type: str) -> Decimal:
    """Normaliza debe/haber al signo documental AR/AP."""
    value = _decimal(getattr(line, "value", None))
    if ledger_type == "AP":
        return -value
    return value


def _find_target_open_item(
    *,
    company: str,
    party_type: str,
    party_id: str,
    reference_type: str,
    reference_name: str,
    account_id: str,
) -> ARAPOpenItem | None:
    """Resuelve una referencia por id o número en el cache rápido."""
    query = (
        select(ARAPOpenItem)
        .where(
            ARAPOpenItem.company == company,
            ARAPOpenItem.party_type == party_type,
            ARAPOpenItem.party_id == party_id,
            ARAPOpenItem.document_type == reference_type,
            ARAPOpenItem.unallocated_amount > 0,
        )
        .where((ARAPOpenItem.document_id == reference_name) | (ARAPOpenItem.document_no == reference_name))
    )
    targets = database.session.execute(query).scalars().all()
    if len(targets) == 1:
        return targets[0]
    if len(targets) > 1:
        return None
    from cacao_accounting.contabilidad.arap_allocation import list_open_items

    ledger_matches = [
        item
        for item in list_open_items(company=company, party_type=party_type, party_id=party_id)
        if item.document_type == reference_type and item.document_id == reference_name and item.outstanding > 0
    ]
    if len(ledger_matches) != 1:
        return None
    item = ledger_matches[0]
    target = ARAPOpenItem(
        company=company,
        ledger_type=item.ledger_type or ("AR" if party_type == "customer" else "AP"),
        party_type=party_type,
        party_id=party_id,
        account_id=account_id,
        document_type=item.document_type,
        document_id=item.document_id,
        document_no=item.document_no,
        economic_line_id=item.economic_line_id or item.document_id,
        posting_date=item.posting_date or date.today(),
        currency=item.currency,
        original_amount=item.outstanding,
        unallocated_amount=item.outstanding,
        direction=item.direction or "debit",
    )
    database.session.add(target)
    database.session.flush()
    return target


def _normalize_journal_reference_type(value: str, party_type: str) -> str:
    """Normaliza los tipos de referencia del comprobante contable."""
    normalized = value.strip().lower().replace(" ", "_")
    normalized = {
        "factura": "invoice",
        "invoice": "invoice",
        "nota_debito": "debit_note",
        "debit_note": "debit_note",
        "nota_credito": "credit_note",
        "credit_note": "credit_note",
        "pago": "payment_entry",
        "payment": "payment_entry",
        "comprobante_contable": "journal_entry",
        "otro_comprobante_contable": "journal_entry",
    }.get(normalized, normalized)
    if normalized == "invoice":
        return "sales_invoice" if party_type == "customer" else "purchase_invoice"
    if normalized == "debit_note":
        return "sales_debit_note" if party_type == "customer" else "purchase_debit_note"
    if normalized == "credit_note":
        return "sales_credit_note" if party_type == "customer" else "purchase_credit_note"
    return normalized


def _apply_journal_open_item(
    *,
    document: ComprobanteContable,
    line: ComprobanteContableDetalle,
    source: ARAPLedgerEntry,
    source_cache: ARAPOpenItem,
    target: ARAPOpenItem,
    amount: Decimal,
    source_signed: Decimal,
    source_consumed: Decimal,
) -> ARAPLedgerEntry:
    """Registra la aplicación de una línea de diario a un open item."""
    if source_cache.direction == target.direction:
        raise ValueError("La referencia AP/AR debe tener sentido contrario al movimiento del diario.")
    target_delta = -amount if target.direction == "debit" else amount
    target_movement = _new_movement(
        document,
        amount=target_delta,
        event_type="allocation",
        reference_type="journal_entry",
        reference_id=str(document.id),
        ledger_type=target.ledger_type,
        party_type=target.party_type,
        party_id=target.party_id,
        currency=target.currency,
        document_type=target.document_type,
        document_id=target.document_id,
        economic_line_id=target.economic_line_id,
        voucher_type="journal_entry",
        voucher_id=str(document.id),
    )
    source_allocation = _new_movement(
        document,
        amount=-source_consumed if source_signed > 0 else source_consumed,
        event_type="allocation",
        reference_type=target.document_type,
        reference_id=target.document_id,
        ledger_type=source.ledger_type,
        party_type=source.party_type,
        party_id=source.party_id,
        currency=source.currency,
        document_type="journal_entry",
        voucher_type="journal_entry",
        voucher_id=str(document.id),
        economic_line_id=source.economic_line_id,
    )
    posting_date = getattr(document, "date", None) or date.today()
    for book in _active_books(str(document.entity)):
        target_rate = _book_exchange_rate(
            str(document.entity), target.currency, str(book.currency or target.currency), posting_date, Decimal("1")
        )
        source_rate = _book_exchange_rate(
            str(document.entity), source.currency, str(book.currency or source.currency), posting_date, Decimal("1")
        )
        _add_book_entry(target_movement, book=book, amount=target_delta * target_rate, gl_entry=None)
        source_value = -source_consumed if source_signed > 0 else source_consumed
        _add_book_entry(source_allocation, book=book, amount=source_value * source_rate, gl_entry=None)
    _decrease_open_item_cache(target.id, amount)
    _decrease_open_item_cache(source_cache.id, source_consumed)
    return source_allocation


def _process_journal_line_reference(
    document: ComprobanteContable,
    line: ComprobanteContableDetalle,
    party_type: str,
    party_id: str,
    account_id: str,
    currency: str,
    source: ARAPLedgerEntry,
    source_cache: ARAPOpenItem,
    source_signed: Decimal,
) -> ARAPLedgerEntry | None:
    """Procesa la referencia de una linea de diario y genera su aplicacion."""
    reference_type = (
        _normalize_journal_reference_type(str(getattr(line, "reference_type", None) or ""), party_type)
        if getattr(line, "reference_type", None)
        else ""
    )
    reference_name = str(
        getattr(line, "reference_name", None)
        or getattr(line, "reference_open_item_id", None)
        or getattr(line, "internal_reference_id", None)
        or ""
    ).strip()
    if not reference_type and not reference_name:
        return None
    if not reference_type or not reference_name:
        raise ValueError("La referencia AP/AR requiere tipo y documento.")
    target = database.session.get(ARAPOpenItem, reference_name)
    if target is None:
        target = _find_target_open_item(
            company=str(document.entity),
            party_type=party_type,
            party_id=party_id,
            reference_type=reference_type,
            reference_name=reference_name,
            account_id=account_id,
        )
    if target is None:
        raise ValueError("El documento de referencia AP/AR no tiene saldo abierto.")
    if target.party_type != party_type or str(target.party_id) != party_id:
        raise ValueError("El documento de referencia no pertenece al tercero de la línea.")
    source_amount = abs(source_signed)
    if target.currency == currency:
        rate = Decimal("1")
    else:
        rate = _decimal(getattr(line, "reference_exchange_rate", None) or getattr(line, "exchange_rate", None))
        if rate <= 0:
            raise ValueError("La referencia AP/AR requiere una tasa positiva entre monedas.")
    amount = min(_decimal(target.unallocated_amount), source_amount / rate)
    source_consumed = (amount * rate).quantize(Decimal("0.0001"))
    if amount <= 0 or source_consumed <= 0:
        raise ValueError("El documento de referencia AP/AR no tiene saldo disponible.")
    return _apply_journal_open_item(
        document=document,
        line=line,
        source=source,
        source_cache=source_cache,
        target=target,
        amount=amount,
        source_signed=source_signed,
        source_consumed=source_consumed,
    )


def _populate_journal_line_books(
    document: ComprobanteContable,
    entry_list: list[GLEntry],
    economic_line_id: str,
    ledger_type: str,
    source: ARAPLedgerEntry,
    reversal_source: ARAPLedgerEntry | None,
) -> None:
    """Agrega valoraciones por libro para una linea de comprobante contable."""
    for book in _active_books(str(document.entity)):
        candidates = [
            entry
            for entry in entry_list
            if str(getattr(entry, "ledger_id", None) or "") in {str(book.id), str(book.code)}
            and str(getattr(entry, "economic_line_id", None) or "") == economic_line_id
        ]
        if candidates:
            book_value = sum((_book_value_from_gl(entry, ledger_type) for entry in candidates), Decimal("0"))
            source_book = (
                next(
                    (row for row in cast(list[ARAPLedgerBookEntry], reversal_source.book_entries) if row.ledger_id == book.id),
                    None,
                )
                if reversal_source is not None
                else None
            )
            _add_book_entry(
                source,
                book=book,
                amount=book_value,
                gl_entry=candidates[0],
                is_reversal=reversal_source is not None,
                reversal_of=source_book,
            )


def _process_journal_party_line(
    document: ComprobanteContable,
    line: ComprobanteContableDetalle,
    entry_list: list[GLEntry],
) -> list[ARAPLedgerEntry]:
    """Procesa una linea individual con tercero de un comprobante contable."""
    account = _journal_account(line, str(document.entity), entry_list)
    account_type = str(getattr(account, "account_type", None) or "").lower()
    if account_type not in {"receivable", "payable", "customer_advance", "supplier_advance"}:
        return []
    party_type = str(getattr(line, "third_type", None) or "").lower()
    party_type = {"cliente": "customer", "proveedor": "supplier"}.get(party_type, party_type)
    party_id = str(getattr(line, "third_code", None) or "")
    ledger_type = "AR" if account_type in {"receivable", "customer_advance"} else "AP"
    source_signed = _journal_line_signed_amount(line, ledger_type)
    if not party_id or not party_type or source_signed == 0:
        return []
    currency = str(getattr(line, "currency_id", None) or document.transaction_currency or "")
    if not currency:
        raise ValueError("La línea AP/AR requiere moneda documental explícita.")
    economic_line_id = str(getattr(line, "economic_line_id", None) or line.id)
    reversal_source = None
    if getattr(document, "reversal_of", None):
        reversal_source = database.session.execute(
            select(ARAPLedgerEntry)
            .where(
                ARAPLedgerEntry.document_type == "journal_entry",
                ARAPLedgerEntry.document_id == str(document.reversal_of),
                ARAPLedgerEntry.economic_line_id == economic_line_id,
                ARAPLedgerEntry.is_reversal.is_(False),
            )
            .order_by(ARAPLedgerEntry.id)
            .limit(1)
        ).scalar_one_or_none()
    source = _new_movement(
        document,
        amount=source_signed,
        event_type="opening",
        ledger_type=ledger_type,
        party_type=party_type,
        party_id=party_id,
        currency=currency,
        document_type="journal_entry",
        document_id=reversal_source.document_id if reversal_source is not None else str(document.id),
        economic_line_id=economic_line_id,
        voucher_type="journal_entry",
        is_reversal=reversal_source is not None,
        reversal_of=str(reversal_source.id) if reversal_source is not None else None,
        voucher_id=str(document.id),
    )
    movements = [source]
    direction = "debit" if source_signed > 0 else "credit"
    source_cache = _upsert_open_item_cache(
        movement=source,
        amount=abs(source_signed),
        direction=direction,
        account_id=str(account.id),
        economic_line_id=economic_line_id,
        unallocated_amount=Decimal("0") if reversal_source is not None else None,
    )
    if reversal_source is not None:
        _close_open_item_cache_for_movement(reversal_source)
    _populate_journal_line_books(document, entry_list, economic_line_id, ledger_type, source, reversal_source)
    allocation_movement = _process_journal_line_reference(
        document, line, party_type, party_id, str(account.id), currency, source, source_cache, source_signed
    )
    if allocation_movement:
        movements.append(allocation_movement)
    return movements


def post_journal_ar_ap(document: ComprobanteContable, entries: Iterable[GLEntry]) -> list[ARAPLedgerEntry]:
    """Publica líneas de tercero de un diario en el subledger AP/AR."""
    existing = (
        database.session.execute(
            select(ARAPLedgerEntry)
            .where(
                ARAPLedgerEntry.document_type == "journal_entry",
                ARAPLedgerEntry.voucher_type == "journal_entry",
                ARAPLedgerEntry.voucher_id == str(document.id),
            )
            .order_by(ARAPLedgerEntry.id)
        )
        .scalars()
        .all()
    )
    if existing:
        return list(existing)
    entry_list = list(entries)
    movements: list[ARAPLedgerEntry] = []
    for line in _journal_party_lines(document):
        movements.extend(_process_journal_party_line(document, line, entry_list))
    return movements


def _cancellation_originals(document: Any, source_types: set[str], source_ids: set[str]) -> list[ARAPLedgerEntry]:
    """Obtiene movimientos originales que deben tener una contrapartida."""
    if isinstance(document, PaymentEntry):
        source_filter = (ARAPLedgerEntry.document_type == "payment_entry") & (
            ARAPLedgerEntry.document_id == str(document.id)
        ) | (ARAPLedgerEntry.reference_type == "payment_entry") & (ARAPLedgerEntry.reference_id == str(document.id))
    else:
        source_filter = (ARAPLedgerEntry.document_type.in_(source_types)) & (ARAPLedgerEntry.document_id.in_(source_ids)) | (
            ARAPLedgerEntry.reference_type == "journal_entry"
        ) & (ARAPLedgerEntry.reference_id == str(document.id))
    return list(
        database.session.execute(select(ARAPLedgerEntry).where(ARAPLedgerEntry.is_reversal.is_(False), source_filter))
        .scalars()
        .all()
    )


def _reverse_arap_movement(
    original: ARAPLedgerEntry,
    document: Any,
    cancellation_date: date | None,
) -> ARAPLedgerEntry:
    """Crea una contrapartida y restaura el caché derivado de un movimiento."""
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
        economic_line_id=original.economic_line_id,
        reference_type=original.reference_type,
        reference_id=original.reference_id,
        voucher_type=_document_type(document),
        voucher_id=str(document.id),
        is_reversal=True,
        reversal_of=original.id,
    )
    database.session.add(reversal)
    database.session.flush()
    for book_row in cast(list[ARAPLedgerBookEntry], original.book_entries):
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
    cache = database.session.execute(
        select(ARAPOpenItem).where(
            ARAPOpenItem.document_type == original.document_type,
            ARAPOpenItem.document_id == original.document_id,
            ARAPOpenItem.economic_line_id == (original.economic_line_id or original.document_id),
        )
    ).scalar_one_or_none()
    if cache is not None:
        if original.event_type == "opening":
            cache.unallocated_amount = Decimal("0")
        elif original.event_type == "allocation":
            cache.unallocated_amount = min(
                _decimal(cache.original_amount),
                _decimal(cache.unallocated_amount) + abs(_decimal(original.document_amount)),
            )
        cache.status = "open" if _decimal(cache.unallocated_amount) else "closed"
        cache.version = int(cache.version or 1) + 1
        database.session.add(cache)
    return reversal


def cancel_document_ar_ap(document: Any, *, cancellation_date: date | None = None) -> list[ARAPLedgerEntry]:
    """Agrega contrapartidas documentales para una anulación del mismo período."""
    source_types = {_document_type(document)}
    source_ids = {str(document.id)}
    if isinstance(document, ComprobanteContable):
        source_types.add("journal_entry")
    originals = _cancellation_originals(document, source_types, source_ids)
    originals = sorted(originals, key=lambda row: 0 if row.event_type == "opening" else 1)
    return [_reverse_arap_movement(original, document, cancellation_date) for original in originals]
