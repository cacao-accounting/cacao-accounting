# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1113/#1116: saldos y pagos de notas de crédito y devoluciones.

El saldo canónico ya descuenta las aplicaciones; la confirmación no debe
restarlas otra vez. El subledger debe orientar el saldo negativo de una
devolución antes de calcular el importe pagado.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.contabilidad.balance_confirmation import _invoice_open_items
from cacao_accounting.database import ARAPLedgerEntry, Party, SalesInvoice, database
from cacao_accounting.reportes.services import _subledger_document_amounts

CORTE = date(2026, 6, 1)


def _customer_id() -> str:
    """Devuelve el cliente del escenario contable."""
    return str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())


def _credit_note(party_id: str, amount: Decimal, document_type: str, is_return: bool) -> SalesInvoice:
    """Crea una nota de crédito/devolución publicada."""
    document = SalesInvoice(
        company="cacao",
        customer_id=party_id,
        document_type=document_type,
        is_return=is_return,
        posting_date=date(2026, 5, 15),
        docstatus=1,
        total=amount,
        grand_total=amount,
        base_total=amount,
        base_grand_total=amount,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(document)
    database.session.flush()
    return document


def _ledger_row(
    document: SalesInvoice,
    party_id: str,
    amount: Decimal,
    event_type: str,
) -> ARAPLedgerEntry:
    """Registra una fila AR canónica para el documento."""
    row = ARAPLedgerEntry(
        company="cacao",
        ledger_type="ar",
        party_type="customer",
        party_id=party_id,
        document_type=str(document.document_type),
        document_id=str(document.id),
        document_no=document.document_no or str(document.id),
        posting_date=date(2026, 5, 15),
        event_type=event_type,
        currency="NIO",
        document_amount=amount,
    )
    database.session.add(row)
    database.session.flush()
    return row


def test_confirmacion_no_descuenta_dos_veces_la_nota_aplicada(entorno_contable_aislado):
    """Una nota de 500 con 200 aplicados conserva un saldo de 300 (#1113)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _customer_id()
        note = _credit_note(party_id, Decimal("500"), "sales_credit_note", is_return=False)
        _ledger_row(note, party_id, Decimal("-500"), "opening")
        _ledger_row(note, party_id, Decimal("200"), "allocation")
        database.session.commit()

        items = _invoice_open_items("cacao", party_id, "customer", CORTE)

        assert len(items) == 1
        assert Decimal(items[0]["outstanding_amount"]) == Decimal("-300")


def test_confirmacion_conserva_la_rama_legacy_sin_ledger_canonico(entorno_contable_aislado):
    """Sin apertura canónica se mantiene la deducción legacy de aplicaciones."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _customer_id()
        _credit_note(party_id, Decimal("500"), "sales_credit_note", is_return=False)
        database.session.commit()

        items = _invoice_open_items("cacao", party_id, "customer", CORTE)

        assert len(items) == 1
        assert Decimal(items[0]["outstanding_amount"]) == Decimal("-500")


def test_subledger_devolucion_sin_aplicaciones_no_reporta_pago(entorno_contable_aislado):
    """Una devolución de 20 sin aplicaciones tiene paid cero y saldo 20 (#1116)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _customer_id()
        document = _credit_note(party_id, Decimal("20"), "sales_invoice", is_return=True)
        _ledger_row(document, party_id, Decimal("-20"), "opening")
        database.session.commit()

        paid, outstanding = _subledger_document_amounts(document, "sales_invoice", "cacao", CORTE)

        assert paid == Decimal("0")
        assert outstanding == Decimal("20")


def test_subledger_devolucion_parcialmente_aplicada_reporta_solo_lo_aplicado(entorno_contable_aislado):
    """Una devolución de 20 con 5 aplicados reporta paid 5 y saldo 15 (#1116)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _customer_id()
        document = _credit_note(party_id, Decimal("20"), "sales_invoice", is_return=True)
        _ledger_row(document, party_id, Decimal("-20"), "opening")
        _ledger_row(document, party_id, Decimal("5"), "allocation")
        database.session.commit()

        paid, outstanding = _subledger_document_amounts(document, "sales_invoice", "cacao", CORTE)

        assert paid == Decimal("5")
        assert outstanding == Decimal("15")
