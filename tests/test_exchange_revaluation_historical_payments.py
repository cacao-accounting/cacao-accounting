# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2333: el valor en libros histórico ignora pagos posteriores al corte."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.accounting_engine.document_builders import _document_carrying_value_in_ledger
from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
from cacao_accounting.database import (
    Accounts,
    Book,
    DocumentRelation,
    GLEntry,
    PaymentEntry,
    PaymentReference,
    database,
)

CUENTA = "1105"
FACTURA = "INV-2333"
CORTE = date(2026, 5, 31)
FECHA_PAGO = date(2026, 6, 15)


def _escenario(entorno_contable_aislado):
    """Factura AR con pago parcial posterior al corte en el libro primario."""
    application = entorno_contable_aislado.app
    with application.app_context():
        libro = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code=CUENTA)).scalar_one()
        database.session.add(
            GLEntry(
                company="cacao",
                posting_date=date(2026, 5, 10),
                ledger_id=libro.id,
                account_id=cuenta.id,
                account_code=cuenta.code,
                debit=Decimal("1000"),
                credit=Decimal("0"),
                voucher_type="sales_invoice",
                voucher_id=FACTURA,
                is_cancelled=False,
            )
        )
        pago = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=FECHA_PAGO,
            currency="NIO",
            docstatus=1,
        )
        database.session.add(pago)
        database.session.flush()
        referencia = PaymentReference(
            payment_id=pago.id,
            reference_type="sales_invoice",
            reference_id=FACTURA,
            company="cacao",
            allocated_amount=Decimal("400"),
        )
        database.session.add(referencia)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
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
        database.session.add(
            GLEntry(
                company="cacao",
                posting_date=FECHA_PAGO,
                ledger_id=libro.id,
                account_id=cuenta.id,
                account_code=cuenta.code,
                debit=Decimal("0"),
                credit=Decimal("400"),
                voucher_type="payment_entry",
                voucher_id=pago.id,
                is_cancelled=False,
            )
        )
        database.session.commit()
        return application, libro.id, cuenta.id


def _carrying(application, libro_id: str, cuenta_id: str, as_of_date: date | None) -> Decimal | None:
    with application.app_context():
        return _document_carrying_value_in_ledger(
            company="cacao",
            document_type="sales_invoice",
            document_id=FACTURA,
            exclude_payment_id="",
            party_account_id=cuenta_id,
            ledger_id=libro_id,
            receivable=True,
            as_of_date=as_of_date,
        )


def test_valor_en_libros_ignora_pago_posterior_al_corte(entorno_contable_aislado):
    """El pago de junio no reduce el valor en libros medido al 31 de mayo."""
    application, libro_id, cuenta_id = _escenario(entorno_contable_aislado)

    assert _carrying(application, libro_id, cuenta_id, CORTE) == Decimal("1000")


def test_valor_en_libros_incluye_pagos_hasta_el_corte(entorno_contable_aislado):
    """El mismo pago sí reduce el valor cuando el corte lo incluye."""
    application, libro_id, cuenta_id = _escenario(entorno_contable_aislado)

    assert _carrying(application, libro_id, cuenta_id, date(2026, 6, 30)) == Decimal("600")
    assert _carrying(application, libro_id, cuenta_id, None) == Decimal("600")


def test_revalorizacion_historica_mide_solo_evidencia_del_corte(entorno_contable_aislado):
    """La ruta del servicio aplica el corte también al pago parcial."""
    application, libro_id, cuenta_id = _escenario(entorno_contable_aislado)
    candidato = SimpleNamespace(
        source_document_type="sales_invoice",
        source_document_id=FACTURA,
        account_id=cuenta_id,
        normal_balance="debit",
        open_amount_original=Decimal("1000"),
        total_amount_original=Decimal("1000"),
        as_of_date=CORTE,
    )
    with application.app_context():
        libro = database.session.get(Book, libro_id)
        saldo = ExchangeRevaluationService()._source_gl_balance(candidato, libro)

    assert saldo == Decimal("1000")

    candidato.as_of_date = date(2026, 6, 30)
    with application.app_context():
        libro = database.session.get(Book, libro_id)
        saldo_posterior = ExchangeRevaluationService()._source_gl_balance(candidato, libro)

    assert saldo_posterior == Decimal("600")
