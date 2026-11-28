"""Escenarios adicionales de #2333: AP, multilibro, bajas y reversas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from cacao_accounting.accounting_engine.document_builders import _document_carrying_value_in_ledger
from cacao_accounting.database import (
    Accounts,
    Book,
    DocumentRelation,
    GLEntry,
    PaymentEntry,
    PaymentReference,
    database,
)

FACTURA = "INV-2333-B"
CORTE = date(2026, 5, 31)
PAGO = date(2026, 6, 15)


def _cuenta(application, code: str, tipo: str) -> tuple[str, str]:
    """Crea cuenta de control propia del escenario y devuelve su ID."""
    with application.app_context():
        libro = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        cuenta = Accounts(
            entity="cacao",
            code=code,
            name=f"Cuenta {code}",
            classification="asset" if tipo == "receivable" else "liability",
            account_type=tipo,
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        return libro.id, cuenta.id


def _gl(application, *, libro_id, cuenta_id, debit, credit, fecha, voucher_type, voucher_id, cancelada=False, modified=None):
    """Inserta una partida GL con la firma indicada."""
    with application.app_context():
        partida = GLEntry(
            company="cacao",
            posting_date=fecha,
            ledger_id=libro_id,
            account_id=cuenta_id,
            debit=Decimal(debit),
            credit=Decimal(credit),
            voucher_type=voucher_type,
            voucher_id=voucher_id,
            is_cancelled=cancelada,
        )
        if modified is not None:
            partida.modified = modified
        database.session.add(partida)
        database.session.commit()


def _pago(application, *, libro_id, cuenta_id, fecha, monto, factura=FACTURA):
    """Crea un pago aplicado al documento con su partida GL."""
    with application.app_context():
        pago = PaymentEntry(company="cacao", payment_type="receive", posting_date=fecha, currency="NIO", docstatus=1)
        database.session.add(pago)
        database.session.flush()
        referencia = PaymentReference(
            payment_id=pago.id,
            reference_type="sales_invoice",
            reference_id=factura,
            company="cacao",
            allocated_amount=Decimal(monto),
        )
        database.session.add(referencia)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=factura,
                target_type="payment_entry",
                target_id=str(pago.id),
                target_item_id=str(referencia.id),
                company="cacao",
                qty=Decimal(monto),
                amount=Decimal(monto),
                relation_type="payment_allocation",
                status="active",
            )
        )
        database.session.commit()
        pago_id = pago.id
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="0",
        credit=monto,
        fecha=fecha,
        voucher_type="payment_entry",
        voucher_id=pago_id,
    )
    return pago_id


def _carrying(application, libro_id, cuenta_id, as_of_date, document_type="sales_invoice", receivable=True):
    """Valor en libros del documento en el libro y corte indicados."""
    with application.app_context():
        return _document_carrying_value_in_ledger(
            company="cacao",
            document_type=document_type,
            document_id=FACTURA,
            exclude_payment_id="",
            party_account_id=cuenta_id,
            ledger_id=libro_id,
            receivable=receivable,
            as_of_date=as_of_date,
        )


def test_ap_ignora_pago_posterior_al_corte(entorno_contable_aislado):
    """Una factura por pagar mide su saldo histórico igual que una AR."""
    application = entorno_contable_aislado.app
    libro_id, cuenta_id = _cuenta(application, "2101-2333", "payable")
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="0",
        credit="1000",
        fecha=date(2026, 5, 10),
        voucher_type="purchase_invoice",
        voucher_id=FACTURA,
    )
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="400",
        credit="0",
        fecha=PAGO,
        voucher_type="payment_entry",
        voucher_id="PAY-AP",
    )
    with application.app_context():
        pago = PaymentEntry(company="cacao", payment_type="pay", posting_date=PAGO, currency="NIO", docstatus=1)
        database.session.add(pago)
        database.session.flush()
        referencia = PaymentReference(
            payment_id=pago.id,
            reference_type="purchase_invoice",
            reference_id=FACTURA,
            company="cacao",
            allocated_amount=Decimal("400"),
        )
        database.session.add(referencia)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_invoice",
                source_id=FACTURA,
                target_type="payment_entry",
                target_id=str(pago.id),
                target_item_id=str(referencia.id),
                company="cacao",
                qty=Decimal("400"),
                amount=Decimal("400"),
                relation_type="payment_allocation",
                status="active",
            )
        )
        database.session.commit()

    assert _carrying(application, libro_id, cuenta_id, CORTE, "purchase_invoice", False) == Decimal("1000")


def test_multilibro_conserva_su_propio_corte(entorno_contable_aislado):
    """Cada libro mide su valor con los movimientos de su propia moneda."""
    application = entorno_contable_aislado.app
    libro_id, cuenta_id = _cuenta(application, "1105-2333", "receivable")
    with application.app_context():
        niif = database.session.execute(database.select(Book).filter_by(code="NIIF")).scalar_one()
        niif.currency = "USD"
        database.session.commit()
        niif_id = niif.id
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="1000",
        credit="0",
        fecha=date(2026, 5, 10),
        voucher_type="sales_invoice",
        voucher_id=FACTURA,
    )
    _gl(
        application,
        libro_id=niif_id,
        cuenta_id=cuenta_id,
        debit="200",
        credit="0",
        fecha=date(2026, 5, 10),
        voucher_type="sales_invoice",
        voucher_id=FACTURA,
    )
    _pago(application, libro_id=libro_id, cuenta_id=cuenta_id, fecha=PAGO, monto="400")

    assert _carrying(application, libro_id, cuenta_id, CORTE) == Decimal("1000")
    assert _carrying(application, niif_id, cuenta_id, CORTE) == Decimal("200")
    assert _carrying(application, libro_id, cuenta_id, date(2026, 6, 30)) == Decimal("600")
    assert _carrying(application, niif_id, cuenta_id, date(2026, 6, 30)) == Decimal("200")


def test_anulacion_posterior_no_altera_el_corte(entorno_contable_aislado):
    """Una factura anulada después del corte conserva su valor en el histórico."""
    application = entorno_contable_aislado.app
    libro_id, cuenta_id = _cuenta(application, "1105-2333-C", "receivable")
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="1000",
        credit="0",
        fecha=date(2026, 5, 10),
        voucher_type="sales_invoice",
        voucher_id=FACTURA,
        cancelada=True,
        modified=datetime(2026, 7, 15, 12, 0),
    )

    assert _carrying(application, libro_id, cuenta_id, CORTE) == Decimal("1000")
    assert _carrying(application, libro_id, cuenta_id, date(2026, 8, 31)) is None


def test_reversion_posterior_no_contamina_el_valor_historico(entorno_contable_aislado):
    """La partida de reversa posterior no se suma al valor del corte."""
    application = entorno_contable_aislado.app
    libro_id, cuenta_id = _cuenta(application, "1105-2333-R", "receivable")
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="1000",
        credit="0",
        fecha=date(2026, 5, 10),
        voucher_type="sales_invoice",
        voucher_id=FACTURA,
    )
    with application.app_context():
        database.session.add(
            GLEntry(
                company="cacao",
                posting_date=date(2026, 6, 20),
                ledger_id=libro_id,
                account_id=cuenta_id,
                debit=Decimal("0"),
                credit=Decimal("1000"),
                voucher_type="sales_invoice",
                voucher_id=FACTURA,
                is_cancelled=False,
                is_reversal=True,
            )
        )
        database.session.commit()

    assert _carrying(application, libro_id, cuenta_id, CORTE) == Decimal("1000")
    assert _carrying(application, libro_id, cuenta_id, date(2026, 6, 30)) == Decimal("1000")


def test_factura_sin_pagos_mantiene_su_total(entorno_contable_aislado):
    """Sin pagos, el valor en libros es el total original en cualquier corte."""
    application = entorno_contable_aislado.app
    libro_id, cuenta_id = _cuenta(application, "1105-2333-N", "receivable")
    _gl(
        application,
        libro_id=libro_id,
        cuenta_id=cuenta_id,
        debit="750",
        credit="0",
        fecha=date(2026, 5, 10),
        voucher_type="sales_invoice",
        voucher_id=FACTURA,
    )

    assert _carrying(application, libro_id, cuenta_id, CORTE) == Decimal("750")
    assert _carrying(application, libro_id, cuenta_id, date(2026, 12, 31)) == Decimal("750")
