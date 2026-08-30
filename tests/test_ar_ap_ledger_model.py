# SPDX-License-Identifier: Apache-2.0
"""Pruebas unitarias del subledger documental AR/AP multimoneda."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def arap_app():
    """Crea un esquema SQLite aislado para validar el contrato del ledger."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Book, Currency, Entity, ExchangeRate, Party, database

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", active=True),
                Currency(code="USD", name="Dólar", active=True),
                Currency(code="EUR", name="Euro", active=True),
                Entity(code="cacao", company_name="Cacao SA", tax_id="T-ARAP", currency="NIO"),
                Party(code="P-ARAP", name="Tercero ARAP", is_customer=True, is_supplier=True),
                Book(code="FISC", name="Fiscal", entity="cacao", currency="NIO", is_primary=True, status="activo"),
                Book(code="IFRS", name="NIIF", entity="cacao", currency="USD", status="activo"),
                ExchangeRate(origin="USD", destination="NIO", rate=36, date=date(2026, 8, 1)),
                ExchangeRate(origin="NIO", destination="USD", rate=Decimal("0.027777778"), date=date(2026, 8, 1)),
                ExchangeRate(origin="EUR", destination="NIO", rate=40, date=date(2026, 8, 1)),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()


def _entry(**values):
    """Construye un movimiento documental con los valores mínimos comunes."""
    from cacao_accounting.database import ARAPLedgerEntry

    defaults = dict(
        company="cacao",
        ledger_type="AR",
        party_type="customer",
        party_id="P-ARAP",
        document_type="sales_invoice",
        document_id="INV-1",
        posting_date=date(2026, 8, 1),
        event_type="invoice",
        currency="USD",
        document_amount=Decimal("1000"),
    )
    defaults.update(values)
    return ARAPLedgerEntry(**defaults)


def test_document_balance_is_reconstructible_and_supports_reversal(arap_app):
    """Factura, devolución, pago y anulación reconstruyen el saldo documental."""
    from cacao_accounting.database import ARAPLedgerEntry, database

    database.session.add_all(
        [
            _entry(),
            _entry(document_id="INV-1", event_type="return", document_amount=Decimal("-100")),
            _entry(document_id="INV-1", event_type="payment", document_amount=Decimal("-500")),
            _entry(
                document_id="INV-1",
                event_type="payment_cancellation",
                document_amount=Decimal("500"),
                is_reversal=True,
            ),
        ]
    )
    database.session.commit()

    assert ARAPLedgerEntry.document_balance("sales_invoice", "INV-1") == Decimal("900.0000")


def test_book_valuation_keeps_document_and_functional_currency(arap_app):
    """Una valoración conserva snapshots independientes de moneda y tasa."""
    from cacao_accounting.database import ARAPLedgerBookEntry, Book, database

    entry = _entry()
    database.session.add(entry)
    database.session.flush()
    nio_book = database.session.query(Book).filter_by(code="FISC").one()
    valuation = ARAPLedgerBookEntry(
        ledger_entry_id=entry.id,
        book_id=nio_book.id,
        posting_date=entry.posting_date,
        document_currency="USD",
        book_currency="NIO",
        amount_document=Decimal("1000"),
        functional_amount=Decimal("36500"),
        exchange_rate=Decimal("36.500000000"),
    )
    database.session.add(valuation)
    database.session.commit()

    assert valuation.document_amount == Decimal("1000.0000")
    assert valuation.book_amount == Decimal("36500.0000")
    assert valuation.debit == Decimal("36500.0000")
    assert valuation.credit == Decimal("0.0000")
    assert valuation.functional_currency == "NIO"


def test_ar_ap_ledger_rows_are_append_only_except_cancellation(arap_app):
    """Cambiar importes o borrar filas falla, pero marcar cancelación es válido."""
    from cacao_accounting.database import ARAPLedgerBookEntry, Book, database

    entry = _entry()
    database.session.add(entry)
    database.session.flush()
    book = database.session.query(Book).filter_by(code="FISC").one()
    valuation = ARAPLedgerBookEntry(
        ledger_entry=entry,
        book_id=book.id,
        posting_date=entry.posting_date,
        document_currency="USD",
        book_currency="NIO",
        document_amount=Decimal("1000"),
        book_amount=Decimal("36500"),
        exchange_rate=Decimal("36.5"),
    )
    database.session.add(valuation)
    database.session.commit()

    entry.is_cancelled = True
    valuation.is_cancelled = True
    database.session.commit()

    entry.document_amount = Decimal("900")
    with pytest.raises(ValueError, match="inmutables"):
        database.session.commit()
    database.session.rollback()

    database.session.delete(valuation)
    with pytest.raises(ValueError, match="no se pueden eliminar"):
        database.session.flush()


def test_payment_cancellation_reverses_only_payment_movements(arap_app):
    """Anular un pago restaura la factura sin invertir su apertura original."""
    from cacao_accounting.contabilidad.arap_ledger_service import cancel_document_ar_ap
    from cacao_accounting.database import ARAPLedgerEntry, PaymentEntry, database

    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id="P-ARAP",
        transaction_currency="USD",
        currency="USD",
        posting_date=date(2026, 8, 2),
        paid_amount=Decimal("500"),
        received_amount=Decimal("500"),
        docstatus=1,
    )
    database.session.add(payment)
    database.session.flush()
    database.session.add_all(
        [
            _entry(document_id="INV-1", document_amount=Decimal("1000"), event_type="opening"),
            _entry(
                document_id="INV-1",
                document_amount=Decimal("-500"),
                event_type="allocation",
                reference_type="payment_entry",
                reference_id=payment.id,
            ),
            ARAPLedgerEntry(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id="P-ARAP",
                document_type="payment_entry",
                document_id=payment.id,
                posting_date=payment.posting_date,
                event_type="opening",
                currency="USD",
                document_amount=Decimal("-500"),
            ),
        ]
    )
    database.session.commit()

    cancel_document_ar_ap(payment, cancellation_date=date(2026, 8, 2))
    database.session.commit()

    assert ARAPLedgerEntry.document_balance("sales_invoice", "INV-1") == Decimal("1000.0000")
    assert ARAPLedgerEntry.document_balance("payment_entry", payment.id) == Decimal("0.0000")


def test_ledger_helpers_normalize_documents_and_gl_rows(arap_app):
    """Las funciones puras conservan signos AR/AP y toleran ORM incompleto."""
    from cacao_accounting.contabilidad.arap_ledger_service import (
        _book_entries_for,
        _book_value_from_gl,
        _currency,
        _decimal,
        _document_amount,
        _document_type,
        _ledger_type,
        _party_gl_entries,
        _party_id,
    )
    from cacao_accounting.database import PaymentEntry, PurchaseInvoice, SalesInvoice

    assert _decimal(None) == Decimal("0")
    assert _document_type(SimpleNamespace(document_type=None, __tablename__="legacy_doc")) == "legacy_doc"
    assert _currency(SimpleNamespace(transaction_currency=None, currency="USD")) == "USD"
    assert _party_id(SimpleNamespace(customer_id=None, supplier_id="SUP-1", party_id=None)) == "SUP-1"
    assert _document_amount(SimpleNamespace(grand_total=None, paid_amount=None, received_amount=12)) == Decimal("12")
    sales = SalesInvoice(company="cacao", customer_id="P-ARAP", transaction_currency="USD", grand_total=100)
    purchase = PurchaseInvoice(company="cacao", supplier_id="P-ARAP", transaction_currency="USD", grand_total=100)
    assert _ledger_type(sales) == "AR"
    assert _ledger_type(purchase) == "AP"
    assert _ledger_type(PaymentEntry(payment_type="receive", party_type="customer")) == "AR"
    assert _ledger_type(PaymentEntry(payment_type="pay", party_type="supplier")) == "AP"
    gl_ar = SimpleNamespace(party_id="P-ARAP", ledger_id="book-1", debit=100, credit=0)
    gl_ap = SimpleNamespace(party_id="P-ARAP", ledger_id="book-1", debit=0, credit=100)
    assert _party_gl_entries([gl_ar], "P-ARAP") == [gl_ar]
    assert _party_gl_entries([gl_ar], None) == []
    assert _book_entries_for("book-1", [gl_ar, gl_ap]) == [gl_ar, gl_ap]
    assert _book_value_from_gl(gl_ar, "AR") == Decimal("100")
    assert _book_value_from_gl(gl_ap, "AP") == Decimal("100")


def test_post_document_records_return_and_book_valuation(arap_app):
    """La apertura y una devolución se reflejan por libro sin mutar el documento."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_document_ar_ap
    from cacao_accounting.database import ARAPLedgerBookEntry, ARAPLedgerEntry, SalesInvoice, database

    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="USD",
        grand_total=Decimal("1000"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    database.session.add(invoice)
    database.session.flush()
    from cacao_accounting.database import Book

    nio_book = database.session.query(Book).filter_by(code="FISC").one()
    gl = SimpleNamespace(party_id="P-ARAP", ledger_id=nio_book.id, debit=36500, credit=0, id="GL-1")
    movements = post_document_ar_ap(invoice, [gl])
    database.session.commit()
    assert movements[0].document_amount == Decimal("1000.0000")
    assert database.session.query(ARAPLedgerBookEntry).count() == 1

    returned = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="USD",
        grand_total=Decimal("100"),
        posting_date=date(2026, 8, 2),
        document_type="sales_invoice",
        is_return=True,
    )
    database.session.add(returned)
    database.session.flush()
    post_document_ar_ap(returned, [])
    database.session.commit()
    assert ARAPLedgerEntry.document_balance("sales_invoice", returned.id) == Decimal("-100.0000")


def test_manual_journal_party_line_creates_reconstructible_open_item(arap_app):
    """Una línea de diario AR crea saldo rápido y movimiento documental."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_journal_ar_ap
    from cacao_accounting.database import Accounts, ComprobanteContable, ComprobanteContableDetalle, database

    account = Accounts(
        entity="cacao", code="AR-MANUAL", name="Clientes", active=True, enabled=True, group=False, account_type="receivable"
    )
    journal = ComprobanteContable(entity="cacao", date=date(2026, 8, 2), status="submitted")
    database.session.add_all([account, journal])
    database.session.flush()
    line = ComprobanteContableDetalle(
        entity="cacao",
        account=account.code,
        transaction="journal_entry",
        transaction_id=journal.id,
        order=1,
        value=Decimal("250"),
        currency_id="USD",
        third_type="customer",
        third_code="P-ARAP",
        economic_line_id="manual-line-1",
    )
    database.session.add(line)
    database.session.flush()
    movements = post_journal_ar_ap(journal, [])
    database.session.commit()

    from cacao_accounting.database import ARAPLedgerEntry, ARAPOpenItem

    item = database.session.query(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=journal.id).one()
    assert item.unallocated_amount == Decimal("250.0000")
    assert item.direction == "debit"
    assert ARAPLedgerEntry.document_balance("journal_entry", journal.id) == Decimal("250.0000")
    assert len(movements) == 1


def test_manual_journal_reference_allocates_and_cancellation_restores_open_items(arap_app):
    """La aplicación inmediata y su anulación conservan saldos auditables."""
    from cacao_accounting.contabilidad.arap_ledger_service import cancel_document_ar_ap, post_journal_ar_ap
    from cacao_accounting.database import Accounts, ARAPOpenItem, ComprobanteContable, ComprobanteContableDetalle, database

    account = Accounts(
        entity="cacao", code="AR-ALLOC", name="Clientes", active=True, enabled=True, group=False, account_type="receivable"
    )
    target = ARAPOpenItem(
        company="cacao",
        ledger_type="AR",
        party_type="customer",
        party_id="P-ARAP",
        account_id=account.id,
        document_type="sales_invoice",
        document_id="INV-ALLOC",
        document_no="INV-ALLOC",
        economic_line_id="invoice-line",
        posting_date=date(2026, 8, 1),
        currency="USD",
        original_amount=Decimal("100"),
        unallocated_amount=Decimal("100"),
        direction="debit",
    )
    journal = ComprobanteContable(entity="cacao", date=date(2026, 8, 2), status="submitted")
    database.session.add(account)
    database.session.flush()
    target.account_id = account.id
    database.session.add_all([target, journal])
    database.session.flush()
    line = ComprobanteContableDetalle(
        entity="cacao",
        account=account.code,
        transaction="journal_entry",
        transaction_id=journal.id,
        order=1,
        value=Decimal("-40"),
        currency_id="USD",
        third_type="customer",
        third_code="P-ARAP",
        reference_type="invoice",
        reference_name=target.document_id,
        economic_line_id="allocation-line",
    )
    database.session.add(line)
    database.session.flush()
    post_journal_ar_ap(journal, [])
    database.session.commit()

    database.session.refresh(target)
    assert target.unallocated_amount == Decimal("60.0000")
    database.session.refresh(journal)
    cancel_document_ar_ap(journal, cancellation_date=date(2026, 8, 2))
    database.session.commit()
    database.session.refresh(target)
    source = database.session.query(ARAPOpenItem).filter_by(document_type="journal_entry", document_id=journal.id).one()
    assert target.unallocated_amount == Decimal("100.0000")
    assert source.unallocated_amount == Decimal("40.0000")


def test_manual_journal_reversal_links_subledger_and_closes_cache(arap_app):
    """La reversión publicada enlaza su movimiento AR con el origen y cierra cachés."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_journal_ar_ap
    from cacao_accounting.database import (
        ARAPLedgerEntry,
        ARAPOpenItem,
        Accounts,
        ComprobanteContable,
        ComprobanteContableDetalle,
        database,
    )

    account = Accounts(
        entity="cacao", code="AR-REV", name="Clientes", active=True, enabled=True, group=False, account_type="receivable"
    )
    source = ComprobanteContable(entity="cacao", date=date(2026, 8, 2), status="submitted")
    reversal = ComprobanteContable(entity="cacao", date=date(2026, 8, 3), status="submitted", reversal_of=None)
    database.session.add_all([account, source, reversal])
    database.session.flush()
    reversal.reversal_of = source.id
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="cacao",
                account=account.code,
                transaction="journal_entry",
                transaction_id=source.id,
                order=1,
                value=Decimal("100"),
                currency_id="USD",
                third_type="customer",
                third_code="P-ARAP",
                economic_line_id="REV-LINE",
            ),
            ComprobanteContableDetalle(
                entity="cacao",
                account=account.code,
                transaction="journal_entry",
                transaction_id=reversal.id,
                order=1,
                value=Decimal("-100"),
                currency_id="USD",
                third_type="customer",
                third_code="P-ARAP",
                economic_line_id="REV-LINE",
            ),
        ]
    )
    database.session.flush()
    post_journal_ar_ap(source, [])
    database.session.commit()
    post_journal_ar_ap(reversal, [])
    database.session.commit()

    source_rows = database.session.query(ARAPLedgerEntry).filter_by(document_id=source.id).all()
    original = next(row for row in source_rows if not row.is_reversal)
    reversed_entry = next(row for row in source_rows if row.is_reversal)
    assert reversed_entry.is_reversal is True
    assert reversed_entry.reversal_of == original.id
    assert ARAPLedgerEntry.document_balance("journal_entry", source.id) == Decimal("0.0000")
    source_cache = database.session.query(ARAPOpenItem).filter_by(document_id=source.id).one()
    assert source_cache.unallocated_amount == Decimal("0.0000")


def test_list_open_items_exposes_payment_credit_as_positive_available_balance(arap_app):
    """Los pagos abiertos se muestran positivos, conservando su dirección crédito."""
    from cacao_accounting.contabilidad.arap_allocation import list_open_items
    from cacao_accounting.database import ARAPLedgerEntry, database

    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR",
            party_type="customer",
            party_id="P-ARAP",
            document_type="payment_entry",
            document_id="PAY-OPEN",
            posting_date=date(2026, 8, 2),
            event_type="opening",
            currency="USD",
            document_amount=Decimal("-500"),
            economic_line_id="PAY-OPEN",
        )
    )
    database.session.commit()

    items = list_open_items(company="cacao", party_type="customer", party_id="P-ARAP")
    payment = next(item for item in items if item.document_id == "PAY-OPEN")
    assert payment.outstanding == Decimal("500.0000")
    assert payment.direction == "credit"


def test_post_late_payment_application_updates_reconstructible_balances(arap_app):
    """Una conciliación posterior agrega eventos y restaura ambos saldos al anular."""
    from cacao_accounting.contabilidad.arap_ledger_service import cancel_document_ar_ap, post_payment_application_ar_ap
    from cacao_accounting.database import ARAPLedgerEntry, ARAPOpenItem, Accounts, PaymentEntry, SalesInvoice, database

    account = Accounts(
        entity="cacao", code="AR-LATE", name="Clientes", active=True, enabled=True, group=False, account_type="receivable"
    )
    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="USD",
        grand_total=Decimal("1000"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id="P-ARAP",
        transaction_currency="USD",
        currency="USD",
        posting_date=date(2026, 8, 2),
        paid_amount=Decimal("500"),
        received_amount=Decimal("500"),
        docstatus=1,
    )
    database.session.add_all([account, invoice, payment])
    database.session.flush()
    database.session.add_all(
        [
            ARAPLedgerEntry(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id="P-ARAP",
                document_type="sales_invoice",
                document_id=invoice.id,
                posting_date=invoice.posting_date,
                event_type="opening",
                currency="USD",
                document_amount=Decimal("1000"),
                economic_line_id=invoice.id,
            ),
            ARAPLedgerEntry(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id="P-ARAP",
                document_type="payment_entry",
                document_id=payment.id,
                posting_date=payment.posting_date,
                event_type="opening",
                currency="USD",
                document_amount=Decimal("-500"),
                economic_line_id=payment.id,
            ),
            ARAPOpenItem(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id="P-ARAP",
                account_id=account.id,
                document_type="sales_invoice",
                document_id=invoice.id,
                economic_line_id=invoice.id,
                posting_date=invoice.posting_date,
                currency="USD",
                original_amount=Decimal("1000"),
                unallocated_amount=Decimal("1000"),
                direction="debit",
            ),
            ARAPOpenItem(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id="P-ARAP",
                account_id=account.id,
                document_type="payment_entry",
                document_id=payment.id,
                economic_line_id=payment.id,
                posting_date=payment.posting_date,
                currency="USD",
                original_amount=Decimal("500"),
                unallocated_amount=Decimal("500"),
                direction="credit",
            ),
        ]
    )
    database.session.commit()

    post_payment_application_ar_ap(
        payment,
        invoice,
        document_amount=Decimal("500"),
        payment_amount=Decimal("500"),
        allocation_date=date(2026, 8, 2),
    )
    database.session.commit()
    assert ARAPLedgerEntry.document_balance("sales_invoice", invoice.id) == Decimal("500.0000")
    assert ARAPLedgerEntry.document_balance("payment_entry", payment.id) == Decimal("0.0000")
    assert database.session.query(ARAPOpenItem).filter_by(document_id=invoice.id).one().unallocated_amount == Decimal(
        "500.0000"
    )

    cancel_document_ar_ap(payment, cancellation_date=date(2026, 8, 2))
    database.session.commit()
    assert ARAPLedgerEntry.document_balance("sales_invoice", invoice.id) == Decimal("1000.0000")
    assert ARAPLedgerEntry.document_balance("payment_entry", payment.id) == Decimal("0.0000")


def test_post_payment_records_allocations_in_both_currencies(arap_app):
    """Una aplicación conserva el monto documental y el equivalente del banco."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_payment_ar_ap
    from cacao_accounting.database import (
        ARAPLedgerBookEntry,
        ARAPLedgerEntry,
        Book,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        database,
    )

    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="NIO",
        grand_total=Decimal("100"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    payment = PaymentEntry(
        company="cacao",
        party_type="customer",
        party_id="P-ARAP",
        payment_type="receive",
        transaction_currency="USD",
        currency="USD",
        exchange_rate=Decimal("36"),
        received_amount=Decimal("3"),
        paid_amount=Decimal("0"),
        posting_date=date(2026, 8, 2),
    )
    database.session.add_all([invoice, payment])
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("100"),
        payment_amount=Decimal("2.7778"),
        base_allocated_amount=Decimal("3600"),
    )
    database.session.add(reference)
    database.session.flush()
    fiscal_book = database.session.query(Book).filter_by(code="FISC").one()
    gl = SimpleNamespace(party_id="P-ARAP", ledger_id=fiscal_book.id, debit=0, credit=3600, id="GL-PAY-1")
    movements = post_payment_ar_ap(payment, [gl])
    database.session.commit()
    assert len(movements) == 3
    assert ARAPLedgerEntry.document_balance("sales_invoice", invoice.id) == Decimal("-100.0000")
    assert ARAPLedgerEntry.document_balance("payment_entry", payment.id) == Decimal("-0.2222")
    assert database.session.query(ARAPLedgerBookEntry).filter(ARAPLedgerBookEntry.gl_entry_id == "GL-PAY-1").count() == 1
    opening_values = {
        row.book_currency: row.book_amount
        for row in database.session.query(ARAPLedgerBookEntry)
        .join(ARAPLedgerEntry)
        .filter(ARAPLedgerEntry.document_type == "payment_entry", ARAPLedgerEntry.document_id == payment.id)
        .filter(ARAPLedgerEntry.event_type == "opening")
    }
    assert opening_values == {"NIO": Decimal("-108.0000"), "USD": Decimal("-3.0000")}


def test_cancel_non_payment_document_reverses_all_document_rows(arap_app):
    """La anulación de una factura agrega reversos append-only."""
    from cacao_accounting.contabilidad.arap_ledger_service import cancel_document_ar_ap
    from cacao_accounting.database import ARAPLedgerEntry, SalesInvoice, database

    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="USD",
        grand_total=Decimal("100"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(_entry(document_id=invoice.id, document_amount=Decimal("100"), event_type="opening"))
    database.session.commit()
    reversals = cancel_document_ar_ap(invoice, cancellation_date=date(2026, 8, 3))
    database.session.commit()
    assert len(reversals) == 1
    assert ARAPLedgerEntry.document_balance("sales_invoice", invoice.id) == Decimal("0.0000")


def test_post_payment_with_zero_total_skips_opening(arap_app):
    """Si el total del pago es cero, no se crea apertura propia pero sí las allocations."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_payment_ar_ap
    from cacao_accounting.database import (
        ARAPLedgerEntry,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        database,
    )

    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="NIO",
        grand_total=Decimal("100"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    payment = PaymentEntry(
        company="cacao",
        party_type="customer",
        party_id="P-ARAP",
        payment_type="receive",
        transaction_currency="USD",
        currency="USD",
        exchange_rate=Decimal("36"),
        received_amount=Decimal("0"),
        paid_amount=Decimal("0"),
        posting_date=date(2026, 8, 2),
    )
    database.session.add_all([invoice, payment])
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("100"),
        payment_amount=Decimal("0"),
        base_allocated_amount=Decimal("0"),
    )
    database.session.add(reference)
    database.session.flush()
    movements = post_payment_ar_ap(payment, [])
    database.session.commit()
    # Apertura propia del pago NO se crea porque total == 0;
    # sólo allocations contra la factura y contra el pago aplicado.
    assert all(m.event_type == "allocation" for m in movements)
    assert any(
        m.document_type == "sales_invoice" and m.event_type == "allocation" for m in movements
    )
    assert any(
        m.document_type == "payment_entry" and m.event_type == "allocation" for m in movements
    )


def test_post_payment_fully_allocated_closes_open_item(arap_app):
    """Si todas las references cubren el total, el open item se cierra."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_payment_ar_ap
    from cacao_accounting.database import (
        ARAPOpenItem,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        database,
    )

    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="NIO",
        grand_total=Decimal("100"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    payment = PaymentEntry(
        company="cacao",
        party_type="customer",
        party_id="P-ARAP",
        payment_type="receive",
        transaction_currency="NIO",
        currency="NIO",
        exchange_rate=Decimal("1"),
        received_amount=Decimal("100"),
        paid_amount=Decimal("0"),
        posting_date=date(2026, 8, 2),
    )
    database.session.add_all([invoice, payment])
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("100"),
        payment_amount=Decimal("100"),
        base_allocated_amount=Decimal("100"),
    )
    database.session.add(reference)
    database.session.flush()
    gl_party = SimpleNamespace(party_id="P-ARAP", ledger_id=None, debit=0, credit=100, account_id="ACC-PTY-1")
    post_payment_ar_ap(payment, [gl_party])
    database.session.commit()
    open_item = database.session.query(ARAPOpenItem).filter_by(
        document_type="payment_entry", document_id=payment.id
    ).one()
    assert open_item.unallocated_amount == Decimal("0")
    assert open_item.status == "closed"


def test_post_payment_without_references_associates_opening_gl_per_book(arap_app):
    """Sin references, el GL de apertura se asocia al libro del primer candidato."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_payment_ar_ap
    from cacao_accounting.database import (
        ARAPLedgerBookEntry,
        ARAPLedgerEntry,
        Book,
        PaymentEntry,
        database,
    )

    payment = PaymentEntry(
        company="cacao",
        party_type="customer",
        party_id="P-ARAP",
        payment_type="receive",
        transaction_currency="NIO",
        currency="NIO",
        exchange_rate=Decimal("1"),
        received_amount=Decimal("100"),
        paid_amount=Decimal("0"),
        posting_date=date(2026, 8, 2),
    )
    database.session.add(payment)
    database.session.flush()
    fiscal_book = database.session.query(Book).filter_by(code="FISC").one()
    gl_with_party = SimpleNamespace(
        id="GL-FISC-1",
        party_id="P-ARAP",
        ledger_id=fiscal_book.id,
        debit=0,
        credit=100,
        account_id="ACC-PTY-1",
    )
    movements = post_payment_ar_ap(payment, [gl_with_party])
    database.session.commit()
    opening_movement = database.session.query(ARAPLedgerEntry).filter_by(
        document_type="payment_entry", document_id=payment.id, event_type="opening"
    ).one()
    fisc_book_entry = database.session.query(ARAPLedgerBookEntry).filter_by(
        ledger_entry_id=opening_movement.id, ledger_id=fiscal_book.id
    ).one()
    assert fisc_book_entry.gl_entry_id is not None
    assert movements[0].id == opening_movement.id


def test_post_payment_opening_gl_for_books_is_none_when_references_exist(arap_app):
    """Si hay references, el GL de apertura por libro queda en None (regla de la línea 571)."""
    from cacao_accounting.contabilidad.arap_ledger_service import post_payment_ar_ap
    from cacao_accounting.database import (
        ARAPLedgerBookEntry,
        ARAPLedgerEntry,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        database,
    )

    invoice = SalesInvoice(
        company="cacao",
        customer_id="P-ARAP",
        transaction_currency="NIO",
        grand_total=Decimal("100"),
        posting_date=date(2026, 8, 1),
        document_type="sales_invoice",
    )
    payment = PaymentEntry(
        company="cacao",
        party_type="customer",
        party_id="P-ARAP",
        payment_type="receive",
        transaction_currency="NIO",
        currency="NIO",
        exchange_rate=Decimal("1"),
        received_amount=Decimal("50"),
        paid_amount=Decimal("0"),
        posting_date=date(2026, 8, 2),
    )
    database.session.add_all([invoice, payment])
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("30"),
        payment_amount=Decimal("30"),
        base_allocated_amount=Decimal("30"),
    )
    database.session.add(reference)
    database.session.flush()
    gl_with_party = SimpleNamespace(party_id="P-ARAP", ledger_id=None, debit=0, credit=100, id="GL-AP-1")
    post_payment_ar_ap(payment, [gl_with_party])
    database.session.commit()
    # El GL se asocia solo a allocations, no a la apertura del pago.
    opening_movement = database.session.query(ARAPLedgerEntry).filter_by(
        document_type="payment_entry", document_id=payment.id, event_type="opening"
    ).one()
    opening_books = database.session.query(ARAPLedgerBookEntry).filter_by(
        ledger_entry_id=opening_movement.id
    ).all()
    assert all(book.gl_entry_id != "GL-AP-1" for book in opening_books)


def test_ledger_exchange_rate_resolution_and_guard_clauses(arap_app):
    """Las tasas por libro usan directa, inversa y fallback de moneda funcional."""
    from cacao_accounting.contabilidad.arap_ledger_service import (
        _add_book_entry,
        _book_exchange_rate,
        post_document_ar_ap,
        post_payment_ar_ap,
    )
    from cacao_accounting.database import Book, PaymentEntry, SalesInvoice, database

    posting_date = date(2026, 8, 2)
    assert _book_exchange_rate("cacao", "USD", "USD", posting_date, Decimal("36")) == Decimal("1")
    assert _book_exchange_rate("cacao", "USD", "NIO", posting_date, Decimal("36")) == Decimal("36")
    inverse = _book_exchange_rate("cacao", "NIO", "EUR", posting_date, Decimal("1"))
    assert inverse == Decimal("0.025")
    assert _book_exchange_rate("cacao", "GBP", "NIO", posting_date, Decimal("5")) == Decimal("5")
    assert _book_exchange_rate("cacao", "NIO", "GBP", posting_date, Decimal("5")) == Decimal("0.2")
    assert _book_exchange_rate("cacao", "GBP", "EUR", posting_date, Decimal("0")) == Decimal("1")

    assert post_document_ar_ap(SimpleNamespace(id="X"), []) == []
    incomplete = SalesInvoice(company="cacao", customer_id=None, transaction_currency="USD", grand_total=1)
    assert post_document_ar_ap(incomplete, []) == []
    no_party_payment = PaymentEntry(company="cacao", payment_type="receive", party_type=None)
    assert post_payment_ar_ap(no_party_payment, []) == []

    book = database.session.query(Book).filter_by(code="FISC").one()
    movement = _entry(ledger_type="AP")
    database.session.add(movement)
    database.session.flush()
    _add_book_entry(movement, book=book, amount=Decimal("0"), gl_entry=None)
    _add_book_entry(movement, book=book, amount=Decimal("10"), gl_entry=None)
    database.session.commit()
